"""
Timora – PushSubscription Model
"""
from datetime import datetime, timezone
from typing import Optional

from beanie import Document
from pydantic import Field


class PushSubscription(Document):
    user_id: str
    endpoint: str
    p256dh: str
    auth: str
    device: Optional[str] = None
    browser: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "push_subscriptions"
        indexes = ["user_id", "endpoint"]
