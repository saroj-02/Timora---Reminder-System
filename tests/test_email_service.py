import pytest

from app.config import settings
from app.services import email_service


@pytest.mark.asyncio
async def test_resend_failure_falls_back_to_smtp(monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test")

    resend_calls = []
    smtp_calls = []

    async def resend_failure(recipient, subject, body):
        resend_calls.append(recipient)
        return False

    def smtp_success(recipient, subject, body):
        smtp_calls.append(recipient)
        return True

    monkeypatch.setattr(
        email_service,
        "_send_email_via_resend",
        resend_failure,
    )
    monkeypatch.setattr(
        email_service,
        "_send_email",
        smtp_success,
    )

    result = await email_service.send_reminder_email(
        recipient="user@example.com",
        title="Test reminder",
        scheduled_time="05 Sep 2026, 12:00 PM",
    )

    assert result is True
    assert resend_calls == ["user@example.com"]
    assert smtp_calls == ["user@example.com"]


@pytest.mark.asyncio
async def test_successful_resend_does_not_send_duplicate_smtp_email(monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test")

    smtp_calls = []

    async def resend_success(recipient, subject, body):
        return True

    def smtp_send(recipient, subject, body):
        smtp_calls.append(recipient)
        return True

    monkeypatch.setattr(
        email_service,
        "_send_email_via_resend",
        resend_success,
    )
    monkeypatch.setattr(
        email_service,
        "_send_email",
        smtp_send,
    )

    result = await email_service.send_reminder_email(
        recipient="user@example.com",
        title="Test reminder",
        scheduled_time="05 Sep 2026, 12:00 PM",
    )

    assert result is True
    assert smtp_calls == []