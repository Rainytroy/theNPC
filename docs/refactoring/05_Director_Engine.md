# Director Engine (DirectorEngine)

## Path: `backend/app/engines/director_engine.py`

## Logic
Periodically checks the state of the world to determine if a system-level event (plot twist, weather change, etc.) should occur.

## Key Implementation

```python
import logging
import asyncio
import json
from datetime import datetime
from ..core.llm import llm_client
from ..prompts.director import DIRECTOR_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class DirectorEngine:
    def __init__(self, runtime):
        self.runtime = runtime

    async def check_event(self, current_time: datetime):
        """Check for director events (e.g. every 4 hours)."""
        if current_time.minute != 0: return
        if current_time.hour % 4 != 0: return # Only check every 4 hours

        try:
            prompt = f"""
            World Time: {current_time.strftime("%Y-%m-%d %H:%M")}
            Active NPCs: {[n.profile.name for n in self.runtime.npcs]}
            """
            
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                system=DIRECTOR_SYSTEM_PROMPT
            )
            
            result = self.runtime._parse_json(response)
            if result.get("event_occurred"):
                description = result.get("description", "Something happened.")
                event_type = result.get("event_type", "global")
                
                logger.info(f"DIRECTOR EVENT: {description}")
                
                await self.runtime.broadcast_event(f"🌍 SYSTEM EVENT [{event_type.upper()}]: {description}", category="system")
                
                affected = result.get("affected_npcs", [])
                target_npcs = self.runtime.npcs if "all" in affected else [n for n in self.runtime.npcs if n.id in affected]
                
                # Notify affected NPCs so they can react
                for npc in target_npcs:
                    asyncio.create_task(self.runtime.player_engine._npc_react(npc, f"System Event: {description}"))
                        
        except Exception as e:
            logger.error(f"Director failed: {e}")
