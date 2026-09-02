"""
Timora – Email Notification Service

Sends reminder emails to users using SMTP.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


def _send_email(
    recipient: str,
    subject: str,
    body: str,
) -> bool:
    """Send one email using the configured SMTP server."""

    if not settings.SMTP_HOST:
        logger.warning("SMTP_HOST is not configured.")
        return False

    if not settings.SMTP_USERNAME:
        logger.warning("SMTP_USERNAME is not configured.")
        return False

    if not settings.SMTP_PASSWORD:
        logger.warning("SMTP_PASSWORD is not configured.")
        return False

    message = EmailMessage()

    message["From"] = formataddr(
        (
            settings.SMTP_FROM_NAME,
            settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME,
        )
    )

    message["To"] = recipient
    message["Subject"] = subject

    message.set_content(body)

    try:
        if settings.SMTP_USE_TLS:
            with smtplib.SMTP(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=20,
            ) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()

                server.login(
                    settings.SMTP_USERNAME,
                    settings.SMTP_PASSWORD,
                )

                server.send_message(message)

        else:
            with smtplib.SMTP(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=20,
            ) as server:
                server.ehlo()

                server.login(
                    settings.SMTP_USERNAME,
                    settings.SMTP_PASSWORD,
                )

                server.send_message(message)

        logger.info(
            "Reminder email sent to %s",
            recipient,
        )

        return True

    except Exception:
        logger.exception(
            "Failed to send email to %s",
            recipient,
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

    The SMTP operation is synchronous, so it runs in a worker thread
    to avoid blocking the asyncio event loop.
    """

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

    import asyncio

    return await asyncio.to_thread(
        _send_email,
        recipient,
        subject,
        body,
    )