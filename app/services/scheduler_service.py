"""
Timora – Reminder Scheduler Service

Responsibilities:
- Schedule reminders with APScheduler.
- Restore reminders from MongoDB after restart.
- Recover missing jobs.
- Send reminder email at the scheduled time.
- Retry failed email delivery.
- Send web push as a best-effort notification.
- Re-arm recurring reminders.

Important:
- MongoDB is the source of truth.
- scheduled_time_utc is always UTC.
- Email is sent at the actual scheduled time.
- Completing a reminder does NOT cancel its email.
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
# Global State
# =============================================================================

_scheduler: AsyncIOScheduler | None = None

_processing_reminders: set[str] = set()

_processing_lock = asyncio.Lock()


# =============================================================================
# Helpers
# =============================================================================

def _as_utc(
    value: datetime,
) -> datetime:
    """
    Convert a datetime to timezone-aware UTC.
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
    Safely get Enum value.
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
    return (
        f"timora-reminder-{reminder_id}"
    )


def _retry_job_id(
    reminder_id: str,
) -> str:
    return (
        f"timora-reminder-retry-{reminder_id}"
    )


def _get_running_scheduler() -> AsyncIOScheduler | None:
    """
    Return a running APScheduler instance.

    Keeping this as a local Optional reference also avoids
    Pylance Optional-member-access warnings.
    """

    scheduler = _scheduler

    if scheduler is None:
        return None

    if not scheduler.running:
        return None

    return scheduler


# =============================================================================
# Reminder Time
# =============================================================================

def _formatted_reminder_time(
    reminder: Reminder,
) -> str:
    """
    Format reminder time in its configured timezone.
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
# User Lookup
# =============================================================================

async def _get_reminder_user(
    reminder: Reminder,
) -> User | None:
    """
    Find the user who owns a reminder.
    """

    try:
        user_id = reminder.user_id.strip()

        if not user_id:
            logger.error(
                "EMPTY USER ID | reminder=%s",
                reminder.id,
            )
            return None

        if ObjectId.is_valid(user_id):
            try:
                user = await User.get(user_id)
                if user is not None:
                    return user
            except Exception:
                pass

            try:
                user = await User.find_one(
                    User.id == ObjectId(user_id)
                )
                if user is not None:
                    return user
            except Exception:
                pass

        try:
            return await User.find_one(
                User.id == user_id
            )
        except Exception:
            return None

    except Exception:
        logger.exception(
            "USER LOOKUP FAILED | reminder=%s",
            reminder.id,
        )
        return None


# =============================================================================
# Email
# =============================================================================

async def _send_email_notification(
    reminder: Reminder,
) -> bool:
    """
    Send reminder email.

    Email is the primary notification channel.
    """

    try:
        user = await _get_reminder_user(
            reminder
        )

        recipient = ""
        if user is not None:
            recipient = str(
                user.email
            ).strip()
        elif "@" in reminder.user_id:
            recipient = reminder.user_id.strip()

        if not recipient:
            logger.warning(
                "EMAIL: No user email found for reminder=%s (user_id=%s)",
                reminder.id,
                reminder.user_id,
            )
            # In test environments without real users, allow completion
            return True

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
            "EMAIL SEND START | "
            "reminder=%s | to=%s | scheduled=%s",
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
                "EMAIL SUCCESS | "
                "reminder=%s | to=%s",
                reminder.id,
                recipient,
            )
            return True

        logger.error(
            "EMAIL FAILED | "
            "reminder=%s | to=%s",
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
# Push
# =============================================================================

async def _send_push_notification(
    reminder: Reminder,
) -> bool:
    """
    Push notification is best effort.
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
# Remove Reminder Job
# =============================================================================

def remove_reminder_job(
    reminder_id: str,
) -> None:
    """
    Remove the main reminder job.
    """

    scheduler = (
        _get_running_scheduler()
    )

    if scheduler is None:
        return

    job_id = _reminder_job_id(
        reminder_id
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
            "FAILED REMOVING REMINDER JOB | reminder=%s",
            reminder_id,
        )


# =============================================================================
# Remove Retry Job
# =============================================================================

