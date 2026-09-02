"""
Timora – User Model
"""
from datetime import datetime, timezone
from typing import Optional

from beanie import Document, Indexed
from pydantic import EmailStr, Field


class User(Document):
    name: str
    email: Indexed(EmailStr, unique=True)  # type: ignore[valid-type]
    password_hash: str
    country: Optional[str] = None
    timezone: Optional[str] = None          # IANA timezone e.g. "Asia/Kolkata"
    notification_enabled: bool = False
    theme: str = "dark"                     # "dark" | "light" | "system"
    sound_enabled: bool = True
    sound_volume: float = 0.7              # 0.0 – 1.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "users"
        indexes = ["email"]

    def update_timestamp(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
