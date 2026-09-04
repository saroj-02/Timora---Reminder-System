"""
Timora – Reminder Schemas (Pydantic)
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.reminder import (
    ReminderBefore,
    ReminderCategory,
    ReminderPriority,
    ReminderStatus,
    RepeatType,
)
from app.utils.timezone import now_utc

def _parse_category(value: object) -> ReminderCategory:
    if isinstance(value, ReminderCategory):
        return value
    val = str(value or "").strip().lower()
    cat_map = {
        "personal": ReminderCategory.PERSONAL,
        "work": ReminderCategory.WORK,
        "study": ReminderCategory.STUDY,
        "health": ReminderCategory.HEALTH,
        "finance": ReminderCategory.FINANCE,
        "other": ReminderCategory.OTHER,
    }
    return cat_map.get(val, ReminderCategory.OTHER)


def _parse_priority(value: object) -> ReminderPriority:
    if isinstance(value, ReminderPriority):
        return value
    val = str(value or "").strip().lower()
    prio_map = {
        "low": ReminderPriority.LOW,
        "medium": ReminderPriority.MEDIUM,
        "high": ReminderPriority.HIGH,
    }
    return prio_map.get(val, ReminderPriority.MEDIUM)


def _parse_repeat_type(value: object) -> RepeatType:
    if isinstance(value, RepeatType):
        return value
    val = str(value or "").strip().lower()
    rep_map = {
        "never": RepeatType.NEVER,
        "daily": RepeatType.DAILY,
        "weekdays": RepeatType.WEEKDAYS,
        "weekly": RepeatType.WEEKLY,
        "monthly": RepeatType.MONTHLY,
        "yearly": RepeatType.YEARLY,
    }
    return rep_map.get(val, RepeatType.NEVER)


def _parse_reminder_before(value: object) -> ReminderBefore:
    if isinstance(value, ReminderBefore):
        return value
    val = str(value or "").strip().lower()
    before_map = {
        "at_time": ReminderBefore.AT_TIME,
        "at scheduled time": ReminderBefore.AT_TIME,
        "5_minutes": ReminderBefore.FIVE_MINUTES,
        "5 minutes before": ReminderBefore.FIVE_MINUTES,
        "10_minutes": ReminderBefore.TEN_MINUTES,
        "10 minutes before": ReminderBefore.TEN_MINUTES,
        "15_minutes": ReminderBefore.FIFTEEN_MINUTES,
        "15 minutes before": ReminderBefore.FIFTEEN_MINUTES,
        "30_minutes": ReminderBefore.THIRTY_MINUTES,
        "30 minutes before": ReminderBefore.THIRTY_MINUTES,
        "1_hour": ReminderBefore.ONE_HOUR,
        "1 hour before": ReminderBefore.ONE_HOUR,
        "1_day": ReminderBefore.ONE_DAY,
        "1 day before": ReminderBefore.ONE_DAY,
    }
    return before_map.get(val, ReminderBefore.AT_TIME)


class ReminderCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    category: ReminderCategory = ReminderCategory.PERSONAL
    priority: ReminderPriority = ReminderPriority.MEDIUM
    local_datetime: datetime
    timezone: str = "UTC"
    repeat_type: RepeatType = RepeatType.NEVER
    reminder_before: ReminderBefore = ReminderBefore.AT_TIME

    @field_validator("category", mode="before")
    @classmethod
    def validate_category(cls, v: object) -> ReminderCategory:
        return _parse_category(v)

    @field_validator("priority", mode="before")
    @classmethod
    def validate_priority(cls, v: object) -> ReminderPriority:
        return _parse_priority(v)

    @field_validator("repeat_type", mode="before")
    @classmethod
    def validate_repeat_type(cls, v: object) -> RepeatType:
        return _parse_repeat_type(v)

    @field_validator("reminder_before", mode="before")
    @classmethod
    def validate_reminder_before(cls, v: object) -> ReminderBefore:
        return _parse_reminder_before(v)

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

    @field_validator("category", mode="before")
    @classmethod
    def validate_category(cls, v: object) -> Optional[ReminderCategory]:
        return _parse_category(v) if v is not None else None

    @field_validator("priority", mode="before")
    @classmethod
    def validate_priority(cls, v: object) -> Optional[ReminderPriority]:
        return _parse_priority(v) if v is not None else None

    @field_validator("repeat_type", mode="before")
    @classmethod
    def validate_repeat_type(cls, v: object) -> Optional[RepeatType]:
        return _parse_repeat_type(v) if v is not None else None

    @field_validator("reminder_before", mode="before")
    @classmethod
    def validate_reminder_before(cls, v: object) -> Optional[ReminderBefore]:
        return _parse_reminder_before(v) if v is not None else None


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
