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

    async def plan_post_interaction(self, npc):
        """Called when player interaction ends (timeout). Check if schedule needs update."""
        logger.info(f"Director: Planning post-interaction for {npc.profile.name}")
        
        # 1. Fetch Context
        # Query memory for recent interaction
        memories = self.runtime.memory_service.query_memory(npc.id, "Recent conversation with Player", n_results=5)
        conversation_summary = "\n".join([str(m) for m in memories]) if memories else "Unknown conversation."
        
        # 2. Fetch Schedule (Standardized)
        current_schedule = self.runtime.schedules.get(npc.id, [])
        schedule_str = json.dumps(current_schedule, ensure_ascii=False, indent=2)

        # 3. Active Quests (Standardized)
        active_quests = self.runtime.quest_engine.get_active_quests_for_npc(npc.id)
        quest_context_str = "No active quests."
        if active_quests["main"] or active_quests["side"]:
            quest_context_str = ""
            if active_quests["main"]:
                quest_context_str += "[Main Quests (PRIORITY)]:\n" + "\n".join([f"- {q['title']}: {q['current_objective']}" for q in active_quests["main"]])
            if active_quests["side"]:
                    quest_context_str += "\n[Side Quests]:\n" + "\n".join([f"- {q['title']}: {q['current_objective']}" for q in active_quests["side"]])
        
        # 4. Affinity
        affinity = npc.relationships.get("player", {}).get("affinity", 0)

        # 5. Prompt
        prompt = f"""
        You are the scheduler for NPC: {npc.profile.name}.
        The NPC just finished a conversation with the Player.
        
        ## Player Affinity
        {affinity}

        ## Recent Conversation Context
        {conversation_summary}
        
        ## Current Schedule
        {schedule_str}

        ## Active Quests Constraints
        {quest_context_str}
        
        ## Task
        Based on the conversation and quest constraints, does the NPC need to change their plan?
        - If they promised to wait, insert a "Wait" task.
        - If they promised to go somewhere, change the schedule.
        - If nothing changed, return EMPTY list.
        
        ## Output Format (JSON)
        Return ONLY a JSON list of schedule items to MODIFY the future schedule.
        IMPORTANT: If this is a temporary deviation (e.g. meeting for 1 hour), you MUST include a final item with action='resume' to indicate when to return to the original schedule.
        
        Example:
        [
            {{ "time": "14:00", "description": "Wait for player at Park", "location": "Park" }},
            {{ "time": "15:00", "action": "resume" }}
        ]
        OR [] if no change.
        """
        
        try:
            # Track task for cancellation
            state = self.runtime.npc_states.get(npc.id, {})
            state['planning_task'] = asyncio.current_task()
            
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                system="You are an advanced NPC Scheduler."
            )
            
            new_schedule = self.runtime._parse_json(response)
            
            if isinstance(new_schedule, list) and len(new_schedule) > 0:
                logger.info(f"Director: Updating schedule for {npc.profile.name}")
                self.runtime.merge_npc_schedule(npc.id, new_schedule)
                await self.runtime.broadcast_event(f"📝 {npc.profile.name} updated their schedule.", category="system", source_id=npc.id)
            else:
                logger.info(f"Director: No schedule change for {npc.profile.name}")

        except asyncio.CancelledError:
            logger.info(f"Director: Planning cancelled for {npc.profile.name}")
            raise
        except Exception as e:
            logger.error(f"Director: Planning failed: {e}")
        finally:
            # Reset State to IDLE
            if state.get('interaction_state') == 'PLANNING':
                state['interaction_state'] = 'IDLE'
                state['is_busy'] = False
                state['planning_task'] = None
                logger.info(f"{npc.profile.name} returned to IDLE.")

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
