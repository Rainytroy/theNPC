from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class WorldBackground(BaseModel):
    era: str = Field(..., description="时代背景，如赛博朋克、中世纪、现代")
    rules: List[str] = Field(default=[], description="世界法则，如高科技低生活、魔法存在")
    society: str = Field(..., description="社会结构")

class GameScene(BaseModel):
    name: str = Field(..., description="场景名称")
    description: str = Field(..., description="场景详细描述")
    key_objects: List[str] = Field(default=[], description="关键物品列表")
    locations: List[str] = Field(default=["Main Area"], description="场景内的具体地点列表 (如: 吧台, 门口, VIP座)")

class TimeConfig(BaseModel):
    start_datetime: str = Field(
        default="2024-01-01 08:00", 
        description="游戏开始时间 (YYYY-MM-DD HH:MM)，由 Agent 根据世界氛围推断"
    )
    display_year: Optional[str] = Field(
        default=None,
        description="纪元标签，如'黑暗纪元5年'、'魔法元年'，None时显示真实年份"
    )
    day_length_real_sec: int = Field(default=3600, description="现实一小时等于游戏一天")

class WorldBible(BaseModel):
    world_id: str = Field(..., description="世界唯一ID")
    title: Optional[str] = Field(default=None, description="世界标题")
    player_objective: Optional[str] = Field(default=None, description="玩家在这个世界的主要目标")
    background: WorldBackground
    scene: GameScene
    time_config: TimeConfig

# API Request/Response Models

class GenesisChatRequest(BaseModel):
    session_id: str = Field(..., description="会话ID")
    content: str = Field(..., description="用户输入内容")
    current_bible: Optional[Dict] = Field(default=None, description="当前的 World Bible (可选)，用于修改设定时提供明确上下文")
    phase: Optional[str] = Field(default="world", description="当前创世阶段 (world | npc | quest)")

class PendingAction(BaseModel):
    type: str = Field(..., description="Action type: add_npc, regenerate_npc, manage_images")
    data: Dict[str, Any] = Field(default={}, description="Action parameters")
    label: str = Field(..., description="Button label")
    style: str = Field(default="primary", description="Button style: primary, secondary, danger")

class GenesisChatResponse(BaseModel):
    response: str = Field(..., description="播种者回复")
    is_ready_to_generate: bool = Field(default=False, description="是否信息充足，可以生成世界")
    suggested_world_setting: Optional[Dict] = Field(default=None, description="推测的世界设定草稿")
    is_ready_for_npc: bool = Field(default=False, description="是否准备好生成NPC")
    npc_requirements: Optional[str] = Field(default=None, description="NPC生成要求")
    npc_count: Optional[int] = Field(default=3, description="NPC生成数量")
    is_ready_for_quest: bool = Field(default=False, description="是否准备好生成任务")
    quest_requirements: Optional[str] = Field(default=None, description="任务生成要求")
    quest_count: Optional[int] = Field(default=None, description="任务数量")
    pending_actions: Optional[List[PendingAction]] = Field(default=None, description="待确认的操作提案")

class GenerateWorldRequest(BaseModel):
    session_id: str
    world_setting: Optional[dict] = None # Optional override
    chat_history: Optional[List[Dict]] = None # Save chat history

class GenerateWorldResponse(BaseModel):
    status: str
    world_bible: WorldBible
    is_locked: bool = False

class GenerateQuestsRequest(BaseModel):
    world_bible: Dict = Field(..., description="World Bible Data")
    npcs: List[Dict] = Field(..., description="List of NPCs")

class GenerateQuestsResponse(BaseModel):
    quests: List[Dict] = Field(..., description="Generated Quests")
    items: List[Dict] = Field(default=[], description="Updated Items")
    locations: List[Dict] = Field(default=[], description="Updated Locations")

class GenerateMainQuestRequest(BaseModel):
    world_bible: Dict = Field(..., description="World Bible Data")
    npcs: List[Dict] = Field(..., description="List of NPCs (for context)")
    skip_enrichment: bool = Field(default=False, description="Skip asset reset and enrichment (if done previously)")
    requirements: Optional[str] = Field(default=None, description="User's Main Quest Requirements")

class EnrichAssetsRequest(BaseModel):
    world_bible: Dict = Field(..., description="World Bible Data")

class EnrichAssetsResponse(BaseModel):
    items: List[Dict] = Field(default=[], description="Optimized Items")
    locations: List[Dict] = Field(default=[], description="Optimized Locations")

class GenerateSideQuestRequest(BaseModel):
    target_npc: Dict = Field(..., description="Target NPC")
    world_bible: Dict = Field(..., description="World Bible Data")

class WorldCreationStatus(BaseModel):
    world_setting_finalized: bool = Field(default=False, description="世界设定是否定稿")
    npc_setting_finalized: bool = Field(default=False, description="NPC设定是否定稿")
    quest_setting_finalized: bool = Field(default=False, description="任务蓝图是否定稿")
    ready_to_start: bool = Field(default=False, description="是否可以启动世界")
    current_phase: str = Field(..., description="当前所处阶段 (World Bible | NPC | Quest | Launch | Ready)")
    message: str = Field(..., description="给用户的指导建议信息")
    details: Dict = Field(default={}, description="详细统计信息 (npc_count, avatar_count, quest_count)")
    progress: Dict[str, Dict] = Field(default={}, description="各阶段详细进度")

class WorldStatusFile(BaseModel):
    # 核心状态
    current_phase: str = Field(default="world", description="当前聚焦的阶段 (world, npc, quest, launch, ready)")
    
    # 额外选项
    options: Dict[str, Any] = Field(
        default={
            "is_illustrated": False, # 是否开启立绘
            "language_style": "normal", # 语言风格
        },
        description="世界生成的额外选项"
    )

    # 详细进度
    progress: Dict[str, Dict] = Field(
        default={
            "world_bible": { "status": "pending", "updated_at": None },  # pending, finalizing, completed
            "npc_roster": { "status": "pending", "count": 0, "updated_at": None }, # pending, drafting, finalizing, completed
            "quest_blueprint": { "status": "pending", "count": 0, "updated_at": None },
            "launch": { "status": "pending", "count": 0, "updated_at": None }, # pending, processing, completed
            # Launch phase sub-tasks
            "intro": { "status": "pending", "content": None, "message": None, "updated_at": None },
            "quest_enrich": { "status": "pending", "message": None, "updated_at": None },
            "schedule": { "status": "pending", "current": 0, "total": 0, "message": None, "updated_at": None }
        },
        description="各阶段详细进度"
    )
    
    # 上下文记忆
    phase_summaries: Dict[str, str] = Field(
        default={},
        description="各阶段的文本摘要 (world_summary, npc_summary, quest_summary)"
    )
    last_user_intent: str = Field(default="", description="用户最近的意图")
    active_task: str = Field(default="", description="当前 Agent 的具体任务")
    last_updated: str = Field(default="", description="最后更新时间")
