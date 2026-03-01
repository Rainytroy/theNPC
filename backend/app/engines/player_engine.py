import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from ..schemas.npc import NPC, NPCGoal
from ..core.llm import llm_client
from ..prompts.reaction import REACTION_SYSTEM_PROMPT, QUEST_TRIGGER_INJECTION, INVESTIGATION_TRIGGER_INJECTION

logger = logging.getLogger(__name__)

class PlayerEngine:
    def __init__(self, runtime):
        self.runtime = runtime

    async def handle_action(self, action_data: Dict):
        content = action_data.get("content", "")
        target_id = action_data.get("target_npc_id")
        location = action_data.get("location")
        
        # Resolve Location ID to Name if possible (Fix for ID mismatch)
        if location and hasattr(self.runtime, "location_id_map"):
            location = self.runtime.location_id_map.get(location, location)

        metadata = {}
        if location:
            metadata["location"] = location

        reactors = []

        # 0. Check for Movement Events (Frontend sends *进入了...*)
        if content.startswith("*进入了") or content.startswith("*离开了"):
            # Broadcast so frontend logs it
            await self.runtime.broadcast_event(content, category="player_interaction", source_id="player", target_id="all", metadata=metadata)
            
            if content.startswith("*进入了") and location:
                await self.handle_player_move(location)
            return

        # 1. Private Chat (Targeted)
        if target_id:
            target_npc = self.runtime.get_npc(target_id)
            if target_npc:
                # Broadcast only to target
                await self.runtime.broadcast_event(content, category="player_interaction", source_id="player", target_id=target_id, metadata=metadata)
                
                # Context Update
                loc = target_npc.dynamic.current_location
                self.runtime.add_to_context(loc, f"Player (to {target_npc.profile.name}): {content}")
                
                # Reactor: Only the target
                reactors = [target_npc]

        # 2. Location Broadcast (Say)
        elif location:
            # Broadcast to "all" (Frontend filters by location view, or backend could be smarter but "all" is safe for now)
            await self.runtime.broadcast_event(content, category="player_interaction", source_id="player", target_id="all", metadata=metadata)
            self.runtime.add_to_context(location, f"Player (to room): {content}")
            
            # Reactors: All NPCs in this location
            reactors = [n for n in self.runtime.npcs if n.dynamic.current_location == location]
            
            # Memory Injection for Bystanders
            timestamp = self.runtime.clock.current_time.strftime("%Y-%m-%d %H:%M")
            for npc in reactors:
                self.runtime.memory_service.add_memory(
                    npc.id, 
                    f"Heard Player say in {location}: \"{content}\"", 
                    timestamp, 
                    memory_type="player_interaction", 
                    importance=2
                )

        # 3. Global Shout (Ignore for now)
        else:
            logger.info("Global shout ignored by NPCs")
            await self.runtime.broadcast_event(content, category="player_interaction", source_id="player", target_id="all", metadata={"type": "global"})
            
        # Trigger Reactions
        for npc in reactors:
            # INTERRUPT LOGIC: Player is God.
            # 1. Force State to PROCESSING (Lock NPC)
            # 2. Update Timestamp (Reset Timeout)
            # 3. Cancel any Planning task (Stop thinking about schedule)
            
            state = self.runtime.npc_states.get(npc.id, {})
            
            # Cancel Planning Task if exists
            if state.get('planning_task') and not state['planning_task'].done():
                state['planning_task'].cancel()
                logger.info(f"Interrupted Planning for {npc.profile.name}")

            # Cancel Social Task if exists
            if state.get('social_task') and not state['social_task'].done():
                state['social_task'].cancel()
                logger.info(f"Interrupted Social Task for {npc.profile.name}")
            
            # Force State
            state['interaction_state'] = 'PROCESSING'
            state['is_busy'] = True
            
            # Set Busy Timeout (180s real time converted to game time)
            time_scale = getattr(self.runtime.clock, 'time_scale', 60.0)
            game_seconds = 180 * time_scale
            state['busy_until'] = self.runtime.clock.current_time + timedelta(seconds=game_seconds)
            
            state['last_interaction_time'] = datetime.now()
            
            asyncio.create_task(self._npc_react(npc, content))

    async def handle_player_move(self, location: str):
        """Handle player entry into a location (Trigger greetings from Owners)"""
        potential_reactors = [n for n in self.runtime.npcs if n.dynamic.current_location == location]
        
        for npc in potential_reactors:
            # 1. Check if NPC is a target for any active quest (Passive Trigger)
            # If so, they should react regardless of ownership
            quest_node = self.runtime.quest_engine.get_active_quest_node_for_npc(npc.id)
            is_quest_target = quest_node is not None

            # 2. Heuristic: Only "Owners" or "Employees" react proactively
            # Check if Location Name appears in Occupation (e.g. "小卖部" in "小卖部老板娘")
            is_owner = location in npc.profile.occupation
            
            if is_owner or is_quest_target:
                trigger_reason = "Quest Target" if is_quest_target else "Owner"
                logger.info(f"Triggering Greeting for {npc.profile.name} at {location} (Reason: {trigger_reason})")
                asyncio.create_task(self._npc_react(npc, f"*Player entered {location}*"))

    async def _npc_react(self, npc: NPC, event_content: str):
        try:
            loc = npc.dynamic.current_location
            
            # A. Shared History with Player
            history_memories = self.runtime.memory_service.query_memory(npc.id, "Interaction with Player", n_results=5)
            history_text = "\n".join([f"    - {m}" for m in history_memories]) if history_memories else "    - No significant history."

            # B. Identity & Location Check
            is_workplace = "Unknown"
            if npc.profile.occupation in loc or loc in npc.profile.occupation:
                is_workplace = "Yes"
            
            # C. Quest Stance
            quest_info = "Neutral"
            if npc.quest_role:
                quest_info = f"Role: {npc.quest_role.role}, Motivation: {npc.quest_role.motivation}"

            # D. Current Action & Schedule
            current_action = npc.dynamic.current_action or "Idling"
            
            # Full Schedule (Standardized)
            full_schedule = self.runtime.schedules.get(npc.id, [])
            schedule_context_str = json.dumps(full_schedule, ensure_ascii=False) if full_schedule else "No specific schedule."
            
            # E. Quest Context (Standardized)
            active_quests = self.runtime.quest_engine.get_active_quests_for_npc(npc.id)
            affinity = npc.relationships.get("player", {}).get("affinity", 0)
            
            quest_context_str = "No active quest specific to this NPC."
            if active_quests["main"] or active_quests["side"]:
                quest_context_str = ""
                if active_quests["main"]:
                    quest_context_str += "Active Main Quests:\n" + "\n".join([f"- {q['title']}: {q['current_objective']}" for q in active_quests["main"]])
                if active_quests["side"]:
                     quest_context_str += "\nActive Side Quests:\n" + "\n".join([f"- {q['title']}: {q['current_objective']}" for q in active_quests["side"]])
            
            # ==================== NEW: Quest Trigger Detection ====================
            # F. Check if quest trigger conditions are met
            player_items = self.runtime.get_player_items()  # List of item IDs player owns
            quest_trigger = self.runtime.quest_engine.check_node_conditions(
                npc_id=npc.id,
                player_location=loc,
                player_items=player_items,
                affinity=affinity
            )
            
            quest_trigger_injection = ""
            if quest_trigger:
                quest_id, node_id, node = quest_trigger
                quest_context = self.runtime.quest_engine.get_full_quest_context(quest_id, node_id)
                
                if quest_context:
                    # Immediately mark node as triggered to prevent re-triggering
                    self.runtime.quest_engine.mark_node_triggered(quest_id, node_id)
                    
                    # Inject quest trigger prompt
                    quest_trigger_injection = QUEST_TRIGGER_INJECTION.format(
                        quest_title=quest_context.get("quest_title", ""),
                        quest_type=quest_context.get("quest_type", "main"),
                        quest_description=quest_context.get("quest_description", ""),
                        node_description=quest_context.get("node_description", ""),
                        node_type=quest_context.get("node_type", "dialogue"),
                        dialogue_script=quest_context.get("dialogue_script", ""),
                        next_node_hint=quest_context.get("next_node_hint", ""),
                        quest_id=quest_id,
                        node_id=node_id
                    )
                    logger.info(f"Quest trigger detected for {npc.profile.name}: {quest_id}/{node_id}")
            # ==================== END: Quest Trigger Detection ====================
            
            prompt = f"""
## NPC Profile
- **Name**: {npc.profile.name}
- **Occupation**: {npc.profile.occupation}
- **Personality**: {npc.dynamic.personality_desc}
- **Current Location**: {loc} (Is this my workplace/home? You decide based on Occupation)
- **Current Action**: {current_action}
- **Mood**: {npc.dynamic.mood}
- **Player Affinity**: {affinity}

## Full Schedule Context
{schedule_context_str}

## Active Quest Context
{quest_context_str}

## Player Context
- **History**: 
{history_text}
- **Quest Stance**: {quest_info}
- **Player Objective**: {self.runtime.world_bible.get("player_objective", "Unknown")}

## Event
Player said: "{event_content}"

{quest_trigger_injection}
"""
            # Build system prompt (add quest trigger injection if present)
            system_prompt = REACTION_SYSTEM_PROMPT
            if quest_trigger_injection:
                system_prompt = REACTION_SYSTEM_PROMPT + "\n\n" + quest_trigger_injection
            
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                system=system_prompt
            )
            
            reaction = self.runtime._parse_json(response)

            if reaction:
                # ==================== Handle Quest Chips ====================
                quest_chips = reaction.get("quest_chips")
                if quest_chips and quest_trigger:
                    # Get quest info from trigger
                    q_id, n_id, _ = quest_trigger
                    
                    # Broadcast NPC response first
                    text = reaction.get("content", "...")
                    import re
                    text = re.sub(r'\((.*?)\)', r'*\1*', text)
                    
                    msg = f"{npc.profile.name}: {text}"
                    
                    # Broadcast NPC's dialogue line
                    await self.runtime.broadcast_event(
                        msg, 
                        category="player_interaction", 
                        source_id=npc.id, 
                        target_id="player", 
                        metadata={"location": loc}
                    )
                    self.runtime.add_to_context(loc, msg)
                    
                    # Add quest_id and node_id to each chip (LLM doesn't return these)
                    enriched_chips = []
                    for chip in quest_chips:
                        enriched_chip = {
                            **chip,
                            "quest_id": q_id,
                            "node_id": n_id,
                            "npc_id": npc.id
                        }
                        enriched_chips.append(enriched_chip)
                    
                    # Send chips as separate WebSocket message (type: "chips")
                    chips_payload = {
                        "type": "chips",
                        "npc_id": npc.id,
                        "npc_name": npc.profile.name,
                        "chips": enriched_chips
                    }
                    for conn in self.runtime.active_connections:
                        try:
                            await conn.send_json(chips_payload)
                        except Exception as e:
                            logger.error(f"Failed to send chips: {e}")
                    
                    # Update NPC state to WAITING
                    state = self.runtime.npc_states.get(npc.id, {})
                    state['interaction_state'] = 'WAITING'
                    state['is_busy'] = True
                    
                    # Set Busy Timeout (180s real time converted to game time)
                    time_scale = getattr(self.runtime.clock, 'time_scale', 60.0)
                    game_seconds = 180 * time_scale
                    state['busy_until'] = self.runtime.clock.current_time + timedelta(seconds=game_seconds)

                    state['last_interaction_time'] = datetime.now()
                    
                    logger.info(f"Sent quest chips to player: {len(quest_chips)} options")
                    return  # Early return - wait for player to click chip
                # ==================== END: Handle Quest Chips ====================
                
                # Handle Quest & Affinity Updates
                quest_update = reaction.get("update_quest")
                if quest_update:
                    self.runtime.quest_engine.advance_quest(quest_update.get("quest_id"))
                    
                affinity_change = reaction.get("update_affinity")
                if affinity_change:
                    if "player" not in npc.relationships:
                        npc.relationships["player"] = {"affinity": 0}
                    
                    current_aff = npc.relationships["player"].get("affinity", 0)
                    npc.relationships["player"]["affinity"] = current_aff + affinity_change
                    logger.info(f"Affinity update for {npc.profile.name}: {current_aff} -> {current_aff + affinity_change}")

                # Handle Schedule Modification
                sched_mod = reaction.get("schedule_modification")
                if sched_mod:
                    mod_type = sched_mod.get("type")
                    new_event = sched_mod.get("event")
                    if mod_type == "add" and new_event:
                        # Use Merge Logic
                        self.runtime.merge_npc_schedule(npc.id, [new_event])
                        logger.info(f"Schedule Modified for {npc.profile.name}: Added {new_event['action']} at {new_event['time']}")

                if reaction.get("reaction_type") != "ignore":
                    text = reaction.get("content", "...")
                    # Sanitize content: Replace (action) with *action*
                    import re
                    text = re.sub(r'\((.*?)\)', r'*\1*', text)

                    new_action = reaction.get("new_action")
                    
                    if text:
                        # Determine Category and Target based on reaction_type
                        r_type = reaction.get("reaction_type", "speak")
                        
                        if r_type == "action":
                            # Monologue / Self-talk (Amber color, No arrow)
                            evt_category = "social"
                            evt_target = npc.id
                        else:
                            # Direct Speech to Player (Pink color, Arrow to Player)
                            evt_category = "player_interaction"
                            evt_target = "player"

                        msg = f"{npc.profile.name}: {text}"
                        await self.runtime.broadcast_event(msg, category=evt_category, source_id=npc.id, target_id=evt_target, metadata={"location": loc})
                        self.runtime.add_to_context(loc, msg)
                        # self.runtime.set_npc_busy(npc.id, 15) # Handled by State Machine
                    
                    if new_action:
                        npc.dynamic.current_action = new_action
                        msg = f"{new_action} [REACTION]"
                        await self.runtime.broadcast_event(msg, category="action", source_id=npc.id, metadata={"location": loc})
                        self.runtime.add_to_context(loc, f"[{npc.profile.name} Action]: {new_action}")
                        
                        update_msg = {
                            "type": "npc_update",
                            "payload": {
                                "npc_id": npc.id,
                                "changes": {
                                    "current_action": new_action
                                }
                            }
                        }
                        for conn in self.runtime.active_connections:
                            await conn.send_json(update_msg)
                            
                        # self.runtime.set_npc_busy(npc.id, 30) # Handled by State Machine
                    
                    # Update State -> WAITING
                    # NPC has spoken, now waiting for player response
                    state = self.runtime.npc_states.get(npc.id, {})
                    state['interaction_state'] = 'WAITING'
                    state['is_busy'] = True # Keep locked
                    
                    # Set Busy Timeout (180s real time converted to game time)
                    time_scale = getattr(self.runtime.clock, 'time_scale', 60.0)
                    game_seconds = 180 * time_scale
                    state['busy_until'] = self.runtime.clock.current_time + timedelta(seconds=game_seconds)

                    state['last_interaction_time'] = datetime.now()

                    new_goal_data = reaction.get("new_goal")
                    if new_goal_data:
                        import uuid
                        new_goal = NPCGoal(
                            id=str(uuid.uuid4()),
                            description=new_goal_data["description"],
                            type=new_goal_data["type"],
                            status="in_progress"
                        )
                        npc.goals.append(new_goal)
                        await self.runtime.broadcast_event(f"🎯 {npc.profile.name} decides to: {new_goal.description}", category="system", source_id=npc.id)
                        
                        # Persist World State immediately to save new goal
                        self.runtime.save_world_state()
                        
                        # Broadcast goal update to frontend
                        update_msg = {
                            "type": "npc_update",
                            "payload": {
                                "npc_id": npc.id,
                                "changes": {
                                    "goals": [g.model_dump() for g in npc.goals]
                                }
                            }
                        }
                        for conn in self.runtime.active_connections:
                            await conn.send_json(update_msg)
                    
        except Exception as e:
            logger.error(f"Reaction failed for {npc.profile.name}: {e}")
