# Reflection Engine (ReflectionEngine)

## Path: `backend/app/engines/reflection_engine.py`

## Logic
Handles the nightly "reflection" process where NPCs summarize their day, update their mood/values, and form new goals.

## Key Implementation

```python
import logging
import asyncio
import json
from datetime import datetime
from ..schemas.npc import NPC, NPCGoal
from ..core.llm import llm_client
from ..prompts.reflection import REFLECTION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class ReflectionEngine:
    def __init__(self, runtime):
        self.runtime = runtime

    async def check_schedule(self, current_time: datetime):
        """Run daily reflections at 22:00."""
        if current_time.hour == 22 and current_time.minute == 0:
            date_str = current_time.strftime("%Y-%m-%d")
            await self.run_daily_reflections(date_str)

    async def run_daily_reflections(self, date_str: str):
        for npc in self.runtime.npcs:
            key = f"{npc.id}_{date_str}"
            if key in self.runtime.daily_reflections:
                continue
            
            self.runtime.daily_reflections[key] = True
            logger.info(f"Triggering daily reflection for {npc.profile.name}")
            asyncio.create_task(self.trigger_daily_reflection(npc, date_str))

    async def trigger_daily_reflection(self, npc: NPC, date_str: str):
        try:
            memories = self.runtime.memory_service.query_memory(npc.id, f"Events on {date_str}", n_results=10)
            memory_text = "\n".join([f"- {m}" for m in memories]) if memories else "No significant events."
            
            prompt = f"""
            Current Date: {date_str}
            NPC Profile:
            - Name: {npc.profile.name}
            - Personality: {npc.dynamic.personality_desc}
            - Current Mood: {npc.dynamic.mood}
            - Values: {", ".join(npc.dynamic.values)}
            - Goals: {[g.description for g in npc.goals]}
            
            Daily Memories:
            {memory_text}
            """
            
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                system=REFLECTION_SYSTEM_PROMPT
            )
            
            result = self.runtime._parse_json(response)
            summary = result.get("summary", "")
            state_updates = result.get("state_updates", {})
            new_goals = result.get("new_goals", [])
            
            # Update Mood
            if state_updates.get("mood"):
                npc.dynamic.mood = state_updates["mood"]
            
            # Add New Goals
            import uuid
            for g in new_goals:
                new_goal = NPCGoal(
                    id=str(uuid.uuid4()),
                    description=g["description"],
                    type=g["type"],
                    status="pending"
                )
                npc.goals.append(new_goal)
                await self.runtime.broadcast_event(f"💡 {npc.profile.name} formed a new goal: {new_goal.description}", category="system", source_id=npc.id)

            # Store Summary Memory
            if summary:
                self.runtime.memory_service.add_memory(
                    npc.id, 
                    f"Daily Summary ({date_str}): {summary}", 
                    game_time=f"{date_str} 23:59",
                    memory_type="reflection", 
                    importance=3
                )
                await self.runtime.broadcast_event(f"🌙 {npc.profile.name} reflects: {summary}", category="system", source_id=npc.id)
                    
        except Exception as e:
            logger.error(f"Reflection failed for {npc.profile.name}: {e}")
