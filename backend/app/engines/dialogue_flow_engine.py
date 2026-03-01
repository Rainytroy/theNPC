"""
Dialogue Flow Engine - 任务对话流演出引擎

负责管理预设对话流的半自动播放，包括：
- 对话流启动与状态管理
- 玩家Chip点击后的对话推进
- 物品交互处理 (show/give/receive)
- 任务节点完成与推进
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class DialogueFlowEngine:
    """任务对话流演出引擎"""
    
    def __init__(self, runtime):
        self.runtime = runtime
        # Active dialogue flow state
        self.active_flows: Dict[str, Dict] = {}  # npc_id -> flow state
    
    def _get_line_attr(self, line, attr: str, default=None):
        """Helper to get attribute from DialogueLine (Pydantic object or dict)"""
        if isinstance(line, dict):
            return line.get(attr, default)
        return getattr(line, attr, default)
    
    def is_flow_active(self, npc_id: str) -> bool:
        """Check if a dialogue flow is currently active for this NPC"""
        return npc_id in self.active_flows
    
    def get_flow_state(self, npc_id: str) -> Optional[Dict]:
        """Get current flow state for an NPC"""
        return self.active_flows.get(npc_id)
    
    async def start_flow(self, npc_id: str, quest_id: str, node_id: str) -> Dict:
        """
        Start a dialogue flow for a quest node.
        
        Returns initial state with first NPC line and player's first Chip.
        """
        # Get quest context
        quest_context = self.runtime.quest_engine.get_full_quest_context(quest_id, node_id)
        if not quest_context:
            return {"success": False, "error": "Quest context not found"}
        
        dialogue_script = quest_context.get("dialogue_script_raw", [])
        if not dialogue_script:
            # For investigate nodes, return the investigation description
            if quest_context.get("node_type") == "investigate":
                return await self._handle_investigation(npc_id, quest_id, node_id, quest_context)
            return {"success": False, "error": "No dialogue script"}
        
        npc = self.runtime.get_npc(npc_id)
        npc_name = npc.profile.name if npc else "NPC"
        
        # Initialize flow state
        flow_state = {
            "quest_id": quest_id,
            "node_id": node_id,
            "npc_id": npc_id,
            "npc_name": npc_name,
            "dialogue_script": dialogue_script,
            "current_index": 0,
            "started_at": datetime.now().isoformat(),
            "status": "active"
        }
        
        self.active_flows[npc_id] = flow_state
        
        # Mark node as triggered (prevent re-trigger if rejected)
        self.runtime.quest_engine.mark_node_triggered(quest_id, node_id)
        
        # Get first lines to display
        result = await self._get_next_dialogue_chunk(npc_id)
        result["success"] = True
        result["flow_started"] = True
        result["quest_title"] = quest_context.get("quest_title")
        
        # Convert player_chip to new_chips format for frontend compatibility
        if result.get("player_chip"):
            chip = result["player_chip"]
            chip["quest_id"] = quest_id
            chip["node_id"] = node_id
            chip["npc_id"] = npc_id
            result["new_chips"] = [chip]
        
        logger.info(f"Started dialogue flow: {quest_id}/{node_id} for NPC {npc_name}")
        
        return result
    
    async def _handle_investigation(self, npc_id: str, quest_id: str, node_id: str, quest_context: Dict) -> Dict:
        """Handle investigation type nodes (no NPC dialogue, just description)"""
        investigation_desc = quest_context.get("investigation_desc", "")
        
        if not investigation_desc:
            investigation_desc = quest_context.get("node_description", "你仔细调查了这个地方...")
        
        # Broadcast investigation description
        await self.runtime.broadcast_event(
            investigation_desc,
            category="investigation",
            source_id="system",
            target_id="player",
            metadata={
                "quest_id": quest_id,
                "node_id": node_id,
                "type": "investigation"
            }
        )
        
        # Auto-complete the node after investigation
        result = self.runtime.quest_engine.advance_node(quest_id, node_id)
        
        # Broadcast rewards if any
        if result.get("rewards"):
            for reward in result["rewards"]:
                await self.runtime.broadcast_event(
                    f"🎁 {reward.get('message', '获得了奖励')}",
                    category="reward",
                    source_id="system",
                    target_id="player",
                    metadata=reward
                )
        
        # Broadcast quest update with meaningful message
        quest_title = result.get("quest_title", "调查")
        if result.get("quest_completed"):
            completion_msg = f"📜 任务完成 - {quest_title}"
        else:
            completion_msg = f"🔍 调查完成 - {quest_title}"
        
        await self.runtime.broadcast_event(
            completion_msg,
            category="quest_update",
            source_id="system",
            target_id="player",
            metadata={
                "type": "quest_update",
                "quest_id": quest_id,
                "completed_node_id": node_id,
                "quest_completed": result.get("quest_completed", False),
                "quest_title": quest_title
            }
        )
        
        return {
            "success": True,
            "type": "investigation",
            "description": investigation_desc,
            "quest_update": result
        }
    
    async def player_speak(self, npc_id: str, chip_index: int = None) -> Dict:
        """
        Handle player clicking a dialogue Chip.
        
        Advances the dialogue flow by:
        1. Broadcasting the player's line
        2. Processing any actions (show_item, give_item)
        3. Getting the next NPC line(s) and player chip
        """
        flow_state = self.active_flows.get(npc_id)
        if not flow_state:
            return {"success": False, "error": "No active flow"}
        
        dialogue_script = flow_state["dialogue_script"]
        current_index = flow_state["current_index"]
        
        # Find the player's line at current position
        if current_index >= len(dialogue_script):
            # Flow completed
            return await self.complete_flow(npc_id)
        
        current_line = dialogue_script[current_index]
        
        # Verify it's a Player line (handle both DialogueLine object and dict)
        speaker = self._get_line_attr(current_line, "speaker", "")
        if speaker != "Player":
            # Skip to player line
            return {"success": False, "error": "Expected player line"}
        
        # Broadcast player's line
        player_text = self._get_line_attr(current_line, "text", "...")
        await self.runtime.broadcast_event(
            player_text,
            category="player_interaction",
            source_id="player",
            target_id=npc_id,
            metadata={
                "type": "dialogue_flow",
                "quest_id": flow_state["quest_id"],
                "line_index": current_index
            }
        )
        
        # Process action if present
        action = self._get_line_attr(current_line, "action")
        if action:
            await self._process_action(action, flow_state)
        
        # Advance index
        flow_state["current_index"] = current_index + 1
        
        # Get next chunk
        result = await self._get_next_dialogue_chunk(npc_id)
        result["success"] = True
        
        # Convert player_chip to new_chips format for frontend compatibility
        if result.get("player_chip"):
            chip = result["player_chip"]
            chip["quest_id"] = flow_state["quest_id"]
            chip["node_id"] = flow_state["node_id"]
            chip["npc_id"] = npc_id
            result["new_chips"] = [chip]
        
        # Mark flow as ended if complete
        if result.get("flow_complete"):
            result["flow_ended"] = True
        
        return result
    
    async def _get_next_dialogue_chunk(self, npc_id: str) -> Dict:
        """
        Get next dialogue lines to display.
        
        Returns:
        - npc_lines: List of NPC lines to display (auto-play)
        - player_chip: The next player line as a clickable Chip (or None if done)
        - flow_complete: True if dialogue flow is finished
        """
        flow_state = self.active_flows.get(npc_id)
        if not flow_state:
            return {"error": "No active flow"}
        
        dialogue_script = flow_state["dialogue_script"]
        current_index = flow_state["current_index"]
        npc_name = flow_state["npc_name"]
        
        npc_lines = []
        player_chip = None
        flow_complete = False
        
        # Collect consecutive NPC lines
        while current_index < len(dialogue_script):
            line = dialogue_script[current_index]
            # Handle both DialogueLine Pydantic object and dict
            speaker = self._get_line_attr(line, "speaker", "Unknown")
            
            if speaker == "Player":
                # Stop at player line - this becomes the chip
                player_chip = {
                    "type": "player_line",
                    "label": self._get_line_attr(line, "text", "..."),
                    "index": current_index,
                    "action": self._get_line_attr(line, "action")
                }
                break
            else:
                # NPC line - add to list and broadcast
                text = self._get_line_attr(line, "text", "...")
                action = self._get_line_attr(line, "action")
                
                npc_lines.append({
                    "speaker": speaker,
                    "text": text,
                    "action": action,
                    "index": current_index
                })
                
                # Broadcast NPC line
                await self.runtime.broadcast_event(
                    f"{speaker}: {text}",
                    category="dialogue_flow",
                    source_id=npc_id,
                    target_id="player",
                    metadata={
                        "type": "dialogue_flow",
                        "quest_id": flow_state["quest_id"],
                        "line_index": current_index,
                        "speaker": speaker
                    }
                )
                
                # Process action if present
                if action:
                    await self._process_action(action, flow_state)
                
                current_index += 1
                
                # Small delay between NPC lines for dramatic effect
                await asyncio.sleep(0.5)
        
        # Update state
        flow_state["current_index"] = current_index
        
        # Check if flow is complete
        if current_index >= len(dialogue_script) and player_chip is None:
            flow_complete = True
            # Auto-complete the flow
            complete_result = await self.complete_flow(npc_id)
            return {
                "npc_lines": npc_lines,
                "player_chip": None,
                "flow_complete": True,
                "quest_update": complete_result.get("quest_update")
            }
        
        return {
            "npc_lines": npc_lines,
            "player_chip": player_chip,
            "flow_complete": flow_complete
        }
    
    async def _process_action(self, action: Dict, flow_state: Dict):
        """Process dialogue action (show_item, give_item, etc.)"""
        action_type = action.get("type")
        item_id = action.get("item_id")
        
        if action_type == "show_item" and item_id:
            # Player shows item
            item_name = self.runtime.quest_engine._get_item_name(item_id)
            await self.runtime.broadcast_event(
                f"*展示了 [{item_name}]*",
                category="item_action",
                source_id="player",
                target_id=flow_state["npc_id"],
                metadata={
                    "type": "show_item",
                    "item_id": item_id,
                    "item_name": item_name
                }
            )
            
        elif action_type == "give_item" and item_id:
            # Player gives item to NPC
            item_name = self.runtime.quest_engine._get_item_name(item_id)
            self.runtime.quest_engine._update_item_owner(item_id, flow_state["npc_id"])
            await self.runtime.broadcast_event(
                f"*将 [{item_name}] 交给了 {flow_state['npc_name']}*",
                category="item_action",
                source_id="player",
                target_id=flow_state["npc_id"],
                metadata={
                    "type": "give_item",
                    "item_id": item_id,
                    "item_name": item_name,
                    "to_npc": flow_state["npc_id"]
                }
            )
            
        elif action_type == "receive_item" and item_id:
            # NPC gives item to player (handled by rewards, but can also be mid-dialogue)
            item_name = self.runtime.quest_engine._get_item_name(item_id)
            self.runtime.quest_engine._update_item_owner(item_id, "player")
            await self.runtime.broadcast_event(
                f"🎁 获得了 [{item_name}]",
                category="item_action",
                source_id=flow_state["npc_id"],
                target_id="player",
                metadata={
                    "type": "receive_item",
                    "item_id": item_id,
                    "item_name": item_name
                }
            )
    
    async def complete_flow(self, npc_id: str) -> Dict:
        """
        Complete the dialogue flow and advance the quest.
        """
        flow_state = self.active_flows.get(npc_id)
        if not flow_state:
            return {"success": False, "error": "No active flow"}
        
        quest_id = flow_state["quest_id"]
        node_id = flow_state["node_id"]
        
        # Remove from active flows
        del self.active_flows[npc_id]
        
        # Advance quest node
        result = self.runtime.quest_engine.advance_node(quest_id, node_id)
        
        # Broadcast rewards
        if result.get("rewards"):
            for reward in result["rewards"]:
                await self.runtime.broadcast_event(
                    f"🎁 {reward.get('message', '获得了奖励')}",
                    category="reward",
                    source_id="system",
                    target_id="player",
                    metadata=reward
                )
        
        # Broadcast quest update with meaningful message
        quest_title = result.get("quest_title", "任务步骤")
        if result.get("quest_completed"):
            completion_msg = f"📜 任务完成 - {quest_title}"
        else:
            completion_msg = f"📜 剧情演出完毕 - {quest_title}"
        
        await self.runtime.broadcast_event(
            completion_msg,
            category="quest_update",
            source_id="system",
            target_id="player",
            metadata={
                "type": "quest_update",
                "quest_id": quest_id,
                "completed_node_id": node_id,
                "next_node_id": result.get("next_node_id"),
                "quest_completed": result.get("quest_completed", False),
                "quest_title": quest_title
            }
        )
        
        logger.info(f"Completed dialogue flow: {quest_id}/{node_id}")
        
        return {
            "success": True,
            "quest_update": result
        }
    
    async def reject_flow(self, npc_id: str, quest_id: str, node_id: str):
        """
        Handle player rejecting a quest trigger.
        The node remains triggered (won't re-trigger until next session or manual reset).
        """
        # Already marked as triggered in start_flow, so just log
        logger.info(f"Player rejected quest flow: {quest_id}/{node_id}")
        
        # Optionally broadcast a rejection message
        await self.runtime.broadcast_event(
            "*暂时拒绝了这个话题*",
            category="system",
            source_id="player",
            target_id=npc_id,
            metadata={
                "type": "quest_reject",
                "quest_id": quest_id,
                "node_id": node_id
            }
        )
