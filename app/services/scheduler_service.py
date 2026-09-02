"""
Timora – Reliable Reminder Scheduler

Processes reminder notifications in UTC.

When a reminder becomes due:
1. Browser push notification is attempted.
2. Email notification is attempted.
3. Reminder is marked as SENT.
4. Recurring reminders are re-armed.

The scheduler polls every 5 seconds.
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
    """
    Calculate the actual notification time.

    Example:

    scheduled_time = 10:00
    reminder_before = 5_minutes

    notification time = 09:55
    """

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
    """
    Format reminder time using the
    reminder's selected timezone.
    """

    scheduled_utc = _as_utc(
        reminder.scheduled_time_utc
    )

    try:
        timezone_name = (
            reminder.timezone
            or "UTC"
        )

        tz = ZoneInfo(
            timezone_name
        )

        local_time = scheduled_utc.astimezone(
            tz
        )

        return (
            local_time.strftime(
                "%d %B %Y at %I:%M %p"
            )
            + f" ({timezone_name})"
        )

    except Exception:
        logger.warning(
            "Could not convert reminder %s "
            "to timezone %s. Using UTC.",
            reminder.id,
            reminder.timezone,
        )

        return (
            scheduled_utc.strftime(
                "%d %B %Y at %I:%M %p UTC"
            )
        )


async def _get_reminder_user(
    reminder: Reminder,
) -> User | None:
    """
    Resolve reminder.user_id to the
    corresponding User document.
    """

    try:
        user_object_id = ObjectId(
            str(reminder.user_id)
        )

    except Exception:
        logger.error(
            "Reminder %s contains invalid "
            "user_id: %s",
            reminder.id,
            reminder.user_id,
        )

        return None

    try:
        user = await User.find_one(
            User.id == user_object_id
        )

    except Exception:
        logger.exception(
            "Database error while looking up "
            "user for reminder %s",
            reminder.id,
        )

        return None

    if user is None:
        logger.warning(
            "No user found for reminder %s "
            "(user_id=%s)",
            reminder.id,
            reminder.user_id,
        )

    return user


async def _send_email_notification(
    reminder: Reminder,
) -> bool:
    """
    Send email notification for one reminder.

    Returns True only when the email service
    confirms successful SMTP delivery.
    """

    try:
        logger.info(
            "Preparing email for reminder %s",
            reminder.id,
        )

        user = await _get_reminder_user(
            reminder
        )

        if user is None:
            logger.error(
                "Cannot send email for reminder %s: "
                "user not found.",
                reminder.id,
            )

            return False

        if not user.email:
            logger.error(
                "Cannot send email for reminder %s: "
                "user %s has no email address.",
                reminder.id,
                user.id,
            )

            return False

        recipient = str(
            user.email
        ).strip()

        if not recipient:
            logger.error(
                "Cannot send email for reminder %s: "
                "recipient email is empty.",
                reminder.id,
            )

            return False

        logger.info(
            "Attempting reminder email for %s "
            "to %s",
            reminder.id,
            recipient,
        )

        email_sent = await send_reminder_email(
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

        if email_sent:
            logger.info(
                "EMAIL SUCCESS: reminder %s "
                "sent to %s",
                reminder.id,
                recipient,
            )

            return True

        logger.error(
            "EMAIL FAILED: email service returned "
            "False for reminder %s to %s",
            reminder.id,
            recipient,
        )

        return False

    except Exception:
        logger.exception(
            "Unexpected email error for "
            "reminder %s",
            reminder.id,
        )

        return False


async def _send_push_notification(
    reminder: Reminder,
) -> bool:
    """
    Send browser push notification.

    Returns True when at least one push
    subscription was successfully processed.
    """

    try:
        logger.info(
            "Attempting push notification "
            "for reminder %s",
            reminder.id,
        )

        sent_count = await notify_reminder_due(
            reminder
        )

        if sent_count:
            logger.info(
                "PUSH SUCCESS: reminder %s "
                "delivered to %s subscription(s)",
                reminder.id,
                sent_count,
            )

            return True

        logger.warning(
            "PUSH WARNING: reminder %s reached "
            "due time but no push notification "
            "was delivered.",
            reminder.id,
        )

        return False

    except Exception:
        logger.exception(
            "PUSH FAILED: reminder %s",
            reminder.id,
        )

        return False


async def _process_due_reminders() -> None:
    """
    Find and process reminders whose
    notification time has arrived.
    """

    async with _process_lock:

        now = now_utc()

        logger.debug(
            "Checking reminders at %s",
            now,
        )

        # ---------------------------------------------------------
        # Fetch pending reminders
        # ---------------------------------------------------------

        try:
            pending = await Reminder.find(
                Reminder.status
                == ReminderStatus.PENDING
            ).limit(1000).to_list()

        except Exception:
            logger.exception(
                "Failed to fetch pending reminders."
            )

            pending = []

        # ---------------------------------------------------------
        # Fetch snoozed reminders
        # ---------------------------------------------------------

        try:
            snoozed = await Reminder.find(
                Reminder.status
                == ReminderStatus.SNOOZED
            ).limit(1000).to_list()

        except Exception:
            logger.exception(
                "Failed to fetch snoozed reminders."
            )

            snoozed = []

        reminders = (
            pending + snoozed
        )

        if not reminders:
            logger.debug(
                "No pending/snoozed reminders."
            )

            return

        logger.debug(
            "Found %s pending/snoozed reminder(s).",
            len(reminders),
        )

        # ---------------------------------------------------------
        # Process each reminder
        # ---------------------------------------------------------

        for reminder in reminders:

            try:

                # -------------------------------------------------
                # Snoozed reminder
                # -------------------------------------------------

                if (
                    reminder.status
                    == ReminderStatus.SNOOZED
                ):

                    if not reminder.snooze_until:

                        reminder.status = (
                            ReminderStatus.PENDING
                        )

                        reminder.update_timestamp()

                        await reminder.save()

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

                        reminder.update_timestamp()

                        await reminder.save()

                # -------------------------------------------------
                # Calculate notification time
                # -------------------------------------------------

                due_at = _due_at(
                    reminder
                )

                if due_at > now:
                    continue

                # -------------------------------------------------
                # Reminder is due
                # -------------------------------------------------

                logger.info(
                    "========================================"
                )

                logger.info(
                    "REMINDER DUE"
                )

                logger.info(
                    "Reminder ID: %s",
                    reminder.id,
                )

                logger.info(
                    "Title: %s",
                    reminder.title,
                )

                logger.info(
                    "Scheduled UTC: %s",
                    _as_utc(
                        reminder.scheduled_time_utc
                    ),
                )

                logger.info(
                    "Notification due UTC: %s",
                    due_at,
                )

                logger.info(
                    "Current UTC: %s",
                    now,
                )

                logger.info(
                    "========================================"
                )

                # -------------------------------------------------
                # IMPORTANT:
                #
                # Do NOT mark SENT before sending.
                # First attempt push + email.
                # -------------------------------------------------

                push_sent = (
                    await _send_push_notification(
                        reminder
                    )
                )

                email_sent = (
                    await _send_email_notification(
                        reminder
                    )
                )

                # -------------------------------------------------
                # Delivery summary
                # -------------------------------------------------

                logger.info(
                    "Reminder %s delivery result: "
                    "push=%s email=%s",
                    reminder.id,
                    push_sent,
                    email_sent,
                )

                # -------------------------------------------------
                # Mark as SENT after notification attempts
                # -------------------------------------------------

                reminder.status = (
                    ReminderStatus.SENT
                )

                reminder.notification_sent_at = (
                    now
                )

                reminder.update_timestamp()

                await reminder.save()

                logger.info(
                    "Reminder %s marked as SENT.",
                    reminder.id,
                )

                # -------------------------------------------------
                # Recurring reminder
                # -------------------------------------------------

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
                        "Recurring reminder %s "
                        "re-armed for %s",
                        reminder.id,
                        next_time,
                    )

            except Exception:

                logger.exception(
                    "Failed to process reminder %s",
                    reminder.id,
                )

                # -------------------------------------------------
                # Mark failed only when processing itself crashes.
                # -------------------------------------------------

                try:

                    reminder.status = (
                        ReminderStatus.FAILED
                    )

                    reminder.update_timestamp()

                    await reminder.save()

                except Exception:

                    logger.exception(
                        "Could not mark reminder %s "
                        "as FAILED.",
                        reminder.id,
                    )


def start_scheduler() -> None:
    """Start Timora reminder scheduler."""

    global _scheduler

    if (
        _scheduler is not None
        and _scheduler.running
    ):
        logger.info(
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
        "========================================"
    )

    logger.info(
        "APScheduler STARTED"
    )

    logger.info(
        "Reminder polling interval: 5 seconds"
    )

    logger.info(
        "========================================"
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

        logger.info(
            "Reminder scheduler stopped."
        )

    except Exception:

        logger.exception(
            "Error while shutting down "
            "reminder scheduler."
        )

    finally:

        _scheduler = None