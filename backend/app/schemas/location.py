from pydantic import BaseModel, Field
from typing import Optional, List

class Location(BaseModel):
    id: str = Field(..., description="Unique Location ID (e.g. loc_inn_01)")
    name: str = Field(..., description="Display Name")
    description: str = Field(..., description="Description of the location")
    type: str = Field(default="generic", description="Type of location (building, area, room)")
    parent_id: Optional[str] = Field(None, description="Parent location ID if nested")
