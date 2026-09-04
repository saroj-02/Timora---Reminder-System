"""
Timora – Reminder Service

Core business logic:
- Reminder CRUD
- Timezone conversion
- Scheduler integration
- Snooze/reschedule handling
- Recurring reminder calculations
- API response formatting
"""

from __future__ import annotations

import calendar
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional, cast
from zoneinfo import ZoneInfo

from beanie.operators import In
from bson import ObjectId

from app.models.reminder import (
    Reminder,
    ReminderBefore,
    ReminderCategory,
    ReminderPriority,
    ReminderStatus,
    RepeatType,
)
from app.models.user import User
from app.schemas.reminder import (
    ReminderCreateRequest,
    ReminderResponse,
    ReminderUpdateRequest,
)
from app.utils.timezone import (
    format_local,
    local_to_utc,
    now_utc,
)


logger = logging.getLogger(__name__)


# =============================================================================
# Create
# =============================================================================

async def create_reminder(
    user: User,
    body: ReminderCreateRequest,
) -> Reminder:
    """
    Create a reminder in MongoDB and immediately register its scheduler job.
    """

    utc_time = local_to_utc(
        body.local_datetime,
        body.timezone,
    )

    if utc_time <= now_utc():
        raise ValueError(
            "The selected time has already passed."
        )

    logger.info(
        "CREATE REMINDER REQUEST | "
        "user=%s | title=%s | timezone=%s | "
        "local_datetime=%s | utc_time=%s",
        user.id,
        body.title,
        body.timezone,
        body.local_datetime,
        utc_time.isoformat(),
    )

    reminder = Reminder(
        user_id=str(user.id),
        title=body.title,
        description=body.description,
        category=body.category,
        priority=body.priority,
        scheduled_time_utc=utc_time,
        timezone=body.timezone,
        repeat_type=body.repeat_type,
        reminder_before=body.reminder_before,
        status=ReminderStatus.PENDING,
    )

    await reminder.insert()

    logger.info(
        "REMINDER STORED IN MONGODB | "
        "reminder=%s | user=%s | scheduled_utc=%s",
        reminder.id,
        user.id,
        utc_time.isoformat(),
    )

    # Local import prevents circular import because scheduler_service
    # imports compute_next_occurrence from this module.
    from app.services.scheduler_service import schedule_reminder

    scheduled = schedule_reminder(
        reminder,
        utc_time,
    )

    logger.info(
        "REMINDER SCHEDULER RESULT | "
        "reminder=%s | scheduled=%s",
        reminder.id,
        scheduled,
    )

    if not scheduled:
        logger.error(
            "REMINDER CREATED BUT NOT SCHEDULED | "
            "reminder=%s",
            reminder.id,
        )

    return reminder


# =============================================================================
# Get
# =============================================================================

async def get_reminder(
    reminder_id: str,
    user_id: str,
) -> Optional[Reminder]:
    """
    Fetch a reminder belonging to the requesting user.
    """

    try:
        oid = ObjectId(reminder_id)
    except Exception:
        return None

    return await Reminder.find_one(
        Reminder.id == oid,
        Reminder.user_id == user_id,
    )


# =============================================================================
# List
# =============================================================================

async def list_reminders(
    user_id: str,
    status_filter: Optional[list[str]] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Literal[
        "nearest",
        "newest",
        "oldest",
        "priority",
    ] = "nearest",
    limit: int = 100,
    skip: int = 0,
) -> tuple[int, list[Reminder]]:
    """
    List reminders for a user.
    """

    conditions: list[Any] = [
        Reminder.user_id == user_id
    ]

    if status_filter:
        conditions.append(
            In(
                Reminder.status,
                list(status_filter),
            )
        )

    if category:
        conditions.append(
            Reminder.category == category
        )

    if priority:
        conditions.append(
            Reminder.priority == priority
        )

    query = Reminder.find(
        *conditions
    )

    if search:
        query = Reminder.find(
            *conditions,
            {
                "$or": [
                    {
                        "title": {
                            "$regex": search,
                            "$options": "i",
                        }
                    },
                    {
                        "description": {
                            "$regex": search,
                            "$options": "i",
                        }
                    },
                ]
            },
        )

    total = await query.count()

    sort_map = {
        "nearest": [
            ("scheduled_time_utc", 1)
        ],
        "newest": [
            ("created_at", -1)
        ],
        "oldest": [
            ("created_at", 1)
        ],
        "priority": [
            ("priority", -1),
            ("scheduled_time_utc", 1),
        ],
    }

    sort_fields = sort_map.get(
        sort_by,
        [
            ("scheduled_time_utc", 1)
        ],
    )

    query = (
        query
        .sort(cast(Any, sort_fields))
        .skip(skip)
        .limit(limit)
    )

    items = await query.to_list()

    return total, items


