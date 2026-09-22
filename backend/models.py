from pydantic import BaseModel, Field
from typing import Optional

class Prediction(BaseModel):
    home_probability: float = Field(ge=0, le=1)
    draw_probability: float = Field(ge=0, le=1)
    away_probability: float = Field(ge=0, le=1)
    confidence: str
    edge_home: Optional[float] = None
    edge_draw: Optional[float] = None
    edge_away: Optional[float] = None
    reasons: list[str] = []
