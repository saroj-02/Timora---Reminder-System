"""
Timora Reminder Scheduler

Responsibilities:
- Check pending/snoozed reminders
- Detect reminders that are due
- Send push notifications
- Send email notifications
- Mark reminders as sent
- Re-arm recurring reminders
- Run continuously with APScheduler

Render optimized:
- Poll every 10 seconds
- Avoid noisy logs when there is nothing to process
- Prevent overlapping executions
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bson import ObjectId

from app.models.reminder import Reminder, ReminderStatus
from app.models.user import User
from app.services.email_service import send_reminder_email
from app.services.notification_service import notify_reminder_due
from app.services.reminder_service import compute_next_occurrence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

POLL_INTERVAL_SECONDS = 10

_scheduler: AsyncIOScheduler | None = None
_scheduler_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _as_utc(value: datetime) -> datetime:
    """Return a timezone-aware UTC datetime."""

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _enum_value(value: Any) -> str:
    """Safely return an enum's string value."""

    return getattr(value, "value", str(value))


def _due_at(reminder: Reminder) -> datetime:
    """
    Calculate when the notification should actually fire.

    Example:
        scheduled = 10:00
        reminder_before = 10_minutes

        notification due = 09:50
    """

    scheduled = _as_utc(
        reminder.scheduled_time_utc
    )

    before_value = _enum_value(
        reminder.reminder_before
    )

    before_minutes = {
        "at_time": 0,
        "5_minutes": 5,
        "10_minutes": 10,
        "15_minutes": 15,
        "30_minutes": 30,
        "1_hour": 60,
        "1_day": 1440,
    }

    minutes = before_minutes.get(
        before_value,
        0,
    )

    return scheduled - timedelta(
        minutes=minutes
    )


def _formatted_reminder_time(
    reminder: Reminder,
) -> str:
    """Format reminder time using its configured timezone."""

    try:
        timezone_name = (
            reminder.timezone or "UTC"
        )

        local_timezone = ZoneInfo(
            timezone_name
        )

        local_time = _as_utc(
            reminder.scheduled_time_utc
        ).astimezone(
            local_timezone
        )

        return local_time.strftime(
            "%d %b %Y, %I:%M %p"
        )

    except Exception:
        return _as_utc(
            reminder.scheduled_time_utc
        ).strftime(
            "%d %b %Y, %I:%M %p UTC"
        )


# ---------------------------------------------------------------------------
# User lookup
# ---------------------------------------------------------------------------

async def _get_reminder_user(
    reminder: Reminder,
) -> User | None:
    """
    Find the user who owns the reminder.

    Reminder.user_id is stored as a string.
    User.id is a Mongo/Beanie ObjectId.
    """

    try:
        user_id = str(
            reminder.user_id
        ).strip()

        if not ObjectId.is_valid(user_id):
            logger.error(
                "Invalid user_id | reminder=%s | user_id=%s",
                reminder.id,
                user_id,
            )
            return None

        user = await User.find_one(
            User.id == ObjectId(user_id)
        )

        if user is None:
            logger.error(
                "User not found | reminder=%s | user_id=%s",
                reminder.id,
                user_id,
            )
            return None

        return user

    except Exception:
        logger.exception(
            "Failed to find reminder owner | reminder=%s",
            reminder.id,
        )
        return None


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

async def _send_email_notification(
    reminder: Reminder,
) -> bool:
    """Send reminder email to the reminder owner."""

    try:
        user = await _get_reminder_user(
            reminder
        )

        if user is None:
            logger.warning(
                "Email skipped: user not found | reminder=%s",
                reminder.id,
            )
            return False

        recipient = str(
            user.email
        ).strip()

        if not recipient:
            logger.warning(
                "Email skipped: user email empty | reminder=%s",
                reminder.id,
            )
            return False

        reminder_time = (
            _formatted_reminder_time(
                reminder
            )
        )

        logger.info(
            "Sending reminder email | reminder=%s | to=%s",
            reminder.id,
            recipient,
        )

        # IMPORTANT:
        # This matches the actual email_service.py signature.
        result = await send_reminder_email(
            recipient,
            reminder.title,
            reminder_time,
            _enum_value(reminder.category),
            _enum_value(reminder.priority),
        )

        if result:
            logger.info(
                "EMAIL SUCCESS | reminder=%s | to=%s",
                reminder.id,
                recipient,
            )
        else:
            logger.error(
                "EMAIL FAILED | reminder=%s | to=%s",
                reminder.id,
                recipient,
            )

        return bool(result)

    except Exception:
        logger.exception(
            "Unexpected email error | reminder=%s",
            reminder.id,
        )
        return False


# ---------------------------------------------------------------------------
# Push notification
# ---------------------------------------------------------------------------

async def _send_push_notification(
    reminder: Reminder,
) -> bool:
    """Send web push notification."""

    try:
        result = await notify_reminder_due(
            reminder
        )

        if result:
            logger.info(
                "PUSH SUCCESS | reminder=%s",
                reminder.id,
            )
        else:
            logger.warning(
                "PUSH FAILED/UNAVAILABLE | reminder=%s",
                reminder.id,
            )

        return bool(result)

    except Exception:
        logger.exception(
            "Unexpected push error | reminder=%s",
            reminder.id,
        )
        return False


# ---------------------------------------------------------------------------
# Recurring reminders
# ---------------------------------------------------------------------------