# =============================================================================
# Update
# =============================================================================

async def update_reminder(
    reminder: Reminder,
    body: ReminderUpdateRequest,
) -> Reminder:
    """
    Update a reminder and re-register its scheduler job.
    """

    reminder_id = str(reminder.id)

    from app.services.scheduler_service import (
        remove_reminder_job,
        schedule_reminder,
    )

    # Remove old job first.
    remove_reminder_job(
        reminder_id
    )

    if body.title is not None:
        reminder.title = body.title

    if body.description is not None:
        reminder.description = body.description

    if body.category is not None:
        reminder.category = body.category

    if body.priority is not None:
        reminder.priority = body.priority

    if body.repeat_type is not None:
        reminder.repeat_type = body.repeat_type

    if body.reminder_before is not None:
        reminder.reminder_before = body.reminder_before

    # -------------------------------------------------------------------------
    # Date/time changed
    # -------------------------------------------------------------------------

    if body.local_datetime is not None:
        tz = (
            body.timezone
            or reminder.timezone
            or "UTC"
        )

        utc_time = local_to_utc(
            body.local_datetime,
            tz,
        )

        if utc_time <= now_utc():
            raise ValueError(
                "The selected time has already passed."
            )

        reminder.scheduled_time_utc = utc_time
        reminder.timezone = tz

    elif body.timezone is not None:
        reminder.timezone = body.timezone

    # -------------------------------------------------------------------------
    # Re-arm
    # -------------------------------------------------------------------------

    reminder.status = ReminderStatus.PENDING
    reminder.snooze_until = None
    reminder.notification_sent_at = None
    reminder.completed_at = None

    reminder.update_timestamp()

    await reminder.save()

    logger.info(
        "REMINDER UPDATED IN MONGODB | "
        "reminder=%s | scheduled=%s",
        reminder.id,
        reminder.scheduled_time_utc.isoformat(),
    )

    scheduled = schedule_reminder(
        reminder,
        reminder.scheduled_time_utc,
    )

    logger.info(
        "REMINDER UPDATE SCHEDULER RESULT | "
        "reminder=%s | scheduled=%s",
        reminder.id,
        scheduled,
    )

    if not scheduled:
        logger.error(
            "REMINDER UPDATED BUT NOT SCHEDULED | "
            "reminder=%s",
            reminder.id,
        )

    return reminder


# =============================================================================
# Delete
# =============================================================================

async def delete_reminder(
    reminder: Reminder,
) -> None:
    """
    Delete a reminder and remove its scheduled jobs.
    """

    reminder_id = str(
        reminder.id
    )

    from app.services.scheduler_service import (
        remove_reminder_job,
        remove_retry_job,
    )

    remove_reminder_job(
        reminder_id
    )

    remove_retry_job(
        reminder_id
    )

    await reminder.delete()

    logger.info(
        "REMINDER DELETED | reminder=%s",
        reminder_id,
    )


# =============================================================================
# Complete
# =============================================================================

