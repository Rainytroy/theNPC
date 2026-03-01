import asyncio
import os
import shutil
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable, List, Any
from fastapi import WebSocket
import logging
import json
import re
import uuid
from ..core.config import settings
from ..schemas.npc import NPC
from ..schemas.genesis import WorldStatusFile
from ..core.llm import llm_client
from ..prompts.scheduler import SCHEDULER_SYSTEM_PROMPT
from ..prompts.reaction import REACTION_SYSTEM_PROMPT
from ..prompts.social import SOCIAL_SYSTEM_PROMPT
from ..prompts.reflection import REFLECTION_SYSTEM_PROMPT
from ..prompts.director import DIRECTOR_SYSTEM_PROMPT
from ..services.memory_service import MemoryService
from ..engines.social_engine import SocialEngine
from ..engines.player_engine import PlayerEngine
from ..engines.director_engine import DirectorEngine
from ..engines.reflection_engine import ReflectionEngine
from ..engines.quest_engine import QuestEngine
from ..engines.dialogue_flow_engine import DialogueFlowEngine

logger = logging.getLogger(__name__)

SOCIAL_COOLDOWN = timedelta(minutes=60) # Game time

class WorldClock:
    def __init__(self, start_time: datetime, time_scale: float = 60.0):
        self.current_time = start_time
        self.time_scale = time_scale  # 1 real second = X game seconds
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._subscribers: List[Callable[[datetime], None]] = []

    def start(self):
        if not self.is_running:
            self.is_running = True
            self._task = asyncio.create_task(self._tick_loop())
            logger.info(f"World Clock started (Task ID: {id(self._task)})")

    def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("World Clock stopped")

    def set_scale(self, scale: float):
        self.time_scale = scale
        logger.info(f"World Clock scale set to {scale}")

    def subscribe(self, callback: Callable[[datetime], None]):
        self._subscribers.append(callback)

    async def _tick_loop(self):
        try:
            while self.is_running:
                await asyncio.sleep(1)  # Real world 1 second
                # Advance game time
                self.current_time += timedelta(seconds=self.time_scale)
                # Notify subscribers
                for callback in self._subscribers:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(self.current_time)
                        else:
                            callback(self.current_time)
                    except Exception as e:
                        logger.error(f"Error in clock subscriber: {e}")
        except asyncio.CancelledError:
            logger.info("World Clock cancelled")
        except BaseException as e:
            logger.critical(f"World Clock CRASHED: {e}", exc_info=True)
        finally:
            self.is_running = False
            logger.info("World Clock stopped (Status Reset)")

