"""
Timora - Reliable Reminder & Email Scheduler

Behaviour:
- A reminder gets an APScheduler date job immediately after creation.
- Updating a reminder replaces its old scheduler job.
- Snoozing replaces the job with the snooze time.
- Completing/deleting a reminder removes the job.
- On application restart, pending jobs are restored from MongoDB.
- Email is sent at the reminder's scheduled date/time.
- Failed email deliveries remain pending and are retried.
- Recurring reminders automatically schedule their next occurrence.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from bson import ObjectId

from app.models.reminder import (
    Reminder,
    ReminderStatus,
)
from app.models.user import User
from app.services.email_service import send_reminder_email
from app.services.notification_service import notify_reminder_due
from app.services.reminder_service import compute_next_occurrence


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

EMAIL_RETRY_MINUTES = 2

# Safety sweep. This is NOT the primary scheduling mechanism.
# It only repairs missing jobs if Render restarted or something went wrong.
RECOVERY_INTERVAL_SECONDS = 60

_scheduler: AsyncIOScheduler | None = None
_scheduler_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _as_utc(value: datetime) -> datetime:
    """Return a timezone-aware UTC datetime."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _enum_value(value: Any) -> str:
    """Return string value for Enum or plain value."""

    return str(
        getattr(
            value,
            "value",
            value,
        )
    )


def _reminder_job_id(reminder_id: str) -> str:
    """Unique APScheduler job ID for one reminder."""

    return f"timora-reminder-{reminder_id}"


