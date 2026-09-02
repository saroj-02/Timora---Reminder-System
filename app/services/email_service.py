"""
Timora – Email Notification Service

Sends reminder emails to users through Gmail SMTP.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from typing import Optional

from app.config import settings


logger = logging.getLogger(__name__)


def _clean(value: str | None) -> str:
    """Clean environment values safely."""
    if not value:
        return ""

    return value.strip()


def _clean_app_password(value: str | None) -> str:
    """
    Gmail App Passwords are sometimes copied with spaces.

    Example:
        abcd efgh ijkl mnop

    Gmail SMTP expects:
        abcdefghijklmnop
    """
    if not value:
        return ""

    return "".join(value.split())


def _send_email(
    recipient: str,
    subject: str,
    body: str,
) -> bool:
    """Send one email using the configured SMTP server."""

    smtp_host = _clean(settings.SMTP_HOST)
    smtp_username = _clean(settings.SMTP_USERNAME)
    smtp_password = _clean_app_password(settings.SMTP_PASSWORD)

    smtp_from_email = (
        _clean(settings.SMTP_FROM_EMAIL)
        or smtp_username
    )

    smtp_from_name = (
        _clean(settings.SMTP_FROM_NAME)
        or "Timora"
    )

    smtp_port = settings.SMTP_PORT

    # ─────────────────────────────────────────────
    # Configuration validation
    # ─────────────────────────────────────────────

    if not smtp_host:
        logger.error(
            "EMAIL ERROR: SMTP_HOST is empty."
        )
        return False

    if not smtp_username:
        logger.error(
            "EMAIL ERROR: SMTP_USERNAME is empty."
        )
        return False

    if not smtp_password:
        logger.error(
            "EMAIL ERROR: SMTP_PASSWORD is empty."
        )
        return False

    if not smtp_from_email:
        logger.error(
            "EMAIL ERROR: SMTP_FROM_EMAIL is empty."
        )
        return False

    recipient = _clean(recipient)

    if not recipient:
        logger.error(
            "EMAIL ERROR: recipient email is empty."
        )
        return False

    message = EmailMessage()

    message["From"] = formataddr(
        (
            smtp_from_name,
            smtp_from_email,
        )
    )

    message["To"] = recipient
    message["Subject"] = subject

    message.set_content(body)

    logger.info(
        "Connecting to SMTP server %s:%s...",
        smtp_host,
        smtp_port,
    )

    try:
        # ─────────────────────────────────────────
        # Gmail SMTP with STARTTLS
        # ─────────────────────────────────────────

        if settings.SMTP_USE_TLS:

            context = ssl.create_default_context()

            with smtplib.SMTP(
                smtp_host,
                smtp_port,
                timeout=30,
            ) as server:

                server.ehlo()

                logger.info(
                    "Starting SMTP TLS..."
                )

                server.starttls(
                    context=context
                )

                server.ehlo()

                logger.info(
                    "Authenticating SMTP user %s...",
                    smtp_username,
                )

                server.login(
                    smtp_username,
                    smtp_password,
                )

                logger.info(
                    "SMTP authentication successful."
                )

                server.send_message(
                    message
                )

        # ─────────────────────────────────────────
        # SMTP without TLS
        # ─────────────────────────────────────────

        else:

            with smtplib.SMTP(
                smtp_host,
                smtp_port,
                timeout=30,
            ) as server:

                server.ehlo()

                server.login(
                    smtp_username,
                    smtp_password,
                )

                server.send_message(
                    message
                )

        logger.info(
            "✅ EMAIL SENT successfully: %s -> %s",
            smtp_from_email,
            recipient,
        )

        return True

    except smtplib.SMTPAuthenticationError as exc:

        logger.error(
            "❌ Gmail SMTP authentication failed."
        )

        logger.error(
            "Check SMTP_USERNAME and Gmail App Password."
        )

        logger.error(
            "Do NOT use the normal Gmail account password."
        )

        logger.error(
            "SMTP authentication details: %s",
            exc,
        )

        return False

    except smtplib.SMTPConnectError as exc:

        logger.error(
            "❌ Could not connect to SMTP server %s:%s",
            smtp_host,
            smtp_port,
        )

        logger.error(
            "SMTP connection error: %s",
            exc,
        )

        return False

    except smtplib.SMTPServerDisconnected as exc:

        logger.error(
            "❌ SMTP server disconnected unexpectedly: %s",
            exc,
        )

        return False

    except smtplib.SMTPException as exc:

        logger.error(
            "❌ SMTP error while sending email: %s",
            exc,
        )

        return False

    except TimeoutError as exc:

        logger.error(
            "❌ SMTP connection timed out: %s",
            exc,
        )

        return False

    except OSError as exc:

        logger.error(
            "❌ Network/OS error while connecting to SMTP: %s",
            exc,
        )

        return False

    except Exception:

        logger.exception(
            "❌ Unexpected error while sending email."
        )

        return False


async def send_reminder_email(
    recipient: str,
    title: str,
    scheduled_time: str,
    category: Optional[str] = None,
    priority: Optional[str] = None,
) -> bool:
    """
    Send a Timora reminder email.

    SMTP is synchronous, so the operation runs in
    a worker thread to avoid blocking asyncio.
    """

    category_text = (
        category
        if category
        else "Reminder"
    )

    priority_text = (
        priority
        if priority
        else "Normal"
    )

    subject = (
        f"Timora Reminder: {title}"
    )

    body = f"""
Hello,

You have a reminder from Timora.

========================================

TASK
{title}

TIME
{scheduled_time}

CATEGORY
{category_text}

PRIORITY
{priority_text}

========================================

Your task is due now.

Open Timora to manage this reminder.

This email was automatically sent by
Timora – Smart Reminder.
""".strip()

    return await asyncio.to_thread(
        _send_email,
        recipient,
        subject,
        body,
    )