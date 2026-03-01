from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class TimeChronology(BaseModel):
    display_rule: str = Field(..., description="Format rule e.g. 'Year {year}'")
    current_year: int = Field(default=1, description="Current year in the chronology")

class TimeConfig(BaseModel):
    start_datetime: str = Field(..., description="ISO format start time e.g. 1515-03-15 08:00")
    time_scale: float = Field(default=60.0, description="Real seconds per game second")
    chronology: Optional[TimeChronology] = None
    display_year: Optional[str] = Field(None, description="Legacy display string")
