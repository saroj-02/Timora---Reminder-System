"""Timora – Reminder Create/Edit Modal."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable, Optional, cast
from zoneinfo import ZoneInfo

from nicegui import ui

from app.frontend.api_client import api_post, api_put
from app.frontend.components.toast import toast_error, toast_success
from app.frontend.state import get_user_data
from app.utils.timezone import get_timezones_for_country, list_countries


CATEGORIES = [
    "Personal",
    "Work",
    "Study",
    "Health",
    "Finance",
    "Other",
]

PRIORITIES = [
    "Low",
    "Medium",
    "High",
]

REPEAT_TYPES = [
    "Never",
    "Daily",
    "Weekly",
    "Monthly",
    "Yearly",
]

REMINDER_BEFORE = [
    "At scheduled time",
    "5 minutes before",
    "10 minutes before",
    "15 minutes before",
    "30 minutes before",
    "1 hour before",
    "1 day before",
]


# Friendly UI labels -> backend enum values.
CATEGORY_TO_API = {
    "Personal": "personal",
    "Work": "work",
    "Study": "study",
    "Health": "health",
    "Finance": "finance",
    "Other": "other",
}

PRIORITY_TO_API = {
    "Low": "low",
    "Medium": "medium",
    "High": "high",
}

REPEAT_TO_API = {
    "Never": "never",
    "Daily": "daily",
    "Weekly": "weekly",
    "Monthly": "monthly",
    "Yearly": "yearly",
}

BEFORE_TO_API = {
    "At scheduled time": "at_time",
    "5 minutes before": "5_minutes",
    "10 minutes before": "10_minutes",
    "15 minutes before": "15_minutes",
    "30 minutes before": "30_minutes",
    "1 hour before": "1_hour",
    "1 day before": "1_day",
}

# Backend -> friendly UI labels. This also makes edit mode work correctly
# when the API returns enum values such as "personal" or "at_time".
API_TO_CATEGORY = {v: k for k, v in CATEGORY_TO_API.items()}
API_TO_PRIORITY = {v: k for k, v in PRIORITY_TO_API.items()}
API_TO_REPEAT = {v: k for k, v in REPEAT_TO_API.items()}
API_TO_BEFORE = {v: k for k, v in BEFORE_TO_API.items()}


# NiceGUI's runtime exposes these as callable UI factories,
# but some NiceGUI/Pylance combinations incorrectly resolve
# them as modules. Casting keeps the runtime behavior unchanged
# while giving Pylance the correct callable type.
_ui_card = cast(Callable[..., Any], ui.card)
_ui_button = cast(Callable[..., Any], ui.button)


def _existing_datetime(
    existing: Optional[dict[str, Any]],
    tz_name: str,
) -> tuple[str, str]:
    """Return date/time values for an existing reminder."""

    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")

    if existing:
        raw_value = (
            existing.get("local_datetime")
            or existing.get("local_datetime_str")
            or ""
        )

        raw = str(raw_value)

        try:
            if "T" in raw:
                dt = datetime.fromisoformat(
                    raw.replace("Z", "+00:00")
                )

                if dt.tzinfo is not None:
                    dt = dt.astimezone(tz)

                return (
                    dt.strftime("%Y-%m-%d"),
                    dt.strftime("%H:%M"),
                )

            dt = datetime.strptime(
                raw,
                "%B %d, %Y %I:%M %p",
            )

            return (
                dt.strftime("%Y-%m-%d"),
                dt.strftime("%H:%M"),
            )

        except (ValueError, TypeError):
            pass

    dt = datetime.now(tz) + timedelta(hours=1)

    return (
        dt.strftime("%Y-%m-%d"),
        dt.strftime("%H:%M"),
    )


def open_reminder_modal(
    on_saved: Optional[Callable[[], Any]] = None,
    existing: Optional[dict[str, Any]] = None,
) -> None:
    """Open the reminder create/edit modal."""

    raw_user_data = get_user_data()

    user_data: dict[str, Any] = (
        raw_user_data
        if isinstance(raw_user_data, dict)
        else {}
    )

    user_country = (
        str(user_data.get("country") or "India")
    )

    user_tz = (
        str(user_data.get("timezone") or "Asia/Kolkata")
    )

    is_edit = existing is not None

    reminder_id = (
        existing.get("id")
        if isinstance(existing, dict)
        else None
    )

    default_date, default_time = _existing_datetime(
        existing,
        user_tz,
    )

    # ------------------------------------------------------------------
    # Dialog
    # ------------------------------------------------------------------

    with ui.dialog().props("persistent") as dialog:

        with _ui_card().style(
            "width:min(720px,calc(100vw - 28px));"
            "max-height:90vh;"
            "overflow-y:auto;"
            "padding:28px;"
            "border-radius:22px;"
            "background:#151E33;"
            "border:1px solid #334155;"
            "box-shadow:0 28px 80px rgba(0,0,0,.45);"
        ):

            # ----------------------------------------------------------
            # Header
            # ----------------------------------------------------------

            with ui.row().classes(
                "items-center justify-between full-width"
            ).style(
                "margin-bottom:22px;"
            ):

                with ui.column().classes("gap-none"):

                    ui.label(
                        "Edit Reminder"
                        if is_edit
                        else "New Reminder"
                    ).style(
                        "font-size:22px;"
                        "font-weight:800;"
                        "color:#F1F5F9;"
                    )

                    ui.label(
                        "Update the details and schedule."
                        if is_edit
                        else "Create a reminder you won't forget."
                    ).style(
                        "font-size:13px;"
                        "color:#94A3B8;"
                        "margin-top:4px;"
                    )

                ui.button(
                    icon="close",
                    on_click=dialog.close,
                ).props(
                    "flat round dense"
                ).style(
                    "color:#94A3B8;"
                ).tooltip("Close")

            # ----------------------------------------------------------
            # Basic information
            # ----------------------------------------------------------

            title_input = ui.input(
                "Task title *",
                value=(
                    existing.get("title", "")
                    if existing
                    else ""
                ),
                placeholder="e.g. Finish Python project",
            ).props(
                "outlined"
            ).classes(
                "full-width q-mb-md"
            )

            desc_input = ui.textarea(
                "Description",
                value=(
                    existing.get("description", "")
                    if existing
                    else ""
                ),
                placeholder="Optional notes or details",
            ).props(
                "outlined autogrow"
            ).classes(
                "full-width q-mb-md"
            )

            # ----------------------------------------------------------
            # Category + Priority
            # ----------------------------------------------------------

            with ui.row().classes(
                "full-width"
            ).style(
                "gap:12px;"
                "flex-wrap:wrap;"
            ):

                category_select = ui.select(
                    CATEGORIES,
                    label="Category",
                    value=(
                        API_TO_CATEGORY.get(
                            str(existing.get("category", "")),
                            str(existing.get("category", "Personal")),
                        )
                        if existing
                        else "Personal"
                    ),
                ).props(
                    "outlined"
                ).style(
                    "flex:1;"
                    "min-width:220px;"
                )

                priority_select = ui.select(
                    PRIORITIES,
                    label="Priority",
                    value=(
                        API_TO_PRIORITY.get(
                            str(existing.get("priority", "")),
                            str(existing.get("priority", "Medium")),
                        )
                        if existing
                        else "Medium"
                    ),
                ).props(
                    "outlined"
                ).style(
                    "flex:1;"
                    "min-width:220px;"
                )

            # ----------------------------------------------------------
            # Country + Timezone
            # ----------------------------------------------------------

            countries = list_countries()

            country_select = ui.select(
                countries,
                label="Country",
                value=user_country,
                with_input=True,
            ).props(
                "outlined"
            ).classes(
                "full-width q-mt-md"
            )

            tz_list = (
                get_timezones_for_country(user_country)
                or ["UTC"]
            )

            initial_timezone = (
                user_tz
                if user_tz in tz_list
                else tz_list[0]
            )

            tz_select = ui.select(
                tz_list,
                label="Timezone",
                value=initial_timezone,
                with_input=True,
            ).props(
                "outlined"
            ).classes(
                "full-width q-mt-md"
            )

            def update_tz_options(
                country: Any,
            ) -> None:
                """Update timezone choices when country changes."""

                selected_country = str(
                    country or "India"
                )

                options = (
                    get_timezones_for_country(
                        selected_country
                    )
                    or ["UTC"]
                )

                tz_select.options = options

                if tz_select.value not in options:
                    tz_select.value = options[0]

                tz_select.update()

            country_select.on(
                "update:model-value",
                lambda event: update_tz_options(
                    event.args
                ),
            )

            # ----------------------------------------------------------
            # Date + Time
            # ----------------------------------------------------------

            with ui.row().classes(
                "full-width"
            ).style(
                "gap:12px;"
                "flex-wrap:wrap;"
                "margin-top:12px;"
            ):

                date_input = ui.input(
                    "Date *",
                    value=default_date,
                ).props(
                    "outlined type=date"
                ).style(
                    "flex:1;"
                    "min-width:220px;"
                )

                time_input = ui.input(
                    "Time *",
                    value=default_time,
                ).props(
                    "outlined type=time"
                ).style(
                    "flex:1;"
                    "min-width:220px;"
                )

            # ----------------------------------------------------------
            # Repeat + Notification timing
            # ----------------------------------------------------------

            with ui.row().classes(
                "full-width"
            ).style(
                "gap:12px;"
                "flex-wrap:wrap;"
                "margin-top:12px;"
            ):

                repeat_select = ui.select(
                    REPEAT_TYPES,
                    label="Repeat",
                    value=(
                        API_TO_REPEAT.get(
                            str(existing.get("repeat_type", "")),
                            str(existing.get("repeat_type", "Never")),
                        )
                        if existing
                        else "Never"
                    ),
                ).props(
                    "outlined"
                ).style(
                    "flex:1;"
                    "min-width:220px;"
                )

                before_select = ui.select(
                    REMINDER_BEFORE,
                    label="Remind me",
                    value=(
                        API_TO_BEFORE.get(
                            str(existing.get("reminder_before", "")),
                            str(existing.get("reminder_before", "At scheduled time")),
                        )
                        if existing
                        else "At scheduled time"
                    ),
                ).props(
                    "outlined"
                ).style(
                    "flex:1;"
                    "min-width:220px;"
                )

            # ----------------------------------------------------------
            # Error message
            # ----------------------------------------------------------

            error_label = ui.label(
                ""
            ).style(
                "display:none;"
                "color:#FCA5A5;"
                "background:rgba(239,68,68,.10);"
                "border:1px solid rgba(239,68,68,.20);"
                "padding:10px 12px;"
                "border-radius:10px;"
                "font-size:12px;"
                "margin-top:14px;"
            )

            # ----------------------------------------------------------
            # Save
            # ----------------------------------------------------------

            async def save_reminder() -> None:
                """Validate and save the reminder."""

                error_label.style(
                    "display:none;"
                )

                title = str(
                    title_input.value or ""
                ).strip()

                if not title:
                    error_label.text = (
                        "Task title is required."
                    )
                    error_label.style(
                        "display:block;"
                    )
                    return

                if (
                    not date_input.value
                    or not time_input.value
                ):
                    error_label.text = (
                        "Please select both a date and a time."
                    )
                    error_label.style(
                        "display:block;"
                    )
                    return

                local_dt_str = (
                    f"{date_input.value}"
                    f"T{time_input.value}:00"
                )

                try:
                    selected_tz = str(
                        tz_select.value or "UTC"
                    )

                    local_dt = (
                        datetime
                        .fromisoformat(local_dt_str)
                        .replace(
                            tzinfo=ZoneInfo(
                                selected_tz
                            )
                        )
                    )

                    now_in_timezone = datetime.now(
                        ZoneInfo(selected_tz)
                    )

                    if local_dt <= now_in_timezone:
                        error_label.text = (
                            "That time has already passed. "
                            "Choose a future time."
                        )
                        error_label.style(
                            "display:block;"
                        )
                        return

                except (
                    ValueError,
                    TypeError,
                    KeyError,
                ):
                    error_label.text = (
                        "Invalid date, time, or timezone."
                    )
                    error_label.style(
                        "display:block;"
                    )
                    return

                # ------------------------------------------------------
                # API payload
                # ------------------------------------------------------

                payload: dict[str, Any] = {
                    "title": title,
                    "description": (
                        str(
                            desc_input.value or ""
                        ).strip()
                        or None
                    ),
                    "category": CATEGORY_TO_API.get(
                        str(category_select.value),
                        str(category_select.value).lower(),
                    ),
                    "priority": PRIORITY_TO_API.get(
                        str(priority_select.value),
                        str(priority_select.value).lower(),
                    ),
                    "local_datetime": local_dt_str,
                    "timezone": selected_tz,
                    "repeat_type": REPEAT_TO_API.get(
                        str(repeat_select.value),
                        str(repeat_select.value).lower(),
                    ),
                    "reminder_before": BEFORE_TO_API.get(
                        str(before_select.value),
                        str(before_select.value).lower(),
                    ),
                }

                save_btn.props(
                    "loading"
                )

                try:
                    if is_edit:

                        if reminder_id is None:
                            raise ValueError(
                                "Reminder ID is missing."
                            )

                        await api_put(
                            f"/api/reminders/{reminder_id}",
                            payload,
                        )

                        toast_success(
                            "Reminder updated successfully."
                        )

                    else:

                        await api_post(
                            "/api/reminders",
                            payload,
                        )

                        toast_success(
                            "Reminder scheduled successfully."
                        )

                    dialog.close()

                    if on_saved:
                        result = on_saved()

                        if hasattr(
                            result,
                            "__await__",
                        ):
                            await result

                except Exception as exc:

                    # Do not turn every 400/422 response into a fake
                    # "time has passed" error. Show the real API validation
                    # message when httpx provides a response body.
                    message = str(exc)
                    detail_message = ""

                    response = getattr(exc, "response", None)
                    if response is not None:
                        try:
                            body = response.json()
                            detail = body.get("detail") if isinstance(body, dict) else None
                            if isinstance(detail, list):
                                parts = []
                                for item in detail:
                                    if isinstance(item, dict) and item.get("msg"):
                                        parts.append(str(item["msg"]))
                                detail_message = " ".join(parts)
                            elif detail:
                                detail_message = str(detail)
                        except Exception:
                            detail_message = ""

                    if detail_message:
                        error_label.text = detail_message
                    elif "422" in message:
                        error_label.text = (
                            "The server rejected the reminder details. "
                            "Please check the date, time, timezone, and options."
                        )
                    elif "400" in message:
                        error_label.text = (
                            "The reminder could not be saved. "
                            "Please check the selected options."
                        )
                    else:
                        error_label.text = (
                            "Unable to save the reminder. "
                            "Please check your connection and try again."
                        )

                    error_label.style(
                        "display:block;"
                    )

                    toast_error(
                        "Could not save reminder."
                    )

                finally:
                    save_btn.props(
                        remove="loading"
                    )

            # ----------------------------------------------------------
            # Footer buttons
            # ----------------------------------------------------------

            with ui.row().classes(
                "items-center justify-end full-width"
            ).style(
                "gap:10px;"
                "margin-top:22px;"
            ):

                ui.button(
                    "Cancel",
                    on_click=dialog.close,
                ).props(
                    "flat"
                ).style(
                    "color:#94A3B8;"
                    "font-weight:600;"
                )

                save_btn = _ui_button(
                    "Update Reminder"
                    if is_edit
                    else "Schedule Reminder",
                    icon="event_available",
                    on_click=save_reminder,
                ).classes(
                    "btn-primary"
                ).style(
                    "min-height:44px;"
                    "padding:0 20px;"
                )

    dialog.open()