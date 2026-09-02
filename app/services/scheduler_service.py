"""
Timora – Reliable Reminder Scheduler

Processes reminder notification times in UTC.

The scheduler checks every 5 seconds so reminders are delivered
very close to their requested time.

When a reminder becomes due, Timora:
1. Sends a browser push notification.
2. Sends an email to the user's registered email address.
3. Handles recurring reminders automatically.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

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
    """Convert a datetime to timezone-aware UTC."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _due_at(reminder: Reminder) -> datetime:
    """
    Calculate the actual notification time.

    Example:
        scheduled = 10:00
        reminder_before = 5_minutes

        notification time = 09:55
    """

    minutes = REMINDER_BEFORE_MINUTES.get(
        reminder.reminder_before,
        0,
    )

    return (
        _as_utc(reminder.scheduled_time_utc)
        - timedelta(minutes=minutes)
    )


async def _send_reminder_email(reminder: Reminder) -> bool:
    """
    Send the reminder email to the user who owns the reminder.

    Returns:
        True if the email was sent successfully.
        False if the user/email is unavailable or sending failed.
    """

    try:
        user = await User.get(reminder.user_id)

        if user is None:
            logger.warning(
                "Cannot send email for reminder %s: "
                "user %s was not found.",
                reminder.id,
                reminder.user_id,
            )
            return False

        if not user.email:
            logger.warning(
                "Cannot send email for reminder %s: "
                "user %s has no email address.",
                reminder.id,
                reminder.user_id,
            )
            return False

        # Handle both Enum values and plain strings safely.
        category = (
            reminder.category.value
            if hasattr(reminder.category, "value")
            else str(reminder.category)
        )

        priority = (
            reminder.priority.value
            if hasattr(reminder.priority, "value")
            else str(reminder.priority)
        )

        # Display the reminder time in UTC.
        scheduled_time = _as_utc(
            reminder.scheduled_time_utc
        ).strftime(
            "%d %B %Y at %I:%M %p UTC"
        )

        email_sent = await send_reminder_email(
            recipient=str(user.email),
            title=reminder.title,
            scheduled_time=scheduled_time,
            category=category,
            priority=priority,
        )

        if email_sent:
            logger.info(
                "Reminder %s email sent successfully to %s",
                reminder.id,
                user.email,
            )
            return True

        logger.warning(
            "Reminder %s email could not be sent to %s",
            reminder.id,
            user.email,
        )
        return False

    except Exception:
        # Email failure must NEVER stop the reminder scheduler.
        logger.exception(
            "Unexpected error while sending email "
            "for reminder %s",
            reminder.id,
        )
        return False


async def _process_due_reminders() -> None:
    """
    Find and process reminders whose notification time has arrived.
    """

    async with _process_lock:

        now = now_utc()

        # Query pending reminders.
        pending = await Reminder.find(
            Reminder.status == ReminderStatus.PENDING
        ).limit(1000).to_list()

        # Query snoozed reminders separately.
        snoozed = await Reminder.find(
            Reminder.status == ReminderStatus.SNOOZED
        ).limit(1000).to_list()

        reminders = pending + snoozed

        for reminder in reminders:

            try:

                # ── Snoozed reminder ──────────────────────────────────────

                if reminder.status == ReminderStatus.SNOOZED:

                    if not reminder.snooze_until:
                        reminder.status = ReminderStatus.PENDING

                    elif _as_utc(reminder.snooze_until) > now:
                        # Still snoozed.
                        continue

                    else:
                        # Snooze period has finished.
                        reminder.snooze_until = None
                        reminder.status = ReminderStatus.PENDING

                # ── Check notification time ───────────────────────────────

                if _due_at(reminder) > now:
                    continue

                # ── Mark as sent BEFORE sending notifications ─────────────

                reminder.status = ReminderStatus.SENT
                reminder.notification_sent_at = now

                reminder.update_timestamp()

                await reminder.save()

                logger.info(
                    "Reminder %s is due. Sending notifications.",
                    reminder.id,
                )

                # ── Send browser push notification ────────────────────────

                try:
                    sent_count = await notify_reminder_due(
                        reminder
                    )

                    if sent_count:
                        logger.info(
                            "Reminder %s delivered to %s "
                            "push subscription(s)",
                            reminder.id,
                            sent_count,
                        )
                    else:
                        logger.warning(
                            "Reminder %s reached due time "
                            "but no push notification was delivered.",
                            reminder.id,
                        )

                except Exception:
                    # Push failure must not stop email delivery.
                    logger.exception(
                        "Push notification failed for reminder %s",
                        reminder.id,
                    )

                # ── Send email notification ───────────────────────────────

                await _send_reminder_email(reminder)

                # ── Recurring reminder ─────────────────────────────────────

                next_time = compute_next_occurrence(
                    reminder
                )

                if next_time is not None:

                    reminder.scheduled_time_utc = next_time

                    reminder.status = ReminderStatus.PENDING

                    reminder.notification_sent_at = None
                    reminder.snooze_until = None

                    reminder.update_timestamp()

                    await reminder.save()

                    logger.info(
                        "Recurring reminder %s re-armed for %s",
                        reminder.id,
                        next_time,
                    )

            except Exception:

                logger.exception(
                    "Failed to process reminder %s",
                    reminder.id,
                )

                try:

                    reminder.status = ReminderStatus.FAILED

                    reminder.update_timestamp()

                    await reminder.save()

                except Exception:

                    logger.exception(
                        "Could not mark reminder %s as failed",
                        reminder.id,
                    )


def start_scheduler() -> None:
    """Start the Timora reminder scheduler."""

    global _scheduler

    # Prevent multiple scheduler instances.
    if (
        _scheduler is not None
        and _scheduler.running
    ):
        logger.debug(
            "Reminder scheduler is already running."
        )
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
        "APScheduler started — "
        "reminder polling every 5 seconds"
    )


def stop_scheduler() -> None:
    """Stop the reminder scheduler."""

    global _scheduler

    if _scheduler is not None:

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