class RuntimeEngine:
    _instances: Dict[str, 'RuntimeEngine'] = {}

    def __init__(self, world_id: str):
        self.world_id = world_id
        logger.info(f"RuntimeEngine initialized for {world_id} (ID: {id(self)})")
        # Default start time: 2024-01-01 08:00 (will be overridden by load_data)
        # time_scale=24.0 means 1 real hour = 1 game day
        self.clock = WorldClock(datetime(2024, 1, 1, 8, 0, 0), time_scale=24.0)
        self.display_year = None  # 纪元标签，如 "黑暗纪元5年"
        self.active_connections = []
        self.world_bible = {}
        self.npcs: List[NPC] = []
        self.schedules: Dict[str, List[Dict]] = {} # npc_id -> schedule list
        self.last_interaction_time: Dict[str, datetime] = {} # location_key -> last interaction time
        self.daily_reflections: Dict[str, bool] = {} # "npc_id_YYYY-MM-DD" -> True
        self.memory_service = MemoryService.get_instance(world_id)
        self.context_buffer: Dict[str, List[str]] = {} # location -> list of recent messages
        
        self.locations_list: List[str] = [] # Cache for locations
        self.location_id_map: Dict[str, str] = {} # Map ID to Name (e.g. loc_008 -> 听雨轩)
        self.item_id_map: Dict[str, str] = {} # Map Item ID to Name
        self.last_processed_time_str: Optional[str] = None # For schedule tracking
        
        # NPC Runtime States (Transient)
        self.npc_states: Dict[str, Dict] = {} 
        
        # Event History (InMemory Buffer for recent events)
        self.event_history: List[Dict] = []
        
        # Schedule Idempotency Tracker - Prevents duplicate triggers within same tick
        self._schedule_triggered_this_tick: Dict[str, str] = {}  # {npc_id: triggered_time_str}

        # Initialize Engines
        self.social_engine = SocialEngine(self)
        self.player_engine = PlayerEngine(self)
        self.director_engine = DirectorEngine(self)
        self.reflection_engine = ReflectionEngine(self)
        self.quest_engine = QuestEngine(self)
        self.dialogue_flow_engine = DialogueFlowEngine(self)

    @classmethod
    def get_instance(cls, world_id: str) -> 'RuntimeEngine':
        if world_id not in cls._instances:
            logger.info(f"Creating new RuntimeEngine instance for {world_id}")
            cls._instances[world_id] = RuntimeEngine(world_id)
        else:
            logger.debug(f"Returning existing RuntimeEngine instance for {world_id} (ID: {id(cls._instances[world_id])})")
        return cls._instances[world_id]

    def load_data(self, bible: Dict, npcs: List[Dict]):
        self.world_bible = bible
        self.npcs = [NPC(**n) if isinstance(n, dict) else n for n in npcs]
        logger.info(f"Loaded {len(self.npcs)} NPCs into Runtime {self.world_id}")
        
        # 1. Load Time Config (Prioritize time.json > bible)
        time_path = os.path.join(settings.DATA_DIR, "worlds", self.world_id, "time.json")
        time_config = {}
        
        if os.path.exists(time_path):
            try:
                with open(time_path, "r", encoding="utf-8") as f:
                    time_config = json.load(f)
                logger.info("Loaded time config from time.json")
            except Exception as e:
                logger.error(f"Failed to load time.json: {e}")
        
        if not time_config:
            time_config = bible.get("time_config", {})
            logger.info("Loaded time config from bible.json")

        start_datetime_str = time_config.get("start_datetime", "2024-01-01 08:00")
        self.display_year = time_config.get("display_year")
        
        try:
            # Parse start_datetime
            start_dt = datetime.strptime(start_datetime_str, "%Y-%m-%d %H:%M")
            self.clock.current_time = start_dt
            logger.info(f"World Clock initialized to: {start_dt}")
            if self.display_year:
                logger.info(f"Display Year: {self.display_year}")
        except Exception as e:
            logger.error(f"Failed to parse start_datetime '{start_datetime_str}': {e}")
            logger.warning("Using default start time: 2024-01-01 08:00")
        
        # 2. Load Locations (Prioritize locations.json > bible)
        # We store this for schedule generation context
        self.locations_list = []
        self.location_id_map = {}
        locations_path = os.path.join(settings.DATA_DIR, "worlds", self.world_id, "locations.json")
        
        if os.path.exists(locations_path):
            try:
                with open(locations_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Handle {"locations": [...]} or [...]
                    if isinstance(data, dict):
                        locs = data.get("locations", [])
                        self.locations_list = [l.get("name", "Unknown") for l in locs]
                        self.location_id_map = {l.get("id"): l.get("name") for l in locs if l.get("id") and l.get("name")}
                    elif isinstance(data, list):
                        self.locations_list = [l.get("name", "Unknown") for l in data]
                        self.location_id_map = {l.get("id"): l.get("name") for l in data if l.get("id") and l.get("name")}
                logger.info(f"Loaded {len(self.locations_list)} locations from locations.json (Map size: {len(self.location_id_map)})")
            except Exception as e:
                logger.error(f"Failed to load locations.json: {e}")
        
        # 3. Load Items (Build ID map)
        self.item_id_map = {}
        items_path = os.path.join(settings.DATA_DIR, "worlds", self.world_id, "items.json")
        if os.path.exists(items_path):
            try:
                with open(items_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    items = data.get("items", []) if isinstance(data, dict) else data
                    self.item_id_map = {i.get("id"): i.get("name") for i in items if i.get("id") and i.get("name")}
                logger.info(f"Loaded items map (Size: {len(self.item_id_map)})")
            except Exception as e:
                logger.error(f"Failed to load items.json: {e}")

        if not self.locations_list:
            scene_data = self.world_bible.get("scene", {})
            self.locations_list = scene_data.get("locations", ["Main Area"]) if isinstance(scene_data, dict) else ["Main Area"]
            logger.info("Loaded locations from bible.json")

        # Load schedules from schedules/ directory (new format: one JSON file per NPC)
        schedules_dir = os.path.join(settings.DATA_DIR, "worlds", self.world_id, "schedules")
        self.schedules = {}
        
        if os.path.exists(schedules_dir) and os.path.isdir(schedules_dir):
            try:
                for filename in os.listdir(schedules_dir):
                    if filename.endswith(".json"):
                        # Extract NPC ID from filename (e.g., "npc_emei_lingyue.json" -> "npc_emei_lingyue")
                        npc_id = filename[:-5]  # Remove .json extension
                        filepath = os.path.join(schedules_dir, filename)
                        with open(filepath, "r", encoding="utf-8") as f:
                            schedule_data = json.load(f)
                            # Ensure schedule_data is a list
                            if isinstance(schedule_data, list):
                                self.schedules[npc_id] = schedule_data
                            elif isinstance(schedule_data, dict):
                                # If it's a single object, wrap in a list
                                self.schedules[npc_id] = [schedule_data]
                logger.info(f"Loaded schedules for {len(self.schedules)} NPCs from schedules/ directory")
            except Exception as e:
                logger.error(f"Failed to load schedules from directory: {e}")
        else:
            # Fallback: Try legacy schedules.json format
            schedules_path = os.path.join(settings.DATA_DIR, "worlds", self.world_id, "schedules.json")
            if os.path.exists(schedules_path):
                try:
                    with open(schedules_path, "r", encoding="utf-8") as f:
                        self.schedules = json.load(f)
                    logger.info(f"Loaded schedules for {len(self.schedules)} NPCs from legacy schedules.json")
                except Exception as e:
                    logger.error(f"Failed to load schedules: {e}")
            
        self.npc_states = {
            npc.id: {
                'is_busy': False, 
                'busy_until': None, 
                'dynamic_queue': [],
                'interaction_state': 'IDLE', # IDLE, PROCESSING, WAITING, PLANNING
                'last_interaction_time': None
            } 
            for npc in self.npcs
        }
        
        # Migration: events.json -> events.jsonl
        json_path = os.path.join(settings.DATA_DIR, "worlds", self.world_id, "events.json")
        jsonl_path = os.path.join(settings.DATA_DIR, "worlds", self.world_id, "events.jsonl")
        
        if os.path.exists(json_path) and not os.path.exists(jsonl_path):
            logger.info("Migrating events.json to events.jsonl...")
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    old_events = json.load(f)
                with open(jsonl_path, "w", encoding="utf-8") as f:
                    for event in old_events:
                        f.write(json.dumps(event, ensure_ascii=False) + "\n")
                shutil.move(json_path, json_path + ".bak")
                logger.info("Migration complete.")
            except Exception as e:
                logger.error(f"Migration failed: {e}")

        # Load Recent History (Last 100)
        self.event_history = []
        if os.path.exists(jsonl_path):
            try:
                with open(jsonl_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    # Parse last 100 lines for buffer
                    for line in lines[-100:]:
                        if line.strip():
                            self.event_history.append(json.loads(line))
                    
                    # Time Persistence: Restore from last event
                    if lines:
                        last_event = json.loads(lines[-1])
                        if "game_datetime" in last_event:
                            self.clock.current_time = datetime.fromisoformat(last_event["game_datetime"])
                            logger.info(f"Restored world time to {self.clock.current_time}")
            except Exception as e:
                logger.error(f"Failed to load event history: {e}")
        
        # Load Quests
        self.quest_engine.load_quests()

        # State Alignment: Initialize NPC affinity based on active quests
        logger.info("Initializing NPC affinity based on active quests...")
        for npc in self.npcs:
            required_affinity = self.quest_engine.get_initial_affinity_for_npc(npc.id)
            if required_affinity is not None:
                if "player" not in npc.relationships:
                    npc.relationships["player"] = {}
                
                # Ensure minimum requirement is met
                current_affinity = npc.relationships["player"].get("affinity", 0)
                if current_affinity < required_affinity:
                     npc.relationships["player"]["affinity"] = required_affinity
                     logger.info(f"Aligned affinity for {npc.profile.name}: {current_affinity} -> {required_affinity}")

        # State Alignment: Initialize NPC location based on schedule and current time
        logger.info("Initializing NPC states based on current schedule...")
        for npc in self.npcs:
            sched_status = self.get_npc_current_schedule(npc.id)
            if sched_status and sched_status.get("current"):
                current_item = sched_status["current"]
                new_location = current_item.get('location')
                new_action = current_item.get('description')
                
                if new_location:
                    npc.dynamic.current_location = new_location
                if new_action:
                    npc.dynamic.current_action = new_action
                    
                logger.info(f"Initialized {npc.profile.name} at {new_location} doing: {new_action}")

    def _save_event(self, event: Dict):
        """Append event to history buffer and JSONL file"""
        # Add ISO datetime for persistence
        if "game_datetime" not in event:
            event["game_datetime"] = self.clock.current_time.isoformat()

        # Update Buffer (Keep size limited to avoid OOM)
        self.event_history.append(event)
        if len(self.event_history) > 200:
            self.event_history.pop(0)

        # Append to JSONL
        events_path = os.path.join(settings.DATA_DIR, "worlds", self.world_id, "events.jsonl")
        try:
            with open(events_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to save event: {e}")

    def _parse_json(self, text: str) -> Dict:
        """Helper to extract JSON from LLM response (Robust)"""
        try:
            json_str = ""
            match = re.search(r'```json\s*(\{.*?\}|\[.*?\])\s*```', text, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                match = re.search(r'```\s*(\{.*?\}|\[.*?\])\s*```', text, re.DOTALL)
                if match:
                    json_str = match.group(1)
                else:
                    first_brace = text.find('{')
                    first_bracket = text.find('[')
                    
                    if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
                        last_brace = text.rfind('}')
                        if last_brace != -1:
                            json_str = text[first_brace:last_brace+1]
                    elif first_bracket != -1:
                        last_bracket = text.rfind(']')
                        if last_bracket != -1:
                            json_str = text[first_bracket:last_bracket+1]
                    
                    if not json_str:
                        json_str = text 
            
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"JSON Parse Error in Runtime: {e}")
            logger.debug(f"Raw Text: {text}")
            return {} 

    # --- Helper Methods for Engines ---
    def get_npc(self, npc_id: str) -> Optional[NPC]:
        return next((n for n in self.npcs if n.id == npc_id), None)

    def is_npc_busy(self, npc_id: str) -> bool:
        state = self.npc_states.get(npc_id, {})
        return state.get('is_busy', False)

    def get_npc_current_schedule(self, npc_id: str) -> Dict:
        """Get the current active schedule item for an NPC"""
        schedule = self.schedules.get(npc_id, [])
        if not schedule:
            return None
            
        current_time_str = self.clock.current_time.strftime("%H:%M")
        
        # Sort schedule by time just in case
        sorted_schedule = sorted(schedule, key=lambda x: x.get("time", "00:00"))
        
        # Find the last item that is <= current_time
        current_item = None
        next_item = None
        
        for i, item in enumerate(sorted_schedule):
            if item.get("time") <= current_time_str:
                current_item = item
            else:
                next_item = item
                break
                
        # If no item is <= current_time (e.g. it's 00:01 but first schedule is 08:00)
        # We should logically take the LAST item of the day (from previous day context) or the first item?
        # Typically "Sleep" starts at 22:00. So at 01:00, the valid schedule is the one from 22:00.
        if current_item is None and sorted_schedule:
             current_item = sorted_schedule[-1] # Wrap around assumption: Last item covers early morning
             
        return {
            "current": current_item,
            "next": next_item
        }

    def get_context_buffer(self, location: str) -> List[str]:
        return self.context_buffer.get(location, [])
    # ----------------------------------

    async def broadcast_event(self, message: str, category: str = "general", source_id: str = "system", target_id: str = "all", metadata: Dict = None):
         payload = {
            "id": str(uuid.uuid4()),
            "type": "event",
            "content": message,
            "category": category,
            "source": source_id,
            "target": target_id,
            "game_time": self.clock.current_time.strftime("%H:%M"),
            "real_time": datetime.now().isoformat(),
            "timestamp": int(datetime.now().timestamp() * 1000), # For frontend compat
            "metadata": metadata or {}
        }
         
         # Persist
         self._save_event(payload)
         
         # Broadcast
         for connection in self.active_connections:
            try:
                await connection.send_json(payload)
            except Exception:
                pass

    async def generate_schedules(self, status_callback: Optional[Callable[[str], Any]] = None):
        """Generate schedules for all NPCs"""
        logger.info(f"Starting schedule generation for {len(self.npcs)} NPCs...")
        if not self.npcs:
            logger.warning("No NPCs found! Skipping schedule generation.")
            return

        # Use loaded locations
        locations = self.locations_list if hasattr(self, 'locations_list') and self.locations_list else ["Main Area"]

        import random
        # Creative messages for loading screen
        loading_templates = [
            "正在偷看 {name} 的日程表...",
            "正在猜测 {name} 今天的心情...",
            "嘘... {name} 似乎在密谋什么...",
            "正在为 {name} 安排今天的命运...",
            "{name} 正在思考今天去哪里闲逛..."
        ]

        for npc in self.npcs:
            if npc.id in self.schedules:
                continue 
            
            try:
                if status_callback:
                    msg = random.choice(loading_templates).format(name=npc.profile.name)
                    if asyncio.iscoroutinefunction(status_callback):
                        await status_callback(msg)
                    else:
                        status_callback(msg)

                logger.info(f"Generating schedule for {npc.profile.name}...")
                
                quest_context = "None"
                if npc.quest_role:
                    quest_context = f"""
                    - Player Objective: {self.world_bible.get("player_objective", "Unknown")}
                    - My Role: {npc.quest_role.role}
                    - Motivation: {npc.quest_role.motivation}
                    """

                prompt = f"""
                NPC: {npc.profile.name}, Role: {npc.profile.occupation}
                Personality: {npc.dynamic.personality_desc}
                Quest Context:
                {quest_context}
                Available Locations: {", ".join(locations)}
                """
                response = await llm_client.chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    system=SCHEDULER_SYSTEM_PROMPT
                )
                
                schedule = []
                try:
                    match = re.search(r'\[.*\]', response, re.DOTALL)
                    if match:
                        schedule = json.loads(match.group(0))
                    else:
                         parsed = self._parse_json(response)
                         if isinstance(parsed, list):
                             schedule = parsed
                except Exception:
                    pass
                
                if schedule:
                    self.schedules[npc.id] = schedule
                    logger.info(f"Schedule generated for {npc.profile.name}: {len(schedule)} items")
            except Exception as e:
                logger.error(f"Failed to generate schedule for {npc.id}: {e}")
        
        # Save schedules to file after generation
        self.save_schedules()
        
        # Update Status
        self._update_status("schedules", {"status": "completed", "count": len(self.schedules)})

    def _update_status(self, section: str, updates: Dict):
        """Update status.json from Runtime"""
        try:
            status_path = os.path.join(settings.DATA_DIR, "worlds", self.world_id, "status.json")
            status = None
            if os.path.exists(status_path):
                with open(status_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Handle missing fields if schema updated
                    if "progress" in data and "schedules" not in data["progress"]:
                        data["progress"]["schedules"] = { "status": "pending", "count": 0, "updated_at": None }
                    status = WorldStatusFile(**data)
            else:
                status = WorldStatusFile() 
            
            if section in status.progress:
                status.progress[section].update(updates)
                status.progress[section]["updated_at"] = datetime.now().isoformat()
                
            status.last_updated = datetime.now().isoformat()
            
            with open(status_path, "w", encoding="utf-8") as f:
                f.write(status.model_dump_json(indent=2))
        except Exception as e:
            logger.error(f"Failed to update status.json: {e}")

    def save_schedules(self):
        """Persist schedules to schedules/ directory (one file per NPC)"""
        schedules_dir = os.path.join(settings.DATA_DIR, "worlds", self.world_id, "schedules")
        os.makedirs(schedules_dir, exist_ok=True)
        
        try:
            for npc_id, schedule in self.schedules.items():
                file_path = os.path.join(schedules_dir, f"{npc_id}.json")
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(schedule, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved schedules for {len(self.schedules)} NPCs to schedules/ directory")
        except Exception as e:
            logger.error(f"Failed to save schedules: {e}")

    def update_npc_schedule(self, npc_id: str, new_schedule: List[Dict]):
        """Update a specific NPC's schedule and persist"""
        self.schedules[npc_id] = new_schedule
        self.save_schedules()
        logger.info(f"Updated schedule for NPC {npc_id}")
        
        # Broadcast schedule update
        asyncio.create_task(self.broadcast_schedule_update(npc_id))

    def merge_npc_schedule(self, npc_id: str, new_items: List[Dict]):
        """
        Merge new schedule items into the existing schedule using Slice & Insert.
        1. Identify Start Time (Time of first new item).
        2. Identify End Time (Time of last item if it is a 'resume' marker, else last item + 1h).
        3. Remove old items in [Start, End).
        4. Insert new items.
        5. Sort and Save.
        """
        if not new_items: return

        current_schedule = self.schedules.get(npc_id, [])
        
        # Sort new items to be sure
        sorted_new = sorted(new_items, key=lambda x: x.get("time", "00:00"))
        start_time = sorted_new[0].get("time")
        
        # Determine End Time & Filter Marker
        last_item = sorted_new[-1]
        items_to_insert = sorted_new
        end_time = "23:59" # Default fallback
        
        # Check for explicit marker (action='resume' or 'end_marker')
        if last_item.get("action") in ["resume", "end_marker", "resume_schedule"]:
            end_time = last_item.get("time")
            items_to_insert = sorted_new[:-1] # Remove marker
        else:
            # Fallback: Assume last event lasts 60 minutes
            try:
                t_str = last_item.get("time")
                if len(t_str) == 4: t_str = "0" + t_str
                dt = datetime.strptime(t_str, "%H:%M")
                end_dt = dt + timedelta(minutes=60)
                end_time = end_dt.strftime("%H:%M")
                # Handle day rollover (if goes past 24:00, cap at 24:00 or handle properly? For now simple cap string comparison works for today)
                if end_time < t_str: end_time = "23:59" 
            except:
                pass

        # Perform Slice
        preserved_schedule = []
        for item in current_schedule:
            t = item.get("time", "00:00")
            if len(t) == 4: t = "0" + t
            
            # Keep if BEFORE start OR AFTER/EQUAL end
            if t < start_time or t >= end_time:
                preserved_schedule.append(item)
        
        # Combine
        final_schedule = preserved_schedule + items_to_insert
        final_schedule.sort(key=lambda x: x.get("time", "00:00"))
        
        logger.info(f"Merged schedule for {npc_id}: Replaced [{start_time}, {end_time}) with {len(items_to_insert)} items.")
        
        # Update
        self.update_npc_schedule(npc_id, final_schedule)

    async def broadcast_schedule_update(self, npc_id: str):
        payload = {
            "type": "schedule_update",
            "npc_id": npc_id,
            "schedule": self.schedules.get(npc_id, [])
        }
        for connection in self.active_connections:
            try:
                await connection.send_json(payload)
            except Exception:
                pass

    async def connect(self, websocket):
        self.active_connections.append(websocket)
        
        # Send initial state
        await websocket.send_json({
            "type": "init",
            "world_time": self.clock.current_time.isoformat(),
            "is_running": self.clock.is_running
        })
        
        # Send History
        await websocket.send_json({
            "type": "history",
            "events": self.event_history
        })

        # [New] Sync NPC States immediately (Initial Sync)
        # This ensures the frontend UI reflects the "Aligned State" calculated in load_data
        for npc in self.npcs:
            payload = {
                "type": "npc_update",
                "payload": {
                    "npc_id": npc.id,
                    "changes": {
                        "location": npc.dynamic.current_location,
                        "current_action": npc.dynamic.current_action
                    }
                }
            }
            try:
                await websocket.send_json(payload)
            except Exception:
                pass

        # Send Player Objective Notification
        objective = self.world_bible.get("player_objective")
        if objective:
             await websocket.send_json({
                "type": "event",
                "category": "system",
                "content": f"🌟 你的终极目标: {objective}",
                "source": "system",
                "target": "player",
                "game_time": self.clock.current_time.strftime("%H:%M"),
                "timestamp": int(datetime.now().timestamp() * 1000),
                "metadata": {"type": "objective"}
            })

    def disconnect(self, websocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_time(self, current_time: datetime):
        payload = {
            "type": "time_update",
            "world_time": current_time.isoformat()
        }
        for connection in self.active_connections:
            try:
                await connection.send_json(payload)
            except Exception as e:
                logger.error(f"WebSocket send error: {e}")
                self.disconnect(connection)

    async def on_tick(self, current_time: datetime):
        await self.broadcast_time(current_time)
        time_str = current_time.strftime("%H:%M")
        
        # Reset idempotency tracker when time changes
        if time_str != self.last_processed_time_str:
            self._schedule_triggered_this_tick.clear()
        
        # Calculate time range to check (Exclusive last, Inclusive current)
        # This handles Time Skipping (e.g. 18:50 -> 19:20)
        times_to_check = [time_str]
        
        if self.last_processed_time_str and self.last_processed_time_str != time_str:
            try:
                # Simple logic: If we jumped more than 1 minute, fill gaps
                # We won't implement full datetime diff logic here to keep it simple, 
                # but we will check if the gap is reasonably small (e.g. within same day)
                # For robustness, we mostly care about the current time triggering. 
                # But to support "fast forward", we should really iterate.
                
                # Re-parse to compare
                last_dt = datetime.strptime(self.last_processed_time_str, "%H:%M")
                curr_dt = datetime.strptime(time_str, "%H:%M")
                
                # Handle day rollover simply by ignoring negative diffs for now (or assuming forward)
                if curr_dt > last_dt:
                    diff_mins = int((curr_dt - last_dt).total_seconds() / 60)
                    if 1 < diff_mins <= 180: # Limit catch-up to 3 hours to avoid lag spikes
                        times_to_check = []
                        for m in range(1, diff_mins + 1):
                            check_dt = last_dt + timedelta(minutes=m)
                            times_to_check.append(check_dt.strftime("%H:%M"))
            except Exception:
                pass # Fallback to just current time
        
        self.last_processed_time_str = time_str

        if current_time.minute == 0:
            logger.info(f"Tick: {time_str} (Engine {id(self)})")

        for npc in self.npcs:
            npc_id = npc.id
            state = self.npc_states.get(npc_id, {})
            
            # Check Busy Timeout
            if state.get('is_busy') and state.get('busy_until'):
                if current_time >= state['busy_until']:
                    state['is_busy'] = False
                    state['busy_until'] = None
                    logger.info(f"{npc.profile.name} is no longer busy.")
            
            if state.get('is_busy'):
                continue

            # 1. Check Dynamic Queue (Priority)
            if state.get('dynamic_queue'):
                task = state['dynamic_queue'].pop(0)
                logger.info(f"Dynamic Task Triggered! {npc_id}: {task['description']}")
                
                new_location = task.get('location', npc.dynamic.current_location)
                npc.dynamic.current_location = new_location
                npc.dynamic.current_action = task['description']
                
                await self.broadcast_event(
                    f"{task['description']} [DYNAMIC]", 
                    category="action",
                    source_id=npc_id,
                    metadata={"location": new_location}
                )
                
                update_msg = {
                    "type": "npc_update",
                    "payload": {
                        "npc_id": npc.id,
                        "changes": {
                            "location": new_location,
                            "current_action": task['description']
                        }
                    }
                }
                for conn in self.active_connections:
                    await conn.send_json(update_msg)
                
                duration = task.get('duration', 30)
                self.set_npc_busy(npc_id, duration)
                continue

            # 2. Check Static Schedule (Robust Range Check)
            schedule = self.schedules.get(npc_id, [])
            schedule_triggered = False  # Track if Edge Trigger fired for this NPC
            
            # Check ALL time points in the catch-up range
            for check_time in times_to_check:
                # Idempotency check: Skip if already triggered for this time
                if self._schedule_triggered_this_tick.get(npc_id) == check_time:
                    continue
                    
                for item in schedule:
                    sched_time = item.get("time", "")
                    if len(sched_time) == 4: sched_time = "0" + sched_time

                    if sched_time == check_time:
                        logger.info(f"Action Triggered! {npc_id} at {check_time}")
                        
                        new_location = item.get('location', 'Unknown')
                        npc.dynamic.current_location = new_location
                        npc.dynamic.current_action = item['description']
                        
                        await self.broadcast_event(
                            f"{item['description']} [SCHEDULE]", 
                            category="action",
                            source_id=npc_id,
                            metadata={"location": new_location}
                        )
                        
                        update_msg = {
                            "type": "npc_update",
                            "payload": {
                                "npc_id": npc.id,
                                "changes": {
                                    "location": new_location,
                                    "current_action": item['description']
                                }
                            }
                        }
                        for conn in self.active_connections:
                            await conn.send_json(update_msg)
                        
                        # Mark as triggered for idempotency
                        self._schedule_triggered_this_tick[npc_id] = check_time
                        schedule_triggered = True
                        break  # Only trigger once per NPC per tick
                
                if schedule_triggered:
                    break  # Exit outer loop as well

            # 3. State Alignment (Self-Healing / Level Trigger)
            # Skip if Edge Trigger already fired for this NPC this tick
            if schedule_triggered:
                continue
                
            # Ensure NPC is in the correct state according to schedule
            # This fixes issues where Edge Triggers were missed (e.g. due to busy state or time jumps)
            sched_status = self.get_npc_current_schedule(npc_id)
            if sched_status and sched_status.get("current"):
                current_item = sched_status["current"]
                expected_desc = current_item.get("description")
                expected_loc = current_item.get("location")
                
                # Check for location deviation (Drift)
                # When NPC is released from busy state but not at scheduled location, 
                # they should return to their scheduled position
                if expected_loc and npc.dynamic.current_location != expected_loc:
                    # NPC is not at the scheduled location - force alignment
                    
                    logger.info(f"State Alignment: {npc.profile.name} location drift. Expected: {expected_loc}, Actual: {npc.dynamic.current_location}")
                    
                    # Apply Correction
                    if expected_loc:
                        npc.dynamic.current_location = expected_loc
                    npc.dynamic.current_action = expected_desc
                    
                    # Broadcast Recovery Event
                    await self.broadcast_event(
                        f"{expected_desc} [SCHEDULE RECOVERY]", 
                        category="action",
                        source_id=npc_id,
                        metadata={"location": expected_loc}
                    )
                    
                    update_msg = {
                        "type": "npc_update",
                        "payload": {
                            "npc_id": npc.id,
                            "changes": {
                                "location": expected_loc,
                                "current_action": expected_desc
                            }
                        }
                    }
                    for conn in self.active_connections:
                        try:
                            await conn.send_json(update_msg)
                        except Exception:
                            pass

        # Check Social Interactions
        await self.check_social_interactions(current_time)
        
        if current_time.hour == 22 and current_time.minute == 0:
            await self.check_daily_reflections(current_time)

        if current_time.minute == 0 and current_time.hour % 4 == 0:
            await self.check_director_event(current_time)

    def save_world_state(self):
        """Force save in-memory state to disk (for archiving)"""
        if not self.world_id: return
        
        world_dir = os.path.join(settings.DATA_DIR, "worlds", self.world_id)
        if not os.path.exists(world_dir): return

        # 1. Save NPCs (Dynamic state like location, mood)
        try:
            npc_path = os.path.join(world_dir, "npcs.json")
            with open(npc_path, "w", encoding="utf-8") as f:
                # Convert list of Pydantic models to list of dicts
                f.write(json.dumps([npc.model_dump() for npc in self.npcs], indent=2, ensure_ascii=False))
            logger.info(f"Saved {len(self.npcs)} NPCs state to file.")
        except Exception as e:
            logger.error(f"Failed to save NPC state: {e}")

        # 2. Save Schedules
        self.save_schedules()
        
        # 3. Save Quests
        self.quest_engine.save_quests()

    def reset(self):
        """Reset runtime state (clear history/schedules, keep definition)"""
        self.event_history = []
        self.schedules = {}
        self.context_buffer = {}
        self.npc_states = {
            npc.id: {
                'is_busy': False, 
                'busy_until': None, 
                'dynamic_queue': [],
                'interaction_state': 'IDLE',
                'last_interaction_time': None
            } 
            for npc in self.npcs
        }
        # Reset clock to start time? 
        # Ideally yes, reload from Bible start time.
        if self.world_bible:
             time_config = self.world_bible.get("time_config", {})
             start_datetime_str = time_config.get("start_datetime", "2024-01-01 08:00")
             try:
                 self.clock.current_time = datetime.strptime(start_datetime_str, "%Y-%m-%d %H:%M")
             except:
                 pass
        
        logger.info(f"Runtime Reset for {self.world_id}")

    # --- Clock Control Methods (Delegated to WorldClock) ---
    def start(self):
        """Start the world clock and subscribe to tick events"""
        # Force reset subscribers to avoid duplicates
        self.clock._subscribers = [self.on_tick]
        self.clock.start()
        logger.info(f"RuntimeEngine started for world {self.world_id} (Clock running: {self.clock.is_running})")

    def stop(self):
        """Stop the world clock"""
        self.clock.stop()
        logger.info(f"RuntimeEngine stopped for world {self.world_id}")

    def set_time_scale(self, scale: int):
        """Change the time scale (1 real second = X game seconds)"""
        self.clock.set_scale(scale)
        logger.info(f"Time scale set to {scale} for world {self.world_id}")

    # --- Engine Delegation Methods ---
    async def check_social_interactions(self, current_time: datetime):
        """Delegate to social engine for NPC interactions"""
        await self.social_engine.check_interactions(current_time)

    async def check_daily_reflections(self, current_time: datetime):
        """Delegate to reflection engine for daily reflections"""
        await self.reflection_engine.check_schedule(current_time)

    async def check_director_event(self, current_time: datetime):
        """Delegate to director engine for world events"""
        await self.director_engine.check_event(current_time)

    def set_npc_busy(self, npc_id: str, duration_minutes: int):
        """Set an NPC as busy for a duration (in game minutes)"""
        state = self.npc_states.get(npc_id)
        if state:
            state['is_busy'] = True
            state['busy_until'] = self.clock.current_time + timedelta(minutes=duration_minutes)
            logger.info(f"NPC {npc_id} set busy for {duration_minutes} minutes")

    def add_to_context(self, location: str, message: str):
        """Add a message to the context buffer for a location"""
        if location not in self.context_buffer:
            self.context_buffer[location] = []
        self.context_buffer[location].append(message)
        # Keep buffer size limited
        if len(self.context_buffer[location]) > 50:
            self.context_buffer[location].pop(0)

    async def send_history_chunk(self, before_timestamp: int, websocket):
        """Send a chunk of historical events before the given timestamp"""
        try:
            events_path = os.path.join(settings.DATA_DIR, "worlds", self.world_id, "events.jsonl")
            if not os.path.exists(events_path):
                await websocket.send_json({"type": "history_chunk", "events": [], "has_more": False})
                return

            # Read all events and filter
            all_events = []
            with open(events_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            event = json.loads(line)
                            all_events.append(event)
                        except:
                            pass

            # Filter events before timestamp
            filtered = []
            for event in all_events:
                event_ts = event.get("timestamp", 0)
                if event_ts < before_timestamp:
                    filtered.append(event)

            # Sort by timestamp desc and take last 50
            filtered.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            chunk = filtered[:50]
            has_more = len(filtered) > 50

            await websocket.send_json({
                "type": "history_chunk",
                "events": list(reversed(chunk)),  # Return in chronological order
                "has_more": has_more
            })
        except Exception as e:
            logger.error(f"Failed to send history chunk: {e}")
            await websocket.send_json({"type": "history_chunk", "events": [], "has_more": False})

    async def handle_player_action(self, message: Dict):
        """Handle player actions from WebSocket"""
        # Delegate directly to PlayerEngine which handles the unified action payload
        await self.player_engine.handle_action(message)

    # ==================== Quest System Helper Methods ====================
    
    def get_player_items(self) -> List[str]:
        """Get list of item IDs currently owned by the player"""
        items_path = os.path.join(settings.DATA_DIR, "worlds", self.world_id, "items.json")
        
        if not os.path.exists(items_path):
            return []
        
        try:
            with open(items_path, "r", encoding="utf-8") as f:
                items_data = json.load(f)
            
            player_items = []
            items = items_data.get("items", []) if isinstance(items_data, dict) else items_data
            
            for item in items:
                if item.get("owner") == "player":
                    player_items.append(item.get("id", ""))
            
            return player_items
        except Exception as e:
            logger.error(f"Failed to get player items: {e}")
            return []
    
    async def handle_chip_click(self, chip_data: Dict):
        """
        Handle player clicking a quest chip.
        
        chip_data format:
        {
            "type": "accept" | "reject" | "investigate" | "ignore" | "player_line",
            "quest_id": "...",
            "node_id": "...",
            "npc_id": "...",
            "label": "chip text"
        }
        """
        chip_type = chip_data.get("type")
        quest_id = chip_data.get("quest_id")
        node_id = chip_data.get("node_id")
        npc_id = chip_data.get("npc_id")
        
        logger.info(f"Chip clicked: type={chip_type}, quest={quest_id}, node={node_id}")
        
        if chip_type == "accept":
            # Player accepted quest trigger - start dialogue flow
            result = await self.dialogue_flow_engine.start_flow(npc_id, quest_id, node_id)
            return result
            
        elif chip_type == "reject":
            # Player rejected - mark as triggered but not completed
            await self.dialogue_flow_engine.reject_flow(npc_id, quest_id, node_id)
            return {"success": True, "rejected": True}
            
        elif chip_type == "investigate":
            # Player chose to investigate - start investigation flow
            result = await self.dialogue_flow_engine.start_flow(npc_id, quest_id, node_id)
            return result
            
        elif chip_type == "ignore":
            # Player ignored investigation prompt
            return {"success": True, "ignored": True}
            
        elif chip_type == "player_line":
            # Player clicked their dialogue line chip - advance dialogue
            result = await self.dialogue_flow_engine.player_speak(npc_id)
            return result
        
        return {"success": False, "error": "Unknown chip type"}
    
    async def handle_dialogue_flow_action(self, action_data: Dict):
        """Handle dialogue flow specific actions from WebSocket"""
        action_type = action_data.get("action")
        npc_id = action_data.get("npc_id")
        
        if action_type == "player_speak":
            # Advance dialogue flow
            result = await self.dialogue_flow_engine.player_speak(npc_id)
            return result
        
        return {"success": False, "error": "Unknown action"}
