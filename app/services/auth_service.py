"""
Timora – Auth Service
Handles password hashing, JWT creation/decoding, and current-user dependency.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)

_ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
)

_bearer = HTTPBearer(auto_error=False)


# ── Password Hashing ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except VerifyMismatchError:
        return False
    except Exception as exc:
        logger.warning("Password verification error: %s", exc)
        return False


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(user_id: str, remember_me: bool = False) -> tuple[str, int]:
    """Returns (encoded_jwt, expires_in_seconds)."""
    if remember_me:
        expire_delta = timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    else:
        expire_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + expire_delta,
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, int(expire_delta.total_seconds())


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# ── FastAPI Dependencies ──────────────────────────────────────────────────────

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    timora_token: Optional[str] = Cookie(default=None),
) -> User:
    """Accepts JWT from Authorization header OR HttpOnly cookie."""
    token: Optional[str] = None

    if credentials:
        token = credentials.credentials
    elif timora_token:
        token = timora_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(token)
    user_id: str = payload.get("sub", "")

    user = await User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    timora_token: Optional[str] = Cookie(default=None),
) -> Optional[User]:
    try:
        return await get_current_user(credentials=credentials, timora_token=timora_token)
    except HTTPException:
        return None
