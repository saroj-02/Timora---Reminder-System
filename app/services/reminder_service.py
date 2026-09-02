"""
Timora – Reminder Service
Core business logic: CRUD, timezone conversion, recurring logic.
"""

from __future__ import annotations

import calendar
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

from beanie.operators import In
from bson import ObjectId

from app.models.reminder import (
    Reminder,
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


# ── CRUD ─────────────────────────────────────────────────────────────────────


async def create_reminder(
    user: User,
    body: ReminderCreateRequest,
) -> Reminder:
    utc_time = local_to_utc(
        body.local_datetime,
        body.timezone,
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
        "Created reminder %s for user %s",
        reminder.id,
        user.id,
    )

    return reminder


async def get_reminder(
    reminder_id: str,
    user_id: str,
) -> Optional[Reminder]:
    """Fetch a reminder, ensuring it belongs to the requesting user."""

    try:
        oid = ObjectId(reminder_id)
    except Exception:
        return None

    return await Reminder.find_one(
        Reminder.id == oid,
        Reminder.user_id == user_id,
    )


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

    # -------------------------------------------------------------------------
    # Base query conditions
    # -------------------------------------------------------------------------

    # Beanie query expressions can be bool-like expressions or mappings.
    # Using Any prevents Pylance from incorrectly narrowing this list
    # to list[bool] after the first condition.
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

    # -------------------------------------------------------------------------
    # Query
    # -------------------------------------------------------------------------

    query = Reminder.find(
        *conditions
    )

    if search:
        # Simple case-insensitive text search
        # on title / description.
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

    # -------------------------------------------------------------------------
    # Sorting
    # -------------------------------------------------------------------------

    # Use Beanie's string-based sort syntax.
    #
    # "field"  = ascending
    # "-field" = descending
    #
    # This avoids the SortDirection typing issue caused by raw 1 / -1 ints.

    if sort_by == "nearest":
        query = query.sort(
            "scheduled_time_utc"
        )

    elif sort_by == "newest":
        query = query.sort(
            "-created_at"
        )

    elif sort_by == "oldest":
        query = query.sort(
            "created_at"
        )

    elif sort_by == "priority":
        query = query.sort(
            "-priority",
            "scheduled_time_utc",
        )

    else:
        query = query.sort(
            "scheduled_time_utc"
        )

    # -------------------------------------------------------------------------
    # Pagination
    # -------------------------------------------------------------------------

    query = (
        query
        .skip(skip)
        .limit(limit)
    )

    items = await query.to_list()

    return total, items


# ── Update ───────────────────────────────────────────────────────────────────


async def update_reminder(
    reminder: Reminder,
    body: ReminderUpdateRequest,
) -> Reminder:

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

    if body.local_datetime is not None:
        tz = (
            body.timezone
            or reminder.timezone
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

        # Re-arm reminder.
        reminder.status = (
            ReminderStatus.PENDING
        )

    reminder.update_timestamp()

    await reminder.save()

    return reminder


async def delete_reminder(
    reminder: Reminder,
) -> None:
    await reminder.delete()


async def complete_reminder(
    reminder: Reminder,
) -> Reminder:

    reminder.status = (
        ReminderStatus.COMPLETED
    )

    reminder.completed_at = now_utc()

    reminder.update_timestamp()

    await reminder.save()

    return reminder


async def snooze_reminder(
    reminder: Reminder,
    minutes: int,
) -> Reminder:

    snooze_until = (
        now_utc()
        + timedelta(minutes=minutes)
    )

    reminder.snooze_until = snooze_until

    reminder.status = (
        ReminderStatus.SNOOZED
    )

    reminder.update_timestamp()

    await reminder.save()

    return reminder


async def reschedule_reminder(
    reminder: Reminder,
    utc_time: datetime,
) -> Reminder:

    reminder.scheduled_time_utc = utc_time

    reminder.status = (
        ReminderStatus.PENDING
    )

    reminder.snooze_until = None
    reminder.notification_sent_at = None

    reminder.update_timestamp()

    await reminder.save()

    return reminder


# ── Recurring Logic ──────────────────────────────────────────────────────────


def compute_next_occurrence(
    reminder: Reminder,
) -> Optional[datetime]:
    """
    Compute the next UTC occurrence for a recurring reminder.
    Returns None if the repeat_type is NEVER.
    """

    from zoneinfo import ZoneInfo

    if reminder.repeat_type == RepeatType.NEVER:
        return None

    tz = ZoneInfo(
        reminder.timezone
    )

    base_local = (
        reminder.scheduled_time_utc.astimezone(tz)
    )

    now_local = (
        now_utc().astimezone(tz)
    )

    if reminder.repeat_type == RepeatType.DAILY:

        next_local = (
            base_local
            + timedelta(days=1)
        )

        while next_local <= now_local:
            next_local += timedelta(days=1)

    elif reminder.repeat_type == RepeatType.WEEKDAYS:

        next_local = (
            base_local
            + timedelta(days=1)
        )

        while (
            next_local <= now_local
            or next_local.weekday() >= 5
        ):
            next_local += timedelta(days=1)

    elif reminder.repeat_type == RepeatType.WEEKLY:

        next_local = (
            base_local
            + timedelta(weeks=1)
        )

        while next_local <= now_local:
            next_local += timedelta(weeks=1)

    elif reminder.repeat_type == RepeatType.MONTHLY:

        month = base_local.month + 1

        year = (
            base_local.year
            + (month - 1) // 12
        )

        month = (
            (month - 1) % 12
        ) + 1

        try:
            next_local = base_local.replace(
                year=year,
                month=month,
            )

        except ValueError:
            # Handle months with fewer days,
            # e.g. Jan 31 → Feb.
            last_day = calendar.monthrange(
                year,
                month,
            )[1]

            next_local = base_local.replace(
                year=year,
                month=month,
                day=last_day,
            )

        while next_local <= now_local:
            next_local += timedelta(days=28)

    elif reminder.repeat_type == RepeatType.YEARLY:

        try:
            next_local = base_local.replace(
                year=base_local.year + 1
            )

        except ValueError:
            # Handle leap day.
            next_local = base_local.replace(
                year=base_local.year + 1,
                day=28,
            )

        while next_local <= now_local:
            try:
                next_local = next_local.replace(
                    year=next_local.year + 1
                )

            except ValueError:
                next_local = next_local.replace(
                    year=next_local.year + 1,
                    day=28,
                )

    else:
        return None

    return (
        next_local
        .astimezone(
            ZoneInfo("UTC")
        )
        .replace(
            tzinfo=timezone.utc
        )
    )


# ── Response Formatter ───────────────────────────────────────────────────────


def to_response(
    reminder: Reminder,
    user_tz: Optional[str] = None,
) -> ReminderResponse:

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

        scheduled_time_utc=(
            reminder.scheduled_time_utc
        ),

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