def _formatted_reminder_time(
    reminder: Reminder,
) -> str:
    """Format scheduled time in reminder's selected timezone."""

    try:
        timezone_name = (
            reminder.timezone
            or "UTC"
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
        logger.exception(
            "Could not format reminder timezone | reminder=%s",
            reminder.id,
        )

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
    Load the reminder owner.

    Reminder.user_id is stored as string.
    User.id is MongoDB ObjectId.
    """

    try:
        user_id = str(
            reminder.user_id
        ).strip()

        if not ObjectId.is_valid(user_id):
            logger.error(
                "Invalid reminder user_id | reminder=%s | user_id=%s",
                reminder.id,
                user_id,
            )
            return None

        user = await User.find_one(
            User.id == ObjectId(user_id)
        )

        if user is None:
            logger.error(
                "Reminder owner not found | reminder=%s | user_id=%s",
                reminder.id,
                user_id,
            )
            return None

        return user

    except Exception:
        logger.exception(
            "Failed to load reminder owner | reminder=%s",
            reminder.id,
        )
        return None


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

async def _send_email_notification(
    reminder: Reminder,
) -> bool:
    """Send reminder email to the user."""

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
            "User email is empty | reminder=%s",
            reminder.id,
        )
        return False

    reminder_time = (
        _formatted_reminder_time(
            reminder
        )
    )

    logger.info(
        "EMAIL SEND START | reminder=%s | user=%s | scheduled=%s",
        reminder.id,
        recipient,
        _as_utc(
            reminder.scheduled_time_utc
        ).isoformat(),
    )

    try:
        result = await send_reminder_email(
            recipient,
            reminder.title,
            reminder_time,
            _enum_value(
                reminder.category
            ),
            _enum_value(
                reminder.priority
            ),
        )

    except Exception:
        logger.exception(
            "EMAIL SEND EXCEPTION | reminder=%s",
            reminder.id,
        )
        return False

    if result:
        logger.info(
            "EMAIL DELIVERY SUCCESS | reminder=%s | user=%s",
            reminder.id,
            recipient,
        )
        return True

    logger.error(
        "EMAIL DELIVERY FAILED | reminder=%s | user=%s",
        reminder.id,
        recipient,
    )

    return False


# ---------------------------------------------------------------------------
# Push
# ---------------------------------------------------------------------------

async def _send_push_notification(
    reminder: Reminder,
) -> bool:
    """Send browser push if available."""

    try:
        result = await notify_reminder_due(
            reminder
        )

        if result:
            logger.info(
                "PUSH SUCCESS | reminder=%s",
                reminder.id,
            )
            return True

        logger.warning(
            "PUSH NOT DELIVERED | reminder=%s",
            reminder.id,
        )

        return False

    except Exception:
        logger.exception(
            "Push notification error | reminder=%s",
            reminder.id,
        )
        return False


# ---------------------------------------------------------------------------
# Remove job
# ---------------------------------------------------------------------------

def remove_reminder_job(
    reminder_id: str,
) -> None:
    """Remove scheduled reminder job if it exists."""

    if _scheduler is None:
        return

    job_id = _reminder_job_id(
        reminder_id
    )

    try:
        _scheduler.remove_job(
            job_id
        )

        logger.info(
            "REMINDER JOB REMOVED | reminder=%s",
            reminder_id,
        )

    except JobLookupError:
        pass

    except Exception:
        logger.exception(
            "Failed removing reminder job | reminder=%s",
            reminder_id,
        )


# ---------------------------------------------------------------------------
# Schedule one reminder
# ---------------------------------------------------------------------------

def schedule_reminder(
    reminder: Reminder,
    *,
    run_at: datetime | None = None,
) -> bool:
    """
    Schedule or replace one reminder job.

    Email is scheduled for the actual reminder date/time.

    For snoozed reminders, pass run_at=snooze_until.
    """

    if _scheduler is None:
        logger.warning(
            "Cannot schedule reminder because APScheduler is not running"
        )
        return False

    if reminder.id is None:
        logger.error(
            "Cannot schedule reminder without MongoDB ID"
        )
        return False

    reminder_id = str(
        reminder.id
    )

    job_id = _reminder_job_id(
        reminder_id
    )

    status = _enum_value(
        reminder.status
    ).lower()

    if status not in {
        "pending",
        "snoozed",
    }:
        remove_reminder_job(
            reminder_id
        )
        return False

    target_time = _as_utc(
        run_at
        or reminder.scheduled_time_utc
    )

    now = datetime.now(
        timezone.utc
    )

    # If service restarted just after reminder became due,
    # run it almost immediately instead of losing it.
    if target_time <= now:
        target_time = (
            now
            + timedelta(seconds=2)
        )

    try:
        _scheduler.add_job(
            _execute_reminder_job,
            trigger=DateTrigger(
                run_date=target_time,
                timezone=timezone.utc,
            ),
            args=[
                reminder_id,
            ],
            id=job_id,
            name=f"Timora Reminder {reminder_id}",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=300,
        )

        logger.info(
            "REMINDER EMAIL SCHEDULED | "
            "reminder=%s | run_at=%s | timezone=%s",
            reminder_id,
            target_time.isoformat(),
            reminder.timezone,
        )

        return True

    except Exception:
        logger.exception(
            "Failed scheduling reminder | reminder=%s",
            reminder_id,
        )
        return False


# ---------------------------------------------------------------------------
# Retry
# ---------------------------------------------------------------------------

def _schedule_retry(
    reminder: Reminder,
) -> None:
    """Retry failed email after EMAIL_RETRY_MINUTES."""

    retry_at = (
        datetime.now(
            timezone.utc
        )
        + timedelta(
            minutes=EMAIL_RETRY_MINUTES
        )
    )

    reminder_id = str(
        reminder.id
    )

    logger.warning(
        "EMAIL RETRY SCHEDULED | reminder=%s | retry_at=%s",
        reminder_id,
        retry_at.isoformat(),
    )

    schedule_reminder(
        reminder,
        run_at=retry_at,
    )


# ---------------------------------------------------------------------------
# Recurring
# ---------------------------------------------------------------------------

async def _schedule_next_recurring(
    reminder: Reminder,
) -> bool:
    """Compute, save and schedule next recurring reminder."""

    try:
        next_occurrence = (
            compute_next_occurrence(
                reminder
            )
        )

        if next_occurrence is None:
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

        reminder.update_timestamp()

        await reminder.save()

        scheduled = schedule_reminder(
            reminder
        )

        logger.info(
            "RECURRING REMINDER RE-ARMED | "
            "reminder=%s | next=%s | scheduled=%s",
            reminder.id,
            reminder.scheduled_time_utc.isoformat(),
            scheduled,
        )

        return scheduled

    except Exception:
        logger.exception(
            "Failed scheduling recurring reminder | reminder=%s",
            reminder.id,
        )

        return False


# ---------------------------------------------------------------------------
# Execute reminder
# ---------------------------------------------------------------------------

async def _execute_reminder_job(
    reminder_id: str,
) -> None:
    """
    Execute one scheduled reminder.

    IMPORTANT:
    The reminder is loaded fresh from MongoDB,
    therefore an old edited job cannot use stale reminder data.
    """

    async with _scheduler_lock:

        logger.info(
            "REMINDER JOB FIRED | reminder=%s | now=%s",
            reminder_id,
            datetime.now(
                timezone.utc
            ).isoformat(),
        )

        try:
            if not ObjectId.is_valid(
                reminder_id
            ):
                logger.error(
                    "Invalid reminder ID in scheduler | reminder=%s",
                    reminder_id,
                )
                return

            reminder = await Reminder.get(
                ObjectId(
                    reminder_id
                )
            )

            if reminder is None:
                logger.warning(
                    "Scheduled reminder no longer exists | reminder=%s",
                    reminder_id,
                )
                return

            status = _enum_value(
                reminder.status
            ).lower()

            if status not in {
                "pending",
                "snoozed",
            }:
                logger.info(
                    "Skipping inactive reminder | reminder=%s | status=%s",
                    reminder_id,
                    status,
                )
                return

            now = datetime.now(
                timezone.utc
            )

            # -------------------------------------------------------------
            # Snooze
            # -------------------------------------------------------------

            if (
                status == "snoozed"
                and reminder.snooze_until is not None
            ):
                expected_time = _as_utc(
                    reminder.snooze_until
                )

            else:
                expected_time = _as_utc(
                    reminder.scheduled_time_utc
                )

            # Guard against accidental early execution.
            if expected_time > (
                now
                + timedelta(seconds=2)
            ):
                logger.warning(
                    "Reminder job fired early; rescheduling | "
                    "reminder=%s | expected=%s | now=%s",
                    reminder_id,
                    expected_time.isoformat(),
                    now.isoformat(),
                )

                schedule_reminder(
                    reminder,
                    run_at=expected_time,
                )

                return

            logger.info(
                "REMINDER DUE | "
                "reminder=%s | title=%s | expected=%s | now=%s",
                reminder.id,
                reminder.title,
                expected_time.isoformat(),
                now.isoformat(),
            )

            # -------------------------------------------------------------
            # Email
            # -------------------------------------------------------------

            email_success = (
                await _send_email_notification(
                    reminder
                )
            )

            # -------------------------------------------------------------
            # Push
            # -------------------------------------------------------------

            push_success = (
                await _send_push_notification(
                    reminder
                )
            )

            logger.info(
                "NOTIFICATION RESULT | "
                "reminder=%s | email=%s | push=%s",
                reminder.id,
                email_success,
                push_success,
            )

            # -------------------------------------------------------------
            # Email failed
            #
            # Do NOT mark SENT.
            # Keep it pending and retry.
            # -------------------------------------------------------------

            if not email_success:

                reminder.status = (
                    ReminderStatus.PENDING
                )

                reminder.notification_sent_at = None

                reminder.update_timestamp()

                await reminder.save()

                _schedule_retry(
                    reminder
                )

                return

            # -------------------------------------------------------------
            # Successful email
            # -------------------------------------------------------------

            sent_at = datetime.now(
                timezone.utc
            )

            reminder.notification_sent_at = sent_at
            reminder.snooze_until = None

            repeat_type = _enum_value(
                reminder.repeat_type
            ).lower()

            # -------------------------------------------------------------
            # Recurring
            # -------------------------------------------------------------

            if repeat_type != "never":

                await _schedule_next_recurring(
                    reminder
                )

                return

            # -------------------------------------------------------------
            # One-time reminder
            # -------------------------------------------------------------

            reminder.status = (
                ReminderStatus.SENT
            )

            reminder.update_timestamp()

            await reminder.save()

            logger.info(
                "REMINDER COMPLETED SUCCESSFULLY | "
                "reminder=%s | email_sent_at=%s",
                reminder.id,
                sent_at.isoformat(),
            )

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception(
                "REMINDER JOB FAILED | reminder=%s",
                reminder_id,
            )

            # Recover the reminder if possible.
            try:
                if ObjectId.is_valid(
                    reminder_id
                ):
                    reminder = await Reminder.get(
                        ObjectId(
                            reminder_id
                        )
                    )

                    if reminder is not None:
                        reminder.status = (
                            ReminderStatus.PENDING
                        )

                        reminder.update_timestamp()

                        await reminder.save()

                        _schedule_retry(
                            reminder
                        )

            except Exception:
                logger.exception(
                    "Could not recover failed reminder | reminder=%s",
                    reminder_id,
                )


# ---------------------------------------------------------------------------
# Restore jobs from database
# ---------------------------------------------------------------------------

async def restore_reminder_jobs() -> None:
    """
    Restore reminder jobs after application start / Render deployment.

    MongoDB remains the source of truth.
    """

    if _scheduler is None:
        return

    logger.info(
        "Restoring reminder jobs from MongoDB..."
    )

    try:
        pending = await Reminder.find(
            Reminder.status
            == ReminderStatus.PENDING
        ).to_list()

        snoozed = await Reminder.find(
            Reminder.status
            == ReminderStatus.SNOOZED
        ).to_list()

        reminders = (
            pending
            + snoozed
        )

        restored = 0

        for reminder in reminders:

            try:
                status = _enum_value(
                    reminder.status
                ).lower()

                if (
                    status == "snoozed"
                    and reminder.snooze_until is not None
                ):
                    run_at = _as_utc(
                        reminder.snooze_until
                    )

                else:
                    run_at = _as_utc(
                        reminder.scheduled_time_utc
                    )

                if schedule_reminder(
                    reminder,
                    run_at=run_at,
                ):
                    restored += 1

            except Exception:
                logger.exception(
                    "Could not restore reminder | reminder=%s",
                    reminder.id,
                )

        logger.info(
            "REMINDER JOB RESTORE COMPLETE | "
            "active=%d | restored=%d",
            len(reminders),
            restored,
        )

    except Exception:
        logger.exception(
            "Failed restoring reminder jobs"
        )


# ---------------------------------------------------------------------------
# Recovery sweep
# ---------------------------------------------------------------------------

async def _recovery_sweep() -> None:
    """
    Safety net.

    If an active MongoDB reminder somehow has no APScheduler job,
    create one again.
    """

    if _scheduler is None:
        return

    try:
        pending = await Reminder.find(
            Reminder.status
            == ReminderStatus.PENDING
        ).to_list()

        snoozed = await Reminder.find(
            Reminder.status
            == ReminderStatus.SNOOZED
        ).to_list()

        reminders = (
            pending
            + snoozed
        )

        for reminder in reminders:

            if reminder.id is None:
                continue

            reminder_id = str(
                reminder.id
            )

            job_id = _reminder_job_id(
                reminder_id
            )

            existing_job = (
                _scheduler.get_job(
                    job_id
                )
            )

            if existing_job is not None:
                continue

            status = _enum_value(
                reminder.status
            ).lower()

            if (
                status == "snoozed"
                and reminder.snooze_until
            ):
                run_at = _as_utc(
                    reminder.snooze_until
                )
            else:
                run_at = _as_utc(
                    reminder.scheduled_time_utc
                )

            logger.warning(
                "RECOVERY: missing scheduler job | reminder=%s",
                reminder_id,
            )

            schedule_reminder(
                reminder,
                run_at=run_at,
            )

    except Exception:
        logger.exception(
            "Reminder recovery sweep failed"
        )


# ---------------------------------------------------------------------------
# Start scheduler
# ---------------------------------------------------------------------------

def start_scheduler() -> None:
    """
    Start APScheduler.

    Called from FastAPI lifespan after MongoDB initialization.
    """

    global _scheduler

    if (
        _scheduler is not None
        and _scheduler.running
    ):
        logger.info(
            "APScheduler already running"
        )
        return

    _scheduler = AsyncIOScheduler(
        timezone=timezone.utc,
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 300,
        },
    )

    # Safety/recovery job only.
    _scheduler.add_job(
        _recovery_sweep,
        trigger="interval",
        seconds=RECOVERY_INTERVAL_SECONDS,
        id="timora-recovery-sweep",
        name="Timora Reminder Recovery",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    _scheduler.start()

    logger.info(
        "APScheduler started successfully"
    )

    # Database is already initialized when start_scheduler()
    # is called from FastAPI lifespan.
    try:
        loop = asyncio.get_running_loop()

        loop.create_task(
            restore_reminder_jobs()
        )

    except RuntimeError:
        logger.exception(
            "No running event loop while restoring reminders"
        )


# ---------------------------------------------------------------------------
# Stop scheduler
# ---------------------------------------------------------------------------

def stop_scheduler() -> None:
    """Shutdown scheduler gracefully."""

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
            "Failed stopping APScheduler"
        )

    finally:
        _scheduler = None