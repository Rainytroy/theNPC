from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any

class QuestCondition(BaseModel):
    """任务节点的完成条件"""
    type: Literal["affinity", "item", "location", "time", "state", "dialogue"]
    operator: Literal["AND", "OR"] = "AND"
    params: Dict[str, Any] = Field(default_factory=dict, description="条件参数 (例如 {'item_id': 'xxx', 'count': 1})")

class QuestReward(BaseModel):
    """任务奖励"""
    type: Literal["item", "affinity", "exp", "gold", "unlock"]
    params: Dict[str, Any] = Field(default_factory=dict, description="奖励参数 (例如 {'item_id': 'xxx', 'action': 'receive'})")

class DialogueLine(BaseModel):
    """对话脚本中的单行对话"""
    speaker: str = Field(..., description="说话者名称 (NPC名 或 'Player')")
    text: str = Field(..., description="对话内容")
    action: Optional[Dict[str, Any]] = Field(None, description="对话动作 (例如 {'type': 'show_item', 'item_id': 'xxx'})")

class QuestNode(BaseModel):
    id: str = Field(..., description="Unique ID for this node (e.g. q1_n1)")
    type: Literal["dialogue", "collect", "investigate", "wait", "choice"] = Field("dialogue", description="Node type")
    description: str = Field(..., description="What the player needs to do or find out")
    
    conditions: List[QuestCondition] = Field(default=[], description="List of conditions to complete this node")
    
    # Optional target for dialogue/investigate
    target_npc_id: Optional[str] = Field(None, description="The NPC the player must interact with")
    location_id: Optional[str] = Field(None, description="Location where this node takes place")
    
    # Legacy field for backward compatibility
    required_affinity: int = Field(default=0, description="Minimum affinity required (Backward Compatibility)")
    
    # Status: locked = pending (new term), active, completed, failed
    status: Literal["locked", "pending", "active", "completed", "failed"] = "locked"
    
    # Rewards - NOW A LIST!
    rewards: List[QuestReward] = Field(default=[], description="List of rewards upon completion")
    
    # Dialogue content
    dialogue_script: Optional[List[DialogueLine]] = Field(None, description="Pre-scripted dialogue for this node")
    
    # Investigation content
    investigation_desc: Optional[str] = Field(None, description="Narrative description for investigate nodes")
    
    # Other optional fields
    completion_hint: Optional[str] = None

class Quest(BaseModel):
    id: str = Field(..., description="Unique Quest ID")
    title: str = Field(..., description="Quest Title")
    type: Literal["main", "side"] = "side"
    description: str = Field(..., description="Overall story summary")
    nodes: List[QuestNode] = []
    
    # Optional: target NPC for the entire quest (for side quests)
    target_npc_id: Optional[str] = Field(None, description="Primary NPC for this quest line")
    
    # New: Support for non-linear quests
    active_nodes: List[str] = Field(default=[], description="List of currently active node IDs")
    
    # Legacy: Linear support
    current_node_index: int = 0
    
    status: Literal["active", "completed", "failed"] = "active"

    @property
    def current_node(self) -> Optional[QuestNode]:
        """Legacy property for linear engine"""
        if 0 <= self.current_node_index < len(self.nodes):
            return self.nodes[self.current_node_index]
        return None
