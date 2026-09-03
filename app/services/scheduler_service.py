"""
Timora – Reminder Scheduler Service

Responsibilities:
- Schedule individual reminders with APScheduler date jobs.
- Restore pending/snoozed reminders after application restart.
- Send reminder email at the actual scheduled time.
- Send web push notification on a best-effort basis.
- Retry failed email delivery.
- Re-arm recurring reminders.
- Keep a low-frequency recovery scan.

Important:
- scheduled_time_utc is always stored in UTC.
- Email is sent at scheduled_time_utc.
- reminder_before is NOT applied to email delivery.
- Browser/in-app "before" notification behavior remains separate.
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


# =============================================================================
# Configuration
# =============================================================================

RECOVERY_INTERVAL_SECONDS = 60

EMAIL_RETRY_SECONDS = 120

MISFIRE_GRACE_SECONDS = 300


# =============================================================================
# Global scheduler state
# =============================================================================

_scheduler: AsyncIOScheduler | None = None

_processing_reminders: set[str] = set()

_processing_lock = asyncio.Lock()


# =============================================================================
# General helpers
# =============================================================================


def _as_utc(
    value: datetime,
) -> datetime:
    """
    Return a timezone-aware UTC datetime.
    """

    if value.tzinfo is None:
        value = value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def _enum_value(
    value: Any,
) -> str:
    """
    Safely get the string value from an Enum or normal string.
    """

    return str(
        getattr(
            value,
            "value",
            value,
        )
    )


def _reminder_job_id(
    reminder_id: str,
) -> str:
    """
    Stable APScheduler job ID.
    """

    return f"timora-reminder-{reminder_id}"


def _retry_job_id(
    reminder_id: str,
) -> str:
    """
    Stable APScheduler retry job ID.
    """

    return f"timora-reminder-retry-{reminder_id}"


def _get_running_scheduler() -> AsyncIOScheduler | None:
    """
    Return the active APScheduler instance.

    Keeping the scheduler in a local variable after the None check
    prevents Pylance Optional-member-access errors.
    """

    scheduler = _scheduler

    if scheduler is None:
        return None

    if not scheduler.running:
        return None

    return scheduler


# =============================================================================
# Reminder time formatting
# =============================================================================


def _formatted_reminder_time(
    reminder: Reminder,
) -> str:
    """
    Format scheduled time using the reminder timezone.
    """

    try:
        timezone_name = (
            reminder.timezone
            or "UTC"
        )

        local_timezone = ZoneInfo(
            timezone_name
        )

        local_time = (
            _as_utc(
                reminder.scheduled_time_utc
            )
            .astimezone(
                local_timezone
            )
        )

        return local_time.strftime(
            "%d %b %Y, %I:%M %p"
        )

    except Exception:
        logger.exception(
            "Failed formatting reminder time | reminder=%s",
            reminder.id,
        )

        return (
            _as_utc(
                reminder.scheduled_time_utc
            )
            .strftime(
                "%d %b %Y, %I:%M %p UTC"
            )
        )


# =============================================================================
# User lookup
# =============================================================================


async def _get_reminder_user(
    reminder: Reminder,
) -> User | None:
    """
    Find the User who owns a reminder.
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
            "Failed to find reminder owner | reminder=%s",
            reminder.id,
        )
        return None


# =============================================================================
# Email notification
# =============================================================================


async def _send_email_notification(
    reminder: Reminder,
) -> bool:
    """
    Send the reminder email.

    Returns:
        True  -> email successfully accepted by SMTP.
        False -> email failed.
    """

    try:
        user = await _get_reminder_user(
            reminder
        )

        if user is None:
            logger.error(
                "EMAIL FAILED: reminder owner not found | reminder=%s",
                reminder.id,
            )
            return False

        recipient = str(
            user.email
        ).strip()

        if not recipient:
            logger.error(
                "EMAIL FAILED: user email is empty | reminder=%s",
                reminder.id,
            )
            return False

        scheduled_time = (
            _formatted_reminder_time(
                reminder
            )
        )

        category = _enum_value(
            reminder.category
        )

        priority = _enum_value(
            reminder.priority
        )

        logger.info(
            "EMAIL SEND START | reminder=%s | to=%s | scheduled=%s",
            reminder.id,
            recipient,
            scheduled_time,
        )

        result = await send_reminder_email(
            recipient,
            reminder.title,
            scheduled_time,
            category,
            priority,
        )

        if result:
            logger.info(
                "EMAIL SUCCESS | reminder=%s | to=%s",
                reminder.id,
                recipient,
            )
            return True

        logger.error(
            "EMAIL FAILED | reminder=%s | to=%s",
            reminder.id,
            recipient,
        )

        return False

    except Exception:
        logger.exception(
            "EMAIL EXCEPTION | reminder=%s",
            reminder.id,
        )
        return False