async def complete_reminder(
    reminder: Reminder,
) -> Reminder:
    """
    Mark reminder completed.

    IMPORTANT:
    Completing a reminder MUST NOT cancel its scheduled email.

    The scheduler job remains active. The scheduler is allowed to process
    COMPLETED reminders as long as notification_sent_at is still None.
    """

    reminder.status = ReminderStatus.COMPLETED

    reminder.completed_at = now_utc()

    reminder.update_timestamp()

    await reminder.save()

    logger.info(
        "REMINDER COMPLETED | "
        "reminder=%s | email_job_preserved=true",
        reminder.id,
    )

    return reminder


# =============================================================================
# Snooze
# =============================================================================

async def snooze_reminder(
    reminder: Reminder,
    minutes: int,
) -> Reminder:
    """
    Snooze a reminder and schedule it for the snooze time.
    """

    if minutes <= 0:
        raise ValueError(
            "Snooze duration must be greater than zero."
        )

    reminder_id = str(
        reminder.id
    )

    from app.services.scheduler_service import (
        remove_reminder_job,
        schedule_reminder,
    )

    remove_reminder_job(
        reminder_id
    )

    snooze_until = (
        now_utc()
        + timedelta(minutes=minutes)
    )

    reminder.snooze_until = snooze_until
    reminder.status = ReminderStatus.SNOOZED
    reminder.notification_sent_at = None

    reminder.update_timestamp()

    await reminder.save()

    scheduled = schedule_reminder(
        reminder,
        snooze_until,
    )

    logger.info(
        "REMINDER SNOOZED | "
        "reminder=%s | minutes=%s | until=%s | scheduled=%s",
        reminder.id,
        minutes,
        snooze_until.isoformat(),
        scheduled,
    )

    if not scheduled:
        logger.error(
            "REMINDER SNOOZED BUT NOT SCHEDULED | "
            "reminder=%s",
            reminder.id,
        )

    return reminder


# =============================================================================
# Reschedule
# =============================================================================

async def reschedule_reminder(
    reminder: Reminder,
    utc_time: datetime,
) -> Reminder:
    """
    Reschedule an existing reminder.
    """

    if utc_time.tzinfo is None:
        utc_time = utc_time.replace(
            tzinfo=timezone.utc
        )

    utc_time = utc_time.astimezone(
        timezone.utc
    )

    if utc_time <= now_utc():
        raise ValueError(
            "The selected time has already passed."
        )

    reminder_id = str(
        reminder.id
    )

    from app.services.scheduler_service import (
        remove_reminder_job,
        schedule_reminder,
    )

    remove_reminder_job(
        reminder_id
    )

    reminder.scheduled_time_utc = utc_time
    reminder.status = ReminderStatus.PENDING
    reminder.snooze_until = None
    reminder.notification_sent_at = None
    reminder.completed_at = None

    reminder.update_timestamp()

    await reminder.save()

    scheduled = schedule_reminder(
        reminder,
        utc_time,
    )

    logger.info(
        "REMINDER RESCHEDULED | "
        "reminder=%s | utc=%s | scheduled=%s",
        reminder.id,
        utc_time.isoformat(),
        scheduled,
    )

    if not scheduled:
        logger.error(
            "REMINDER RESCHEDULED BUT NOT SCHEDULED | "
            "reminder=%s",
            reminder.id,
        )

    return reminder


# =============================================================================
# Recurring Logic
# =============================================================================