async def _rearm_recurring_reminder(
    reminder: Reminder,
) -> bool:
    """Calculate and save the next recurring occurrence."""

    try:
        repeat_type = _enum_value(
            reminder.repeat_type
        )

        if repeat_type == "never":
            return False

        # IMPORTANT:
        # The actual reminder_service.py expects
        # the complete Reminder object.
        next_occurrence = (
            compute_next_occurrence(
                reminder
            )
        )

        if next_occurrence is None:
            logger.warning(
                "Could not calculate next occurrence | reminder=%s",
                reminder.id,
            )
            return False

        reminder.scheduled_time_utc = (
            _as_utc(
                next_occurrence
            )
        )

        reminder.status = (
            ReminderStatus.PENDING
        )

        reminder.notification_sent_at = None
        reminder.snooze_until = None

        await reminder.save()

        logger.info(
            "Recurring reminder re-armed | reminder=%s | next=%s",
            reminder.id,
            reminder.scheduled_time_utc.isoformat(),
        )

        return True

    except Exception:
        logger.exception(
            "Failed to re-arm recurring reminder | reminder=%s",
            reminder.id,
        )
        return False


# ---------------------------------------------------------------------------
# Process due reminders
# ---------------------------------------------------------------------------

async def _process_due_reminders() -> None:
    """
    Find and process reminders that are due.
    """

    async with _scheduler_lock:

        try:
            now = datetime.now(
                timezone.utc
            )

            # ---------------------------------------------------------------
            # Load pending reminders
            # ---------------------------------------------------------------

            pending = await Reminder.find(
                Reminder.status
                == ReminderStatus.PENDING
            ).to_list()

            # ---------------------------------------------------------------
            # Load snoozed reminders
            # ---------------------------------------------------------------

            snoozed = await Reminder.find(
                Reminder.status
                == ReminderStatus.SNOOZED
            ).to_list()

            reminders = (
                pending + snoozed
            )

            if not reminders:
                return

            logger.debug(
                "Scheduler checked %d active reminder(s)",
                len(reminders),
            )

            due_count = 0

            # ---------------------------------------------------------------
            # Process
            # ---------------------------------------------------------------

            for reminder in reminders:

                try:

                    # -------------------------------------------------------
                    # Determine due time
                    # -------------------------------------------------------

                    if (
                        reminder.status
                        == ReminderStatus.SNOOZED
                    ):
                        if (
                            reminder.snooze_until
                            is None
                        ):
                            continue

                        due_time = _as_utc(
                            reminder.snooze_until
                        )

                    else:
                        due_time = _due_at(
                            reminder
                        )

                    # -------------------------------------------------------
                    # Not due yet
                    # -------------------------------------------------------

                    if due_time > now:
                        continue

                    due_count += 1

                    logger.info(
                        "REMINDER DUE | id=%s | title=%s | due=%s | now=%s",
                        reminder.id,
                        reminder.title,
                        due_time.isoformat(),
                        now.isoformat(),
                    )

                    # -------------------------------------------------------
                    # Send push
                    # -------------------------------------------------------

                    push_success = (
                        await _send_push_notification(
                            reminder
                        )
                    )

                    # -------------------------------------------------------
                    # Send email
                    # -------------------------------------------------------

                    email_success = (
                        await _send_email_notification(
                            reminder
                        )
                    )

                    logger.info(
                        "NOTIFICATION RESULT | reminder=%s | push=%s | email=%s",
                        reminder.id,
                        push_success,
                        email_success,
                    )

                    # -------------------------------------------------------
                    # Mark as sent
                    # -------------------------------------------------------

                    reminder.status = (
                        ReminderStatus.SENT
                    )

                    reminder.notification_sent_at = now
                    reminder.snooze_until = None

                    await reminder.save()

                    logger.info(
                        "REMINDER MARKED SENT | reminder=%s",
                        reminder.id,
                    )

                    # -------------------------------------------------------
                    # Recurring reminder
                    # -------------------------------------------------------

                    repeat_type = _enum_value(
                        reminder.repeat_type
                    )

                    if repeat_type != "never":

                        await _rearm_recurring_reminder(
                            reminder
                        )

                except Exception:
                    logger.exception(
                        "Failed processing reminder | reminder=%s",
                        reminder.id,
                    )

            if due_count:
                logger.info(
                    "Processed %d due reminder(s)",
                    due_count,
                )

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception(
                "Scheduler reminder processing failed"
            )


# ---------------------------------------------------------------------------
# Scheduler start
# ---------------------------------------------------------------------------

def start_scheduler() -> None:
    """Start APScheduler."""

    global _scheduler

    if _scheduler is not None:

        if _scheduler.running:
            logger.info(
                "APScheduler already running"
            )
            return

    _scheduler = AsyncIOScheduler(
        timezone="UTC"
    )

    _scheduler.add_job(
        _process_due_reminders,
        trigger="interval",
        seconds=POLL_INTERVAL_SECONDS,
        id="process_due_reminders",
        name="Process Due Reminders",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=30,
    )

    _scheduler.start()

    logger.info(
        "APScheduler started | reminder polling=%ss",
        POLL_INTERVAL_SECONDS,
    )


# ---------------------------------------------------------------------------
# Scheduler shutdown
# ---------------------------------------------------------------------------

def stop_scheduler() -> None:
    """Stop APScheduler gracefully."""

    global _scheduler

    if _scheduler is None:
        return

    try:

        if _scheduler.running:

            _scheduler.shutdown(
                wait=False
            )

            logger.info(
                "APScheduler stopped"
            )

    except Exception:
        logger.exception(
            "Failed to stop APScheduler"
        )

    finally:
        _scheduler = None