# =============================================================================
# Push notification
# =============================================================================


async def _send_push_notification(
    reminder: Reminder,
) -> bool:
    """
    Send web push notification.

    Push is best-effort.
    Email remains the primary delivery channel.
    """

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
            "PUSH FAILED/UNAVAILABLE | reminder=%s",
            reminder.id,
        )

        return False

    except Exception:
        logger.exception(
            "PUSH EXCEPTION | reminder=%s",
            reminder.id,
        )
        return False


# =============================================================================
# APScheduler job helpers
# =============================================================================


def remove_reminder_job(
    reminder_id: str,
) -> None:
    """
    Remove the scheduled APScheduler job for a reminder.
    """

    scheduler = _get_running_scheduler()

    if scheduler is None:
        return

    job_id = _reminder_job_id(
        str(reminder_id)
    )

    try:
        job = scheduler.get_job(
            job_id
        )

        if job is not None:
            scheduler.remove_job(
                job_id
            )

            logger.info(
                "REMINDER JOB REMOVED | reminder=%s",
                reminder_id,
            )

    except Exception:
        logger.exception(
            "Failed removing reminder job | reminder=%s",
            reminder_id,
        )


def _remove_retry_job(
    reminder_id: str,
) -> None:
    """
    Remove a pending retry job.
    """

    scheduler = _get_running_scheduler()

    if scheduler is None:
        return

    job_id = _retry_job_id(
        str(reminder_id)
    )

    try:
        job = scheduler.get_job(
            job_id
        )

        if job is not None:
            scheduler.remove_job(
                job_id
            )

            logger.debug(
                "REMINDER RETRY JOB REMOVED | reminder=%s",
                reminder_id,
            )

    except Exception:
        logger.exception(
            "Failed removing retry job | reminder=%s",
            reminder_id,
        )


def schedule_reminder(
    reminder: Reminder,
    run_at: datetime | None = None,
) -> bool:
    """
    Schedule one reminder as an APScheduler date job.

    Normal reminder:
        run_at = scheduled_time_utc

    Snoozed reminder:
        run_at = snooze_until

    If run_at is already in the past, execute approximately immediately.
    """

    scheduler = _get_running_scheduler()

    if scheduler is None:
        logger.warning(
            "Cannot schedule reminder: APScheduler is not running | reminder=%s",
            reminder.id,
        )
        return False

    reminder_id = str(
        reminder.id
    )

    if run_at is None:
        if (
            reminder.status
            == ReminderStatus.SNOOZED
            and reminder.snooze_until is not None
        ):
            run_at = reminder.snooze_until
        else:
            run_at = reminder.scheduled_time_utc

    run_at = _as_utc(
        run_at
    )

    now = datetime.now(
        timezone.utc
    )

    if run_at <= now:
        run_at = (
            now
            + timedelta(seconds=1)
        )

    job_id = _reminder_job_id(
        reminder_id
    )

    try:
        scheduler.add_job(
            _execute_reminder_job,
            trigger="date",
            run_date=run_at,
            args=[reminder_id],
            id=job_id,
            name=f"Reminder: {reminder.title}",
            replace_existing=True,
            misfire_grace_time=MISFIRE_GRACE_SECONDS,
        )

        logger.info(
            "REMINDER JOB SCHEDULED | reminder=%s | run_at=%s | title=%s",
            reminder_id,
            run_at.isoformat(),
            reminder.title,
        )

        return True

    except Exception:
        logger.exception(
            "Failed scheduling reminder | reminder=%s",
            reminder_id,
        )
        return False


# =============================================================================
# Retry handling
# =============================================================================


