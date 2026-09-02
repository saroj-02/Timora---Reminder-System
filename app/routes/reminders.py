"""
Timora – Reminder Routes
Full REST API for reminder CRUD + actions.
"""
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status

from app.models.user import User
from app.schemas.reminder import (
    ReminderCreateRequest,
    ReminderListResponse,
    ReminderResponse,
    ReminderUpdateRequest,
    RescheduleRequest,
    SnoozeRequest,
)
from app.services.auth_service import get_current_user
from app.services.reminder_service import (
    complete_reminder,
    create_reminder,
    delete_reminder,
    get_reminder,
    list_reminders,
    reschedule_reminder,
    snooze_reminder,
    to_response,
    update_reminder,
)
from app.utils.timezone import local_to_utc, now_utc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reminders", tags=["reminders"])


@router.get("", response_model=ReminderListResponse)
async def get_reminders(
    status_filter: Optional[str] = Query(None, alias="status"),
    category: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: Literal["nearest", "newest", "oldest", "priority"] = Query("nearest"),
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
) -> ReminderListResponse:
    statuses = status_filter.split(",") if status_filter else None
    total, items = await list_reminders(
        user_id=str(current_user.id),
        status_filter=statuses,
        category=category,
        priority=priority,
        search=search,
        sort_by=sort_by,
        limit=limit,
        skip=skip,
    )
    return ReminderListResponse(
        total=total,
        items=[to_response(r, current_user.timezone) for r in items],
    )


@router.post("", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED)
async def create(
    body: ReminderCreateRequest = Body(...),
    current_user: User = Depends(get_current_user),
) -> ReminderResponse:
    reminder = await create_reminder(current_user, body)
    return to_response(reminder, current_user.timezone)


@router.get("/{reminder_id}", response_model=ReminderResponse)
async def get_one(
    reminder_id: str,
    current_user: User = Depends(get_current_user),
) -> ReminderResponse:
    reminder = await get_reminder(reminder_id, str(current_user.id))
    if not reminder:
        raise HTTPException(status_code=404, detail="This reminder no longer exists.")
    return to_response(reminder, current_user.timezone)


@router.put("/{reminder_id}", response_model=ReminderResponse)
async def update(
    reminder_id: str,
    body: ReminderUpdateRequest = Body(...),
    current_user: User = Depends(get_current_user),
) -> ReminderResponse:
    reminder = await get_reminder(reminder_id, str(current_user.id))
    if not reminder:
        raise HTTPException(status_code=404, detail="This reminder no longer exists.")
    try:
        reminder = await update_reminder(reminder, body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return to_response(reminder, current_user.timezone)


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete(
    reminder_id: str,
    current_user: User = Depends(get_current_user),
) -> Response:
    reminder = await get_reminder(reminder_id, str(current_user.id))
    if not reminder:
        raise HTTPException(status_code=404, detail="This reminder no longer exists.")
    await delete_reminder(reminder)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{reminder_id}/complete", response_model=ReminderResponse)
async def complete(
    reminder_id: str,
    current_user: User = Depends(get_current_user),
) -> ReminderResponse:
    reminder = await get_reminder(reminder_id, str(current_user.id))
    if not reminder:
        raise HTTPException(status_code=404, detail="This reminder no longer exists.")
    reminder = await complete_reminder(reminder)
    return to_response(reminder, current_user.timezone)


@router.post("/{reminder_id}/snooze", response_model=ReminderResponse)
async def snooze(
    reminder_id: str,
    body: SnoozeRequest = Body(...),
    current_user: User = Depends(get_current_user),
) -> ReminderResponse:
    reminder = await get_reminder(reminder_id, str(current_user.id))
    if not reminder:
        raise HTTPException(status_code=404, detail="This reminder no longer exists.")
    reminder = await snooze_reminder(reminder, body.minutes)
    return to_response(reminder, current_user.timezone)


@router.post("/{reminder_id}/reschedule", response_model=ReminderResponse)
async def reschedule(
    reminder_id: str,
    body: RescheduleRequest = Body(...),
    current_user: User = Depends(get_current_user),
) -> ReminderResponse:
    reminder = await get_reminder(reminder_id, str(current_user.id))
    if not reminder:
        raise HTTPException(status_code=404, detail="This reminder no longer exists.")
    try:
        utc_time = local_to_utc(body.local_datetime, body.timezone)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid timezone or datetime.")
    if utc_time <= now_utc():
        raise HTTPException(status_code=422, detail="The selected time has already passed.")
    reminder = await reschedule_reminder(reminder, utc_time)
    return to_response(reminder, current_user.timezone)
