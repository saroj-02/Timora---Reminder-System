"""
Timora – Reminder Model

Beanie/MongoDB document model and reminder enums.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from beanie import Document
from pydantic import Field


class ReminderCategory(str, Enum):
    PERSONAL = "personal"
    WORK = "work"
    STUDY = "study"
    HEALTH = "health"
    FINANCE = "finance"
    OTHER = "other"


class ReminderPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReminderStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    SNOOZED = "snoozed"
    FAILED = "failed"


class RepeatType(str, Enum):
    NEVER = "never"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class ReminderBefore(str, Enum):
    AT_TIME = "at_time"
    FIVE_MINUTES = "5_minutes"
    TEN_MINUTES = "10_minutes"
    FIFTEEN_MINUTES = "15_minutes"
    THIRTY_MINUTES = "30_minutes"
    ONE_HOUR = "1_hour"
    ONE_DAY = "1_day"


REMINDER_BEFORE_MINUTES: dict[
    ReminderBefore,
    int,
] = {

    ReminderBefore.AT_TIME: 0,

    ReminderBefore.FIVE_MINUTES: 5,

    ReminderBefore.TEN_MINUTES: 10,

    ReminderBefore.FIFTEEN_MINUTES: 15,

    ReminderBefore.THIRTY_MINUTES: 30,

    ReminderBefore.ONE_HOUR: 60,

    ReminderBefore.ONE_DAY: 1440,
}


class Reminder(Document):

    user_id: str

    title: str

    description: Optional[str] = None

    category: ReminderCategory = (
        ReminderCategory.PERSONAL
    )

    priority: ReminderPriority = (
        ReminderPriority.MEDIUM
    )

    # Always stored internally as UTC.
    scheduled_time_utc: datetime

    # IANA timezone.
    timezone: str = "UTC"

    repeat_type: RepeatType = (
        RepeatType.NEVER
    )

    reminder_before: ReminderBefore = (
        ReminderBefore.AT_TIME
    )

    status: ReminderStatus = (
        ReminderStatus.PENDING
    )

    snooze_until: Optional[datetime] = None

    # IMPORTANT:
    # Used by scheduler to record successful processing.
    notification_sent_at: Optional[datetime] = None

    completed_at: Optional[datetime] = None

    created_at: datetime = Field(
        default_factory=lambda:
        datetime.now(timezone.utc)
    )

    updated_at: datetime = Field(
        default_factory=lambda:
        datetime.now(timezone.utc)
    )

    class Settings:

        name = "reminders"

        indexes = [
            "user_id",
            "scheduled_time_utc",
            "status",
            "category",
            "priority",
        ]

    def update_timestamp(self) -> None:

        self.updated_at = (
            datetime.now(timezone.utc)
        )