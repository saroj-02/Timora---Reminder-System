"""
Timora – User Routes
GET /api/users/me
PUT /api/users/me
POST /api/users/me/change-password
"""
from fastapi import APIRouter, Body, Depends, HTTPException, Response, status

from app.models.user import User
from app.schemas.auth import PasswordChangeRequest, UserResponse
from app.schemas.user import UserUpdateRequest
from app.services.auth_service import get_current_user, hash_password, verify_password
from app.utils.timezone import is_valid_timezone

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return _to_response(current_user)


@router.put("/me", response_model=UserResponse)
async def update_me(
    body: UserUpdateRequest = Body(...),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    if body.name is not None:
        current_user.name = body.name
    if body.country is not None:
        current_user.country = body.country
    if body.timezone is not None:
        if not is_valid_timezone(body.timezone):
            raise HTTPException(status_code=422, detail="Invalid timezone identifier.")
        current_user.timezone = body.timezone
    if body.notification_enabled is not None:
        current_user.notification_enabled = body.notification_enabled
    if body.theme is not None:
        if body.theme not in ("dark", "light", "system"):
            raise HTTPException(status_code=422, detail="Invalid theme.")
        current_user.theme = body.theme
    if body.sound_enabled is not None:
        current_user.sound_enabled = body.sound_enabled
    if body.sound_volume is not None:
        current_user.sound_volume = body.sound_volume

    current_user.update_timestamp()
    await current_user.save()
    return _to_response(current_user)


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def change_password(
    body: PasswordChangeRequest = Body(...),
    current_user: User = Depends(get_current_user),
) -> Response:
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    current_user.password_hash = hash_password(body.new_password)
    current_user.update_timestamp()
    await current_user.save()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _to_response(user: User) -> UserResponse:
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
