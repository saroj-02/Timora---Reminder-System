"""
Timora Reminder Scheduler

Responsibilities:
- Check for due reminders
- Send push notifications
- Send email notifications
- Mark reminders as sent
- Re-arm recurring reminders
- Handle snoozed reminders
- Run continuously with APScheduler

Optimized for Render:
- Poll every 10 seconds instead of every 5 seconds
- Avoid unnecessary verbose logs
- Process only pending/snoozed reminders
- Prevent overlapping scheduler executions
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
# Scheduler configuration
# ---------------------------------------------------------------------------

POLL_INTERVAL_SECONDS = 10

_scheduler: AsyncIOScheduler | None = None
_scheduler_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _as_utc(value: datetime) -> datetime:
    """Return a timezone-aware UTC datetime."""

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _enum_value(value: Any) -> str:
    """Safely extract the value from an enum."""

    return getattr(value, "value", str(value))


def _due_at(reminder: Reminder) -> datetime:
    """
    Calculate the actual notification time.

    Example:
        Reminder at 10:00 with 10-minute advance notification
        -> notification due at 09:50.
    """

    scheduled = _as_utc(reminder.scheduled_time_utc)

    before_value = _enum_value(reminder.reminder_before)

    before_minutes = {
        "at_time": 0,
        "5_minutes": 5,
        "10_minutes": 10,
        "15_minutes": 15,
        "30_minutes": 30,
        "1_hour": 60,
        "1_day": 1440,
    }

    minutes = before_minutes.get(before_value, 0)

    return scheduled - timedelta(minutes=minutes)


def _formatted_reminder_time(reminder: Reminder) -> str:
    """Format reminder time in the reminder's configured timezone."""

    try:
        timezone_name = reminder.timezone or "UTC"
        local_timezone = ZoneInfo(timezone_name)

        local_time = _as_utc(
            reminder.scheduled_time_utc
        ).astimezone(local_timezone)

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

    Reminder.user_id is stored as a string/ObjectId-compatible value.
    """

    try:
        user_id = str(reminder.user_id)

        if not ObjectId.is_valid(user_id):
            logger.error(
                "Invalid user_id for reminder %s: %s",
                reminder.id,
                user_id,
            )
            return None

        user_object_id = ObjectId(user_id)

        user = await User.find_one(
            User.id == user_object_id
        )

        if user is None:
            logger.error(
                "User not found for reminder %s (user_id=%s)",
                reminder.id,
                user_id,
            )

        return user

    except Exception:
        logger.exception(
            "Failed to find user for reminder %s",
            reminder.id,
        )
        return None


# ---------------------------------------------------------------------------
# Email notification
# ---------------------------------------------------------------------------

async def _send_email_notification(
    reminder: Reminder,
) -> bool:
    """Send reminder email to the reminder owner."""

    try:
        user = await _get_reminder_user(reminder)

        if user is None:
            logger.warning(
                "Email skipped: user not found for reminder %s",
                reminder.id,
            )
            return False

        recipient = str(user.email).strip()

        if not recipient:
            logger.warning(
                "Email skipped: user has no email for reminder %s",
                reminder.id,
            )
            return False

        reminder_time = _formatted_reminder_time(reminder)

        logger.info(
            "Sending reminder email | reminder=%s | to=%s",
            reminder.id,
            recipient,
        )

        # IMPORTANT:
        # These parameter names exactly match email_service.py.
        result = await send_reminder_email(
            recipient=recipient,
            title=reminder.title,
            scheduled_time=reminder_time,
            category=_enum_value(reminder.category),
            priority=_enum_value(reminder.priority),
        )

        if result:
            logger.info(
                "Reminder email sent successfully | reminder=%s",
                reminder.id,
            )
        else:
            logger.error(
                "Reminder email failed | reminder=%s",
                reminder.id,
            )

        return bool(result)

    except Exception:
        logger.exception(
            "Unexpected email error for reminder %s",
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
        delivery_count = await notify_reminder_due(reminder)

        success = delivery_count > 0

        if success:
            logger.info(
                "Push notification sent | reminder=%s | devices=%s",
                reminder.id,
                delivery_count,
            )
        else:
            logger.warning(
                "Push notification unavailable/failed | reminder=%s",
                reminder.id,
            )

        return success

    except Exception:
        logger.exception(
            "Unexpected push notification error | reminder=%s",
            reminder.id,
        )
        return False


# ---------------------------------------------------------------------------
# Recurring reminder
# ---------------------------------------------------------------------------

async def _rearm_recurring_reminder(
    reminder: Reminder,
) -> bool:
    """
    Calculate and schedule the next occurrence.

    Returns True when successfully re-armed.
    """

    try:
        repeat_type = _enum_value(
            reminder.repeat_type
        )

        if repeat_type == "never":
            return False

        next_occurrence = compute_next_occurrence(
            reminder
        )

        if next_occurrence is None:
            logger.warning(
                "Could not calculate next occurrence | reminder=%s",
                reminder.id,
            )
            return False

        reminder.scheduled_time_utc = _as_utc(
            next_occurrence
        )

        reminder.status = ReminderStatus.PENDING
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
            "Failed to re-arm recurring reminder %s",
            reminder.id,
        )
        return False


# ---------------------------------------------------------------------------
# Due reminder processing
# ---------------------------------------------------------------------------

async def _process_due_reminders() -> None:
    """
    Process reminders that are due.

    This function intentionally stays lightweight because it
    runs continuously on the Render web service.
    """

    async with _scheduler_lock:
        try:
            now = datetime.now(timezone.utc)

            # ---------------------------------------------------------------
            # Load pending reminders
            # ---------------------------------------------------------------

            pending_reminders = await Reminder.find(
                Reminder.status == ReminderStatus.PENDING
            ).to_list()

            # ---------------------------------------------------------------
            # Load snoozed reminders
            # ---------------------------------------------------------------

            snoozed_reminders = await Reminder.find(
                Reminder.status == ReminderStatus.SNOOZED
            ).to_list()

            reminders = (
                pending_reminders
                + snoozed_reminders
            )

            if not reminders:
                return

            due_count = 0

            # ---------------------------------------------------------------
            # Process reminders
            # ---------------------------------------------------------------

            for reminder in reminders:
                try:
                    # -------------------------------------------------------
                    # Handle snoozed reminder
                    # -------------------------------------------------------

                    if (
                        reminder.status
                        == ReminderStatus.SNOOZED
                    ):
                        if reminder.snooze_until is None:
                            continue

                        snooze_until = _as_utc(
                            reminder.snooze_until
                        )

                        if snooze_until > now:
                            continue

                        # Snooze period has ended.
                        due_time = snooze_until

                    else:
                        due_time = _due_at(reminder)

                    # -------------------------------------------------------
                    # Not due yet
                    # -------------------------------------------------------

                    if due_time > now:
                        continue

                    due_count += 1

                    logger.info(
                        "Reminder due | id=%s | title=%s | scheduled=%s",
                        reminder.id,
                        reminder.title,
                        _as_utc(
                            reminder.scheduled_time_utc
                        ).isoformat(),
                    )

                    # -------------------------------------------------------
                    # Send push notification
                    # -------------------------------------------------------

                    push_success = (
                        await _send_push_notification(
                            reminder
                        )
                    )

                    # -------------------------------------------------------
                    # Send email notification
                    # -------------------------------------------------------

                    email_success = (
                        await _send_email_notification(
                            reminder
                        )
                    )

                    logger.info(
                        "Notification result | reminder=%s | "
                        "push=%s | email=%s",
                        reminder.id,
                        push_success,
                        email_success,
                    )

                    # -------------------------------------------------------
                    # Mark as sent
                    # -------------------------------------------------------

                    reminder.status = ReminderStatus.SENT
                    reminder.notification_sent_at = now
                    reminder.snooze_until = None

                    await reminder.save()

                    # -------------------------------------------------------
                    # Re-arm recurring reminder
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
                        "Failed processing reminder %s",
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
    """
    Start APScheduler.

    Polling every 10 seconds reduces MongoDB/CPU load on Render
    while keeping reminders responsive.
    """

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