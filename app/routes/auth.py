"""
Timora – Auth Routes
POST /api/auth/signup
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
"""

import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def signup(request: Request, response: Response, body: SignupRequest = Body(...)) -> TokenResponse:
    existing = await User.find_one(User.email == body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        name=body.name,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    await user.insert()

    token, expires_in = create_access_token(str(user.id))
    _set_auth_cookie(response, token, expires_in)

    logger.info("New user signed up: %s", user.email)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def login(request: Request, response: Response, body: LoginRequest = Body(...)) -> TokenResponse:
    user = await User.find_one(User.email == body.email)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token, expires_in = create_access_token(str(user.id), remember_me=body.remember_me)
    _set_auth_cookie(response, token, expires_in)

    logger.info("User logged in: %s", user.email)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie("timora_token", path="/")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return _to_user_response(current_user)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _set_auth_cookie(response: Response, token: str, expires_in: int) -> None:
    response.set_cookie(
        key="timora_token",
        value=token,
        max_age=expires_in,
        httponly=True,
        samesite="lax",
        secure=False,   # Set True in production with HTTPS
        path="/",
    )


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        name=user.name,
        email=user.email,
        country=user.country,
        timezone=user.timezone,
        notification_enabled=user.notification_enabled,
        theme=user.theme,
        sound_enabled=user.sound_enabled,
        sound_volume=user.sound_volume,
    )
