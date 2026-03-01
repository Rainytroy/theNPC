from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class WorldMeta(BaseModel):
    world_id: str
    title: Optional[str] = Field(None, description="自定义世界标题")
    name: str = Field(..., description="核心场景名称 (fallback)")
    era: str = Field(..., description="时代背景")
    created_at: datetime = Field(default_factory=datetime.now)
    npc_count: int = Field(default=0)
    preview: str = Field(default="", description="简短描述")

class WorldListResponse(BaseModel):
    worlds: List[WorldMeta]

class WorldConfig(BaseModel):
    is_illustrated: bool = False
    enable_advanced_tasks: bool = False
    image_style: Optional[str] = None
    manga_page_size: int = 10
    world_confirmed: bool = False
    roster_confirmed: bool = False
    quest_confirmed: bool = False

class LoadWorldResponse(BaseModel):
    status: str
    world_bible: Dict[str, Any]
    npcs: List[Dict[str, Any]]
    items: List[Dict[str, Any]] = []
    locations: List[Dict[str, Any]] = []
    time_config: Optional[Dict[str, Any]] = None
    quests: List[Dict[str, Any]] = []
    chat_history: List[Dict[str, Any]]
    schedules: Dict[str, List[Dict[str, Any]]] = {}
    is_locked: bool = False
    config: WorldConfig = Field(default_factory=WorldConfig)

class WorldConfigUpdate(BaseModel):
    config: WorldConfig
