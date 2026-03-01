import json
import os
import asyncio
from typing import Dict, List, Optional, Any
from ...core.config import settings
from ...core.llm import llm_client
from ...core.utils import parse_json_from_llm
from ...prompts.scheduler import SCHEDULER_SYSTEM_PROMPT

class ScheduleGenerator:
    def __init__(self):
        pass

    def _extract_quest_constraints(self, npc_id: str, npc_name: str, quests: List[Dict]) -> List[str]:
        """
        Extract time/location constraints for this NPC from quests.
        """
        constraints = []
        for quest in quests:
            for node in quest.get("nodes", []):
                target = node.get("target", {})
                involved = False
                
                params = target.get("params", {})
                if params.get("npc_id") == npc_id or params.get("npc_name") == npc_name:
                    involved = True
                
                if not involved:
                    script = node.get("dialogue_script", [])
                    for line in script:
                        if line.get("speaker") == npc_name:
                            involved = True
                            break
                
                if involved:
                    desc = node.get("description", "")
                    constraints.append(f"Quest '{quest.get('title')}': {desc}")
        
        return constraints

    async def generate_schedule_for_npc(self, world_id: str, npc: Dict, world_bible: Dict, quests: List[Dict], provider: Optional[str] = None) -> Dict:
        """
        Generate a daily schedule for a specific NPC.
        """
        npc_id = npc.get("id")
        profile = npc.get("profile", {})
        name = profile.get("name", "Unknown")
        
        print(f"DEBUG: Generating schedule for {name} ({npc_id})...")
        
        # New Constraint Extraction Logic
        main_quest_constraints = []
        side_quest_constraints = []
        
        for quest in quests:
            is_active = quest.get("status") == "active"
            if not is_active: continue

            # Get active nodes
            active_node_ids = quest.get("active_nodes", [])
            # If linear, use current_node_index
            if not active_node_ids:
                 idx = quest.get("current_node_index", 0)
                 if idx < len(quest.get("nodes", [])):
                     active_node_ids = [quest["nodes"][idx].get("id")]
            
            for node in quest.get("nodes", []):
                if node.get("id") not in active_node_ids: continue
                
                # Check relevance
                relevant = False
                if node.get("target_npc_id") == npc_id: relevant = True
                
                # Check params
                for cond in node.get("conditions", []):
                     if str(cond.get("params", {}).get("target_id")) == npc_id: relevant = True
                
                if relevant:
                    desc = f"Quest [{quest.get('title')}]: {node.get('description')}"
                    if quest.get("type") == "main":
                        main_quest_constraints.append(desc)
                    else:
                        side_quest_constraints.append(desc)

        constraints = self._extract_quest_constraints(npc_id, name, quests)
        
        bible_json = json.dumps(world_bible, ensure_ascii=False, indent=2)
        # Include Dynamic Profile for Mood/Personality nuances
        full_profile = {**profile, **npc.get("dynamic", {})}
        npc_json = json.dumps(full_profile, ensure_ascii=False, indent=2)
        
        # Prioritize locations.json
        locations_path = os.path.join(settings.DATA_DIR, "worlds", world_id, "locations.json")
        locations = []
        if os.path.exists(locations_path):
            try:
                with open(locations_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        locations = [l.get("name", "Unknown") for l in data.get("locations", [])]
                    elif isinstance(data, list):
                        locations = [l.get("name", "Unknown") for l in data]
            except Exception as e:
                print(f"Error loading locations.json: {e}")
        
        if not locations:
            locations = world_bible.get("scene", {}).get("locations", [])
            
        loc_str = ", ".join(locations)
        
        quest_context_str = "No active quests."
        if constraints:
            quest_context_str = "CRITICAL QUEST OBLIGATIONS (Must be prioritized):\n" + "\n".join([f"- {c}" for c in constraints])

        user_prompt = f"""
**World Context**:
{bible_json}

**Available Locations**:
{loc_str}

**NPC Profile**:
{npc_json}

**Quest Context**:
{quest_context_str}

**Current State**:
Normal daily routine.
"""

        try:
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": user_prompt}],
                system=SCHEDULER_SYSTEM_PROMPT,
                provider=provider,
                timeout=120.0
            )
            
            schedule_data = parse_json_from_llm(response)
            
            # 简单处理：如果是单对象就包装成数组
            if isinstance(schedule_data, dict):
                schedule_data = [schedule_data]
            
            # 保存到 schedules/{npc_id}.json
            world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
            schedule_dir = os.path.join(world_dir, "schedules")
            os.makedirs(schedule_dir, exist_ok=True)
            
            file_path = os.path.join(schedule_dir, f"{npc_id}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(schedule_data, f, indent=2, ensure_ascii=False)
                
            print(f"DEBUG: Schedule saved for {name} at {file_path}")
            return schedule_data

        except Exception as e:
            print(f"Error generating schedule for {name}: {e}")
            return []

    async def generate_all_schedules(self, world_id: str, world_bible: Dict, npcs: List[Dict], quests: List[Dict], provider: Optional[str] = None, progress_callback=None):
        """
        Generate schedules for all NPCs concurrently.
        """
        print(f"DEBUG: Generating schedules for {len(npcs)} NPCs...")
        
        total = len(npcs)
        completed = 0
        
        async def generate_wrapper(npc):
            nonlocal completed
            npc_name = npc.get("profile", {}).get("name", "Unknown")
            if progress_callback:
                await progress_callback(completed, total, f"Generating schedule for \"{npc_name}\" ({completed + 1}/{total})...")
            
            await self.generate_schedule_for_npc(world_id, npc, world_bible, quests, provider)
            completed += 1

        tasks = []
        for npc in npcs:
            tasks.append(generate_wrapper(npc))
            
        await asyncio.gather(*tasks)
        print(f"DEBUG: All schedules generated.")
