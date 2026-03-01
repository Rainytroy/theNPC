# Player Engine (PlayerEngine)

## Path: `backend/app/engines/player_engine.py`

## Logic
Handles direct interactions from the player (e.g., chat messages or commands). It determines the target NPC(s) and triggers their reaction logic using LLMs.

## Key Implementation

```python
import logging
import asyncio
import json
from typing import Dict, Any
from ..schemas.npc import NPC, NPCGoal
from ..core.llm import llm_client
from ..prompts.reaction import REACTION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class PlayerEngine:
    def __init__(self, runtime):
        self.runtime = runtime

    async def handle_action(self, action_data: Dict):
        content = action_data.get("content", "")
        target_id = action_data.get("target_npc_id")
        
        # Broadcast Player Action
        if target_id:
            target_npc = self.runtime.get_npc(target_id)
            target_name = target_npc.profile.name if target_npc else "Unknown"
            await self.runtime.broadcast_event(f"我 (对 {target_name}): {content}", category="player_interaction", source_id="player", target_id=target_id)
        else:
            await self.runtime.broadcast_event(f"我 (所有人): {content}", category="player_interaction", source_id="player", target_id="all")
        
        # Identify Reactors
        reactors = []
        if target_id:
            npc = self.runtime.get_npc(target_id)
            if npc: 
                loc = npc.dynamic.current_location
                self.runtime.add_to_context(loc, f"Player (to {npc.profile.name}): {content}")
                # All NPCs in same location hear it, but only target reacts (or maybe others react too?)
                # Current logic: Reactors are those in the same location
                reactors = [n for n in self.runtime.npcs if n.dynamic.current_location == loc]
        else:
            # Global shout? Or check where player "is" (not defined yet)?
            # Assume global shout affects all locations with NPCs?
            active_locs = set(n.dynamic.current_location for n in self.runtime.npcs)
            for loc in active_locs:
                self.runtime.add_to_context(loc, f"Player (Global): {content}")
            reactors = self.runtime.npcs
            
        for npc in reactors:
            asyncio.create_task(self._npc_react(npc, content))

    async def _npc_react(self, npc: NPC, event_content: str):
        try:
            loc = npc.dynamic.current_location
            recent_context = self.runtime.get_context_buffer(loc)
            recent_context_str = "\n".join(recent_context[-5:])

            quest_role_str = "None"
            if npc.quest_role:
                quest_role_str = f"""
                - Role: {npc.quest_role.role}
                - Motivation: {npc.quest_role.motivation}
                - Clue/Action: {npc.quest_role.clue}
                """
            
            prompt = f"""
NPC: {npc.profile.name} ({npc.profile.occupation})
Personality: {npc.dynamic.personality_desc}
Quest Role: {quest_role_str}
Player Objective: {self.runtime.world_bible.get("player_objective", "Unknown")}
Current Time: {self.runtime.clock.current_time.strftime("%H:%M")}
Event: Player said "{event_content}"
Recent Conversation:
{recent_context_str}
"""
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                system=REACTION_SYSTEM_PROMPT
            )
            
            reaction = self.runtime._parse_json(response)

            if reaction:
                if reaction.get("reaction_type") != "ignore":
                    text = reaction.get("content", "...")
                    new_action = reaction.get("new_action")
                    
                    if text:
                        msg = f"{npc.profile.name}: {text}"
                        await self.runtime.broadcast_event(msg, category="player_interaction", source_id=npc.id, target_id="player")
                        self.runtime.add_to_context(loc, msg)
                        self.runtime.set_npc_busy(npc.id, 15)
                    
                    if new_action:
                        # ... Handle action update ...
                        pass
                    
                    if reaction.get("new_goal"):
                        # ... Handle new goal ...
                        pass
                    
        except Exception as e:
            logger.error(f"Reaction failed for {npc.profile.name}: {e}")
