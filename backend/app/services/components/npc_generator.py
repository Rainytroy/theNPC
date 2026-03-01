import json
import asyncio
import os
from typing import Dict, List, Optional, Any
from ...core.config import settings
from ...core.llm import llm_client
from ...core.utils import parse_json_from_llm
from ...services.image_service import image_service
from ...prompts.shaper import SHAPER_PHASE1_PROMPT, SHAPER_PHASE2_PROMPT, SHAPER_UPDATE_PROMPT
from ...schemas.genesis import PendingAction
from ...schemas.npc import NPC
from .world_status_manager import WorldStatusManager

class NPCGenerator:
    def __init__(self, status_manager: WorldStatusManager):
        self.status_manager = status_manager

    # --- PHASE 1: SKELETON & MAP ---
    async def generate_roster(self, world_bible: Dict, count: int = 3, provider: Optional[str] = None, requirements: Optional[str] = None) -> Dict:
        """Phase 1: Generate NPC Skeletons and expand locations."""
        try:
            print(f"DEBUG: [Phase 1] Generating Skeletons & Locations... Requirements: {requirements}")
            bible_json = json.dumps(world_bible, ensure_ascii=False, indent=2)
            
            req_text = ""
            if requirements and requirements.strip():
                req_text = f"\n\n**User Additional Requirements**:\n{requirements.strip()}\nPlease ensure the generated NPCs adhere to these requirements."

            user_prompt_p1 = f"""
Here is the World Bible:
{bible_json}

Please generate {count} NPC Skeletons and expand the location list.
{req_text}
"""
            system_prompt_p1 = SHAPER_PHASE1_PROMPT.replace("{count}", str(count))
            
            response_p1 = await llm_client.chat_completion(
                messages=[{"role": "user", "content": user_prompt_p1}],
                system=system_prompt_p1,
                provider=provider,
                timeout=120.0 
            )
            
            data_p1 = parse_json_from_llm(response_p1)
            new_locations = data_p1.get("new_locations", [])
            npc_skeletons = data_p1.get("npcs", [])
            
            for skeleton in npc_skeletons:
                if "relationships" not in skeleton:
                    skeleton["relationships"] = {}
            
            print(f"DEBUG: [Phase 1] Generated {len(npc_skeletons)} skeletons and {len(new_locations)} locations.")
            return {
                "skeletons": npc_skeletons,
                "new_locations": new_locations
            }
            
        except Exception as e:
            print(f"CRITICAL ERROR in Phase 1: {e}")
            raise e

    def _validate_npc_complete(self, npc_data: Dict) -> bool:
        required_fields = ['quest_role', 'goals', 'skills']
        has_all_fields = all(key in npc_data for key in required_fields)
        if has_all_fields:
            has_quest_role = bool(npc_data.get('quest_role'))
            has_goals = bool(npc_data.get('goals')) and len(npc_data.get('goals', [])) > 0
            has_skills = bool(npc_data.get('skills')) and len(npc_data.get('skills', [])) > 0
            return has_quest_role and has_goals and has_skills
        return False

    async def generate_npc_details_with_retry(self, skeleton: Dict, world_bible: Dict, roster_names: str, provider: Optional[str] = None, requirements: Optional[str] = None, max_retries: int = 2) -> Dict:
        """Phase 2 with retry logic."""
        npc_name = skeleton.get('profile', {}).get('name', 'Unknown')
        
        for attempt in range(max_retries + 1):
            try:
                print(f"DEBUG: Generating details for {npc_name} (Attempt {attempt + 1}/{max_retries + 1})")
                result = await self.generate_npc_details(skeleton, world_bible, roster_names, provider, requirements)
                if self._validate_npc_complete(result):
                    print(f"✓ {npc_name} generation complete")
                    return result
                else:
                    print(f"⚠ {npc_name} incomplete, retrying...")
                    if attempt < max_retries:
                        await asyncio.sleep(1)
            except Exception as e:
                print(f"✗ Error generating {npc_name}: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(1)
        
        skeleton['_incomplete'] = True
        skeleton['_error'] = 'Failed to generate complete NPC data after retries'
        return skeleton

    async def generate_npc_details(self, skeleton: Dict, world_bible: Dict, roster_names: str, provider: Optional[str] = None, requirements: Optional[str] = None) -> NPC:
        """Phase 2: Generate details for a single NPC."""
        try:
            all_locations = world_bible.get("scene", {}).get("locations", [])
            
            req_text = ""
            if requirements and requirements.strip():
                req_text = f"\n\n**User Additional Requirements/Instructions**:\n{requirements.strip()}\nPlease ensure the generated details adhere to these requirements where applicable."

            user_prompt_p2 = f"""
**Input Data**:
1. **World Bible (Updated)**: 
{json.dumps(world_bible, ensure_ascii=False, indent=2)}

2. **Player Objective**: {world_bible.get("player_objective", "None")}

3. **Full Roster**: {roster_names}

4. **Target NPC Skeleton**:
{json.dumps(skeleton, ensure_ascii=False, indent=2)}
{req_text}
"""
            player_objective = world_bible.get("player_objective", "None")
            
            system_prompt_p2 = SHAPER_PHASE2_PROMPT.replace("{locations}", ", ".join(all_locations))
            system_prompt_p2 = system_prompt_p2.replace("{player_objective}", player_objective)
            system_prompt_p2 = system_prompt_p2.replace("{npc_skeleton}", json.dumps(skeleton, ensure_ascii=False))
            system_prompt_p2 = system_prompt_p2.replace("{roster_names}", roster_names)

            response_p2 = await llm_client.chat_completion(
                messages=[{"role": "user", "content": user_prompt_p2}],
                system=system_prompt_p2,
                provider=provider,
                timeout=120.0
            )
            
            details = parse_json_from_llm(response_p2)
            full_npc_dict = {**skeleton, **details}
            
            if "dynamic_details" in full_npc_dict:
                base_dynamic = full_npc_dict.get("dynamic", {})
                if not base_dynamic and "dynamic_core" in full_npc_dict:
                     base_dynamic = full_npc_dict.get("dynamic_core", {})

                new_dynamic = full_npc_dict.get("dynamic_details", {})
                full_npc_dict["dynamic"] = {**base_dynamic, **new_dynamic}
                del full_npc_dict["dynamic_details"]
            
            if "dynamic_core" in full_npc_dict:
                del full_npc_dict["dynamic_core"]
            
            return full_npc_dict
            
        except Exception as e:
            print(f"Error generating details for {skeleton.get('profile', {}).get('name')}: {e}")
            return skeleton

    async def generate_npcs(self, world_bible: Dict, count: int = 3, provider: Optional[str] = None, requirements: Optional[str] = None) -> List[NPC]:
        """Legacy/Full method: Invoke both phases sequentially/concurrently."""
        print(f"DEBUG: Inside generate_npcs (Full) service method. Provider: {provider}, Requirements: {requirements}")
        
        roster_data = await self.generate_roster(world_bible, count, provider, requirements=requirements)
        npc_skeletons = roster_data["skeletons"]
        new_locations = roster_data["new_locations"]
        
        # [Auto-Collect] Ensure NPC personal locations are added to the world map
        existing_locs = world_bible.get("scene", {}).get("locations", [])
        for sk in npc_skeletons:
            profile = sk.get("profile", {})
            home = profile.get("home_location")
            work = profile.get("work_location")
            
            if home and home not in new_locations and home not in existing_locs:
                print(f"DEBUG: Auto-collecting missing home location: {home}")
                new_locations.append(home)
            
            if work and work not in new_locations and work not in existing_locs:
                print(f"DEBUG: Auto-collecting missing work location: {work}")
                new_locations.append(work)

        scene_name = world_bible.get("scene", {}).get("name", "Unknown Location")
        current_locations = world_bible.get("scene", {}).get("locations", [])
        
        if "Main Area" in current_locations:
            current_locations.remove("Main Area")
        if scene_name not in current_locations:
            current_locations.insert(0, scene_name)
            
        merged = [scene_name]
        for loc in current_locations + new_locations:
            if loc not in merged and loc != "Main Area":
                merged.append(loc)
                
        all_locations = merged
        world_bible["scene"]["locations"] = all_locations
        
        roster_names = ", ".join([n["profile"]["name"] for n in npc_skeletons])
        
        print(f"DEBUG: [Phase 2] Fleshing out {len(npc_skeletons)} NPCs concurrently with retry...")
        tasks = [self.generate_npc_details_with_retry(sk, world_bible, roster_names, provider, requirements=requirements) for sk in npc_skeletons]
        full_npcs_data = await asyncio.gather(*tasks)
        
        incomplete_npcs = [npc for npc in full_npcs_data if npc.get('_incomplete')]
        if incomplete_npcs:
            print(f"⚠ WARNING: {len(incomplete_npcs)} NPCs failed to generate completely")
        
        name_to_id = {}
        for npc_data in full_npcs_data:
            try:
                name = npc_data.get("profile", {}).get("name")
                npc_id = npc_data.get("id")
                if name and npc_id:
                    name_to_id[name] = npc_id
            except Exception:
                pass
        
        for npc_data in full_npcs_data:
            relationships = npc_data.get("relationships", {})
            new_relationships = {}
            for target_name, rel_data in relationships.items():
                target_id = name_to_id.get(target_name, target_name)
                new_relationships[target_id] = rel_data
            npc_data["relationships"] = new_relationships

        npcs = [NPC(**item) for item in full_npcs_data]
        
        if world_bible.get("world_id"):
             self.status_manager.update_status_progress(
                 world_id=world_bible.get("world_id"),
                 section="npc_roster",
                 updates={"status": "completed", "count": len(npcs)},
                 phase_override="quest"
             )

        return npcs

    async def update_npc_full(self, current_npc: Dict, instruction: str, provider: Optional[str] = None) -> Dict:
        """Update existing NPC with full JSON rewrite"""
        try:
            user_prompt = SHAPER_UPDATE_PROMPT.replace(
                "{target_npc_json}", 
                json.dumps(current_npc, ensure_ascii=False, indent=2)
            ).replace(
                "{user_instruction}", 
                instruction
            )
            
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": "Please execute the update based on the system instructions."}],
                system=user_prompt, # The filled prompt becomes the system instruction
                provider=provider,
                timeout=120.0
            )
            
            new_data = parse_json_from_llm(response)
            
            # Validate basic structure
            if "profile" not in new_data or "id" not in new_data:
                raise ValueError("LLM returned incomplete NPC data")
                
            return new_data
            
        except Exception as e:
            print(f"Error in update_npc_full: {e}")
            # Fallback: return original if failed
            return current_npc

    async def _handle_npc_update(self, world_id: str, target_name: str, new_avatar_desc: str):
        """Update avatar description and regenerate image"""
        print(f"DEBUG: Handling NPC Update for {target_name}...")
        try:
            world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
            npc_path = os.path.join(world_dir, "npcs.json")
            
            if not os.path.exists(npc_path):
                return
                
            with open(npc_path, "r", encoding="utf-8") as f:
                npcs = json.load(f)
            
            target_npc = None
            for npc in npcs:
                if npc.get("profile", {}).get("name") == target_name:
                    target_npc = npc
                    break
            
            if target_npc:
                # Update Description
                target_npc["profile"]["avatar_desc"] = new_avatar_desc
                
                # Save first
                with open(npc_path, "w", encoding="utf-8") as f:
                    json.dump(npcs, f, indent=2, ensure_ascii=False)
                
                # Construct prompt (Include gender/age, exclude name)
                profile = target_npc.get("profile", {})
                gender = profile.get("gender", "Unknown")
                age = profile.get("age", "Unknown")
                occupation = profile.get("occupation", "Unknown")
                
                prompt = f"Character portrait of a {age} years old {gender} {occupation}. Appearance: {new_avatar_desc}. Full body, 9:16 aspect ratio."
                
                print(f"DEBUG: Regenerating image for {target_name}...")
                image_url = await image_service.generate_avatar(prompt, world_id, target_npc["id"])
                
                if image_url:
                     # Re-read to be safe
                     with open(npc_path, "r", encoding="utf-8") as f:
                        npcs = json.load(f)
                     
                     for npc in npcs:
                        if npc["id"] == target_npc["id"]:
                            npc["profile"]["avatar_url"] = image_url
                            break
                            
                     with open(npc_path, "w", encoding="utf-8") as f:
                        json.dump(npcs, f, indent=2, ensure_ascii=False)
                     print(f"DEBUG: Image updated for {target_name}")

        except Exception as e:
            print(f"Error in _handle_npc_update: {e}")

    # --- ACTION HANDLERS ---

    async def execute_add_npc(self, world_id: str, count: int, requirements: str):
        """Add new NPCs to the existing roster (Public Action)"""
        print(f"DEBUG: Executing Add NPC: {count} NPCs, requirements: {requirements}")
        try:
            world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
            npc_path = os.path.join(world_dir, "npcs.json")
            bible_path = os.path.join(world_dir, "bible.json")
            
            if not os.path.exists(npc_path) or not os.path.exists(bible_path):
                return
                
            with open(npc_path, "r", encoding="utf-8") as f:
                npcs = json.load(f)
            with open(bible_path, "r", encoding="utf-8") as f:
                bible = json.load(f)
            
            # 1. Generate Skeleton (Phase 1)
            print(f"DEBUG: Generating {count} skeletons...")
            roster_data = await self.generate_roster(bible, count, requirements=requirements)
            new_skeletons = roster_data.get("skeletons", [])
            new_locations = roster_data.get("new_locations", [])
            
            # [Auto-Collect] Ensure NPC personal locations are added to the world map
            existing_locs = bible.get("scene", {}).get("locations", [])
            for sk in new_skeletons:
                profile = sk.get("profile", {})
                home = profile.get("home_location")
                work = profile.get("work_location")
                
                if home and home not in new_locations and home not in existing_locs:
                    print(f"DEBUG: Auto-collecting missing home location: {home}")
                    new_locations.append(home)
                
                if work and work not in new_locations and work not in existing_locs:
                    print(f"DEBUG: Auto-collecting missing work location: {work}")
                    new_locations.append(work)

            # 2. Update Bible Locations
            scene_locations = bible.get("scene", {}).get("locations", [])
            merged_locations = list(set(scene_locations + new_locations))
            bible["scene"]["locations"] = merged_locations
            with open(bible_path, "w", encoding="utf-8") as f:
                json.dump(bible, f, indent=2, ensure_ascii=False)
                
            # 3. Generate Details (Phase 2)
            existing_names = [n.get("profile", {}).get("name") for n in npcs]
            roster_context = ", ".join(existing_names + [n.get("profile", {}).get("name") for n in new_skeletons])
            
            print(f"DEBUG: Fleshing out {len(new_skeletons)} new NPCs...")
            tasks = [self.generate_npc_details_with_retry(sk, bible, roster_context, requirements=requirements) for sk in new_skeletons]
            new_full_npcs = await asyncio.gather(*tasks)
            
            # 4. Append and Save
            final_new_npcs = []
            for item in new_full_npcs:
                if "relationships" not in item:
                    item["relationships"] = {}
                final_new_npcs.append(NPC(**item)) 
                
            for n in final_new_npcs:
                npcs.append(n.model_dump())
                
            with open(npc_path, "w", encoding="utf-8") as f:
                json.dump(npcs, f, indent=2, ensure_ascii=False)
                
            print(f"DEBUG: Added {len(final_new_npcs)} NPCs to roster.")
            
            # 5. Update Status Count
            self.status_manager.update_status_progress(
                world_id=world_id,
                section="npc_roster",
                updates={"count": len(npcs)}
            )
            
            # 6. Auto-gen images if enabled
            status = self.status_manager.load_world_status(world_id)
            if status and status.options.get("is_illustrated"):
                for n in final_new_npcs:
                    desc = n.profile.avatar_desc
                    if desc:
                        await self._handle_npc_update(world_id, n.profile.name, desc)

        except Exception as e:
            print(f"Error in _handle_add_npc: {e}")

    async def execute_npc_regenerate(self, world_id: str, target_name: str, instruction: str):
        """Regenerate a specific NPC based on instruction (Public Action)"""
        print(f"DEBUG: Executing NPC Regenerate for {target_name} with instruction: {instruction}")
        try:
            world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
            npc_path = os.path.join(world_dir, "npcs.json")
            
            if not os.path.exists(npc_path):
                return
                
            with open(npc_path, "r", encoding="utf-8") as f:
                npcs = json.load(f)
            
            target_index = -1
            target_npc = None
            
            for idx, npc in enumerate(npcs):
                if npc.get("profile", {}).get("name") == target_name:
                    target_npc = npc
                    target_index = idx
                    break
            
            if target_npc:
                # Call New Full Update Method
                print(f"DEBUG: Invoking Update Mode for {target_name}...")
                new_npc_data = await self.update_npc_full(target_npc, instruction)
                
                # Verify Critical ID
                if new_npc_data.get("id") != target_npc.get("id"):
                    print(f"WARNING: ID Mismatch after update. Restoring original ID: {target_npc.get('id')}")
                    new_npc_data["id"] = target_npc.get("id")

                # Update List
                npcs[target_index] = new_npc_data
                
                # Save
                with open(npc_path, "w", encoding="utf-8") as f:
                    json.dump(npcs, f, indent=2, ensure_ascii=False)
                
                print(f"DEBUG: NPC {target_name} fully updated and saved.")
                
                # Check Image Regen
                status = self.status_manager.load_world_status(world_id)
                if status and status.options.get("is_illustrated"):
                    new_desc = new_npc_data.get("profile", {}).get("avatar_desc")
                    if new_desc:
                         await self._handle_npc_update(world_id, new_npc_data.get("profile", {}).get("name"), new_desc)

        except Exception as e:
            print(f"Error in _handle_npc_regenerate: {e}")

    async def execute_image_management(self, world_id: str, action: str, target_name: Optional[str] = None):
        """Handle image generation requests (Public Action)"""
        print(f"DEBUG: Executing Image Management: {action} for {target_name}")
        try:
            # 1. Update Options
            if action in ["enable", "generate_all"]:
                self.status_manager.update_status_progress(world_id, "general", {}, options_update={"is_illustrated": True})
            elif action == "disable":
                self.status_manager.update_status_progress(world_id, "general", {}, options_update={"is_illustrated": False})
            
            # 2. Execute Generation
            world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
            npc_path = os.path.join(world_dir, "npcs.json")
            if not os.path.exists(npc_path):
                return
            
            with open(npc_path, "r", encoding="utf-8") as f:
                npcs = json.load(f)
            
            targets = []
            if action == "generate_one" and target_name:
                targets = [n for n in npcs if n.get("profile", {}).get("name") == target_name]
            elif action == "generate_all":
                targets = npcs # Generate for all
            elif action == "enable":
                # Generate for those missing avatars
                targets = [n for n in npcs if not n.get("profile", {}).get("avatar_url")]
            
            for npc in targets:
                desc = npc.get("profile", {}).get("avatar_desc")
                if desc:
                     print(f"DEBUG: Triggering image gen for {npc.get('profile', {}).get('name')}")
                     await self._handle_npc_update(world_id, npc.get("profile", {}).get("name"), desc)
                     
        except Exception as e:
            print(f"Error in _handle_image_management: {e}")
