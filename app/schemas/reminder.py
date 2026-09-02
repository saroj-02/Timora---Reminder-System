"""
Timora – Reminder Schemas (Pydantic)
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.models.reminder import (
    ReminderBefore,
    ReminderCategory,
    ReminderPriority,
    ReminderStatus,
    RepeatType,
)
from app.utils.timezone import now_utc


class ReminderCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    category: ReminderCategory = ReminderCategory.PERSONAL
    priority: ReminderPriority = ReminderPriority.MEDIUM
    local_datetime: datetime
    timezone: str = "UTC"
    repeat_type: RepeatType = RepeatType.NEVER
    reminder_before: ReminderBefore = ReminderBefore.AT_TIME

    @model_validator(mode="after")
    def validate_future_time(self) -> "ReminderCreateRequest":
        from app.utils.timezone import local_to_utc
        utc = local_to_utc(self.local_datetime, self.timezone)
        if utc <= now_utc():
            raise ValueError("The selected reminder time has already passed. Please select a future time.")
        return self


class ReminderUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    category: Optional[ReminderCategory] = None
    priority: Optional[ReminderPriority] = None
    local_datetime: Optional[datetime] = None
    timezone: Optional[str] = None
    repeat_type: Optional[RepeatType] = None
    reminder_before: Optional[ReminderBefore] = None


class SnoozeRequest(BaseModel):
    minutes: int = Field(..., ge=1, le=1440)


class RescheduleRequest(BaseModel):
    local_datetime: datetime
    timezone: str = "UTC"

    @model_validator(mode="after")
    def validate_future(self) -> "RescheduleRequest":
        from app.utils.timezone import local_to_utc
        utc = local_to_utc(self.local_datetime, self.timezone)
        if utc <= now_utc():
            raise ValueError("The selected time has already passed. Please select a future time.")
        return self


class ReminderResponse(BaseModel):
    id: str
    user_id: str
    title: str
    description: Optional[str]
    category: str
    priority: str
    scheduled_time_utc: datetime
    local_datetime_str: str
    timezone: str
    repeat_type: str
    reminder_before: str
    status: str
    snooze_until: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]


class ReminderListResponse(BaseModel):
    total: int
    items: list[ReminderResponse]
