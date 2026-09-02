"""
Timora – User Schemas (Pydantic)
"""
from typing import Optional

from pydantic import BaseModel, Field


class UserUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    country: Optional[str] = None
    timezone: Optional[str] = None
    notification_enabled: Optional[bool] = None
    theme: Optional[str] = None
    sound_enabled: Optional[bool] = None
    sound_volume: Optional[float] = Field(None, ge=0.0, le=1.0)
