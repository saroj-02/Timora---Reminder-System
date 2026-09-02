"""
Timora – Notification Service

Handles Web Push delivery using pywebpush + VAPID.
"""

# cspell:ignore pywebpush webpush

from __future__ import annotations

import json
import logging
from typing import Optional

from app.config import settings
from app.models.push_subscription import PushSubscription
from app.models.reminder import Reminder


logger = logging.getLogger(__name__)


async def send_web_push(
    subscription: PushSubscription,
    title: str,
    body: str,
    reminder_id: Optional[str] = None,
    actions: Optional[list[dict]] = None,
) -> bool:
    """
    Send a Web Push notification.

    Returns:
        True  -> notification successfully sent
        False -> notification failed
    """

    if not settings.vapid_configured:

        logger.warning(
            "VAPID keys not configured — "
            "skipping push notification"
        )

        return False

    try:

        from pywebpush import (
            webpush,
            WebPushException,
        )

    except ImportError:

        logger.error(
            "pywebpush is not installed"
        )

        return False

    payload = {

        "title": title,

        "body": body,

        "icon": (
            "/static/icons/icon-192.png"
        ),

        "badge": (
            "/static/icons/badge-72.png"
        ),

        "tag": (
            f"reminder-{reminder_id}"
            if reminder_id
            else "timora"
        ),

        "requireInteraction": True,

        "silent": False,

        "renotify": True,

        "vibrate": [
            250,
            120,
            250,
            120,
            500,
        ],

        "data": {

            "reminder_id": reminder_id,

            "url": (
                f"{settings.APP_URL}"
                f"/reminders/{reminder_id}"
                if reminder_id
                else settings.APP_URL
            ),
        },

        "actions": (
            actions
            or [
                {
                    "action": "done",
                    "title": "✅ Done",
                },
                {
                    "action": "snooze",
                    "title": "⏰ Snooze 10m",
                },
            ]
        ),
    }

    subscription_info = {

        "endpoint": subscription.endpoint,

        "keys": {

            "p256dh": subscription.p256dh,

            "auth": subscription.auth,
        },
    }

    try:

        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=(
                settings.VAPID_PRIVATE_KEY
            ),
            vapid_claims={
                "sub": (
                    f"mailto:"
                    f"{settings.VAPID_CLAIMS_EMAIL}"
                ),
            },
        )

        logger.info(
            "Push sent to endpoint: %s...",
            subscription.endpoint[:40],
        )

        return True

    except WebPushException as exc:

        err_str = str(exc)

        if (
            "410" in err_str
            or "404" in err_str
        ):

            logger.info(
                "Removing expired push subscription: %s",
                subscription.id,
            )

            await subscription.delete()

        else:

            logger.error(
                "Web Push failed: %s",
                exc,
            )

        return False

    except Exception as exc:

        logger.error(
            "Push notification failed: %s",
            exc,
        )

        return False


async def notify_user(
    user_id: str,
    title: str,
    body: str,
    reminder_id: Optional[str] = None,
) -> int:
    """
    Send push notification to all devices/subscriptions
    belonging to the user.

    Returns number of successful deliveries.
    """

    subscriptions = await PushSubscription.find(
        PushSubscription.user_id == user_id
    ).to_list()

    if not subscriptions:

        logger.debug(
            "No push subscriptions for user %s",
            user_id,
        )

        return 0

    success_count = 0

    for subscription in subscriptions:

        success = await send_web_push(
            subscription,
            title=title,
            body=body,
            reminder_id=reminder_id,
        )

        if success:
            success_count += 1

    return success_count


async def notify_reminder_due(
    reminder: Reminder,
) -> int:
    """Notify user that a reminder is due."""

    return await notify_user(
        user_id=reminder.user_id,

        title="🔔 Task Reminder",

        body=(
            f"{reminder.title}\n\n"
            "Your reminder is due now."
        ),

        reminder_id=str(
            reminder.id
        ),
    )