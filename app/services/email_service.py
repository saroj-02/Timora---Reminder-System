"""
Timora – Email Notification Service

Reliable SMTP email delivery with detailed logging.
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


def _clean(value: object) -> str:
    """Convert configuration value to a clean string."""
    if value is None:
        return ""
    return str(value).strip()


def _clean_password(value: object) -> str:
    """
    Gmail App Passwords are often displayed as:

        abcd efgh ijkl mnop

    Gmail expects:

        abcdefghijklmnop
    """
    return "".join(_clean(value).split())


def smtp_configuration_status() -> dict[str, object]:
    """Return SMTP configuration without exposing the password."""

    host = _clean(settings.SMTP_HOST)
    username = _clean(settings.SMTP_USERNAME)
    password = _clean_password(settings.SMTP_PASSWORD)
    from_email = _clean(settings.SMTP_FROM_EMAIL) or username

    return {
        "host": host,
        "port": settings.SMTP_PORT,
        "username_configured": bool(username),
        "password_configured": bool(password),
        "password_length": len(password),
        "from_email_configured": bool(from_email),
        "tls": settings.SMTP_USE_TLS,
    }


def _send_email(
    recipient: str,
    subject: str,
    body: str,
) -> bool:

    host = _clean(settings.SMTP_HOST)
    username = _clean(settings.SMTP_USERNAME)
    password = _clean_password(settings.SMTP_PASSWORD)

    from_email = (
        _clean(settings.SMTP_FROM_EMAIL)
        or username
    )

    from_name = (
        _clean(settings.SMTP_FROM_NAME)
        or "Timora"
    )

    recipient = recipient.strip()

    # ─────────────────────────────────────────────
    # Configuration validation
    # ─────────────────────────────────────────────

    if not host:
        logger.error(
            "EMAIL FAILED: SMTP_HOST is missing."
        )
        return False

    if not username:
        logger.error(
            "EMAIL FAILED: SMTP_USERNAME is missing."
        )
        return False

    if not password:
        logger.error(
            "EMAIL FAILED: SMTP_PASSWORD is missing."
        )
        return False

    if not from_email:
        logger.error(
            "EMAIL FAILED: SMTP_FROM_EMAIL is missing."
        )
        return False

    if not recipient:
        logger.error(
            "EMAIL FAILED: recipient is empty."
        )
        return False

    logger.info(
        "SMTP configuration: host=%s port=%s "
        "username_configured=%s "
        "password_configured=%s "
        "password_length=%s "
        "from_email=%s TLS=%s",
        host,
        settings.SMTP_PORT,
        bool(username),
        bool(password),
        len(password),
        from_email,
        settings.SMTP_USE_TLS,
    )

    # Gmail App Password should normally be 16 characters.
    if host.lower() == "smtp.gmail.com":
        if len(password) != 16:
            logger.warning(
                "Gmail App Password length is %s after "
                "removing spaces. Expected 16 characters.",
                len(password),
            )

    message = EmailMessage()

    message["From"] = formataddr(
        (
            from_name,
            from_email,
        )
    )

    message["To"] = recipient
    message["Subject"] = subject

    message.set_content(body)

    context = ssl.create_default_context()

    try:
        logger.info(
            "Connecting to SMTP server %s:%s...",
            host,
            settings.SMTP_PORT,
        )

        with smtplib.SMTP(
            host=host,
            port=settings.SMTP_PORT,
            timeout=30,
        ) as server:

            server.ehlo()

            if settings.SMTP_USE_TLS:
                logger.info(
                    "Starting SMTP TLS..."
                )

                server.starttls(
                    context=context
                )

                server.ehlo()

            logger.info(
                "Authenticating SMTP user %s...",
                username,
            )

            server.login(
                username,
                password,
            )

            logger.info(
                "SMTP authentication successful."
            )

            server.send_message(
                message
            )

        logger.info(
            "EMAIL SUCCESS: reminder email sent to %s",
            recipient,
        )

        return True

    except smtplib.SMTPAuthenticationError as exc:

        logger.error(
            "EMAIL FAILED: Gmail/SMTP authentication "
            "was rejected. Code=%s error=%s",
            exc.smtp_code,
            exc.smtp_error,
        )

        return False

    except smtplib.SMTPConnectError as exc:

        logger.error(
            "EMAIL FAILED: unable to connect to SMTP "
            "server. Code=%s error=%s",
            exc.smtp_code,
            exc.smtp_error,
        )

        return False

    except smtplib.SMTPServerDisconnected:

        logger.exception(
            "EMAIL FAILED: SMTP server disconnected."
        )

        return False

    except smtplib.SMTPException:

        logger.exception(
            "EMAIL FAILED: SMTP protocol error."
        )

        return False

    except (TimeoutError, OSError):

        logger.exception(
            "EMAIL FAILED: SMTP network/timeout error."
        )

        return False

    except Exception:

        logger.exception(
            "EMAIL FAILED: unexpected error."
        )

        return False


async def send_reminder_email(
    recipient: str,
    title: str,
    scheduled_time: str,
    category: Optional[str] = None,
    priority: Optional[str] = None,
) -> bool:

    category_text = category or "Reminder"
    priority_text = priority or "Normal"

    subject = f"🔔 Timora Reminder: {title}"

    body = f"""
Hello,

You have a reminder from Timora.

━━━━━━━━━━━━━━━━━━━━━━━━━━

🔔 TASK
{title}

🕐 TIME
{scheduled_time}

📂 CATEGORY
{category_text}

⚡ PRIORITY
{priority_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━

Your task is due now.

Open Timora to manage this reminder.

This email was automatically sent by Timora – Smart Reminder.
""".strip()

    return await asyncio.to_thread(
        _send_email,
        recipient,
        subject,
        body,
    )