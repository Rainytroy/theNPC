import json
import re
import uuid
import asyncio
import os
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from ..core.config import settings
from ..core.llm import llm_client
from ..core.utils import parse_json_from_llm
from ..prompts.sower import SOWER_SYSTEM_PROMPT
from ..schemas.genesis import GenesisChatResponse, WorldCreationStatus, WorldStatusFile, PendingAction
from ..schemas.npc import NPC

from .components.world_status_manager import WorldStatusManager
from .components.npc_generator import NPCGenerator
from .components.quest_generator import QuestGenerator
from .components.asset_generator import AssetGenerator
from .components.schedule_generator import ScheduleGenerator

# In-memory session storage (Replace with Redis in production)
# Format: {session_id: [{"role": "user", "content": "..."}]}
sessions: Dict[str, List[Dict[str, str]]] = {}

class GenesisService:
    # Track session phases to detect transitions
    session_phases: Dict[str, str] = {}
    
    def __init__(self):
        self.status_manager = WorldStatusManager()
        self.npc_generator = NPCGenerator(self.status_manager)
        self.quest_generator = QuestGenerator(self.status_manager)
        self.asset_generator = AssetGenerator()
        self.schedule_generator = ScheduleGenerator()

    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        sessions[session_id] = []
        return session_id

    async def chat(self, session_id: str, user_content: str, provider: Optional[str] = None, current_bible: Optional[Dict] = None, phase: str = "world") -> GenesisChatResponse:
        if session_id not in sessions:
            # Auto-create if not exists (or raise error)
            sessions[session_id] = []
            
            # Try to load history from disk if this is a new session for an existing world
            if current_bible and current_bible.get("world_id"):
                world_id = current_bible.get("world_id")
                world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
                chat_path = os.path.join(world_dir, "chat.json")
                if os.path.exists(chat_path):
                    try:
                        with open(chat_path, "r", encoding="utf-8") as f:
                            history = json.load(f)
                            # Convert frontend history to backend format (simple list of dicts)
                            loaded_msgs = []
                            for msg in history:
                                if msg.get("role") in ["user", "assistant"]:
                                    loaded_msgs.append({
                                        "role": msg.get("role"),
                                        "content": msg.get("content")
                                    })
                            sessions[session_id] = loaded_msgs
                            print(f"DEBUG: Loaded {len(loaded_msgs)} messages from history for session {session_id}")
                    except Exception as e:
                        print(f"Error loading chat history: {e}")
        
        # Append user message
        sessions[session_id].append({"role": "user", "content": user_content})
        
        # Construct messages for LLM
        messages_to_send = sessions[session_id].copy()

        # --- VALIDATE PHASE based on World State (Fix for New World showing Phase 2) ---
        world_id = current_bible.get("world_id") if current_bible else None
        if world_id:
            world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
            bible_path = os.path.join(world_dir, "bible.json")
            # If bible.json doesn't exist, we MUST be in Phase 1 (World Setting)
            # This handles cases where user creates a New World but phase comes as "npc" from stale session
            if not os.path.exists(bible_path) and phase != "world":
                print(f"DEBUG: Forcing phase to 'world' because bible.json missing for {world_id}")
                phase = "world"
        elif phase != "world":
            # If no world_id (Drafting new world), force Phase 1
             print(f"DEBUG: Forcing phase to 'world' because no world_id provided")
             phase = "world"
        # -----------------------------------------------------------------------------
        
        # Detect Phase Change & Inject Transition Message
        # Fix: Initialize with current phase if new session to avoid false transition on reload
        if session_id not in self.session_phases:
            self.session_phases[session_id] = phase

        last_phase = self.session_phases.get(session_id, "world")
        if phase != last_phase:
            transition_msg = ""
            if last_phase == "world" and phase == "npc":
                transition_msg = "[系统提示：世界设定阶段已结束。世界设定 (World Bible) 已定稿（已注入上下文）。现在进入第二阶段：NPC生成。请引导用户创建角色，不要再讨论世界观修改。]"
            elif last_phase == "npc" and phase == "quest":
                transition_msg = "[系统提示：NPC生成阶段已结束。角色列表即居民生成 (NPC Roster) 已定稿（已注入上下文）。现在进入第三阶段：任务蓝图。请引导用户生成任务，不要再讨论世界观修改和NPC修改。]"
            
            if transition_msg:
                # Inject as assistant message with system prefix (to avoid role validation issues)
                sessions[session_id].append({"role": "assistant", "content": transition_msg})
                # Sync messages_to_send
                messages_to_send = sessions[session_id].copy()
            
            self.session_phases[session_id] = phase

            # Update status.json with new phase intent
            if current_bible and current_bible.get("world_id"):
                 self.status_manager.update_status_progress(
                     world_id=current_bible.get("world_id"),
                     section="general", # Dummy section, we only care about phase override
                     updates={},
                     phase_override=phase
                 )

        # Inject Context if provided
        if current_bible:
            # Append context to the last user message content to avoid role validation errors
            context_str = f"\n\n[System Context: The user is modifying an existing World Bible. The current state is:\n{json.dumps(current_bible, ensure_ascii=False, indent=2)}\nPlease use this as the baseline for any modifications.]"
            
            # Inject NPCs for Phase 2/3
            if phase in ["npc", "quest"] and current_bible.get("world_id"):
                 world_id = current_bible.get("world_id")
                 
                 # 1. Load NPCs
                 world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
                 npc_path = os.path.join(world_dir, "npcs.json")
                 if os.path.exists(npc_path):
                     try:
                         with open(npc_path, "r", encoding="utf-8") as f:
                             npcs = json.load(f)
                         context_str += f"\n\n[System Context: Existing NPCs:\n{json.dumps(npcs, ensure_ascii=False, indent=2)}]"
                     except Exception as e:
                         print(f"Error loading NPCs for context: {e}")

                 # 2. Load Quests (If Phase 3)
                 if phase == "quest":
                     quest_path = os.path.join(world_dir, "quests.json")
                     if os.path.exists(quest_path):
                         try:
                             with open(quest_path, "r", encoding="utf-8") as f:
                                 quests = json.load(f)
                             context_str += f"\n\n[System Context: Existing Quests:\n{json.dumps(quests, ensure_ascii=False, indent=2)}]"
                         except Exception as e:
                             print(f"Error loading Quests for context: {e}")
                     
                     # 🆕 Load Items
                     items_path = os.path.join(world_dir, "items.json")
                     if os.path.exists(items_path):
                         try:
                             with open(items_path, "r", encoding="utf-8") as f:
                                 items_data = json.load(f)
                             context_str += f"\n\n[System Context: Existing Items:\n{json.dumps(items_data, ensure_ascii=False, indent=2)}]"
                         except Exception as e:
                             print(f"Error loading Items for context: {e}")
                     
                     # 🆕 Load Locations
                     locations_path = os.path.join(world_dir, "locations.json")
                     if os.path.exists(locations_path):
                         try:
                             with open(locations_path, "r", encoding="utf-8") as f:
                                 locations_data = json.load(f)
                             context_str += f"\n\n[System Context: Existing Locations:\n{json.dumps(locations_data, ensure_ascii=False, indent=2)}]"
                         except Exception as e:
                             print(f"Error loading Locations for context: {e}")
                 
                 # 3. Inject Real-time Status (User Request)
                 try:
                     status = await self.check_world_status(world_id)
                     context_str += f"\n\n[System Context: Real-time World Status]\n{status.message}\n(Current Phase: {status.current_phase})"
                 except Exception as e:
                     print(f"Error checking status for chat context: {e}")

            if len(messages_to_send) > 0 and messages_to_send[-1]["role"] == "user":
                messages_to_send[-1]["content"] += context_str
            else:
                # Fallback: Create a user message if the last one isn't user (unlikely)
                messages_to_send.append({"role": "user", "content": context_str})
        
        # Select System Prompt (UNIFIED)
        system_prompt = SOWER_SYSTEM_PROMPT
        
        # Detect data existence for dynamic status generation
        has_bible_draft = bool(current_bible)  # Draft from context
        world_id = current_bible.get("world_id") if current_bible else None
        world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id) if world_id else None
        
        # Check file existence (only when world_id exists)
        bible_file_exists = os.path.exists(os.path.join(world_dir, "bible.json")) if world_dir else False
        npc_file_exists = os.path.exists(os.path.join(world_dir, "npcs.json")) if world_dir else False
        quest_file_exists = os.path.exists(os.path.join(world_dir, "quests.json")) if world_dir else False

        # --- STATUS HELPERS ---
        # Extract Illustrated Mode
        is_illustrated = False
        if current_bible and "config" in current_bible:
            is_illustrated = current_bible["config"].get("is_illustrated", False)
        
        ill_status_str = "🟢 已开启 (ON)" if is_illustrated else "⚪ 已关闭 (OFF)"

        # Glossary
        glossary_text = """
[术语对照 (Terminology)]
• Phase 1 (World) = 世界设定 (World Bible)
• Phase 2 (NPC)   = 居民生成 (NPC Roster)
• Phase 3 (Quest) = 任务蓝图 (Quest Blueprint)
"""
        
        # Construct Dynamic Status Context with Phase-Specific Constraints
        if phase == "world":
            if not has_bible_draft:
                # Scenario: New world creation
                status_context = f"""

[SYSTEM STATUS]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 Current Phase: PHASE 1 - 世界设定 (World Bible)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{glossary_text}

🎯 你的任务：
   • 引导用户设计世界观、背景、规则、场景
   • 收集足够信息后输出 world_setting JSON命令

🚫 严格禁止：
   • 不要提及NPC、角色生成（那是Phase 2）
   • 不要提及任务设计（那是Phase 3）

⚠️ 当前状态：
   • 世界尚未创建
   • 正在收集世界观信息
"""
            else:
                # Scenario: Modifying draft
                status_context = f"""

[SYSTEM STATUS]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 Current Phase: PHASE 1 - 世界设定 (World Bible)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{glossary_text}

🎯 你的任务：
   • 根据已有草稿引导用户完善世界观
   • 用户确认后输出 world_setting JSON命令

🚫 严格禁止：
   • 不要提及NPC、角色生成（那是Phase 2）
   • 不要提及任务设计（那是Phase 3）

⚠️ 当前状态：
   • 世界设定草稿已存在（已注入上下文）
   • 引导用户修改或确认定稿世界之书
"""
        elif phase == "npc":
            if not npc_file_exists:
                # Scenario: Just entered Phase 2
                status_context = f"""

[SYSTEM STATUS]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 Current Phase: PHASE 2 - 居民生成 (NPC Roster)
🎨 立绘模式: {ill_status_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{glossary_text}

🎯 你的任务：
   • 引导用户创建世界居民
   • 可使用：ready_for_npc, add_npc 等命令

🚫 严格禁止：
   • 不要修改世界观（已定稿）
   • 不要提前讨论任务设计

✅ 已完成：
   • 世界之书已定稿（已注入上下文）

⚠️ 当前状态：
   • 世界已定稿，开始生成NPC
"""
            else:
                # Scenario: Modifying/generating NPCs
                status_context = f"""

[SYSTEM STATUS]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 Current Phase: PHASE 2 - 居民生成 (NPC Roster)
🎨 立绘模式: {ill_status_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{glossary_text}

🎯 你的任务：
   • 引导用户生成/修改NPC或立绘
   • 完成后引导用户确认定稿居民名册

🚫 严格禁止：
   • 不要修改世界观（已定稿）
   • 不要提前讨论任务设计

✅ 已完成：
   • 世界之书已定稿（已注入上下文）
   • 居民档案已生成（已注入上下文）

⚠️ 当前状态：
   • 引导NPC生成/修改/立绘
   • 引导用户确认定稿居民名册
"""
        elif phase == "quest":
            if not quest_file_exists:
                # Scenario: Just entered Phase 3
                status_context = f"""

[SYSTEM STATUS]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 Current Phase: PHASE 3 - 任务蓝图 (Quest Blueprint)
🎨 立绘模式: {ill_status_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{glossary_text}

🎯 你的任务：
   • 引导用户设计任务和剧情
   • 可使用：ready_for_quest 等命令

🚫 严格禁止：
   • 不要修改NPC（已定稿）
   • 不要回退到前面的阶段

✅ 已完成：
   • 世界之书已定稿（已注入上下文）
   • 居民名册已定稿（已注入上下文）

⚠️ 当前状态：
   • NPC已定稿，开始设计任务
"""
            else:
                # Scenario: Modifying/generating Quests
                status_context = f"""

[SYSTEM STATUS]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 Current Phase: PHASE 3 - 任务蓝图 (Quest Blueprint)
🎨 立绘模式: {ill_status_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{glossary_text}

🎯 你的任务：
   • 引导用户生成/修改任务
   • 完成后引导用户确认定稿任务蓝图

🚫 严格禁止：
   • 不要修改NPC（已定稿）
   • 不要回退到前面的阶段

✅ 已完成：
   • 世界之书已定稿（已注入上下文）
   • 居民名册已定稿（已注入上下文）
   • 任务蓝图已生成（已注入上下文）

⚠️ 当前状态：
   • 引导Quest生成/修改
   • 引导用户确认定稿任务蓝图
"""
        else:
            status_context = f"\n\n[SYSTEM STATUS]\nCurrent Phase: {phase.upper()}\n"
        
        # Append detailed status if world exists (keeping existing logic)
        if world_id:
             try:
                 status_obj = self.status_manager.load_world_status(world_id)
                 if status_obj:
                     status_context += f"\n📊 Full Status Tracker:\n{status_obj.model_dump_json(indent=2)}\n"
                 else:
                     status_context += "\n⚠️ Status file not found (New World).\n"
             except Exception as e:
                 status_context += f"\n⚠️ Status check failed: {e}\n"
        
        # Inject Status into messages (Appending to last user message to ensure visibility)
        if len(messages_to_send) > 0 and messages_to_send[-1]["role"] == "user":
            messages_to_send[-1]["content"] += status_context
        else:
            messages_to_send.append({"role": "user", "content": status_context})
            
        print(f"DEBUG: Using Unified System Prompt with Status Context: {phase}")

        # Call LLM
        response_text = await llm_client.chat_completion(
            messages=messages_to_send,
            system=system_prompt,
            provider=provider
        )
        
        # Append assistant message
        sessions[session_id].append({"role": "assistant", "content": response_text})
        
        # Parse JSON block
        is_ready = False
        suggested_setting = None
        is_ready_for_npc = False
        npc_requirements = None
        npc_count = 3
        is_ready_for_quest = False
        quest_requirements = None
        quest_count = 3
        pending_actions = []
        
        # Robust JSON Extraction via helper
        data = parse_json_from_llm(response_text)

        # Fallback: Manual extraction if helper failed but looks like JSON
        if not data and "ready_for_quest" in response_text:
            try:
                # Try regex first
                match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                else:
                    # Try finding brace block directly
                    start = response_text.find('{')
                    end = response_text.rfind('}')
                    if start != -1 and end != -1 and end > start:
                        json_str = response_text[start:end+1]
                        data = json.loads(json_str)
            except Exception as e:
                print(f"Fallback JSON parsing failed: {e}")

        # Ensure we strip the JSON from the user-facing response if we found it
        clean_response = response_text
        if data:
            # Try standard regex strip first
            clean_response = re.sub(r'```(?:\w+)?\s*(\{.*?\})\s*```', '', response_text, flags=re.DOTALL).strip()
            # If that didn't change anything (e.g. no code blocks), try removing the specific JSON string we found
            if clean_response == response_text and "ready_for_quest" in response_text:
                 # Re-serialize to string to try and find it, or just use the block method
                 try:
                     start = response_text.find('{')
                     end = response_text.rfind('}')
                     if start != -1 and end != -1:
                         clean_response = (response_text[:start] + response_text[end+1:]).strip()
                 except:
                     pass

        if data:
            try:
                world_id = current_bible.get("world_id") if current_bible else None
                
                # --- ACTION HANDLING ---

                # 1. World Ready (Phase 1)
                # ✨ FIX: If world_setting exists, assume ready unless explicitly set to false
                if data.get("world_setting"):
                    suggested_setting = data.get("world_setting")
                    is_ready = data.get("ready", True)  # Default to True if world_setting exists
                    
                    if world_id and data.get("ready"):  # Only update status if explicitly ready
                        self.status_manager.update_status_progress(
                            world_id=world_id,
                            section="world_bible",
                            updates={"status": "completed"},
                            phase_override="npc"
                        )
                
                # 2. NPC Generation Request (Phase 2 - Generate)
                if data.get("ready_for_npc"):
                    is_ready_for_npc = True
                    npc_requirements = data.get("npc_requirements")
                    npc_count = data.get("count", 3)
                    # Update status to drafting if not already
                    if world_id:
                        self.status_manager.update_status_progress(
                            world_id=world_id,
                            section="npc_roster",
                            updates={"status": "drafting"}
                        )

                # 3. Add NPC (Phase 2 - Add)
                if data.get("add_npc") and world_id:
                    add_info = data.get("add_npc")
                    # Generate Proposal
                    pending_actions.append(PendingAction(
                        type="add_npc",
                        data={"world_id": world_id, "count": add_info.get("count", 1), "requirements": add_info.get("requirements")},
                        label=f"增加 {add_info.get('count', 1)} 位居民",
                        style="primary"
                    ))
                    # Add Cancel Option
                    pending_actions.append(PendingAction(
                        type="cancel",
                        data={},
                        label="取消 (Cancel)",
                        style="secondary"
                    ))

                # 4. Regenerate NPC (Phase 2 - Refine)
                if data.get("regenerate_npc") and world_id:
                    reg_data = data.get("regenerate_npc")
                    reg_list = []
                    
                    if isinstance(reg_data, list):
                        reg_list = reg_data
                    elif isinstance(reg_data, dict):
                        reg_list = [reg_data]
                        
                    for item in reg_list:
                        target_name = item.get("target_name")
                        instruction = item.get("instruction")
                        if target_name:
                            pending_actions.append(PendingAction(
                                type="regenerate_npc",
                                data={"world_id": world_id, "target_name": target_name, "instruction": instruction},
                                label=f"修改居民: {target_name}",
                                style="primary"
                            ))
                            
                    # Add Cancel Option (Always available)
                    pending_actions.append(PendingAction(
                        type="cancel",
                        data={},
                        label="取消 (Cancel)",
                        style="secondary"
                    ))

                # 5. Image Management (Phase 2 - Images)
                if data.get("manage_images") and world_id:
                    img_info = data.get("manage_images")
                    action = img_info.get("action")
                    
                    # Refactored: Only support enable/disable toggles
                    if action == "enable":
                        pending_actions.append(PendingAction(
                            type="manage_images",
                            data={"world_id": world_id, "action": action},
                            label="确认开启 (Confirm Enable)",
                            style="primary"
                        ))
                        # Add Cancel
                        pending_actions.append(PendingAction(
                            type="cancel",
                            data={},
                            label="取消 (Cancel)",
                            style="secondary"
                        ))
                    elif action == "disable":
                        pending_actions.append(PendingAction(
                            type="manage_images",
                            data={"world_id": world_id, "action": action},
                            label="确认关闭 (Confirm Disable)",
                            style="primary"
                        ))
                        # Add Cancel
                        pending_actions.append(PendingAction(
                            type="cancel",
                            data={},
                            label="取消 (Cancel)",
                            style="secondary"
                        ))

                # 6. Confirm Roster (Phase 2 - Finalize)
                if data.get("confirm_roster") and world_id:
                    # await self.handle_roster_confirm(world_id=world_id)
                    # Explicitly return an action so frontend can show a button even if triggered by text
                    pending_actions.append(PendingAction(
                        type="enter_quest_phase",
                        data={},
                        label="生成任务 (Generate Quests)",
                        style="primary"
                    ))
                    pending_actions.append(PendingAction(
                        type="cancel_enter_quest",
                        data={},
                        label="调整居民 (Modify NPCs)",
                        style="secondary"
                    ))

                # 7. Universal Update (Routes 'update_npc' to 'regenerate_npc' workflow)
                if data.get("update_npc") and world_id:
                    update_info = data.get("update_npc")
                    
                    # Construct instruction from all fields
                    instruction_parts = []
                    for k, v in update_info.items():
                        if k != "target_name":
                            instruction_parts.append(f"{k}: {v}")
                    instruction = ", ".join(instruction_parts)

                    # Route to PendingAction to trigger Frontend Workflow (Visual Checklist & Shaper)
                    pending_actions.append(PendingAction(
                        type="regenerate_npc",
                        data={
                            "world_id": world_id, 
                            "target_name": update_info.get("target_name"), 
                            "instruction": instruction
                        },
                        label=f"更新属性: {update_info.get('target_name')}",
                        style="primary"
                    ))
                    
                    # Ensure Cancel option exists
                    has_cancel = any(p.type == "cancel" for p in pending_actions)
                    if not has_cancel:
                        pending_actions.append(PendingAction(
                            type="cancel",
                            data={},
                            label="取消 (Cancel)",
                            style="secondary"
                        ))

                # 8. Quest Generation Request (Phase 3)
                if data.get("ready_for_quest"):
                    is_ready_for_quest = True
                    quest_requirements = data.get("quest_requirements")
                    quest_count = data.get("quest_count", 3)
                    
                    # ✅ 只使用 is_ready_for_quest 机制，前端会自动渲染 2 个按钮
                    # ❌ 不再使用 pending_actions（避免重复按钮）

                # 🆕 9. Modify Quest Requirements (Phase 3 - Modify Loop)
                # ❌ Removed: Modify button is confusing. Agent should guide user back to 'ready_for_quest'.
                if data.get("modify_quest_requirements"):
                    # Fallback: Treat as re-generation request if agent outputs this
                    pass 

                # 🆕 10. Confirm Quest Blueprint (Phase 3 - Finalize)
                if data.get("confirm_quest_blueprint") and world_id:
                    pending_actions.append(PendingAction(
                        type="confirm_quest_blueprint",
                        data={"world_id": world_id},
                        label="确认任务蓝图 (Confirm Blueprint)",
                        style="primary"
                    ))
                    pending_actions.append(PendingAction(
                        type="cancel_confirm_quest",
                        data={},
                        label="继续修改 (Keep Modifying)",
                        style="secondary"
                    ))
                    
            except Exception as e:
                print(f"Failed to parse or execute JSON actions: {e}")
        
        return GenesisChatResponse(
            response=clean_response,
            is_ready_to_generate=is_ready,
            suggested_world_setting=suggested_setting,
            is_ready_for_npc=is_ready_for_npc,
            npc_requirements=npc_requirements,
            npc_count=npc_count,
            is_ready_for_quest=is_ready_for_quest,
            quest_requirements=quest_requirements,
            quest_count=quest_count,
            pending_actions=pending_actions
        )

    def get_session_history(self, session_id: str) -> List[Dict[str, str]]:
        return sessions.get(session_id, [])

    # Delegate to StatusManager
    def load_world_status(self, world_id: str) -> Optional[WorldStatusFile]:
        return self.status_manager.load_world_status(world_id)

    def save_world_status(self, world_id: str, status: WorldStatusFile):
        return self.status_manager.save_world_status(world_id, status)

    def update_status_progress(self, world_id: str, section: str, updates: Dict, phase_override: str = None, options_update: Dict = None):
        return self.status_manager.update_status_progress(world_id, section, updates, phase_override, options_update)

    async def check_world_status(self, world_id: str) -> WorldCreationStatus:
        return await self.status_manager.check_world_status(world_id)

    # Delegate to NPCGenerator
    async def generate_roster(self, *args, **kwargs):
        return await self.npc_generator.generate_roster(*args, **kwargs)

    async def generate_npc_details(self, *args, **kwargs):
        return await self.npc_generator.generate_npc_details(*args, **kwargs)

    async def generate_npc_details_with_retry(self, *args, **kwargs):
        return await self.npc_generator.generate_npc_details_with_retry(*args, **kwargs)

    async def generate_npcs(self, *args, **kwargs):
        return await self.npc_generator.generate_npcs(*args, **kwargs)

    async def update_npc_full(self, *args, **kwargs):
        return await self.npc_generator.update_npc_full(*args, **kwargs)

    async def execute_add_npc(self, *args, **kwargs):
        return await self.npc_generator.execute_add_npc(*args, **kwargs)

    async def execute_npc_regenerate(self, *args, **kwargs):
        return await self.npc_generator.execute_npc_regenerate(*args, **kwargs)

    async def execute_image_management(self, *args, **kwargs):
        return await self.npc_generator.execute_image_management(*args, **kwargs)

    # Delegate to QuestGenerator
    async def enrich_world_assets(self, world_id: str, bible_data: Dict, provider: Optional[str] = None) -> Tuple[List[Dict], List[Dict]]:
        """
        Step 1 & 2 of Quest Workflow: Reset & Enrich Assets.
        Returns (items, locations)
        """
        print(f"DEBUG: ========== 任务蓝图生成工作流 (Step 1-2) ==========")
        print(f"DEBUG: [Step 1/2] 重置资产到初始状态...")
        
        # 1. Reset Assets
        self.asset_generator.extract_assets_from_bible(world_id, bible_data)
        
        # 2. Reset Quests
        world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
        quest_path = os.path.join(world_dir, "quests.json")
        try:
            with open(quest_path, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2, ensure_ascii=False)
            print(f"DEBUG: ✓ Quests已重置")
        except Exception as e:
            print(f"Error resetting quests: {e}")

        # 3. Update UI Status
        self.status_manager.update_status_progress(
            world_id=world_id,
            section="quest_blueprint",
            updates={"status": "drafting", "count": 0}
        )
        
        # 4. Enrich
        print(f"DEBUG: [Step 2/2] 使用LLM优化资产描述...")
        try:
            await self.asset_generator.enrich_assets_with_llm(world_id, bible_data, provider)
        except Exception as e:
            print(f"Warning: LLM优化失败，继续使用原始描述: {e}")
            
        # 5. Return updated assets
        items_path = os.path.join(world_dir, "items.json")
        locations_path = os.path.join(world_dir, "locations.json")
        
        items = []
        locations = []
        
        if os.path.exists(items_path):
            with open(items_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                items = data.get("items", [])
        
        if os.path.exists(locations_path):
            with open(locations_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                locations = data.get("locations", [])
                
        return items, locations

    async def generate_quests(self, *args, **kwargs):
        # 🆕 新工作流程：
        # 1. 立刻重置 items/locations/quests 到初始状态
        # 2. 使用LLM优化 items 和 locations 的描述
        # 3. 继续生成任务（主线+支线）
        
        # Extract world_bible from args or kwargs
        world_bible = kwargs.get("world_bible")
        if not world_bible and args and len(args) > 0:
            world_bible = args[0]
        
        # Extract provider from kwargs
        provider = kwargs.get("provider")
            
        # Handle Pydantic Model or Dict
        bible_data = None
        world_id = None
        
        if hasattr(world_bible, "dict"):
            bible_data = world_bible.dict()
        elif isinstance(world_bible, dict):
            bible_data = world_bible
            
        if bible_data:
            world_id = bible_data.get("world_id")
            
        if world_id and bible_data:
             print(f"DEBUG: ========== 任务蓝图生成工作流开始 ==========")
             print(f"DEBUG: [Step 1/3] 重置资产到初始状态...")
             
             # 1️⃣ Reset Assets (Overwrite with Bible data only)
             self.asset_generator.extract_assets_from_bible(world_id, bible_data)
             
             # 2️⃣ Reset Quests (Empty list)
             world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
             quest_path = os.path.join(world_dir, "quests.json")
             try:
                 with open(quest_path, "w", encoding="utf-8") as f:
                     json.dump([], f, indent=2, ensure_ascii=False)
                 print(f"DEBUG: ✓ Quests已重置")
             except Exception as e:
                 print(f"Error resetting quests: {e}")

             # 3️⃣ Update UI to reflect clean state (Loading/Empty)
             self.status_manager.update_status_progress(
                 world_id=world_id,
                 section="quest_blueprint",
                 updates={"status": "drafting", "count": 0}
             )
             
             print(f"DEBUG: [Step 2/3] 使用LLM优化资产描述...")
             # 4️⃣ 🆕 Enrich Assets with LLM (更符合世界观的描述)
             try:
                 await self.asset_generator.enrich_assets_with_llm(world_id, bible_data, provider)
             except Exception as e:
                 print(f"Warning: LLM优化失败，继续使用原始描述: {e}")
             
             print(f"DEBUG: [Step 3/3] 开始生成任务蓝图...")

        return await self.quest_generator.generate_quests(*args, **kwargs)

    async def generate_main_quest(self, world_bible: Dict, npcs: List[Dict], provider: Optional[str] = None, requirements: Optional[str] = None) -> List[Dict]:
        """Wrapper for generate_main_quest to handle item saving and return only quests list."""
        quests, new_items = await self.quest_generator.generate_main_quest(world_bible, npcs, provider, requirements)
        
        world_id = world_bible.get("world_id")
        if world_id and new_items:
            # Save new items automatically
            self.quest_generator._save_new_items(world_id, new_items)
            
        return quests

    async def generate_side_quest(self, target_npc: Dict, world_bible: Dict, provider: Optional[str] = None) -> List[Dict]:
        """Wrapper for generate_side_quest to handle item saving and return only quests list."""
        quests, new_items = await self.quest_generator.generate_side_quest(target_npc, world_bible, provider)
        
        world_id = world_bible.get("world_id")
        if world_id and new_items:
            # Save new items automatically
            self.quest_generator._save_new_items(world_id, new_items)
            
        return quests

    async def finalize_world_phase(self, world_id: str, world_bible: Any):
        """Finalize World Phase: Summary & Transition"""
        print(f"DEBUG: Finalizing World Phase for {world_id}")
        
        # 1. Generate Summary
        if hasattr(world_bible, "dict"):
            bible_data = world_bible.dict()
        else:
            bible_data = world_bible
            
        # --- NEW: Automatically Extract Assets from Bible ---
        # This ensures items.json, locations.json, time.json are created
        self.asset_generator.extract_assets_from_bible(world_id, bible_data)
        # ----------------------------------------------------

        bg = bible_data.get("background", {})
        summary = f"""**🌍 世界设定摘要 (World Summary)**

> **时代背景**: {bg.get('era', '未知')}
> **核心法则**: {', '.join(bg.get('rules', []))}
> **社会形态**: {bg.get('society', '未知')}
> **玩家目标**: {bible_data.get('player_objective', '未知')}
> **核心场景**: {bible_data.get('scene', {}).get('name', '未知')}

(已归档至世界年表)"""

        # 2. Update Status with Summary
        self.status_manager.update_status_progress(
            world_id=world_id,
            section="world_bible",
            updates={"status": "completed"},
            phase_override="npc"
        )
        
        status = self.status_manager.load_world_status(world_id)
        if status:
            status.phase_summaries["world_summary"] = summary
            self.status_manager.save_world_status(world_id, status)
            
        # 3. Inject Transition Messages into Chat History
        world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
        chat_path = os.path.join(world_dir, "chat.json")
        
        if os.path.exists(chat_path):
            try:
                with open(chat_path, "r+", encoding="utf-8") as f:
                    history = json.load(f)
                    
                    history.append({
                        "role": "assistant",
                        "content": summary
                    })
                    
                    history.append({
                        "role": "assistant",
                        "content": "世界观已定稿。舞台已经搭建完毕，现在我们需要一些演员。\n\n**接下来进入第二阶段：居民生成 (NPC Roster)。**\n\n请告诉我，您希望在这个世界中看到什么样的角色？（例如：需要几位？是原住民还是外来者？有什么特殊的职业要求？）"
                    })
                    
                    f.seek(0)
                    json.dump(history, f, indent=2, ensure_ascii=False)
                    f.truncate()
            except Exception as e:
                print(f"Error updating chat history: {e}")

    async def handle_roster_confirm(self, world_id: str):
        """Finalize NPC Roster (Public Method)"""
        print(f"DEBUG: Confirming Roster for {world_id}")
        self.status_manager.update_status_progress(
            world_id=world_id,
            section="npc_roster",
            updates={"status": "completed"},
            phase_override="quest"
        )

        # Initialize Quest Blueprint Status
        self.status_manager.update_status_progress(
            world_id=world_id,
            section="quest_blueprint",
            updates={"status": "drafting"}
        )
        
        # Generate Summary & Transition
        try:
            world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)

            # ✅ NEW: Persist roster confirmation to bible.json (Single Source of Truth)
            bible_path = os.path.join(world_dir, "bible.json")
            if os.path.exists(bible_path):
                try:
                    with open(bible_path, "r", encoding="utf-8") as f:
                        bible = json.load(f)
                    
                    # Update config
                    if "config" not in bible:
                        bible["config"] = {}
                    bible["config"]["roster_confirmed"] = True
                    
                    with open(bible_path, "w", encoding="utf-8") as f:
                        json.dump(bible, f, indent=2, ensure_ascii=False)
                    print(f"DEBUG: Updated bible.json with roster_confirmed=True for {world_id}")
                except Exception as be:
                    print(f"Error updating bible.json config: {be}")

            npc_path = os.path.join(world_dir, "npcs.json")
            if os.path.exists(npc_path):
                with open(npc_path, "r", encoding="utf-8") as f:
                    npcs = json.load(f)
                
                # Enhanced Summary with detailed NPC info
                npc_details = []
                illustrated_count = 0
                for idx, npc in enumerate(npcs, 1):
                    profile = npc.get("profile", {})
                    name = profile.get("name", "未知")
                    age = profile.get("age", "未知")
                    gender = profile.get("gender", "未知")
                    occupation = profile.get("occupation", "未知")
                    race = profile.get("race", "人族")
                    avatar_url = profile.get("avatar_url", "")
                    
                    # Fix: Use dynamic.personality_desc instead of non-existent profile.intro
                    dynamic = npc.get("dynamic", {})
                    intro = dynamic.get("personality_desc", "无介绍")
                    # Optional: Truncate if too long to keep summary clean
                    if len(intro) > 50:
                        intro = intro[:47] + "..."

                    # Check if has avatar
                    has_avatar = "✅ 已生成" if avatar_url else "❌ 未生成"
                    if avatar_url:
                        illustrated_count += 1
                    
                    # Format detail entry
                    detail = f"""> {idx}. **{name}** ({gender}, {age}岁) - {occupation} / {race}
>    - {intro}
>    - 立绘: {has_avatar}
"""
                    npc_details.append(detail)
                
                # Build complete summary
                summary = f"""**👥 居民名册摘要 (Roster Summary)**

> **居民总数**: {len(npcs)} 位 (立绘 {illustrated_count}/{len(npcs)})
> 
> **居民档案**:
{"".join(npc_details)}
(已归档至居民档案)"""

                # Update Status
                status = self.status_manager.load_world_status(world_id)
                if status:
                    status.phase_summaries["npc_summary"] = summary
                    self.status_manager.save_world_status(world_id, status)
                
                # Update Chat
                chat_path = os.path.join(world_dir, "chat.json")
                if os.path.exists(chat_path):
                    with open(chat_path, "r+", encoding="utf-8") as f:
                        history = json.load(f)
                        history.append({"role": "assistant", "content": summary})
                        history.append({
                            "role": "assistant",
                            "content": "居民名册已定稿。演员已经就位，现在我们需要为他们编排剧本。\n\n**接下来进入第三阶段：任务蓝图 (Quest Blueprint)。**\n\n请告诉我，您希望设计什么样的主线任务？剩下的细节就请不要过问了..."
                        })
                        f.seek(0)
                        json.dump(history, f, indent=2, ensure_ascii=False)
                        f.truncate()

        except Exception as e:
            print(f"Error finalizing roster: {e}")

        print("DEBUG: Roster confirmed. Status updated to completed. Phase switched to Quest.")

    def clean_launch_data(self, world_id: str):
        """清理 Launch 相关的临时数据，但保留核心资产"""
        print(f"DEBUG: Cleaning launch data for world {world_id}")
        world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
        
        files_to_remove = [
            "intro.txt",               # 开场白
            "quest_enrichments.json",  # 任务丰富化数据
            # quests_skeleton.json 保留，作为备份
        ]
        
        # 删除 schedules/ 目录下的所有文件
        schedules_dir = os.path.join(world_dir, "schedules")
        if os.path.exists(schedules_dir):
            try:
                for file in os.listdir(schedules_dir):
                    file_path = os.path.join(schedules_dir, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        print(f"DEBUG: Removed {file}")
            except Exception as e:
                print(f"Error cleaning schedules directory: {e}")
        
        # 删除指定文件
        for filename in files_to_remove:
            filepath = os.path.join(world_dir, filename)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    print(f"DEBUG: Removed {filename}")
                except Exception as e:
                    print(f"Error removing {filename}: {e}")
        
        # 重置状态为pending，并确保所有字段存在
        try:
            self.status_manager.update_status_progress(world_id, "intro", {
                "status": "pending",
                "content": None,
                "message": None,
                "updated_at": None
            })
            self.status_manager.update_status_progress(world_id, "quest_enrich", {
                "status": "pending",
                "message": None,
                "updated_at": None
            })
            self.status_manager.update_status_progress(world_id, "schedule", {
                "status": "pending",
                "current": 0,
                "total": 0,
                "message": None,
                "updated_at": None
            })
            self.status_manager.update_status_progress(world_id, "general", {}, phase_override="launch")
            print(f"DEBUG: Reset status to pending for all launch steps with full structure")
        except Exception as e:
            print(f"Error resetting status: {e}")

    async def finalize_quest_phase(self, world_id: str):
        """Finalize Quest Phase: Generate Summary & Start Initialization"""
        print(f"DEBUG: Finalizing Quest Phase for {world_id}")

        # ✅ NEW: Persist quest confirmation to bible.json
        world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
        bible_path = os.path.join(world_dir, "bible.json")
        if os.path.exists(bible_path):
            try:
                with open(bible_path, "r", encoding="utf-8") as f:
                    bible = json.load(f)
                
                # Update config
                if "config" not in bible:
                    bible["config"] = {}
                bible["config"]["quest_confirmed"] = True
                
                with open(bible_path, "w", encoding="utf-8") as f:
                    json.dump(bible, f, indent=2, ensure_ascii=False)
                print(f"DEBUG: Updated bible.json with quest_confirmed=True for {world_id}")
            except Exception as be:
                print(f"Error updating bible.json config: {be}")
        
        # 🔧 清理旧的launch数据（支持重新生成）
        self.clean_launch_data(world_id)
        
        # 1. Load Quests
        world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
        quest_path = os.path.join(world_dir, "quests.json")
        
        quests = []
        if os.path.exists(quest_path):
            with open(quest_path, "r", encoding="utf-8") as f:
                quests_data = json.load(f)
                # Handle both formats: {"quests": [...]} or [...]
                quests = quests_data.get("quests", []) if isinstance(quests_data, dict) else quests_data
        
        # 2. Generate Summary
        main_quests = [q for q in quests if q.get("quest_type") == "main"]
        side_quests = [q for q in quests if q.get("quest_type") == "side"]
        
        summary = f"""**🎯 任务蓝图摘要 (Quest Blueprint Summary)**

> **主线任务**: {len(main_quests)} 条
> **支线任务**: {len(side_quests)} 条
> **总任务数**: {len(quests)} 条

(已归档至任务蓝图)"""

        # 3. Update Status -> launch
        self.status_manager.update_status_progress(
            world_id=world_id,
            section="quest_blueprint",
            updates={"status": "completed"},
            phase_override="launch"  # Switch to new phase
        )
        
        status = self.status_manager.load_world_status(world_id)
        if status:
            status.phase_summaries["quest_summary"] = summary
            self.status_manager.save_world_status(world_id, status)
        
        # 4. Trigger Initialization Background Task
        # In a real app, use Celery/BackgroundTasks. Here we await it (might block chat) or fire & forget.
        # Since we want "automatic", we'll call it here.
        # Ideally, this should be fired as a background task.
        asyncio.create_task(self.initialize_world(world_id))

        print("DEBUG: Quest Blueprint finalized. Status updated to launch. Initialization started.")

    def _create_initial_backup(self, world_id: str):
        """Create a complete initial backup of the world state after launch"""
        print(f"DEBUG: Creating initial_state backup for world {world_id}...")
        try:
            import shutil
            world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
            backup_dir = os.path.join(world_dir, "initial_state")
            
            # Clean existing backup if any
            if os.path.exists(backup_dir):
                shutil.rmtree(backup_dir)
            os.makedirs(backup_dir, exist_ok=True)
            
            # 1. Copy Files
            files_to_copy = [
                "bible.json", "npcs.json", "quests.json", "items.json", 
                "locations.json", "time.json", "intro.txt", "quests_skeleton.json"
            ]
            
            for filename in files_to_copy:
                src = os.path.join(world_dir, filename)
                if os.path.exists(src):
                    shutil.copy2(src, backup_dir)
                    print(f"DEBUG: Backed up {filename}")
            
            # 2. Copy Directories
            dirs_to_copy = ["schedules", "quest_enrichments"]
            
            for dirname in dirs_to_copy:
                src = os.path.join(world_dir, dirname)
                dst = os.path.join(backup_dir, dirname)
                if os.path.exists(src):
                    shutil.copytree(src, dst)
                    print(f"DEBUG: Backed up directory {dirname}")
            
            print(f"DEBUG: ✓ Initial state backup created at {backup_dir}")
            
        except Exception as e:
            print(f"Error creating initial backup: {e}")
            import traceback
            traceback.print_exc()

    async def initialize_world(self, world_id: str):
        """
        Execute the full initialization pipeline: Intro -> Quest Enrichment -> Schedule.
        """
        print(f"DEBUG: Starting World Initialization for {world_id}...")
        
        try:
            # Load Data
            world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
            bible_path = os.path.join(world_dir, "bible.json")
            npc_path = os.path.join(world_dir, "npcs.json")
            quest_path = os.path.join(world_dir, "quests.json")
            
            with open(bible_path, "r", encoding="utf-8") as f:
                bible = json.load(f)
            with open(npc_path, "r", encoding="utf-8") as f:
                npcs = json.load(f)
            with open(quest_path, "r", encoding="utf-8") as f:
                quests_data = json.load(f)
                # Handle both formats: {"quests": [...]} or [...]
                quests = quests_data.get("quests", []) if isinstance(quests_data, dict) else quests_data

            # Step 1: Generate Intro
            print("DEBUG: [Init Step 1] Generating Intro...")
            self.status_manager.update_status_progress(world_id, "intro", {
                "status": "processing",
                "message": "Calling LLM to generate opening crawl..."
            })
            
            try:
                intro_text = await self.asset_generator.generate_intro(world_id, bible)
                
                # ✅ 确保成功后才更新状态
                if intro_text:
                    self.status_manager.update_status_progress(world_id, "intro", {
                        "status": "completed",
                        "content": intro_text,
                        "message": "Intro generated successfully."
                    })
                    print(f"DEBUG: ✓ Intro generated ({len(intro_text)} chars)")
                else:
                    raise ValueError("Intro generation returned empty result")
                    
            except Exception as e:
                print(f"ERROR generating intro: {e}")
                self.status_manager.update_status_progress(world_id, "intro", {
                    "status": "failed",
                    "message": str(e)
                })
                # 继续执行后续步骤（可选择是否抛出异常）
            
            # Step 2: Enrich Quests
            print("DEBUG: [Init Step 2] Enriching Quests...")
            self.status_manager.update_status_progress(world_id, "quest_enrich", {"status": "processing", "message": "Batch processing quest details with LLM..."})
            await self.asset_generator.enrich_quests_with_llm(world_id, bible)
            self.status_manager.update_status_progress(world_id, "quest_enrich", {"status": "completed", "message": "Quest enrichment complete."})
            
            # Reload quests as they might have changed
            with open(quest_path, "r", encoding="utf-8") as f:
                quests_data = json.load(f)
                # Handle both formats: {"quests": [...]} or [...]
                quests = quests_data.get("quests", []) if isinstance(quests_data, dict) else quests_data

            # Step 3: Generate Schedules
            async def schedule_progress(current, total, msg):
                self.status_manager.update_status_progress(world_id, "schedule", {
                    "status": "processing",
                    "current": current,
                    "total": total,
                    "message": msg
                })

            print("DEBUG: [Init Step 3] Generating Schedules...")
            self.status_manager.update_status_progress(world_id, "schedule", {"status": "processing", "message": "Initializing schedule generation..."})
            await self.schedule_generator.generate_all_schedules(world_id, bible, npcs, quests, progress_callback=schedule_progress)
            self.status_manager.update_status_progress(world_id, "schedule", {"status": "completed", "message": "All schedules generated."})
            
            # Finalize
            print("DEBUG: [Init] All steps complete. Creating Backup & Setting status to ready.")
            
            # 🆕 Create Initial Backup
            self._create_initial_backup(world_id)
            
            self.status_manager.update_status_progress(
                world_id=world_id,
                section="launch",
                updates={"status": "completed"},
                phase_override="ready"
            )
            
        except Exception as e:
            print(f"CRITICAL ERROR in initialize_world: {e}")
            import traceback
            traceback.print_exc()

genesis_service = GenesisService()
