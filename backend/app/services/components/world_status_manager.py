import json
import os
from typing import Optional, Dict
from datetime import datetime
from ...core.config import settings
from ...schemas.genesis import WorldCreationStatus, WorldStatusFile

class WorldStatusManager:
    def _get_status_file_path(self, world_id: str) -> str:
        return os.path.join(settings.DATA_DIR, "worlds", world_id, "status.json")

    def load_world_status(self, world_id: str) -> Optional[WorldStatusFile]:
        try:
            path = self._get_status_file_path(world_id)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return WorldStatusFile(**data)
        except Exception as e:
            print(f"Error loading status file: {e}")
        return None

    def save_world_status(self, world_id: str, status: WorldStatusFile):
        try:
            path = self._get_status_file_path(world_id)
            status.last_updated = datetime.now().isoformat()
            with open(path, "w", encoding="utf-8") as f:
                f.write(status.model_dump_json(indent=2))
        except Exception as e:
            print(f"Error saving status file: {e}")

    def update_status_progress(self, world_id: str, section: str, updates: Dict, phase_override: str = None, options_update: Dict = None):
        """Update a specific section of the progress and optionally switch phase or update options"""
        status = self.load_world_status(world_id)
        if not status:
            status = WorldStatusFile()
        
        # ✅ FIX: 如果section不存在，创建它
        if section not in status.progress:
            status.progress[section] = {}
        
        status.progress[section].update(updates)
        status.progress[section]["updated_at"] = datetime.now().isoformat()
        
        if phase_override:
            status.current_phase = phase_override
            
        if options_update:
            status.options.update(options_update)
            
        self.save_world_status(world_id, status)

    async def check_world_status(self, world_id: str) -> WorldCreationStatus:
        """Check the current status of world creation"""
        world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
        status_file = self.load_world_status(world_id)
        
        bible_path = os.path.join(world_dir, "bible.json")
        npc_path = os.path.join(world_dir, "npcs.json")
        quest_path = os.path.join(world_dir, "quests.json")
        
        bible_exists = os.path.exists(bible_path)
        npc_exists = os.path.exists(npc_path)
        quest_exists = os.path.exists(quest_path)
        
        npc_count = 0
        avatar_count = 0
        quest_count = 0
        
        if npc_exists:
            try:
                with open(npc_path, "r", encoding="utf-8") as f:
                    npcs = json.load(f)
                    npc_count = len(npcs)
                    avatar_count = len([n for n in npcs if n.get("profile", {}).get("avatar_url")])
            except Exception:
                pass

        if quest_exists:
            try:
                with open(quest_path, "r", encoding="utf-8") as f:
                    quests = json.load(f)
                    quest_count = len(quests)
            except Exception:
                pass

        # Determine Phase & Message
        current_phase_label = "World Bible"
        current_phase_key = status_file.current_phase if status_file else "world"

        if status_file:
            phase_map = {
                "world": "World Bible",
                "npc": "NPC",
                "quest": "Quest Blueprint",
                "ready": "Ready",
                "launch": "Launch"
            }
            current_phase_label = phase_map.get(status_file.current_phase, "World Bible")
        
        message = f"当前阶段：{current_phase_label}。"
        if status_file and status_file.options.get("is_illustrated"):
             message += " (图文模式已开启)"

        # ✅ SMART INFERENCE: Launch Progress
        # Even if status.json is stale or pending, check files to update progress
        progress = status_file.progress if status_file else {}
        
        # 1. Check Intro
        intro_path = os.path.join(world_dir, "intro.txt")
        if os.path.exists(intro_path):
            try:
                with open(intro_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if "intro" not in progress: progress["intro"] = {}
                progress["intro"]["status"] = "completed"
                progress["intro"]["content"] = content
                progress["intro"]["message"] = "Intro loaded from disk."
            except:
                pass

        # 2. Check Schedules
        schedules_dir = os.path.join(world_dir, "schedules")
        if os.path.exists(schedules_dir) and os.path.isdir(schedules_dir):
            schedule_files = [f for f in os.listdir(schedules_dir) if f.endswith('.json')]
            count = len(schedule_files)
            
            # Load NPC count to determine if truly completed
            total_npcs = npc_count
            if total_npcs == 0: # Fallback if not loaded above
                try:
                    with open(npc_path, "r", encoding="utf-8") as f:
                        total_npcs = len(json.load(f))
                except:
                    pass
            
            if count > 0:
                if "schedule" not in progress: progress["schedule"] = {}
                
                # Only mark completed if ALL NPCs have schedules
                if total_npcs > 0 and count >= total_npcs:
                    progress["schedule"]["status"] = "completed"
                    progress["schedule"]["message"] = f"All {count} schedules generated."
                else:
                    progress["schedule"]["status"] = "processing"
                    progress["schedule"]["message"] = f"Generating schedules ({count}/{total_npcs})..."
                
                progress["schedule"]["current"] = count
                progress["schedule"]["total"] = total_npcs

        # 3. Check Quest Enrichment (Implicit via Quests existence + Launch Phase)
        # If we are in Launch phase and quests exist, we assume they are enriched enough or done
        if quest_exists:
             # Just ensure the field exists so UI shows 'done' if we are past this step
             if "quest_enrich" not in progress: progress["quest_enrich"] = {}
             # Only mark done if we have schedules (meaning fully initialized) OR if status says so
             if progress.get("schedule", {}).get("status") == "completed":
                 progress["quest_enrich"]["status"] = "completed"
                 progress["quest_enrich"]["message"] = "Quests ready."

        # 4. Auto-detect Ready Phase
        if progress.get("intro", {}).get("status") == "completed" and \
           progress.get("schedule", {}).get("status") == "completed":
            if current_phase_key != "ready":
                current_phase_key = "ready"
                current_phase_label = "Ready"
                # Optionally update file here? No, just return dynamic status to avoid disk thrashing on reads
                # But UI needs 'ready' to show Enter button.

        return WorldCreationStatus(
            world_setting_finalized=bible_exists,
            npc_setting_finalized=npc_exists,
            quest_setting_finalized=quest_exists,
            ready_to_start=bible_exists and npc_exists and quest_exists,
            current_phase=current_phase_key, # Return raw key for frontend logic
            message=message,
            details={
                "npc_count": npc_count,
                "avatar_count": avatar_count,
                "quest_count": quest_count
            },
            progress=progress
        )
