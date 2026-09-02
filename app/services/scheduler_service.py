"""
Timora – Reliable Reminder Scheduler

Processes reminder notifications in UTC.

When a reminder becomes due:
1. Browser push notification is sent.
2. Reminder email is sent.
3. Recurring reminders are re-armed.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bson import ObjectId

from app.models.reminder import (
    REMINDER_BEFORE_MINUTES,
    Reminder,
    ReminderStatus,
)
from app.models.user import User
from app.services.email_service import send_reminder_email
from app.services.notification_service import notify_reminder_due
from app.services.reminder_service import compute_next_occurrence
from app.utils.timezone import now_utc


logger = logging.getLogger(__name__)


_scheduler: AsyncIOScheduler | None = None
_process_lock = asyncio.Lock()


def _as_utc(value: datetime) -> datetime:
    """Return a timezone-aware UTC datetime."""

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def _due_at(reminder: Reminder) -> datetime:
    """Calculate the actual notification time."""

    minutes = REMINDER_BEFORE_MINUTES.get(
        reminder.reminder_before,
        0,
    )

    return (
        _as_utc(
            reminder.scheduled_time_utc
        )
        - timedelta(minutes=minutes)
    )


def _enum_value(value: object) -> str:
    """Safely convert Enum/string values to text."""

    enum_value = getattr(
        value,
        "value",
        None,
    )

    if enum_value is not None:
        return str(enum_value)

    return str(value)


def _formatted_reminder_time(
    reminder: Reminder,
) -> str:
    """Format reminder time in its selected timezone."""

    scheduled_utc = _as_utc(
        reminder.scheduled_time_utc
    )

    try:

        tz = ZoneInfo(
            reminder.timezone
        )

        local_time = (
            scheduled_utc.astimezone(tz)
        )

        return (
            local_time.strftime(
                "%d %B %Y at %I:%M %p"
            )
            + f" ({reminder.timezone})"
        )

    except Exception:

        logger.warning(
            "Could not convert reminder %s "
            "to timezone %s",
            reminder.id,
            reminder.timezone,
        )

        return scheduled_utc.strftime(
            "%d %B %Y at %I:%M %p UTC"
        )


async def _get_reminder_user(
    reminder: Reminder,
) -> User | None:
    """Resolve reminder.user_id to a User."""

    try:

        user_object_id = ObjectId(
            reminder.user_id
        )

    except Exception:

        logger.error(
            "Invalid user_id for reminder %s: %s",
            reminder.id,
            reminder.user_id,
        )

        return None

    user = await User.find_one(
        User.id == user_object_id
    )

    if user is None:

        logger.error(
            "No user found for reminder %s. "
            "user_id=%s",
            reminder.id,
            reminder.user_id,
        )

        return None

    return user


async def _send_email_notification(
    reminder: Reminder,
) -> bool:
    """Send reminder email."""

    user = await _get_reminder_user(
        reminder
    )

    if user is None:
        return False

    recipient = str(
        user.email
    ).strip()

    if not recipient:

        logger.error(
            "User %s has no email. "
            "Reminder %s cannot send email.",
            user.id,
            reminder.id,
        )

        return False

    logger.info(
        "📧 Sending reminder email: "
        "reminder=%s recipient=%s",
        reminder.id,
        recipient,
    )

    try:

        result = await send_reminder_email(
            recipient=recipient,
            title=reminder.title,
            scheduled_time=(
                _formatted_reminder_time(
                    reminder
                )
            ),
            category=_enum_value(
                reminder.category
            ),
            priority=_enum_value(
                reminder.priority
            ),
        )

        if result:

            logger.info(
                "✅ Reminder email delivered "
                "successfully: reminder=%s recipient=%s",
                reminder.id,
                recipient,
            )

            return True

        logger.error(
            "❌ Reminder email FAILED: "
            "reminder=%s recipient=%s",
            reminder.id,
            recipient,
        )

        return False

    except Exception:

        logger.exception(
            "❌ Exception while sending email "
            "for reminder %s",
            reminder.id,
        )

        return False


async def _send_push_notification(
    reminder: Reminder,
) -> None:
    """Send browser push notification."""

    try:

        sent_count = (
            await notify_reminder_due(
                reminder
            )
        )

        if sent_count:

            logger.info(
                "Browser push sent for reminder %s "
                "to %s subscription(s)",
                reminder.id,
                sent_count,
            )

        else:

            logger.warning(
                "No browser push subscription "
                "for reminder %s",
                reminder.id,
            )

    except Exception:

        logger.exception(
            "Push notification failed "
            "for reminder %s",
            reminder.id,
        )


async def _process_due_reminders() -> None:
    """Find and process due reminders."""

    async with _process_lock:

        now = now_utc()

        pending = await Reminder.find(
            Reminder.status
            == ReminderStatus.PENDING
        ).limit(1000).to_list()

        snoozed = await Reminder.find(
            Reminder.status
            == ReminderStatus.SNOOZED
        ).limit(1000).to_list()

        reminders = pending + snoozed

        if reminders:
            logger.debug(
                "Scheduler checked %s reminders.",
                len(reminders),
            )

        for reminder in reminders:

            try:

                # ─────────────────────────────
                # Snoozed reminder
                # ─────────────────────────────

                if (
                    reminder.status
                    == ReminderStatus.SNOOZED
                ):

                    if not reminder.snooze_until:

                        reminder.status = (
                            ReminderStatus.PENDING
                        )

                    elif (
                        _as_utc(
                            reminder.snooze_until
                        )
                        > now
                    ):

                        continue

                    else:

                        reminder.snooze_until = None

                        reminder.status = (
                            ReminderStatus.PENDING
                        )

                # ─────────────────────────────
                # Not due yet
                # ─────────────────────────────

                due_time = _due_at(
                    reminder
                )

                if due_time > now:
                    continue

                logger.info(
                    "🔔 REMINDER DUE: id=%s title=%s "
                    "due=%s now=%s",
                    reminder.id,
                    reminder.title,
                    due_time,
                    now,
                )

                # ─────────────────────────────
                # Push notification
                # ─────────────────────────────

                await _send_push_notification(
                    reminder
                )

                # ─────────────────────────────
                # Email notification
                # ─────────────────────────────

                email_sent = (
                    await _send_email_notification(
                        reminder
                    )
                )

                if email_sent:

                    logger.info(
                        "📧 Email notification "
                        "completed for reminder %s",
                        reminder.id,
                    )

                else:

                    logger.error(
                        "🚨 Email notification FAILED "
                        "for reminder %s",
                        reminder.id,
                    )

                # ─────────────────────────────
                # Mark notification processed
                # ─────────────────────────────

                reminder.status = (
                    ReminderStatus.SENT
                )

                reminder.notification_sent_at = now

                reminder.update_timestamp()

                await reminder.save()

                # ─────────────────────────────
                # Recurring reminder
                # ─────────────────────────────

                next_time = (
                    compute_next_occurrence(
                        reminder
                    )
                )

                if next_time is not None:

                    reminder.scheduled_time_utc = (
                        next_time
                    )

                    reminder.status = (
                        ReminderStatus.PENDING
                    )

                    reminder.notification_sent_at = (
                        None
                    )

                    reminder.snooze_until = None

                    reminder.update_timestamp()

                    await reminder.save()

                    logger.info(
                        "🔁 Recurring reminder %s "
                        "re-armed for %s",
                        reminder.id,
                        next_time,
                    )

            except Exception:

                logger.exception(
                    "Failed to process reminder %s",
                    reminder.id,
                )

                try:

                    reminder.status = (
                        ReminderStatus.FAILED
                    )

                    reminder.update_timestamp()

                    await reminder.save()

                except Exception:

                    logger.exception(
                        "Could not mark reminder %s "
                        "as failed",
                        reminder.id,
                    )


def start_scheduler() -> None:
    """Start Timora reminder scheduler."""

    global _scheduler

    if (
        _scheduler is not None
        and _scheduler.running
    ):
        return

    _scheduler = AsyncIOScheduler(
        timezone="UTC",
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 30,
        },
    )

    _scheduler.add_job(
        _process_due_reminders,
        "interval",
        seconds=5,
        id="process_due_reminders",
        name="Process Due Reminders",
        replace_existing=True,
    )

    _scheduler.start()

    logger.info(
        "✅ APScheduler started — "
        "checking reminders every 5 seconds"
    )


def stop_scheduler() -> None:
    """Stop Timora reminder scheduler."""

    global _scheduler

    if _scheduler is None:
        return

    try:

        _scheduler.shutdown(
            wait=False
        )

    except Exception:

        logger.exception(
            "Error while shutting down scheduler"
        )

    finally:

        _scheduler = None