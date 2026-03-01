from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class NPCGoal(BaseModel):
    id: str = Field(..., description="目标ID")
    description: str = Field(..., description="目标描述")
    type: str = Field(..., description="类型: main(主线) 或 sub(次要/支线)")
    status: str = Field(default="pending", description="状态: pending, in_progress, completed, failed, abandoned")
    trigger_condition: Optional[str] = Field(None, description="触发条件 (如时间、事件)")

class NPCSkill(BaseModel):
    name: str = Field(..., description="技能名称")
    description: str = Field(..., description="技能描述")
    level: int = Field(default=1, ge=1, le=10, description="技能等级 1-10")

class NPCQuestRole(BaseModel):
    role: str = Field(..., description="角色定位: helper(引路人), blocker(阻碍者), neutral(中立/不知情)")
    clue: str = Field(default="", description="掌握的线索或阻碍手段")
    motivation: str = Field(default="", description="为什么帮助或阻碍玩家")
    attitude: str = Field(default="neutral", description="对玩家任务的态度")

class NPCStaticProfile(BaseModel):
    name: str = Field(..., description="姓名")
    age: int = Field(..., description="年龄")
    gender: str = Field(..., description="性别")
    race: str = Field(default="Human", description="种族")
    avatar_desc: str = Field(..., description="头像/外貌描述，用于生成图片")
    avatar_url: Optional[str] = Field(None, description="NPC立绘图片URL")
    occupation: str = Field(..., description="职业/身份")
    home_location: Optional[str] = Field(None, description="居住地/家")
    work_location: Optional[str] = Field(None, description="工作地点")

class NPCDynamicProfile(BaseModel):
    personality_desc: str = Field(..., description="性格详细描述")
    values: List[str] = Field(default=[], description="价值观/信念")
    mood: str = Field(default="neutral", description="当前情绪")
    current_location: str = Field(..., description="当前所在地")
    current_action: Optional[str] = Field(default=None, description="当前正在进行的行动")

class NPC(BaseModel):
    id: str = Field(..., description="NPC唯一ID")
    profile: NPCStaticProfile
    dynamic: NPCDynamicProfile
    quest_role: Optional[NPCQuestRole] = Field(default=None, description="NPC在玩家任务中的角色")
    goals: List[NPCGoal] = Field(default=[])
    skills: List[NPCSkill] = Field(default=[])
    # 关系矩阵初始化时可能为空，后续通过互动建立
    relationships: Dict[str, Dict] = Field(default={}, description="关系图谱 {npc_id: {affinity: 50, memory: '...'}}")

class GenerateNPCsRequest(BaseModel):
    world_bible: Dict = Field(..., description="世界设定书 (WorldBible)")
    count: int = Field(default=3, ge=1, le=10, description="生成数量 3-10")
    requirements: Optional[str] = Field(default=None, description="用户对NPC生成的额外要求")

class GenerateNPCsResponse(BaseModel):
    npcs: List[NPC]