def _schedule_email_retry(
    reminder: Reminder,
) -> bool:
    """
    Schedule an email retry.
    """

    scheduler = _get_running_scheduler()

    if scheduler is None:
        logger.error(
            "Cannot schedule email retry: scheduler not running | reminder=%s",
            reminder.id,
        )
        return False

    reminder_id = str(
        reminder.id
    )

    retry_at = (
        datetime.now(timezone.utc)
        + timedelta(
            seconds=EMAIL_RETRY_SECONDS
        )
    )

    job_id = _retry_job_id(
        reminder_id
    )

    try:
        scheduler.add_job(
            _execute_email_retry_job,
            trigger="date",
            run_date=retry_at,
            args=[reminder_id],
            id=job_id,
            name=f"Email Retry: {reminder.title}",
            replace_existing=True,
            misfire_grace_time=MISFIRE_GRACE_SECONDS,
        )

        logger.warning(
            "EMAIL RETRY SCHEDULED | reminder=%s | retry_at=%s",
            reminder_id,
            retry_at.isoformat(),
        )

        return True

    except Exception:
        logger.exception(
            "Failed scheduling email retry | reminder=%s",
            reminder_id,
        )
        return False


async def _execute_email_retry_job(
    reminder_id: str,
) -> None:
    """
    Retry a failed reminder email.
    """

    reminder = await _get_reminder_by_id(
        reminder_id
    )

    if reminder is None:
        logger.error(
            "EMAIL RETRY ABORTED: reminder not found | reminder=%s",
            reminder_id,
        )
        return

    if reminder.status not in {
        ReminderStatus.PENDING,
        ReminderStatus.SNOOZED,
    }:
        logger.info(
            "EMAIL RETRY SKIPPED: reminder no longer active | reminder=%s | status=%s",
            reminder_id,
            _enum_value(reminder.status),
        )
        return

    logger.info(
        "EMAIL RETRY START | reminder=%s",
        reminder_id,
    )

    email_success = await _send_email_notification(
        reminder
    )

    if not email_success:
        _schedule_email_retry(
            reminder
        )
        return

    logger.info(
        "EMAIL RETRY SUCCESS | reminder=%s",
        reminder_id,
    )

    await _finish_successful_reminder(
        reminder
    )


# =============================================================================
# Database reminder lookup
# =============================================================================


async def _get_reminder_by_id(
    reminder_id: str,
) -> Reminder | None:
    """
    Load a reminder directly by MongoDB ObjectId.
    """

    try:
        if not ObjectId.is_valid(
            reminder_id
        ):
            logger.error(
                "Invalid reminder ID | reminder=%s",
                reminder_id,
            )
            return None

        return await Reminder.find_one(
            Reminder.id
            == ObjectId(reminder_id)
        )

    except Exception:
        logger.exception(
            "Failed loading reminder | reminder=%s",
            reminder_id,
        )
        return None


# =============================================================================
# Successful reminder processing
# =============================================================================


async def _finish_successful_reminder(
    reminder: Reminder,
) -> None:
    """
    Mark a reminder successfully processed.

    Recurring reminders are automatically re-armed.
    """

    try:
        repeat_type = _enum_value(
            reminder.repeat_type
        )

        # ---------------------------------------------------------------------
        # Recurring reminder
        # ---------------------------------------------------------------------

        if repeat_type != "never":
            next_occurrence = (
                compute_next_occurrence(
                    reminder
                )
            )

            if next_occurrence is None:
                logger.warning(
                    "Recurring reminder has no next occurrence | reminder=%s",
                    reminder.id,
                )

                reminder.status = (
                    ReminderStatus.SENT
                )

                reminder.notification_sent_at = (
                    datetime.now(timezone.utc)
                )

                reminder.snooze_until = None

                await reminder.save()

                return

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
            reminder.completed_at = None

            if hasattr(
                reminder,
                "update_timestamp",
            ):
                reminder.update_timestamp()

            await reminder.save()

            logger.info(
                "RECURRING REMINDER REARMED | reminder=%s | next=%s",
                reminder.id,
                reminder.scheduled_time_utc.isoformat(),
            )

            schedule_reminder(
                reminder,
                reminder.scheduled_time_utc,
            )

            return

        # ---------------------------------------------------------------------
        # One-time reminder
        # ---------------------------------------------------------------------

        reminder.status = (
            ReminderStatus.SENT
        )

        reminder.notification_sent_at = (
            datetime.now(timezone.utc)
        )

        reminder.snooze_until = None

        if hasattr(
            reminder,
            "update_timestamp",
        ):
            reminder.update_timestamp()

        await reminder.save()

        logger.info(
            "REMINDER MARKED SENT | reminder=%s | title=%s",
            reminder.id,
            reminder.title,
        )

    except Exception:
        logger.exception(
            "Failed finishing successful reminder | reminder=%s",
            reminder.id,
        )


# =============================================================================
# Main reminder execution
# =============================================================================


