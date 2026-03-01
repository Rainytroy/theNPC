# Runtime Core (RuntimeEngine)

## Path: `backend/app/core/runtime.py`

## Logic
The central coordinator that initializes all engines, manages the game loop ticks, handles data persistence, and routes events.

## Key Implementation Structure

```python
import asyncio
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from ..core.config import settings
from ..schemas.npc import NPC
from ..services.memory_service import MemoryService
from ..core.global_state import global_state

# Engines
from ..core.clock import WorldClock
from ..engines.social_engine import SocialEngine
from ..engines.player_engine import PlayerEngine
from ..engines.director_engine import DirectorEngine
from ..engines.reflection_engine import ReflectionEngine

logger = logging.getLogger(__name__)

class RuntimeEngine:
    _instances: Dict[str, 'RuntimeEngine'] = {}

    def __init__(self, world_id: str, save_id: str):
        self.world_id = world_id
        self.save_id = save_id
        self.save_dir = os.path.join(settings.DATA_DIR, "worlds", self.world_id, "saves", self.save_id)
        os.makedirs(self.save_dir, exist_ok=True)

        # Components
        self.clock = WorldClock(datetime(2024, 1, 1, 8, 0, 0))
        self.memory_service = MemoryService.get_instance(world_id, save_id)
        
        # Sub-Engines
        self.social_engine = SocialEngine(self)
        self.player_engine = PlayerEngine(self)
        self.director_engine = DirectorEngine(self)
        self.reflection_engine = ReflectionEngine(self)

        # State
        self.active_connections = []
        self.world_bible = {}
        self.npcs: List[NPC] = []
        self.schedules: Dict[str, List[Dict]] = {}
        self.npc_states: Dict[str, Dict] = {} 
        self.context_buffer: Dict[str, List[str]] = {}
        self.event_buffer: List[Dict] = []
        
        # Subscribe to Clock
        self.clock.subscribe(self.on_tick)

    async def on_tick(self, current_time: datetime):
        """Master Loop Tick"""
        # Update Global State
        if global_state.engine_ref == self:
             global_state.update_time(current_time.strftime("%Y-%m-%d %H:%M"))

        # Broadcast Time
        await self.broadcast_time(current_time)
        
        # Hourly Save
        if current_time.minute == 0:
            self.save_state()

        # Delegate to Engines
        await self.process_schedules(current_time) # Keep simple schedule logic here or move to SchedulerEngine?
        await self.social_engine.check_interactions(current_time)
        await self.director_engine.check_event(current_time)
        await self.reflection_engine.check_schedule(current_time)

    # ... Persistence methods (load_data, save_state) ...
    # ... Websocket handling (connect, disconnect, broadcast_event) ...
    # ... Helper methods (get_npc, is_npc_busy, set_npc_busy) ...
