"""
Timora – Notification Routes
POST   /api/notifications/subscribe
DELETE /api/notifications/unsubscribe
POST   /api/notifications/test
GET    /api/notifications/vapid-public-key
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel

from app.config import settings
from app.models.push_subscription import PushSubscription
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.notification_service import notify_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class SubscribeRequest(BaseModel):
    endpoint: str
    p256dh: str
    auth: str
    device: str = ""
    browser: str = ""


class UnsubscribeRequest(BaseModel):
    endpoint: str


@router.get("/vapid-public-key")
async def get_vapid_public_key() -> dict:
    """Return the VAPID public key for Service Worker registration."""
    return {"public_key": settings.VAPID_PUBLIC_KEY}


@router.post("/subscribe", status_code=status.HTTP_201_CREATED)
async def subscribe(
    body: SubscribeRequest = Body(...),
    current_user: User = Depends(get_current_user),
) -> dict:
    existing = await PushSubscription.find_one(
        PushSubscription.user_id == str(current_user.id),
        PushSubscription.endpoint == body.endpoint,
    )
    if existing:
        existing.p256dh = body.p256dh
        existing.auth = body.auth
        existing.device = body.device
        existing.browser = body.browser
        existing.updated_at = datetime.now(timezone.utc)
        await existing.save()
    else:
        sub = PushSubscription(
            user_id=str(current_user.id),
            endpoint=body.endpoint,
            p256dh=body.p256dh,
            auth=body.auth,
            device=body.device,
            browser=body.browser,
        )
        await sub.insert()

    if not current_user.notification_enabled:
        current_user.notification_enabled = True
        current_user.update_timestamp()
        await current_user.save()

    return {"message": "Subscription saved"}


@router.delete("/unsubscribe")
async def unsubscribe(
    body: UnsubscribeRequest = Body(...),
    current_user: User = Depends(get_current_user),
) -> dict:
    sub = await PushSubscription.find_one(
        PushSubscription.user_id == str(current_user.id),
        PushSubscription.endpoint == body.endpoint,
    )
    if sub:
        await sub.delete()
    return {"message": "Unsubscribed"}


@router.post("/test")
async def test_notification(current_user: User = Depends(get_current_user)) -> dict:
    count = await notify_user(
        user_id=str(current_user.id),
        title="🔔 Timora Test",
        body="Push notifications are working correctly!",
    )
    if count == 0:
        raise HTTPException(
            status_code=400,
            detail="No active push subscriptions found. Please enable notifications first.",
        )
    return {"message": f"Test notification sent to {count} device(s)"}


@router.post("/test-email")
async def test_email_notification(current_user: User = Depends(get_current_user)) -> dict:
    """Send a test reminder email to verify SMTP configuration."""
    from app.services.email_service import send_reminder_email
    from app.utils.timezone import format_local, now_utc

    user_email = str(current_user.email).strip()
    if not user_email:
        raise HTTPException(status_code=400, detail="User email address is missing.")

    tz = current_user.timezone or "Asia/Kolkata"
    current_time_str = format_local(now_utc(), tz, "%d %b %Y, %I:%M %p")

    success = await send_reminder_email(
        recipient=user_email,
        title="Test Reminder from Timora",
        scheduled_time=current_time_str,
        category="Personal",
        priority="High",
    )

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to send test email. Please check your SMTP settings in .env",
        )

    return {"message": f"Test email sent successfully to {user_email}!"}
