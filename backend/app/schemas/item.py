from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class ItemObtainMethod(BaseModel):
    """物品获取方式"""
    method: Literal["dialogue", "investigate", "quest_reward", "trade", "find", "initial"]
    source: str = Field(..., description="NPC ID 或 地点名称")
    condition: Optional[str] = Field(None, description="前置条件描述")

class Item(BaseModel):
    id: str = Field(..., description="物品唯一ID (例如: item_key_01)")
    name: str = Field(..., description="物品名称")
    description: str = Field(..., description="物品描述")
    type: Literal["key", "clue", "tool", "consumable", "generic"] = Field("generic", description="物品类型")
    rarity: Literal["common", "rare", "epic", "legendary"] = Field("common", description="稀有度")
    obtain_methods: List[ItemObtainMethod] = Field(default=[], description="获取方式列表")
    usage: Optional[str] = Field(None, description="用途说明")
    stackable: bool = Field(True, description="是否可堆叠")
    icon: Optional[str] = Field(None, description="图标标识")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "item_rusty_key",
                "name": "锈迹斑斑的钥匙",
                "description": "一把古老的铁钥匙，看起来能打开某个旧箱子。",
                "type": "key",
                "obtain_methods": [
                    {"method": "investigate", "source": "后花园"}
                ]
            }
        }