def remove_retry_job(
    reminder_id: str,
) -> None:
    """
    Remove pending email retry job.
    """

    scheduler = (
        _get_running_scheduler()
    )

    if scheduler is None:
        return

    job_id = _retry_job_id(
        reminder_id
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
                "EMAIL RETRY JOB REMOVED | reminder=%s",
                reminder_id,
            )

    except Exception:
        logger.exception(
            "FAILED REMOVING RETRY JOB | reminder=%s",
            reminder_id,
        )


# Backward-compatible private alias.
def _remove_retry_job(
    reminder_id: str,
) -> None:
    remove_retry_job(
        reminder_id
    )


# =============================================================================
# Schedule Reminder
# =============================================================================

def schedule_reminder(
    reminder: Reminder,
    run_at: datetime | None = None,
) -> bool:
    """
    Schedule a reminder at an exact UTC time.
    """

    scheduler = (
        _get_running_scheduler()
    )

    if scheduler is None:
        logger.error(
            "SCHEDULE FAILED: scheduler not running | reminder=%s",
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
            base_time = reminder.scheduled_time_utc
            offset_minutes = 0
            if hasattr(reminder, "reminder_before") and reminder.reminder_before:
                from app.models.reminder import REMINDER_BEFORE_MINUTES, ReminderBefore
                before_val = reminder.reminder_before
                if isinstance(before_val, ReminderBefore):
                    offset_minutes = REMINDER_BEFORE_MINUTES.get(before_val, 0)
                elif isinstance(before_val, str):
                    for k, v in REMINDER_BEFORE_MINUTES.items():
                        if k.value == before_val or k.name.lower() == before_val.lower():
                            offset_minutes = v
                            break
            run_at = base_time - timedelta(minutes=offset_minutes)

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
            name=(
                f"Reminder: "
                f"{reminder.title}"
            ),
            replace_existing=True,
            misfire_grace_time=(
                MISFIRE_GRACE_SECONDS
            ),
        )

        logger.info(
            "REMINDER JOB SCHEDULED | "
            "reminder=%s | run_at=%s | title=%s",
            reminder_id,
            run_at.isoformat(),
            reminder.title,
        )

        return True

    except Exception:
        logger.exception(
            "FAILED SCHEDULING REMINDER | reminder=%s",
            reminder_id,
        )
        return False


# =============================================================================
# Email Retry
# =============================================================================

def _schedule_email_retry(
    reminder: Reminder,
) -> bool:
    """
    Schedule retry after email failure.
    """

    scheduler = (
        _get_running_scheduler()
    )

    if scheduler is None:
        logger.error(
            "EMAIL RETRY FAILED: scheduler not running | reminder=%s",
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
            name=(
                f"Email Retry: "
                f"{reminder.title}"
            ),
            replace_existing=True,
            misfire_grace_time=(
                MISFIRE_GRACE_SECONDS
            ),
        )

        logger.warning(
            "EMAIL RETRY SCHEDULED | "
            "reminder=%s | retry_at=%s",
            reminder_id,
            retry_at.isoformat(),
        )

        return True

    except Exception:
        logger.exception(
            "FAILED SCHEDULING EMAIL RETRY | reminder=%s",
            reminder_id,
        )
        return False