async def _execute_reminder_job(
    reminder_id: str,
) -> None:
    """
    Execute an individual scheduled reminder.
    """

    async with _processing_lock:
        if reminder_id in _processing_reminders:
            logger.warning(
                "REMINDER ALREADY PROCESSING | reminder=%s",
                reminder_id,
            )
            return

        _processing_reminders.add(
            reminder_id
        )

    try:
        logger.info(
            "REMINDER JOB FIRED | reminder=%s",
            reminder_id,
        )

        reminder = await _get_reminder_by_id(
            reminder_id
        )

        if reminder is None:
            logger.error(
                "REMINDER JOB ABORTED: reminder not found | reminder=%s",
                reminder_id,
            )
            return

        # ---------------------------------------------------------------------
        # Check status
        # ---------------------------------------------------------------------

        # IMPORTANT:
        # COMPLETED is intentionally NOT included here.
        #
        # A completed reminder that still has a scheduled email must be
        # allowed to send that email.
        if reminder.status not in {
            ReminderStatus.PENDING,
            ReminderStatus.SNOOZED,
            ReminderStatus.COMPLETED,
        }:
            logger.info(
                "REMINDER JOB SKIPPED | reminder=%s | status=%s",
                reminder.id,
                _enum_value(
                    reminder.status
                ),
            )
            return

        # ---------------------------------------------------------------------
        # Snooze handling
        # ---------------------------------------------------------------------

        if (
            reminder.status
            == ReminderStatus.SNOOZED
            and reminder.snooze_until is not None
        ):
            snooze_until = _as_utc(
                reminder.snooze_until
            )

            now = datetime.now(
                timezone.utc
            )

            if snooze_until > now:
                logger.info(
                    "REMINDER STILL SNOOZED | reminder=%s | snooze_until=%s",
                    reminder.id,
                    snooze_until.isoformat(),
                )

                schedule_reminder(
                    reminder,
                    snooze_until,
                )

                return

        # ---------------------------------------------------------------------
        # Remove old jobs
        # ---------------------------------------------------------------------

        remove_reminder_job(
            reminder_id
        )

        _remove_retry_job(
            reminder_id
        )

        logger.info(
            "REMINDER DUE | reminder=%s | title=%s | scheduled=%s",
            reminder.id,
            reminder.title,
            _as_utc(
                reminder.scheduled_time_utc
            ).isoformat(),
        )

        # ---------------------------------------------------------------------
        # Email FIRST
        # ---------------------------------------------------------------------

        email_success = (
            await _send_email_notification(
                reminder
            )
        )

        # ---------------------------------------------------------------------
        # Email failure
        # ---------------------------------------------------------------------

        if not email_success:
            logger.error(
                "REMINDER EMAIL FAILED | reminder=%s | keeping reminder PENDING",
                reminder.id,
            )

            # Do NOT mark SENT if email failed.
            reminder.status = (
                ReminderStatus.PENDING
            )

            if hasattr(
                reminder,
                "update_timestamp",
            ):
                reminder.update_timestamp()

            await reminder.save()

            _schedule_email_retry(
                reminder
            )

            return

        # ---------------------------------------------------------------------
        # Email succeeded
        # ---------------------------------------------------------------------

        logger.info(
            "REMINDER EMAIL DELIVERED | reminder=%s",
            reminder.id,
        )

        # ---------------------------------------------------------------------
        # Push is best effort
        # ---------------------------------------------------------------------

        push_success = (
            await _send_push_notification(
                reminder
            )
        )

        logger.info(
            "NOTIFICATION RESULT | reminder=%s | email=%s | push=%s",
            reminder.id,
            email_success,
            push_success,
        )

        # ---------------------------------------------------------------------
        # Mark successful / recurring
        # ---------------------------------------------------------------------

        await _finish_successful_reminder(
            reminder
        )

    except asyncio.CancelledError:
        raise

    except Exception:
        logger.exception(
            "REMINDER JOB EXCEPTION | reminder=%s",
            reminder_id,
        )

    finally:
        async with _processing_lock:
            _processing_reminders.discard(
                reminder_id
            )


# =============================================================================
# Recovery
# =============================================================================


