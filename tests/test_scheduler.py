"""
Background Scheduler and Recurring Reminder Tests:

- Due reminder detection
- Duplicate prevention (idempotency)
- Snoozed reminder re-arming
- Recurring reminder computation (Daily, Weekdays, Weekly, Monthly, Yearly)
- Timezone preserved in recurring occurrences
"""

from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest

from app.models.reminder import (
    Reminder,
    ReminderCategory,
    ReminderPriority,
    ReminderStatus,
    RepeatType,
)
from app.services.reminder_service import compute_next_occurrence
from app.services.scheduler_service import _process_due_reminders
from app.utils.timezone import now_utc


@pytest.mark.asyncio
async def test_due_reminder_processing_and_idempotency(
    auth_user: dict,
):
    # Insert a due reminder
    past_due_utc = (
        now_utc()
        - timedelta(minutes=5)
    )

    reminder = Reminder(
        user_id="test_user_id",
        title="Test Due Reminder",
        category=ReminderCategory.WORK,
        priority=ReminderPriority.HIGH,
        scheduled_time_utc=past_due_utc,
        timezone="Asia/Kolkata",
        repeat_type=RepeatType.NEVER,
        status=ReminderStatus.PENDING,
    )

    await reminder.insert()

    # Process due reminders
    await _process_due_reminders()

    # Verify the reminder still exists
    updated = await Reminder.get(
        reminder.id
    )

    assert updated is not None

    # Verify status changed to SENT
    # and notification_sent_at is set.
    assert updated.status == ReminderStatus.SENT
    assert (
        updated.notification_sent_at
        is not None
    )

    sent_time = (
        updated.notification_sent_at
    )

    # Run scheduler again.
    # Should be idempotent and not process
    # the reminder a second time.
    await _process_due_reminders()

    re_checked = await Reminder.get(
        reminder.id
    )

    assert re_checked is not None

    assert (
        re_checked.notification_sent_at
        == sent_time
    )

    assert (
        re_checked.status
        == ReminderStatus.SENT
    )


@pytest.mark.asyncio
async def test_snoozed_reminder_re_arming():
    # Insert a snoozed reminder whose
    # snooze time has passed.
    past_snooze = (
        now_utc()
        - timedelta(minutes=1)
    )

    reminder = Reminder(
        user_id="test_user_id",
        title="Snoozed Reminder",
        category=ReminderCategory.PERSONAL,
        priority=ReminderPriority.MEDIUM,
        scheduled_time_utc=(
            now_utc()
            - timedelta(hours=1)
        ),
        timezone="Asia/Kolkata",
        repeat_type=RepeatType.NEVER,
        status=ReminderStatus.SNOOZED,
        snooze_until=past_snooze,
    )

    await reminder.insert()

    # Scheduler process
    await _process_due_reminders()

    # Check that it was re-armed and processed
    updated = await Reminder.get(
        reminder.id
    )

    assert updated is not None

    assert updated.status in (
        ReminderStatus.SENT,
        ReminderStatus.PENDING,
    )

    assert (
        updated.snooze_until
        is None
    )


def test_recurring_daily_computation():
    now = now_utc()

    tz = "Asia/Kolkata"

    reminder = Reminder(
        user_id="test_user_id",
        title="Daily Standup",
        category=ReminderCategory.WORK,
        priority=ReminderPriority.MEDIUM,
        scheduled_time_utc=(
            now
            - timedelta(hours=1)
        ),
        timezone=tz,
        repeat_type=RepeatType.DAILY,
    )

    next_time = compute_next_occurrence(
        reminder
    )

    assert next_time is not None

    assert next_time > now

    # Hour in local timezone should match
    local_orig = (
        reminder.scheduled_time_utc.astimezone(
            ZoneInfo(tz)
        )
    )

    local_next = (
        next_time.astimezone(
            ZoneInfo(tz)
        )
    )

    assert (
        local_orig.hour
        == local_next.hour
    )

    assert (
        local_orig.minute
        == local_next.minute
    )


def test_recurring_weekdays_computation():
    tz = "America/New_York"

    now = now_utc()

    reminder = Reminder(
        user_id="test_user_id",
        title="Weekday Check-in",
        category=ReminderCategory.WORK,
        priority=ReminderPriority.MEDIUM,
        scheduled_time_utc=(
            now
            - timedelta(hours=1)
        ),
        timezone=tz,
        repeat_type=RepeatType.WEEKDAYS,
    )

    next_time = compute_next_occurrence(
        reminder
    )

    assert next_time is not None

    assert next_time > now

    local_next = (
        next_time.astimezone(
            ZoneInfo(tz)
        )
    )

    # 0 = Monday
    # 4 = Friday
    # 5 = Saturday
    # 6 = Sunday
    assert local_next.weekday() < 5


def test_recurring_weekly_computation():
    tz = "Europe/London"

    now = now_utc()

    reminder = Reminder(
        user_id="test_user_id",
        title="Weekly Review",
        category=ReminderCategory.STUDY,
        priority=ReminderPriority.LOW,
        scheduled_time_utc=(
            now
            - timedelta(hours=1)
        ),
        timezone=tz,
        repeat_type=RepeatType.WEEKLY,
    )

    next_time = compute_next_occurrence(
        reminder
    )

    assert next_time is not None

    assert next_time > now

    local_orig = (
        reminder.scheduled_time_utc.astimezone(
            ZoneInfo(tz)
        )
    )

    local_next = (
        next_time.astimezone(
            ZoneInfo(tz)
        )
    )

    assert (
        local_orig.weekday()
        == local_next.weekday()
    )