def compute_next_occurrence(
    reminder: Reminder,
) -> Optional[datetime]:
    """
    Calculate next UTC occurrence for recurring reminders.
    """

    if reminder.repeat_type == RepeatType.NEVER:
        return None

    try:
        reminder_timezone = ZoneInfo(
            reminder.timezone or "UTC"
        )
    except Exception:
        logger.warning(
            "Invalid timezone, using UTC | "
            "reminder=%s | timezone=%s",
            reminder.id,
            reminder.timezone,
        )

        reminder_timezone = ZoneInfo(
            "UTC"
        )

    base_local = (
        reminder.scheduled_time_utc
        .astimezone(reminder_timezone)
    )

    now_local = (
        now_utc()
        .astimezone(reminder_timezone)
    )

    # -------------------------------------------------------------------------
    # Daily
    # -------------------------------------------------------------------------

    if reminder.repeat_type == RepeatType.DAILY:
        next_local = (
            base_local
            + timedelta(days=1)
        )

        while next_local <= now_local:
            next_local += timedelta(days=1)

    # -------------------------------------------------------------------------
    # Weekdays
    # -------------------------------------------------------------------------

    elif (
        hasattr(RepeatType, "WEEKDAYS")
        and reminder.repeat_type
        == RepeatType.WEEKDAYS
    ):
        next_local = (
            base_local
            + timedelta(days=1)
        )

        while (
            next_local <= now_local
            or next_local.weekday() >= 5
        ):
            next_local += timedelta(days=1)

    # -------------------------------------------------------------------------
    # Weekly
    # -------------------------------------------------------------------------

    elif reminder.repeat_type == RepeatType.WEEKLY:
        next_local = (
            base_local
            + timedelta(weeks=1)
        )

        while next_local <= now_local:
            next_local += timedelta(weeks=1)

    # -------------------------------------------------------------------------
    # Monthly
    # -------------------------------------------------------------------------

    elif reminder.repeat_type == RepeatType.MONTHLY:
        next_year = base_local.year
        next_month = base_local.month + 1

        if next_month > 12:
            next_month = 1
            next_year += 1

        day = min(
            base_local.day,
            calendar.monthrange(
                next_year,
                next_month,
            )[1],
        )

        next_local = base_local.replace(
            year=next_year,
            month=next_month,
            day=day,
        )

        while next_local <= now_local:
            next_month += 1

            if next_month > 12:
                next_month = 1
                next_year += 1

            day = min(
                base_local.day,
                calendar.monthrange(
                    next_year,
                    next_month,
                )[1],
            )

            next_local = next_local.replace(
                year=next_year,
                month=next_month,
                day=day,
            )

    # -------------------------------------------------------------------------
    # Yearly
    # -------------------------------------------------------------------------

    elif reminder.repeat_type == RepeatType.YEARLY:
        next_year = base_local.year + 1

        try:
            next_local = base_local.replace(
                year=next_year
            )
        except ValueError:
            next_local = base_local.replace(
                year=next_year,
                month=2,
                day=28,
            )

        while next_local <= now_local:
            next_year += 1

            try:
                next_local = next_local.replace(
                    year=next_year
                )
            except ValueError:
                next_local = next_local.replace(
                    year=next_year,
                    month=2,
                    day=28,
                )

    else:
        return None

    return (
        next_local
        .astimezone(timezone.utc)
        .replace(tzinfo=timezone.utc)
    )


# =============================================================================
# Response Formatter
# =============================================================================

def to_response(
    reminder: Reminder,
    user_tz: Optional[str] = None,
) -> ReminderResponse:
    """
    Convert Reminder document into API response.
    """

    tz = (
        user_tz
        or reminder.timezone
        or "UTC"
    )

    local_str = format_local(
        reminder.scheduled_time_utc,
        tz,
    )

    return ReminderResponse(
        id=str(reminder.id),
        user_id=reminder.user_id,
        title=reminder.title,
        description=reminder.description,
        category=(
            reminder.category.value
            if hasattr(
                reminder.category,
                "value",
            )
            else reminder.category
        ),
        priority=(
            reminder.priority.value
            if hasattr(
                reminder.priority,
                "value",
            )
            else reminder.priority
        ),
        scheduled_time_utc=reminder.scheduled_time_utc,
        local_datetime_str=local_str,
        timezone=reminder.timezone,
        repeat_type=(
            reminder.repeat_type.value
            if hasattr(
                reminder.repeat_type,
                "value",
            )
            else reminder.repeat_type
        ),
        reminder_before=(
            reminder.reminder_before.value
            if hasattr(
                reminder.reminder_before,
                "value",
            )
            else reminder.reminder_before
        ),
        status=(
            reminder.status.value
            if hasattr(
                reminder.status,
                "value",
            )
            else reminder.status
        ),
        snooze_until=reminder.snooze_until,
        created_at=reminder.created_at,
        updated_at=reminder.updated_at,
        completed_at=reminder.completed_at,
    )