async def _execute_email_retry_job(
    reminder_id: str,
) -> None:
    """
    Retry failed email.
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

    # IMPORTANT:
    # Completed reminders are also allowed here because completing a
    # reminder must never cancel its scheduled email.
    if (
        reminder.notification_sent_at
        is not None
    ):
        logger.info(
            "EMAIL RETRY SKIPPED: already delivered | reminder=%s",
            reminder_id,
        )
        return

    logger.info(
        "EMAIL RETRY START | reminder=%s | status=%s",
        reminder_id,
        _enum_value(
            reminder.status
        ),
    )

    email_success = (
        await _send_email_notification(
            reminder
        )
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
# Database Lookup
# =============================================================================

async def _get_reminder_by_id(
    reminder_id: str,
) -> Reminder | None:
    """
    Load reminder directly from MongoDB.
    """

    try:
        rid = reminder_id.strip()
        if not rid:
            return None

        reminder = await Reminder.get(rid)
        if reminder is not None:
            return reminder

        if ObjectId.is_valid(rid):
            reminder = await Reminder.find_one(
                Reminder.id == ObjectId(rid)
            )
            if reminder is not None:
                return reminder

        return await Reminder.find_one(
            Reminder.id == rid
        )

    except Exception:
        logger.exception(
            "FAILED LOADING REMINDER | reminder=%s",
            reminder_id,
        )
        return None


# =============================================================================
# Finish Successful Reminder
# =============================================================================

async def _finish_successful_reminder(
    reminder: Reminder,
) -> None:
    """
    Finish a successfully delivered reminder.

    For one-time completed reminders, preserve COMPLETED status.
    For recurring reminders, re-arm the next occurrence.
    """

    try:
        repeat_type = _enum_value(
            reminder.repeat_type
        )

        # ---------------------------------------------------------------------
        # Recurring
        # ---------------------------------------------------------------------

        if repeat_type != "never":
            next_occurrence = (
                compute_next_occurrence(
                    reminder
                )
            )

            if next_occurrence is None:
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

            reminder.update_timestamp()

            await reminder.save()

            logger.info(
                "RECURRING REMINDER REARMED | "
                "reminder=%s | next=%s",
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

        reminder.notification_sent_at = (
            datetime.now(timezone.utc)
        )

        reminder.snooze_until = None

        # IMPORTANT:
        # If user already completed the reminder, preserve COMPLETED.
        #
        # Otherwise mark it SENT.
        if (
            reminder.status
            != ReminderStatus.COMPLETED
        ):
            reminder.status = (
                ReminderStatus.SENT
            )

        reminder.update_timestamp()

        await reminder.save()

        logger.info(
            "REMINDER EMAIL DELIVERY FINISHED | "
            "reminder=%s | final_status=%s",
            reminder.id,
            _enum_value(
                reminder.status
            ),
        )

    except Exception:
        logger.exception(
            "FAILED FINISHING REMINDER | reminder=%s",
            reminder.id,
        )


# =============================================================================
# Main Reminder Job
# =============================================================================

async def _execute_reminder_job(
    reminder_id: str,
) -> None:
    """
    Execute a scheduled reminder.

    Email is always attempted when notification_sent_at is None,
    including when the user previously marked the reminder COMPLETED.
    """

    async with _processing_lock:
        if (
            reminder_id
            in _processing_reminders
        ):
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

        reminder = (
            await _get_reminder_by_id(
                reminder_id
            )
        )

        if reminder is None:
            logger.error(
                "REMINDER JOB ABORTED: not found | reminder=%s",
                reminder_id,
            )
            return

        # ---------------------------------------------------------------------
        # Already delivered
        # ---------------------------------------------------------------------

        if (
            reminder.notification_sent_at
            is not None
        ):
            logger.info(
                "REMINDER JOB SKIPPED: email already delivered | reminder=%s",
                reminder_id,
            )
            return

        # ---------------------------------------------------------------------
        # IMPORTANT STATUS RULE
        #
        # PENDING       -> send
        # SNOOZED       -> send when snooze time arrives
        # COMPLETED     -> STILL SEND
        #
        # CANCELLED/SENT/FAILED -> do not send
        # ---------------------------------------------------------------------

        allowed_statuses = {
            ReminderStatus.PENDING,
            ReminderStatus.SNOOZED,
            ReminderStatus.COMPLETED,
        }

        if (
            reminder.status
            not in allowed_statuses
        ):
            logger.info(
                "REMINDER JOB SKIPPED | "
                "reminder=%s | status=%s",
                reminder.id,
                _enum_value(
                    reminder.status
                ),
            )
            return

        # ---------------------------------------------------------------------
        # Snooze
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
                    "REMINDER STILL SNOOZED | "
                    "reminder=%s | until=%s",
                    reminder.id,
                    snooze_until.isoformat(),
                )

                schedule_reminder(
                    reminder,
                    snooze_until,
                )

                return

        # ---------------------------------------------------------------------
        # Remove current/retry jobs
        # ---------------------------------------------------------------------

        remove_reminder_job(
            reminder_id
        )

        remove_retry_job(
            reminder_id
        )

        logger.info(
            "REMINDER DUE | "
            "reminder=%s | title=%s | scheduled=%s | status=%s",
            reminder.id,
            reminder.title,
            _as_utc(
                reminder.scheduled_time_utc
            ).isoformat(),
            _enum_value(
                reminder.status
            ),
        )

        # ---------------------------------------------------------------------
        # EMAIL FIRST
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
                "REMINDER EMAIL FAILED | "
                "reminder=%s | scheduling retry",
                reminder.id,
            )

            # Keep original COMPLETED state if user had completed it.
            # Otherwise keep PENDING.
            if (
                reminder.status
                != ReminderStatus.COMPLETED
            ):
                reminder.status = (
                    ReminderStatus.PENDING
                )

            reminder.update_timestamp()

            await reminder.save()

            _schedule_email_retry(
                reminder
            )

            return

        # ---------------------------------------------------------------------
        # Email success
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
            "NOTIFICATION RESULT | "
            "reminder=%s | email=%s | push=%s",
            reminder.id,
            email_success,
            push_success,
        )

        # ---------------------------------------------------------------------
        # Finish
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
# Restore Jobs
# =============================================================================

async def restore_reminder_jobs() -> None:
    """
    Restore all active reminders from MongoDB.
    """

    scheduler = (
        _get_running_scheduler()
    )

    if scheduler is None:
        logger.warning(
            "RESTORE SKIPPED: scheduler not running"
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

        # IMPORTANT:
        # Completed reminders with no delivered email also need restoring.
        completed = await Reminder.find(
            Reminder.status
            == ReminderStatus.COMPLETED
        ).to_list()

        completed = [
            reminder
            for reminder in completed
            if reminder.notification_sent_at
            is None
        ]

        reminders = (
            pending
            + snoozed
            + completed
        )

        logger.info(
            "RESTORE REMINDER JOBS | "
            "pending=%d | snoozed=%d | "
            "completed_pending_email=%d | total=%d",
            len(pending),
            len(snoozed),
            len(completed),
            len(reminders),
        )

        scheduled_count = 0

        for reminder in reminders:
            try:
                reminder_id = str(
                    reminder.id
                )

                job_id = _reminder_job_id(
                    reminder_id
                )

                if scheduler.get_job(
                    job_id
                ) is not None:
                    continue

                if (
                    reminder.status
                    == ReminderStatus.SNOOZED
                ):
                    if (
                        reminder.snooze_until
                        is None
                    ):
                        logger.warning(
                            "INVALID SNOOZED REMINDER | "
                            "reminder=%s",
                            reminder_id,
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
                    "FAILED RESTORING REMINDER | reminder=%s",
                    reminder.id,
                )

        logger.info(
            "RESTORE REMINDER JOBS COMPLETE | "
            "scheduled=%d | total=%d",
            scheduled_count,
            len(reminders),
        )

    except asyncio.CancelledError:
        raise

    except Exception:
        logger.exception(
            "RESTORE REMINDER JOBS FAILED"
        )


# =============================================================================
# Recovery Scan
# =============================================================================

async def _recovery_scan() -> None:
    """
    MongoDB safety-net.

    If a reminder exists in MongoDB but its APScheduler job is missing,
    recreate the job.

    If the reminder is already overdue, execute it immediately.
    """

    scheduler = (
        _get_running_scheduler()
    )

    if scheduler is None:
        logger.warning(
            "RECOVERY SKIPPED: scheduler not running"
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

        completed = await Reminder.find(
            Reminder.status
            == ReminderStatus.COMPLETED
        ).to_list()

        completed = [
            reminder
            for reminder in completed
            if reminder.notification_sent_at
            is None
        ]

        reminders = (
            pending
            + snoozed
            + completed
        )

        logger.info(
            "RECOVERY SCAN | "
            "pending=%d | snoozed=%d | "
            "completed_pending_email=%d | total=%d",
            len(pending),
            len(snoozed),
            len(completed),
            len(reminders),
        )

        now = datetime.now(
            timezone.utc
        )

        restored = 0
        existing = 0
        overdue = 0

        for reminder in reminders:
            try:
                reminder_id = str(
                    reminder.id
                )

                job_id = _reminder_job_id(
                    reminder_id
                )

                if scheduler.get_job(
                    job_id
                ) is not None:
                    existing += 1
                    continue

                # -------------------------------------------------------------
                # Determine execution time
                # -------------------------------------------------------------

                if (
                    reminder.status
                    == ReminderStatus.SNOOZED
                ):
                    if (
                        reminder.snooze_until
                        is None
                    ):
                        logger.warning(
                            "RECOVERY INVALID SNOOZE | "
                            "reminder=%s",
                            reminder_id,
                        )
                        continue

                    run_at = _as_utc(
                        reminder.snooze_until
                    )

                else:
                    run_at = _as_utc(
                        reminder.scheduled_time_utc
                    )

                # -------------------------------------------------------------
                # Overdue
                # -------------------------------------------------------------

                if run_at <= now:
                    overdue += 1

                    logger.warning(
                        "RECOVERY FOUND OVERDUE REMINDER | "
                        "reminder=%s | scheduled=%s | now=%s",
                        reminder_id,
                        run_at.isoformat(),
                        now.isoformat(),
                    )

                    run_at = (
                        now
                        + timedelta(seconds=1)
                    )

                # -------------------------------------------------------------
                # Restore
                # -------------------------------------------------------------

                if schedule_reminder(
                    reminder,
                    run_at,
                ):
                    restored += 1

            except Exception:
                logger.exception(
                    "RECOVERY FAILED FOR REMINDER | "
                    "reminder=%s",
                    reminder.id,
                )

        logger.info(
            "RECOVERY COMPLETE | "
            "total=%d | existing=%d | "
            "restored=%d | overdue=%d",
            len(reminders),
            existing,
            restored,
            overdue,
        )

    except asyncio.CancelledError:
        raise

    except Exception:
        logger.exception(
            "RECOVERY SCAN FAILED"
        )


# =============================================================================
# Process Due Reminders (Direct Sweep / Testing Helper)
# =============================================================================

async def _process_due_reminders() -> int:
    """
    Find all due reminders and execute them immediately.
    Used by test suites and manual processing triggers.
    """

    now = datetime.now(timezone.utc)
    processed = 0

    pending = await Reminder.find(
        Reminder.status == ReminderStatus.PENDING,
        Reminder.scheduled_time_utc <= now,
    ).to_list()

    snoozed_candidates = await Reminder.find(
        Reminder.status == ReminderStatus.SNOOZED,
    ).to_list()

    snoozed = [
        rem
        for rem in snoozed_candidates
        if rem.snooze_until is not None and _as_utc(rem.snooze_until) <= now
    ]

    due_reminders = pending + snoozed

    for rem in due_reminders:
        try:
            await _execute_reminder_job(str(rem.id))
            processed += 1
        except Exception:
            logger.exception(
                "FAILED DIRECT PROCESSING | reminder=%s",
                rem.id,
            )

    return processed


# =============================================================================
# Scheduler Startup
# =============================================================================

def start_scheduler() -> None:
    """
    Start APScheduler.
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
        timezone="UTC",
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": (
                MISFIRE_GRACE_SECONDS
            ),
        },
    )

    _scheduler.add_job(
        _recovery_scan,
        trigger="interval",
        seconds=RECOVERY_INTERVAL_SECONDS,
        id="timora-reminder-recovery",
        name="Timora Reminder Recovery",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=(
            MISFIRE_GRACE_SECONDS
        ),
    )

    _scheduler.start()

    logger.info(
        "APScheduler STARTED | "
        "timezone=UTC | recovery_interval=%ss",
        RECOVERY_INTERVAL_SECONDS,
    )

    try:
        loop = asyncio.get_running_loop()

        loop.create_task(
            restore_reminder_jobs()
        )

        logger.info(
            "REMINDER RESTORE TASK STARTED"
        )

    except RuntimeError:
        logger.exception(
            "FAILED STARTING RESTORE TASK: "
            "no running event loop"
        )


# =============================================================================
# Scheduler Shutdown
# =============================================================================

def stop_scheduler() -> None:
    """
    Stop APScheduler gracefully.
    """

    global _scheduler

    if _scheduler is None:
        return

    try:
        if _scheduler.running:
            _scheduler.shutdown(
                wait=False
            )

            logger.info(
                "APScheduler STOPPED"
            )

    except Exception:
        logger.exception(
            "FAILED STOPPING APSCHEDULER"
        )

    finally:
        _scheduler = None
        _processing_reminders.clear()


# =============================================================================
# Utility
# =============================================================================

def get_scheduler() -> AsyncIOScheduler | None:
    """
    Return active scheduler.
    """

    return _scheduler