async def restore_reminder_jobs() -> None:
    """
    Restore all pending/snoozed reminder jobs from MongoDB.

    APScheduler jobs are in memory, so they must be recreated after
    application restart.
    """

    scheduler = _get_running_scheduler()

    if scheduler is None:
        logger.warning(
            "Cannot restore reminder jobs: scheduler is not running"
        )
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

        logger.info(
            "RESTORE REMINDER JOBS | found=%d",
            len(reminders),
        )

        scheduled_count = 0

        for reminder in reminders:
            try:
                if (
                    reminder.status
                    == ReminderStatus.SNOOZED
                ):
                    if (
                        reminder.snooze_until
                        is None
                    ):
                        logger.warning(
                            "Skipping invalid snoozed reminder | reminder=%s",
                            reminder.id,
                        )
                        continue

                    run_at = _as_utc(
                        reminder.snooze_until
                    )

                else:
                    run_at = _as_utc(
                        reminder.scheduled_time_utc
                    )

                if schedule_reminder(
                    reminder,
                    run_at,
                ):
                    scheduled_count += 1

            except Exception:
                logger.exception(
                    "Failed restoring reminder job | reminder=%s",
                    reminder.id,
                )

        logger.info(
            "RESTORE REMINDER JOBS COMPLETE | scheduled=%d | total=%d",
            scheduled_count,
            len(reminders),
        )

    except asyncio.CancelledError:
        raise

    except Exception:
        logger.exception(
            "Failed restoring reminder jobs"
        )


# =============================================================================
# Recovery scan
# =============================================================================


async def _recovery_scan() -> None:
    """
    Safety-net scan.

    If an active reminder has no APScheduler job, recreate it.
    """

    scheduler = _get_running_scheduler()

    if scheduler is None:
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

        if not reminders:
            return

        now = datetime.now(
            timezone.utc
        )

        restored = 0

        for reminder in reminders:
            try:
                reminder_id = str(
                    reminder.id
                )

                job_id = _reminder_job_id(
                    reminder_id
                )

                existing_job = (
                    scheduler.get_job(
                        job_id
                    )
                )

                if existing_job is not None:
                    continue

                if (
                    reminder.status
                    == ReminderStatus.SNOOZED
                ):
                    if (
                        reminder.snooze_until
                        is None
                    ):
                        continue

                    run_at = _as_utc(
                        reminder.snooze_until
                    )

                else:
                    run_at = _as_utc(
                        reminder.scheduled_time_utc
                    )

                # Do not send directly here.
                # schedule_reminder() will execute it.
                if run_at <= now:
                    run_at = now + timedelta(
                        seconds=1
                    )

                if schedule_reminder(
                    reminder,
                    run_at,
                ):
                    restored += 1

            except Exception:
                logger.exception(
                    "Recovery failed for reminder | reminder=%s",
                    reminder.id,
                )

        if restored:
            logger.warning(
                "RECOVERY RESTORED JOBS | count=%d",
                restored,
            )

    except asyncio.CancelledError:
        raise

    except Exception:
        logger.exception(
            "Recovery scan failed"
        )


# =============================================================================
# Scheduler lifecycle
# =============================================================================


def start_scheduler() -> None:
    """
    Start APScheduler and restore reminder jobs.
    """

    global _scheduler

    if _get_running_scheduler() is not None:
        logger.info(
            "APScheduler already running."
        )
        return

    logger.info(
        "Starting Timora APScheduler..."
    )

    scheduler = AsyncIOScheduler(
        timezone="UTC"
    )

    scheduler.add_job(
        _recovery_scan,
        trigger="interval",
        seconds=RECOVERY_INTERVAL_SECONDS,
        id="timora-recovery-scan",
        name="Timora reminder recovery scan",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()

    _scheduler = scheduler

    logger.info(
        "Timora APScheduler started successfully."
    )

    # Restore existing MongoDB reminders after scheduler startup.
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(
            restore_reminder_jobs()
        )
    except RuntimeError:
        logger.warning(
            "No running event loop available for reminder restoration."
        )


def stop_scheduler() -> None:
    """
    Stop APScheduler.
    """

    global _scheduler

    scheduler = _scheduler

    if scheduler is None:
        return

    try:
        if scheduler.running:
            scheduler.shutdown(
                wait=False
            )

            logger.info(
                "Timora APScheduler stopped."
            )

    except Exception:
        logger.exception(
            "Failed stopping APScheduler"
        )

    finally:
        _scheduler = None

        _processing_reminders.clear()


def get_scheduler() -> AsyncIOScheduler | None:
    """
    Return the current scheduler instance.
    """

    return _scheduler


# =============================================================================
# Compatibility / recovery entry point
# =============================================================================


async def _process_due_reminders() -> None:
    """
    Compatibility entry point.

    Older Celery/worker code may import this function.

    The primary delivery mechanism is now individual APScheduler date jobs.
    This function only performs the recovery scan and does not duplicate
    normal reminder delivery.
    """

    await _recovery_scan()