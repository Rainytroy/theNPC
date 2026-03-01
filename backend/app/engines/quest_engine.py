import json
import os
import logging
from datetime import datetime
from typing import List, Optional, Dict, Tuple
from ..schemas.quest import Quest, QuestNode
from ..core.config import settings

logger = logging.getLogger(__name__)

class QuestEngine:
    def __init__(self, runtime):
        self.runtime = runtime
        self.quests: List[Quest] = []
        self.active_quests: Dict[str, Quest] = {} # id -> Quest
        # Track which nodes have been triggered (to avoid re-triggering)
        self.triggered_nodes: Dict[str, bool] = {}  # "quest_id:node_id" -> True

    def load_quests(self):
        """Load quests from world data"""
        if not self.runtime.world_id:
            return

        quest_path = os.path.join(settings.DATA_DIR, "worlds", self.runtime.world_id, "quests.json")
        if os.path.exists(quest_path):
            try:
                with open(quest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Handle both formats: {"quests": [...]} or bare [...]
                    quest_list = data.get("quests", []) if isinstance(data, dict) else data
                    self.quests = [Quest(**q) for q in quest_list]
                    # Index active quests
                    self.active_quests = {q.id: q for q in self.quests if q.status == "active"}
                logger.info(f"Loaded {len(self.quests)} quests.")
            except Exception as e:
                logger.error(f"Failed to load quests: {e}")
        else:
            logger.info("No quests.json found (Fresh world or not generated yet).")

    def save_quests(self):
        """Persist quests"""
        if not self.runtime.world_id:
            return

        quest_path = os.path.join(settings.DATA_DIR, "worlds", self.runtime.world_id, "quests.json")
        try:
            with open(quest_path, "w", encoding="utf-8") as f:
                data = [q.model_dump() for q in self.quests]
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save quests: {e}")

    def get_active_quest_node_for_npc(self, npc_id: str) -> Optional[Dict]:
        """Find if this NPC is the target of any active quest node"""
        for quest in self.active_quests.values():
            node = quest.current_node
            if node and node.target_npc_id == npc_id and node.status != "completed":
                return {
                    "quest_id": quest.id,
                    "quest_title": quest.title,
                    "node_description": node.description,
                    "required_affinity": node.required_affinity
                }
        return None

    def get_initial_affinity_for_npc(self, npc_id: str) -> Optional[int]:
        """
        Check active quests to see if this NPC needs a specific affinity level initialized.
        Returns the MAX affinity required by any active quest node targeting this NPC.
        """
        max_affinity = None
        
        for quest in self.active_quests.values():
            node = quest.current_node
            if not node or node.status == "completed":
                continue
            
            # Only consider if NPC is the direct target of the active node
            if node.target_npc_id == npc_id:
                for cond in node.conditions:
                    if cond.type == "affinity":
                        val = cond.params.get("value", 0)
                        if max_affinity is None or val > max_affinity:
                            max_affinity = val
                            
        return max_affinity

    def get_active_quests_for_npc(self, npc_id: str) -> Dict[str, List[Dict]]:
        """
        Get all active quests relevant to this NPC (Main vs Side).
        Relevance = NPC is target, or NPC is mentioned in params/conditions/description.
        """
        result = {
            "main": [],
            "side": []
        }
        
        for quest in self.active_quests.values():
            # Check current node only, or whole quest? 
            # Usually only current active node matters for immediate schedule/reaction.
            node = quest.current_node
            if not node or node.status == "completed":
                continue
            
            is_relevant = False
            
            # 1. Direct Target
            if node.target_npc_id == npc_id:
                is_relevant = True
            
            # 2. Conditions params (e.g. talk to X)
            if not is_relevant:
                for cond in node.conditions:
                    # Check values in params
                    for val in cond.params.values():
                        if str(val) == npc_id:
                            is_relevant = True
                            break
            
            if is_relevant:
                quest_info = {
                    "id": quest.id,
                    "title": quest.title,
                    "description": quest.description,
                    "current_objective": node.description,
                    "required_affinity": node.required_affinity
                }
                
                if quest.type == "main":
                    result["main"].append(quest_info)
                else:
                    result["side"].append(quest_info)
                    
        return result

    def advance_quest(self, quest_id: str):
        """Move quest to next node"""
        quest = self.active_quests.get(quest_id)
        if quest:
            # Mark current node complete
            if quest.current_node:
                quest.current_node.status = "completed"
            
            quest.current_node_index += 1
            
            # Check completion
            if quest.current_node_index >= len(quest.nodes):
                quest.status = "completed"
                logger.info(f"Quest {quest.title} Completed!")
                # Remove from active index? Or keep for record? 
                # Keep active_quests only for lookup performance, so remove completed.
                del self.active_quests[quest_id]
            else:
                # Activate next node
                if quest.current_node:
                    quest.current_node.status = "active"
                logger.info(f"Quest {quest.title} advanced to node {quest.current_node_index}")
            
            self.save_quests()
            return True
        return False

    # ==================== NEW: Quest Trigger System ====================
    
    def check_node_conditions(self, npc_id: str, player_location: str, 
                               player_items: List[str], affinity: int) -> Optional[Tuple[str, str, 'QuestNode']]:
        """
        Check if any quest node targeting this NPC has all conditions met.
        
        Args:
            npc_id: The NPC being interacted with
            player_location: Current player location
            player_items: List of item IDs the player has
            affinity: Player's affinity with this NPC
            
        Returns:
            Tuple of (quest_id, node_id, QuestNode) if conditions met, else None
        """
        current_time_str = self.runtime.clock.current_time.strftime("%H:%M")
        
        for quest in self.active_quests.values():
            node = quest.current_node
            if not node or node.status != "active":
                continue
            
            # Only check nodes targeting this NPC
            if node.target_npc_id != npc_id:
                continue
            
            # Skip if already triggered (user rejected before)
            trigger_key = f"{quest.id}:{node.id}"
            if self.triggered_nodes.get(trigger_key):
                continue
            
            # Check ALL conditions
            all_conditions_met = True
            
            for cond in node.conditions:
                if cond.type == "affinity":
                    required = cond.params.get("value", 0)
                    if affinity < required:
                        all_conditions_met = False
                        break
                        
                elif cond.type == "time":
                    start = cond.params.get("start", "00:00")
                    end = cond.params.get("end", "23:59")
                    # Handle time range check
                    if not self._is_time_in_range(current_time_str, start, end):
                        all_conditions_met = False
                        break
                        
                elif cond.type == "location":
                    required_loc = cond.params.get("location_id")
                    if required_loc and player_location != required_loc:
                        all_conditions_met = False
                        break
                        
                elif cond.type == "item":
                    item_id = cond.params.get("item_id")
                    action = cond.params.get("action", "show")
                    if action in ["show", "give"] and item_id not in player_items:
                        all_conditions_met = False
                        break
            
            if all_conditions_met:
                logger.info(f"Quest trigger conditions met! Quest: {quest.id}, Node: {node.id}")
                return (quest.id, node.id, node)
        
        return None
    
    def _is_time_in_range(self, current: str, start: str, end: str) -> bool:
        """Check if current time is within start-end range (handles midnight crossing)"""
        try:
            curr = datetime.strptime(current, "%H:%M").time()
            start_t = datetime.strptime(start, "%H:%M").time()
            end_t = datetime.strptime(end, "%H:%M").time()
            
            if start_t <= end_t:
                # Normal range (e.g., 08:00 - 18:00)
                return start_t <= curr <= end_t
            else:
                # Crosses midnight (e.g., 22:00 - 05:00)
                return curr >= start_t or curr <= end_t
        except:
            return True  # Default to True if parsing fails
    
    def get_full_quest_context(self, quest_id: str, node_id: str) -> Optional[Dict]:
        """
        Get complete quest information for LLM prompt injection.
        Includes quest description, node objective, and dialogue_script.
        
        Returns:
            Dict with quest_title, quest_description, node_description, 
            node_type, dialogue_script, investigation_desc, rewards, next_node_hint
        """
        quest = self.active_quests.get(quest_id)
        if not quest:
            # Also check completed/locked quests
            quest = next((q for q in self.quests if q.id == quest_id), None)
        
        if not quest:
            return None
        
        node = next((n for n in quest.nodes if n.id == node_id), None)
        if not node:
            return None
        
        # Build dialogue script text
        dialogue_text = ""
        if node.dialogue_script:
            for line in node.dialogue_script:
                # Handle both DialogueLine Pydantic object and dict formats
                if isinstance(line, dict):
                    speaker = line.get("speaker", "Unknown")
                    text = line.get("text", "")
                    action = line.get("action")
                else:
                    # DialogueLine Pydantic object
                    speaker = line.speaker
                    text = line.text
                    action = line.action
                action_str = f" [Action: {action['type']}]" if action and isinstance(action, dict) and 'type' in action else ""
                dialogue_text += f"{speaker}: {text}{action_str}\n"
        
        # Get next node hint
        next_node_hint = ""
        current_idx = quest.current_node_index
        if current_idx + 1 < len(quest.nodes):
            next_node = quest.nodes[current_idx + 1]
            hints = []
            
            # Location hint
            if next_node.location_id:
                # Try to resolve location name from locations.json
                loc_name = next_node.location_id
                hints.append(f"地点: {loc_name}")
            
            # Time hint
            for cond in next_node.conditions:
                if cond.type == "time":
                    start = cond.params.get("start")
                    end = cond.params.get("end")
                    if start and end:
                        hints.append(f"时间: {start} - {end}")
            
            # Affinity hint
            for cond in next_node.conditions:
                if cond.type == "affinity":
                    val = cond.params.get("value", 0)
                    if val > 0:
                        hints.append(f"需要好感度: Lv.{val}")
            
            if hints:
                next_node_hint = "下一步线索: " + ", ".join(hints)
        
        return {
            "quest_id": quest.id,
            "quest_title": quest.title,
            "quest_type": quest.type,
            "quest_description": quest.description,
            "node_id": node.id,
            "node_type": node.type,
            "node_description": node.description,
            "dialogue_script": dialogue_text,
            "dialogue_script_raw": node.dialogue_script or [],
            "investigation_desc": getattr(node, 'investigation_desc', None),
            "rewards": [r.model_dump() if hasattr(r, 'model_dump') else r for r in (node.rewards or [])],
            "next_node_hint": next_node_hint
        }
    
    def mark_node_triggered(self, quest_id: str, node_id: str):
        """Mark a node as triggered (user saw the chips but may reject)"""
        key = f"{quest_id}:{node_id}"
        self.triggered_nodes[key] = True
        logger.info(f"Marked node as triggered: {key}")
    
    def reset_node_trigger(self, quest_id: str, node_id: str):
        """Reset trigger status (allow re-trigger next time)"""
        key = f"{quest_id}:{node_id}"
        if key in self.triggered_nodes:
            del self.triggered_nodes[key]
            logger.info(f"Reset node trigger: {key}")
    
    def advance_node(self, quest_id: str, node_id: str) -> Dict:
        """
        Complete current node and activate next.
        Returns status info for frontend notification.
        """
        quest = self.active_quests.get(quest_id)
        if not quest:
            return {"success": False, "error": "Quest not found"}
        
        node = quest.current_node
        if not node or node.id != node_id:
            return {"success": False, "error": "Node mismatch"}
        
        # Process rewards first
        rewards_processed = self.process_rewards(quest_id, node_id)
        
        # Mark complete
        node.status = "completed"
        
        # Advance
        quest.current_node_index += 1
        
        result = {
            "success": True,
            "quest_id": quest_id,
            "completed_node_id": node_id,
            "rewards": rewards_processed
        }
        
        # Check if quest completed
        if quest.current_node_index >= len(quest.nodes):
            quest.status = "completed"
            result["quest_completed"] = True
            result["quest_title"] = quest.title
            del self.active_quests[quest_id]
            logger.info(f"Quest completed: {quest.title}")
        else:
            # Activate next node
            next_node = quest.current_node
            if next_node:
                next_node.status = "active"
            result["next_node_id"] = next_node.id if next_node else None
            result["quest_completed"] = False
            logger.info(f"Quest {quest.title} advanced to node {quest.current_node_index}")
        
        self.save_quests()
        return result
    
    def process_rewards(self, quest_id: str, node_id: str) -> List[Dict]:
        """
        Process node rewards (items, affinity).
        Returns list of reward notifications for frontend.
        """
        quest = self.active_quests.get(quest_id)
        if not quest:
            return []
        
        node = next((n for n in quest.nodes if n.id == node_id), None)
        if not node or not node.rewards:
            return []
        
        processed = []
        
        for reward in node.rewards:
            r_type = reward.type
            params = reward.params
            
            if r_type == "item":
                item_id = params.get("item_id")
                action = params.get("action", "receive")
                
                if action == "receive" and item_id:
                    # Update item owner in items.json
                    self._update_item_owner(item_id, "player")
                    item_name = self._get_item_name(item_id)
                    processed.append({
                        "type": "item_receive",
                        "item_id": item_id,
                        "item_name": item_name,
                        "message": f"收到 NPC 赠送的 [{item_name}]"
                    })
                    
            elif r_type == "affinity":
                npc_id = params.get("npc_id")
                delta = params.get("delta", params.get("value", 1))
                
                if npc_id:
                    npc = self.runtime.get_npc(npc_id)
                    if npc:
                        if "player" not in npc.relationships:
                            npc.relationships["player"] = {"affinity": 0}
                        current = npc.relationships["player"].get("affinity", 0)
                        npc.relationships["player"]["affinity"] = current + delta
                        processed.append({
                            "type": "affinity",
                            "npc_id": npc_id,
                            "npc_name": npc.profile.name,
                            "delta": delta,
                            "new_value": current + delta,
                            "message": f"与 {npc.profile.name} 的好感度 +{delta}"
                        })
        
        return processed
    
    def _update_item_owner(self, item_id: str, new_owner: str):
        """Update item ownership in items.json"""
        items_path = os.path.join(settings.DATA_DIR, "worlds", self.runtime.world_id, "items.json")
        if not os.path.exists(items_path):
            return
        
        try:
            with open(items_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            items = data.get("items", data) if isinstance(data, dict) else data
            for item in items:
                if item.get("id") == item_id:
                    item["owner"] = new_owner
                    break
            
            with open(items_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Updated item {item_id} owner to {new_owner}")
        except Exception as e:
            logger.error(f"Failed to update item owner: {e}")
    
    def _get_item_name(self, item_id: str) -> str:
        """Get item name from items.json"""
        # 1. Try Memory Map (Fast & Reliable)
        if hasattr(self.runtime, "item_id_map") and item_id in self.runtime.item_id_map:
            return self.runtime.item_id_map[item_id]

        # 2. Fallback to File (Slow)
        items_path = os.path.join(settings.DATA_DIR, "worlds", self.runtime.world_id, "items.json")
        if not os.path.exists(items_path):
            return item_id
        
        try:
            with open(items_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            items = data.get("items", data) if isinstance(data, dict) else data
            for item in items:
                if item.get("id") == item_id:
                    return item.get("name", item_id)
        except:
            pass
        
        return item_id
