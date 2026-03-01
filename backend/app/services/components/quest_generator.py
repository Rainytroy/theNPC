import json
import os
import asyncio
from typing import Dict, List, Optional
from ...core.config import settings
from ...core.llm import llm_client
from ...core.utils import parse_json_from_llm
from ...prompts.quest_writer import QUEST_WRITER_MAIN_PROMPT, QUEST_WRITER_SIDE_PROMPT
from .world_status_manager import WorldStatusManager

class QuestGenerator:
    def __init__(self, status_manager: WorldStatusManager):
        self.status_manager = status_manager

    def _load_assets(self, world_id: str):
        """Helper to load items, locations, and time configuration."""
        items_json_str = "[]"
        locations_json_str = "[]"
        time_json_str = "{}"
        
        if world_id:
            # 1. Items
            items_path = os.path.join(settings.DATA_DIR, "worlds", world_id, "items.json")
            if os.path.exists(items_path):
                try:
                    with open(items_path, "r", encoding="utf-8") as f:
                        items_data = json.load(f)
                        items_list = items_data.get("items", [])
                        simple_items = [{"id": i.get("id"), "name": i.get("name"), "description": i.get("description"), "type": i.get("type", "generic")} for i in items_list]
                        items_json_str = json.dumps(simple_items, ensure_ascii=False, indent=2)
                except Exception as e:
                    print(f"Warning: Failed to load items.json for prompt: {e}")

            # 2. Locations
            loc_path = os.path.join(settings.DATA_DIR, "worlds", world_id, "locations.json")
            if os.path.exists(loc_path):
                try:
                    with open(loc_path, "r", encoding="utf-8") as f:
                        loc_data = json.load(f)
                        loc_list = loc_data.get("locations", [])
                        simple_locs = [{"id": l.get("id"), "name": l.get("name"), "description": l.get("description")} for l in loc_list]
                        locations_json_str = json.dumps(simple_locs, ensure_ascii=False, indent=2)
                except Exception as e:
                    print(f"Warning: Failed to load locations.json: {e}")

            # 3. Time
            time_path = os.path.join(settings.DATA_DIR, "worlds", world_id, "time.json")
            if os.path.exists(time_path):
                 try:
                    with open(time_path, "r", encoding="utf-8") as f:
                        time_data = json.load(f)
                        time_json_str = json.dumps(time_data, ensure_ascii=False, indent=2)
                 except Exception as e:
                    print(f"Warning: Failed to load time.json: {e}")
        
        return items_json_str, locations_json_str, time_json_str

    def _save_new_items(self, world_id: str, new_items: List[Dict]):
        """Helper to append new items to items.json."""
        if not new_items: return
        
        items_path = os.path.join(settings.DATA_DIR, "worlds", world_id, "items.json")
        try:
            current_data = {"items": []}
            if os.path.exists(items_path):
                with open(items_path, "r", encoding="utf-8") as f:
                    current_data = json.load(f)
            
            # De-duplicate based on ID
            existing_ids = {i.get("id") for i in current_data.get("items", [])}
            
            added_count = 0
            for item in new_items:
                if item.get("id") and item.get("id") not in existing_ids:
                    # Enforce source="Quest"
                    item["obtain_methods"] = [{"method": "create", "source": "Quest"}]
                    
                    current_data["items"].append(item)
                    existing_ids.add(item.get("id"))
                    added_count += 1
            
            if added_count > 0:
                with open(items_path, "w", encoding="utf-8") as f:
                    json.dump(current_data, f, ensure_ascii=False, indent=2)
                print(f"DEBUG: Added {added_count} new items to {items_path}")
                
        except Exception as e:
            print(f"Error saving new items: {e}")

    def _apply_item_ownership_updates(self, world_id: str, updates: List[Dict]):
        """
        Apply item ownership updates to items.json.
        
        Args:
            world_id: The world ID
            updates: List of {"item_id": "...", "owner_id": "...", "reason": "..."}
        """
        if not updates:
            return
        
        items_path = os.path.join(settings.DATA_DIR, "worlds", world_id, "items.json")
        
        try:
            if not os.path.exists(items_path):
                print(f"Warning: items.json not found for world {world_id}, skipping ownership updates.")
                return
            
            # Read current items
            with open(items_path, "r", encoding="utf-8") as f:
                items_data = json.load(f)
            
            items_list = items_data.get("items", [])
            
            # Create item_id to index mapping
            item_map = {item.get("id"): idx for idx, item in enumerate(items_list)}
            
            # Apply updates
            updated_count = 0
            for update in updates:
                item_id = update.get("item_id")
                owner_id = update.get("owner_id")
                reason = update.get("reason", "")
                
                if item_id in item_map:
                    idx = item_map[item_id]
                    items_list[idx]["owner_id"] = owner_id
                    updated_count += 1
                    print(f"  ✓ Updated owner_id for {item_id} → {owner_id} ({reason})")
                else:
                    print(f"  ⚠ Item {item_id} not found, skipping ownership update.")
            
            # Save back
            if updated_count > 0:
                items_data["items"] = items_list
                with open(items_path, "w", encoding="utf-8") as f:
                    json.dump(items_data, f, ensure_ascii=False, indent=2)
                print(f"DEBUG: Applied {updated_count} item ownership updates to {items_path}")
        
        except Exception as e:
            print(f"Error applying item ownership updates: {e}")

    async def generate_main_quest(self, world_bible: Dict, npcs: List[Dict], provider: Optional[str] = None, requirements: Optional[str] = None) -> tuple[List[Dict], List[Dict]]:
        """Generate only the Main Quest. Returns (quests, new_items)."""
        try:
            print(f"DEBUG: Generating Main Quest (Requirements: {requirements})...")
            world_id = world_bible.get("world_id")
            items_str, locs_str, time_str = self._load_assets(world_id)
            
            bible_json = json.dumps(world_bible, ensure_ascii=False, indent=2)
            
            # Simplified roster just for context
            simplified_roster = []
            for npc in npcs:
                profile = npc.get("profile", {})
                simplified_roster.append({
                    "id": npc.get("id"),
                    "name": profile.get("name"),
                    "occupation": profile.get("occupation")
                })
            roster_json = json.dumps(simplified_roster, ensure_ascii=False, indent=2)

            user_prompt = f"""
**Input Data**:
1. **World Bible**: 
{bible_json}

2. **NPC Roster (Context)**: 
{roster_json}

3. **Available Items**:
{items_str}

4. **Available Locations**:
{locs_str}

5. **Time Configuration**:
{time_str}

6. **User Requirements (CRITICAL)**:
{requirements if requirements else "Please design a compelling main quest that fits the world setting perfectly."}
"""
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": user_prompt}],
                system=QUEST_WRITER_MAIN_PROMPT,
                provider=provider,
                timeout=180.0
            )
            
            data = parse_json_from_llm(response)
            if isinstance(data, list):
                # Fallback if LLM returns just the list
                quests = data
                new_items = []
                item_ownership_updates = []
            else:
                quests = data.get("quests", [])
                new_items = data.get("new_items", [])
                item_ownership_updates = data.get("item_ownership_updates", [])  # 🆕
            
            # 🆕 Apply item ownership updates
            if item_ownership_updates and world_id:
                self._apply_item_ownership_updates(world_id, item_ownership_updates)
            
            # 🆕 Save new items to disk (FIX: This was missing!)
            if new_items and world_id:
                self._save_new_items(world_id, new_items)
                print(f"DEBUG: Saved {len(new_items)} new items from Main Quest to items.json")
            
            # 🔧 FIX: After updating ownership AND saving new items, reload the FULL items list from disk
            # So frontend gets the complete, updated items (including World Bible items with new owner_ids + new items from quest)
            full_items_list = []
            if world_id:
                items_path = os.path.join(settings.DATA_DIR, "worlds", world_id, "items.json")
                if os.path.exists(items_path):
                    try:
                        with open(items_path, "r", encoding="utf-8") as f:
                            items_data = json.load(f)
                            full_items_list = items_data.get("items", [])
                    except Exception as e:
                        print(f"Warning: Failed to reload items after ownership update: {e}")
            
            print(f"DEBUG: Generated {len(quests)} Main Quest(s), {len(new_items)} new items, {len(item_ownership_updates)} ownership updates. Returning {len(full_items_list)} total items.")
            return quests, full_items_list  # Return FULL list instead of just new_items

        except Exception as e:
            print(f"CRITICAL ERROR in generate_main_quest: {e}")
            raise e

    async def generate_side_quest(self, target_npc: Dict, world_bible: Dict, used_item_ids: List[str] = None, provider: Optional[str] = None) -> tuple[List[Dict], List[Dict]]:
        """Generate a Side Quest for a specific NPC. Returns (quests, new_items)."""
        try:
            print(f"DEBUG: Generating Side Quest for {target_npc.get('id')}...")
            world_id = world_bible.get("world_id")
            items_str, locs_str, _ = self._load_assets(world_id)
            
            # Prepare NPC Data
            profile = target_npc.get("profile", {})
            personality = target_npc.get("personality", {}) # Ensure this exists in your NPC model or adjust
            if not personality:
                # Fallback if personality is under 'dynamic' or different structure
                dynamic = target_npc.get("dynamic", {})
                personality = dynamic.get("personality_desc", "")
            
            quest_role = target_npc.get("quest_role") or {}
            role_type = quest_role.get("role", "neutral")
            
            npc_context = {
                "id": target_npc.get("id"),
                "name": profile.get("name"),
                "role": role_type,
                "occupation": profile.get("occupation"),
                "personality": personality,
                "backstory": profile.get("backstory", ""),
                "goals": target_npc.get("goals", [])
            }
            
            npc_json = json.dumps(npc_context, ensure_ascii=False, indent=2)
            bible_json = json.dumps(world_bible, ensure_ascii=False, indent=2)
            
            # 🆕 Include used items list
            used_items_str = "[]"
            if used_item_ids:
                used_items_str = json.dumps(used_item_ids, ensure_ascii=False)

            user_prompt = f"""
**Input Data**:
1. **Target NPC**: 
{npc_json}

2. **World Bible**: 
{bible_json}

3. **Available Items**:
{items_str}

4. **Available Locations**:
{locs_str}

5. 🆕 **Used Items from Main Quest** (DO NOT use these): 
{used_items_str}
"""
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": user_prompt}],
                system=QUEST_WRITER_SIDE_PROMPT,
                provider=provider,
                timeout=180.0
            )
            
            data = parse_json_from_llm(response)
            if isinstance(data, list):
                quests = data
                new_items = []
                item_ownership_updates = []
            else:
                quests = data.get("quests", [])
                new_items = data.get("new_items", [])
                item_ownership_updates = data.get("item_ownership_updates", [])  # 🆕
            
            # 🆕 Apply item ownership updates
            if item_ownership_updates and world_id:
                self._apply_item_ownership_updates(world_id, item_ownership_updates)
            
            # 🔧 SIDE QUEST: Only return new_items (for real-time incremental updates)
            # Ownership updates are already applied to disk, no need to return full list
            print(f"DEBUG: Generated Side Quest for {npc_context['name']}. New items: {len(new_items)}, Ownership updates: {len(item_ownership_updates)}.")
            return quests, new_items  # Return only new items for incremental update

        except Exception as e:
            print(f"Error generating side quest for {target_npc.get('id')}: {e}")
            raise e

    # --- PHASE 3: ORCHESTRATOR (Legacy Support + Workflow) ---
    async def generate_quests(self, world_bible: Dict, npcs: List[Dict], provider: Optional[str] = None) -> List[Dict]:
        """Phase 3: Generate All Quests (Main + Side for each NPC)."""
        try:
            all_quests = []
            world_id = world_bible.get("world_id")
            
            # CLEANUP: Remove skeleton and enrichment files if they exist, 
            # because we are generating a FRESH set of quests (the new skeleton).
            if world_id:
                world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
                skeleton_path = os.path.join(world_dir, "quests_skeleton.json")
                enrichments_path = os.path.join(world_dir, "quest_enrichments.json")
                if os.path.exists(skeleton_path):
                    os.remove(skeleton_path)
                    print(f"DEBUG: Removed stale skeleton {skeleton_path}")
                if os.path.exists(enrichments_path):
                    os.remove(enrichments_path)
                    print(f"DEBUG: Removed stale enrichments {enrichments_path}")

            # 1. Main Quest (Sequential)
            main_quests, main_new_items = await self.generate_main_quest(world_bible, npcs, provider)
            all_quests.extend(main_quests)
            
            # 🆕 Extract used item IDs from Main Quest
            used_item_ids = set()
            for quest in main_quests:
                for node in quest.get("nodes", []):
                    # Check conditions for item usage
                    for cond in node.get("conditions", []):
                        if cond.get("type") == "item":
                            item_id = cond.get("params", {}).get("item_id")
                            if item_id:
                                used_item_ids.add(item_id)
                    # Check rewards for item获取
                    for reward in node.get("rewards", []):
                        if reward.get("type") == "item":
                            item_id = reward.get("item_id")
                            if item_id:
                                used_item_ids.add(item_id)
            
            # Also add new item IDs from Main Quest
            for item in main_new_items:
                item_id = item.get("id")
                if item_id:
                    used_item_ids.add(item_id)
            
            used_item_list = list(used_item_ids)
            print(f"DEBUG: Main Quest used {len(used_item_list)} items: {used_item_list}")
            
            # Update Items immediately so Side Quests *might* see them 
            # (Note: In current implementation, generate_side_quest re-reads assets via _load_assets. 
            # So if we save here, and _load_assets reads from disk, they WILL see new items!)
            if main_new_items and world_id:
                self._save_new_items(world_id, main_new_items)
            
            # Update status after Main Quest (Refresh 1)
            if world_id:
                 self.status_manager.update_status_progress(
                     world_id=world_id,
                     section="quest_blueprint",
                     updates={"status": "generating_side_quests", "main_quest_done": True}
                 )

            # 2. Side Quests (Parallel Execution) - 🆕 Pass used_item_ids
            tasks = []
            for npc in npcs:
                tasks.append(self.generate_side_quest(npc, world_bible, used_item_list, provider))
            
            side_quest_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            all_side_new_items = []
            
            for res in side_quest_results:
                if isinstance(res, tuple):
                    q_list, i_list = res
                    all_quests.extend(q_list)
                    all_side_new_items.extend(i_list)
                elif isinstance(res, list): # Fallback/Legacy
                    all_quests.extend(res)
                else:
                    print(f"Warning: Side quest generation failed: {res}")

            # Batch save side quest new items
            if all_side_new_items and world_id:
                self._save_new_items(world_id, all_side_new_items)

            if world_id:
                 self.status_manager.update_status_progress(
                     world_id=world_id,
                     section="quest_blueprint",
                     updates={"status": "completed", "count": len(all_quests)},
                     phase_override="ready"
                 )

            return all_quests
            
        except Exception as e:
            print(f"CRITICAL ERROR in Phase 3: {e}")
            raise e
