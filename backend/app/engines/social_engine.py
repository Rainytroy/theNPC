import logging
import asyncio
import json
import re
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any
from ..schemas.npc import NPC
from ..core.llm import llm_client
from ..prompts.social import SOCIAL_SYSTEM_PROMPT

logger = logging.getLogger(__name__)
SOCIAL_COOLDOWN = timedelta(minutes=60)

class SocialEngine:
    def __init__(self, runtime):
        self.runtime = runtime
        self.last_interaction_time: Dict[str, datetime] = {}

    async def check_interactions(self, current_time: datetime):
        """Check if any colocated NPCs should interact."""
        # if current_time.minute != 0: return # Removed hourly check to match original logic
        
        # Group NPCs by location
        locations: Dict[str, List[NPC]] = {}
        for npc in self.runtime.npcs:
            loc = npc.dynamic.current_location
            if not loc or loc in ["Unknown", "Home", "Bed"]:
                continue
            if loc not in locations:
                locations[loc] = []
            locations[loc].append(npc)
        
        # Trigger events
        for loc, present_npcs in locations.items():
            if len(present_npcs) >= 2:
                # Check cooldown
                if self.is_on_cooldown(loc, current_time):
                    logger.debug(f"Social skip at {loc}: Cooldown")
                    continue
                
                # Check busy status
                if any(self.runtime.is_npc_busy(n.id) for n in present_npcs):
                    logger.debug(f"Social skip at {loc}: NPCs Busy")
                    continue

                # Check Schedule Priority & Mode (Phase 2 Upgrade)
                high_prio_count = 0
                critical_prio_count = 0
                npc_priorities = {}

                for n in present_npcs:
                    schedule_info = self.runtime.get_npc_current_schedule(n.id)
                    prio = 3
                    if schedule_info and schedule_info.get("current"):
                        prio = schedule_info["current"].get("priority", 3)
                    
                    npc_priorities[n.id] = prio
                    if prio >= 5:
                        critical_prio_count += 1
                    elif prio == 4:
                        high_prio_count += 1

                # Rule 1: Anyone Sleeping/Critical (5) -> Silence.
                if critical_prio_count > 0:
                    logger.debug(f"Social skip at {loc}: Critical Priority Present")
                    continue

                # Rule 2: High Priority (4) Logic
                social_mode = "casual"
                if high_prio_count > 0:
                    # If mixed (some high, some low) -> Block (High priority person ignores low)
                    if high_prio_count != len(present_npcs):
                        logger.debug(f"Social skip at {loc}: Mixed Priority (High vs Low)")
                        continue
                    else:
                        # All are High Priority -> Task Focused Mode
                        social_mode = "task_focused"
                        logger.info(f"Social Mode at {loc}: TASK FOCUSED")

                # Probability Check (Increased to 80% for testing)
                rand_val = random.random()
                if rand_val < 0.8:
                    logger.info(f"Social Event Triggered at {loc} (Mode: {social_mode})")
                    self.last_interaction_time[loc] = current_time
                    
                    # Pick 2 participants
                    participants = random.sample(present_npcs, 2)
                    asyncio.create_task(self.trigger_social_event(participants, loc, current_time, social_mode))
                else:
                    logger.debug(f"Social skip at {loc}: Probability {rand_val:.2f} > 0.8")

    def is_on_cooldown(self, location: str, current_time: datetime) -> bool:
        last_time = self.last_interaction_time.get(location)
        if last_time and (current_time - last_time) < SOCIAL_COOLDOWN:
            return True
        return False

    async def trigger_social_event(self, participants: List[NPC], location: str, current_time: datetime, social_mode: str = "casual"):
        # Set State & Task Tracking
        for p in participants:
            state = self.runtime.npc_states.get(p.id, {})
            state['interaction_state'] = 'SOCIAL'
            state['is_busy'] = True
            state['social_task'] = asyncio.current_task()
            state['busy_until'] = None

        try:
            # 1. Build Context
            participants_desc = []
            for npc in participants:
                others = [p for p in participants if p.id != npc.id]
                other_names = ", ".join([p.profile.name for p in others])
                
                # A. Shared History (Interaction with specific people, ignoring location)
                history_memories = self.runtime.memory_service.query_memory(
                    npc.id, 
                    f"Interaction with {other_names}", 
                    n_results=5
                )
                history_text = "\n".join([f"    - {m}" for m in history_memories]) if history_memories else "    - No significant shared history."

                # B. Critical Knowledge (Player, Quest, or Gossip about others)
                # We combine keywords to semantically search for any relevant secrets
                knowledge_query = f"Player Quest Secret Gossip about {other_names}"
                knowledge_memories = self.runtime.memory_service.query_memory(
                    npc.id, 
                    knowledge_query, 
                    n_results=3
                )
                knowledge_text = "\n".join([f"    - {m}" for m in knowledge_memories]) if knowledge_memories else "    - No specific secrets or gossip."

                # C. Quest Role & Active Quests (Standardized)
                quest_info = ""
                if npc.quest_role:
                    quest_info = f"- Quest Role: {npc.quest_role.role}\n  - Motivation: {npc.quest_role.motivation}\n  - Clue: {npc.quest_role.clue}"
                
                # Active Quests
                active_quests = self.runtime.quest_engine.get_active_quests_for_npc(npc.id)
                quest_list_str = "None"
                if active_quests["main"] or active_quests["side"]:
                    quest_list_str = ""
                    if active_quests["main"]:
                        quest_list_str += "\n  [Main Quests]:\n" + "\n".join([f"    - {q['title']}: {q['current_objective']}" for q in active_quests["main"]])
                    if active_quests["side"]:
                        quest_list_str += "\n  [Side Quests]:\n" + "\n".join([f"    - {q['title']}: {q['current_objective']}" for q in active_quests["side"]])

                # D. Routine/Action & Schedule
                current_action = npc.dynamic.current_action or "Idling"
                
                # Full Schedule Context
                full_schedule = self.runtime.schedules.get(npc.id, [])
                schedule_str = json.dumps(full_schedule, ensure_ascii=False) if full_schedule else "No specific schedule."
                
                # Affinity
                affinity = npc.relationships.get("player", {}).get("affinity", 0)

                desc = f"""
### Participant: {npc.profile.name} ({npc.profile.occupation})
- **ID**: {npc.id}
- **Personality**: {npc.dynamic.personality_desc}
- **Current Mood**: {npc.dynamic.mood}
- **Current Action**: {current_action}
- **Player Affinity**: {affinity}
- **Full Schedule**: {schedule_str}
- **Active Quests**: {quest_list_str}
{quest_info}
- **Shared History with {other_names}**:
{history_text}
- **Relevant Knowledge (Player/Secrets/Gossip)**:
{knowledge_text}
"""
                participants_desc.append(desc)

            # We keep recent context but label it clearly as "Environmental Background"
            recent_context = self.runtime.get_context_buffer(location)
            recent_context_str = "\n".join(recent_context[-5:]) if recent_context else "Silence."

            prompt = f"""
## Environment Context
- **Location**: {location}
- **Time**: {current_time.strftime("%Y-%m-%d %H:%M")}
- **Social Mode**: {social_mode}
- **Player Objective**: {self.runtime.world_bible.get("player_objective", "Unknown")}
- **Background Chatter (Recent lines in this room)**:
{recent_context_str}

## Participants Data
{"".join(participants_desc)}
"""
            
            # 2. Call LLM
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                system=SOCIAL_SYSTEM_PROMPT
            )
            
            # 3. Process Result
            result = self.runtime._parse_json(response)
            dialogue = result.get("dialogue", [])
            topic = result.get("topic", "Chatting")
            outcome = result.get("outcome", "")

            # Broadcast Dialogue
            for line in dialogue:
                speaker_name = line.get("speaker_name")
                speaker_npc = next((p for p in participants if p.profile.name == speaker_name), None)
                speaker_id = speaker_npc.id if speaker_npc else "unknown"
                
                # Resolve Target
                raw_target = line.get("target", "all")
                target_id = "all"
                target_metadata_name = None

                if raw_target == "Self":
                    target_id = speaker_id
                elif isinstance(raw_target, str) and raw_target.startswith("Extra:"):
                    target_id = "extra"
                    target_metadata_name = raw_target.split(":", 1)[1].strip()
                elif raw_target != "all":
                     # Try to find target in participants
                    target_npc = next((p for p in participants if p.profile.name == raw_target), None)
                    if target_npc:
                        target_id = target_npc.id
                    else:
                        # If specific name but not in participants, treat as Extra (implicit) or fallback
                        if len(participants) == 2 and raw_target == "all":
                             target = next((p for p in participants if p.id != speaker_id), None)
                             if target: target_id = target.id
                        else:
                            # Assume it's a valid name but maybe not in 'participants' list (edge case)
                            # Treat as extra for safety if not found
                            target_id = "extra"
                            target_metadata_name = raw_target

                content = line.get("content", "")
                action = line.get("action", "")
                
                # Sanitize content: Replace (action) with *action*
                content = re.sub(r'\((.*?)\)', r'*\1*', content)
                
                msg_content = ""
                
                # If action field is used, append it (unless it's already in content)
                if action:
                    # Simple check to avoid duplication if LLM puts it in both
                    if action not in content:
                        msg_content += f"*{action}* "
                
                msg_content += content
                
                metadata = {"location": location, "topic": topic}
                if target_metadata_name:
                    metadata["target_name"] = target_metadata_name

                await self.runtime.broadcast_event(f"{speaker_name}: {msg_content}", category="social", source_id=speaker_id, target_id=target_id, metadata=metadata)
                
                self.runtime.add_to_context(location, f"{speaker_name}: {msg_content}")

                await asyncio.sleep(2)
            
            # Update Memory (Outcome)
            if outcome:
                for npc in participants:
                    others = [p for p in participants if p.id != npc.id]
                    other_names = ", ".join([p.profile.name for p in others])
                    
                    timestamp = current_time.strftime('%Y-%m-%d %H:%M')
                    content = f"[{timestamp}] Interaction with {other_names} at {location}: {outcome}"
                    self.runtime.memory_service.add_memory(npc.id, content, timestamp, memory_type="social", importance=2)
                    
                    # Update relationships
                    for other in others:
                        if other.id not in npc.relationships:
                            npc.relationships[other.id] = {"affinity": 50, "memory": ""}
                        current_mem = npc.relationships[other.id].get("memory", "")
                        # Append outcome to relationship memory
                        npc.relationships[other.id]["memory"] = (current_mem + " | " + outcome).strip(" | ")
                        
                    logger.info(f"Memory committed for {npc.profile.name}")

            # Schedule Modification (Outcome)
            outcome_schedules = result.get("outcome_schedules", [])
            for item in outcome_schedules:
                npc_name = item.get("npc_name")
                schedule_mod = item.get("schedule_modification")
                target_npc = next((p for p in participants if p.profile.name == npc_name), None)
                
                if target_npc and schedule_mod:
                    logger.info(f"Social: Updating schedule for {target_npc.profile.name}")
                    self.runtime.merge_npc_schedule(target_npc.id, schedule_mod)
                    
        except asyncio.CancelledError:
            logger.info("Social Event Interrupted by Player!")
            # Reset bystanders (Participants who are NOT in PROCESSING state)
            for p in participants:
                state = self.runtime.npc_states.get(p.id, {})
                if state.get('interaction_state') == 'SOCIAL':
                    state['interaction_state'] = 'IDLE'
                    state['is_busy'] = False
                    state['social_task'] = None
            raise # Re-raise to ensure task cancellation completes

        except Exception as e:
            logger.error(f"Social Event Generation Failed: {e}")
        finally:
            # Cleanup for successful completion or error (NOT interruption if state changed)
            for p in participants:
                state = self.runtime.npc_states.get(p.id, {})
                if state.get('interaction_state') == 'SOCIAL':
                    state['interaction_state'] = 'IDLE'
                    state['is_busy'] = False
                    state['social_task'] = None
