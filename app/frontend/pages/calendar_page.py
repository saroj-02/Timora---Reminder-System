"""
Timora – Calendar Page

Professional monthly calendar view with:
- 7-column responsive calendar grid
- Previous / next month navigation
- Today button
- Reminder indicators
- User timezone support
- New reminder action
- No horizontal overflow
"""

from __future__ import annotations

import calendar
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from nicegui import ui

from app.frontend.api_client import api_get
from app.frontend.components.reminder_modal import open_reminder_modal
from app.frontend.layouts.main_layout import main_layout
from app.frontend.state import get_user_data, is_authenticated
from app.frontend.theme import inject_global_styles, inject_theme


WEEKDAYS = [
    "Mon",
    "Tue",
    "Wed",
    "Thu",
    "Fri",
    "Sat",
    "Sun",
]

MONTH_NAMES = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


# ─────────────────────────────────────────────────────────────────────────────
# Calendar CSS
# ─────────────────────────────────────────────────────────────────────────────

CALENDAR_CSS = """
<style>

    /* =========================================================
       CALENDAR PAGE
       ========================================================= */

    .timora-calendar-page {
        width: 100%;
        max-width: 1240px;
        margin: 0 auto;
        padding: 32px 32px 56px 32px;

        box-sizing: border-box;

        overflow-x: hidden;
    }


    /* =========================================================
       PAGE HEADER
       ========================================================= */

    .calendar-page-header {
        width: 100%;

        display: flex;
        align-items: center;
        justify-content: space-between;

        gap: 24px;

        margin-bottom: 30px;
    }

    .calendar-page-title {
        margin: 0;

        font-size: 32px;
        line-height: 1.2;
        font-weight: 800;

        color: #E2E8F0;
        letter-spacing: -0.6px;
    }

    .calendar-page-subtitle {
        margin-top: 8px;

        font-size: 15px;
        line-height: 1.5;

        color: #64748B;
    }


    /* =========================================================
       PRIMARY BUTTON
       ========================================================= */

    .calendar-primary-button {
        flex-shrink: 0;

        display: inline-flex;
        align-items: center;
        justify-content: center;

        min-height: 46px;

        padding: 0 20px;

        border-radius: 12px;

        background:
            linear-gradient(
                135deg,
                #7C3AED 0%,
                #2563EB 100%
            ) !important;

        color: white !important;

        font-size: 14px;
        font-weight: 700;

        box-shadow:
            0 8px 24px
            rgba(124, 58, 237, 0.28);

        transition:
            transform 0.18s ease,
            box-shadow 0.18s ease;
    }

    .calendar-primary-button:hover {
        transform: translateY(-2px);

        box-shadow:
            0 12px 30px
            rgba(124, 58, 237, 0.38);
    }


    /* =========================================================
       MONTH TOOLBAR
       ========================================================= */

    .calendar-toolbar {
        width: 100%;

        display: flex;
        align-items: center;
        justify-content: center;

        gap: 12px;

        margin-bottom: 26px;
    }

    .calendar-month-label {
        min-width: 210px;

        text-align: center;

        font-size: 22px;
        line-height: 1.3;
        font-weight: 750;

        color: #E2E8F0;
    }

    .calendar-nav-button {
        width: 42px;
        height: 42px;

        border-radius: 10px !important;

        color: #A78BFA !important;

        transition:
            background 0.18s ease,
            transform 0.18s ease;
    }

    .calendar-nav-button:hover {
        background: rgba(124, 58, 237, 0.12) !important;
        transform: translateY(-1px);
    }

    .calendar-today-button {
        min-height: 42px;

        padding: 0 16px;

        border-radius: 10px !important;

        color: #60A5FA !important;

        border-color:
            rgba(96, 165, 250, 0.55) !important;

        font-weight: 700 !important;
    }


    /* =========================================================
       CALENDAR CONTAINER
       ========================================================= */

    .calendar-shell {
        width: 100%;

        box-sizing: border-box;

        padding: 20px;

        border-radius: 18px;

        background:
            rgba(22, 33, 62, 0.55);

        border:
            1px solid
            rgba(148, 163, 184, 0.10);

        box-shadow:
            0 12px 40px
            rgba(0, 0, 0, 0.16);

        overflow: hidden;
    }


    /* =========================================================
       WEEKDAY HEADER
       ========================================================= */

    .calendar-weekdays {
        display: grid !important;

        grid-template-columns:
            repeat(7, minmax(0, 1fr)) !important;

        width: 100% !important;

        gap: 8px !important;

        margin-bottom: 8px;
    }

    .calendar-weekday {
        min-width: 0;

        text-align: center;

        padding: 8px 4px;

        font-size: 12px;
        line-height: 1.3;
        font-weight: 700;

        text-transform: uppercase;
        letter-spacing: 0.7px;

        color: #64748B;
    }


    /* =========================================================
       ACTUAL CALENDAR GRID
       ========================================================= */

    .calendar-grid {
        display: grid !important;

        grid-template-columns:
            repeat(7, minmax(0, 1fr)) !important;

        grid-auto-rows: minmax(112px, auto) !important;

        width: 100% !important;

        gap: 8px !important;

        align-items: stretch !important;
    }


    /* =========================================================
       EMPTY DAY
       ========================================================= */

    .calendar-empty-day {
        min-width: 0;
        min-height: 112px;

        border-radius: 12px;

        background: transparent;
    }


    /* =========================================================
       CALENDAR DAY
       ========================================================= */

    .calendar-day {
        position: relative;

        min-width: 0;
        min-height: 112px;

        padding: 11px;

        box-sizing: border-box;

        border-radius: 12px;

        border:
            1px solid
            rgba(45, 45, 78, 0.95);

        background:
            rgba(26, 26, 46, 0.82);

        overflow: hidden;

        cursor: pointer;

        transition:
            border-color 0.18s ease,
            background 0.18s ease,
            transform 0.18s ease,
            box-shadow 0.18s ease;
    }

    .calendar-day:hover {
        transform: translateY(-2px);

        border-color:
            rgba(124, 58, 237, 0.55);

        background:
            rgba(34, 32, 62, 0.95);

        box-shadow:
            0 8px 24px
            rgba(0, 0, 0, 0.20);
    }


    /* =========================================================
       TODAY
       ========================================================= */

    .calendar-day.is-today {
        border-color:
            rgba(124, 58, 237, 0.90);

        background:
            linear-gradient(
                145deg,
                rgba(124, 58, 237, 0.18),
                rgba(37, 99, 235, 0.08)
            );

        box-shadow:
            inset 0 0 0 1px
            rgba(167, 139, 250, 0.12);
    }


    /* =========================================================
       DAY NUMBER
       ========================================================= */

    .calendar-day-number {
        display: flex;
        align-items: center;
        justify-content: center;

        width: 30px;
        height: 30px;

        margin-bottom: 8px;

        border-radius: 9px;

        font-size: 14px;
        font-weight: 650;

        color: #CBD5E1;
    }

    .calendar-day.is-today .calendar-day-number {
        background:
            linear-gradient(
                135deg,
                #7C3AED,
                #2563EB
            );

        color: white;

        font-weight: 800;

        box-shadow:
            0 4px 12px
            rgba(124, 58, 237, 0.32);
    }


    /* =========================================================
       REMINDER ITEMS
       ========================================================= */

    .calendar-reminder {
        width: 100%;
        min-width: 0;

        display: flex;
        align-items: center;

        gap: 6px;

        margin-top: 5px;

        padding: 5px 7px;

        box-sizing: border-box;

        border-radius: 7px;

        background: rgba(255, 255, 255, 0.035);

        overflow: hidden;
    }

    .calendar-reminder-dot {
        flex-shrink: 0;

        width: 6px;
        height: 6px;

        border-radius: 50%;
    }

    .calendar-reminder-title {
        min-width: 0;

        overflow: hidden;

        text-overflow: ellipsis;

        white-space: nowrap;

        font-size: 11px;
        line-height: 1.3;
        font-weight: 550;
    }

    .calendar-more {
        margin-top: 6px;

        font-size: 10px;
        font-weight: 600;

        color: #64748B;
    }


    /* =========================================================
       RESPONSIVE
       ========================================================= */

    @media (max-width: 1100px) {

        .timora-calendar-page {
            padding-left: 20px;
            padding-right: 20px;
        }

        .calendar-shell {
            padding: 14px;
        }

        .calendar-grid {
            grid-auto-rows: minmax(96px, auto) !important;
            gap: 6px !important;
        }

        .calendar-weekdays {
            gap: 6px !important;
        }

        .calendar-day {
            min-height: 96px;
            padding: 8px;
        }

        .calendar-empty-day {
            min-height: 96px;
        }
    }


    @media (max-width: 768px) {

        .timora-calendar-page {
            width: 100%;
            max-width: none;

            padding:
                20px 14px 90px 14px;
        }

        .calendar-page-header {
            align-items: flex-start;

            flex-direction: column;

            gap: 16px;

            margin-bottom: 22px;
        }

        .calendar-page-title {
            font-size: 28px;
        }

        .calendar-primary-button {
            width: 100%;
        }

        .calendar-toolbar {
            justify-content: space-between;

            gap: 5px;

            margin-bottom: 18px;
        }

        .calendar-month-label {
            min-width: 0;

            flex: 1;

            font-size: 18px;
        }

        .calendar-nav-button {
            width: 38px;
            height: 38px;
        }

        .calendar-today-button {
            min-height: 38px;

            padding: 0 10px;

            font-size: 12px !important;
        }

        .calendar-shell {
            padding: 8px;

            border-radius: 14px;
        }

        .calendar-grid {
            grid-template-columns:
                repeat(7, minmax(0, 1fr)) !important;

            grid-auto-rows:
                minmax(68px, auto) !important;

            gap: 4px !important;
        }

        .calendar-weekdays {
            grid-template-columns:
                repeat(7, minmax(0, 1fr)) !important;

            gap: 4px !important;
        }

        .calendar-weekday {
            padding: 5px 0;

            font-size: 9px;

            letter-spacing: 0;
        }

        .calendar-day {
            min-height: 68px;

            padding: 6px;

            border-radius: 8px;
        }

        .calendar-empty-day {
            min-height: 68px;
        }

        .calendar-day-number {
            width: 24px;
            height: 24px;

            margin-bottom: 3px;

            font-size: 11px;

            border-radius: 7px;
        }

        .calendar-reminder {
            display: none;
        }

        .calendar-day.has-reminders::after {
            content: '';

            position: absolute;

            bottom: 6px;
            left: 50%;

            width: 5px;
            height: 5px;

            transform: translateX(-50%);

            border-radius: 50%;

            background: #A78BFA;
        }

        .calendar-more {
            display: none;
        }
    }

</style>
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_date_map(reminders: list[Any]) -> dict[str, list[dict[str, Any]]]:
    """
    Convert reminder API data into:

        YYYY-MM-DD -> [reminder, reminder, ...]

    This keeps the calendar rendering simple and predictable.
    """

    result: dict[str, list[dict[str, Any]]] = {}

    for reminder in reminders:
        if not isinstance(reminder, dict):
            continue

        local_datetime = reminder.get(
            "local_datetime_str",
            "",
        )

        if not local_datetime:
            continue

        parsed: datetime | None = None

        formats = [
            "%B %d, %Y %I:%M %p",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
        ]

        for date_format in formats:
            try:
                parsed = datetime.strptime(
                    local_datetime,
                    date_format,
                )
                break
            except (TypeError, ValueError):
                continue

        if parsed is None:
            continue

        date_key = parsed.strftime("%Y-%m-%d")

        result.setdefault(
            date_key,
            [],
        ).append(reminder)

    return result


def _priority_color(priority: str) -> str:
    """
    Return the visual color for a reminder priority.
    """

    colors = {
        "High": "#EF4444",
        "Medium": "#F59E0B",
        "Low": "#10B981",
    }

    return colors.get(
        priority,
        "#A78BFA",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Calendar Page
# ─────────────────────────────────────────────────────────────────────────────

async def calendar_page() -> None:
    """
    Render Timora's calendar page.
    """

    inject_global_styles()

    if not is_authenticated():
        ui.navigate.to("/login")
        return

    user_data = get_user_data() or {}

    inject_theme(
        user_data.get(
            "theme",
            "dark",
        )
    )

    # Main application shell.
    main_layout("calendar")

    user_timezone = user_data.get(
        "timezone",
        "UTC",
    )

    try:
        now = datetime.now(
            ZoneInfo(user_timezone)
        )
    except Exception:
        user_timezone = "UTC"

        now = datetime.now(
            ZoneInfo("UTC")
        )

    # Fetch reminders.
    try:
        response = await api_get(
            "/api/reminders",
            {
                "limit": 500,
            },
        )
    except Exception:
        response = None

    if isinstance(response, dict):
        all_reminders = response.get(
            "items",
            [],
        )

        if not isinstance(all_reminders, list):
            all_reminders = []
    else:
        all_reminders = []

    date_map = _build_date_map(
        all_reminders
    )

    # Inject calendar-specific CSS once for this page.
    ui.add_head_html(
        CALENDAR_CSS
    )

    # We intentionally use a normal dictionary instead of ui.state().
    # This avoids Pylance's incorrect Tuple[Any, callback] typing.
    view = {
        "year": now.year,
        "month": now.month,
    }

    calendar_container = ui.element(
        "div"
    ).classes(
        "full-width"
    )

    # ─────────────────────────────────────────────────────────────────────
    # Render function
    # ─────────────────────────────────────────────────────────────────────

    def render_calendar() -> None:
        """
        Rebuild only the calendar page contents.
        """

        calendar_container.clear()

        year = int(
            view["year"]
        )

        month = int(
            view["month"]
        )

        current_time = datetime.now(
            ZoneInfo(user_timezone)
        )

        with calendar_container:

            with ui.element(
                "div"
            ).classes(
                "timora-calendar-page page-enter"
            ):

                # =========================================================
                # PAGE HEADER
                # =========================================================

                with ui.element(
                    "div"
                ).classes(
                    "calendar-page-header"
                ):

                    with ui.element(
                        "div"
                    ):

                        ui.label(
                            "Calendar"
                        ).classes(
                            "calendar-page-title"
                        )

                        ui.label(
                            "View and manage your reminders by date."
                        ).classes(
                            "calendar-page-subtitle"
                        )

                    ui.button(
                        "＋  New Reminder",
                        on_click=lambda: open_reminder_modal(
                            on_saved=lambda: ui.navigate.to(
                                "/calendar"
                            )
                        ),
                    ).classes(
                        "calendar-primary-button"
                    ).props(
                        "unelevated no-caps"
                    )

                # =========================================================
                # MONTH TOOLBAR
                # =========================================================

                with ui.element(
                    "div"
                ).classes(
                    "calendar-toolbar"
                ):

                    ui.button(
                        icon="chevron_left",
                        on_click=previous_month,
                    ).classes(
                        "calendar-nav-button"
                    ).props(
                        "flat"
                    )

                    ui.label(
                        f"{MONTH_NAMES[month - 1]} {year}"
                    ).classes(
                        "calendar-month-label"
                    )

                    ui.button(
                        icon="chevron_right",
                        on_click=next_month,
                    ).classes(
                        "calendar-nav-button"
                    ).props(
                        "flat"
                    )

                    ui.button(
                        "Today",
                        on_click=go_today,
                    ).classes(
                        "calendar-today-button"
                    ).props(
                        "outline no-caps"
                    )

                # =========================================================
                # CALENDAR SHELL
                # =========================================================

                with ui.element(
                    "div"
                ).classes(
                    "calendar-shell"
                ):

                    # -----------------------------------------------------
                    # Weekday header
                    # -----------------------------------------------------

                    with ui.element(
                        "div"
                    ).classes(
                        "calendar-weekdays"
                    ):

                        for weekday in WEEKDAYS:

                            ui.label(
                                weekday
                            ).classes(
                                "calendar-weekday"
                            )

                    # -----------------------------------------------------
                    # Days
                    # -----------------------------------------------------

                    month_matrix = calendar.monthcalendar(
                        year,
                        month,
                    )

                    with ui.element(
                        "div"
                    ).classes(
                        "calendar-grid"
                    ):

                        for week in month_matrix:

                            for day in week:

                                # Empty cells before/after month.
                                if day == 0:

                                    ui.element(
                                        "div"
                                    ).classes(
                                        "calendar-empty-day"
                                    )

                                    continue

                                date_key = (
                                    f"{year:04d}-"
                                    f"{month:02d}-"
                                    f"{day:02d}"
                                )

                                day_reminders = date_map.get(
                                    date_key,
                                    [],
                                )

                                is_today = (
                                    day == current_time.day
                                    and month == current_time.month
                                    and year == current_time.year
                                )

                                classes = (
                                    "calendar-day"
                                )

                                if is_today:
                                    classes += " is-today"

                                if day_reminders:
                                    classes += " has-reminders"

                                with ui.element(
                                    "div"
                                ).classes(
                                    classes
                                ):

                                    ui.label(
                                        str(day)
                                    ).classes(
                                        "calendar-day-number"
                                    )

                                    # Show maximum 3 reminders.
                                    for reminder in day_reminders[:3]:

                                        title = str(
                                            reminder.get(
                                                "title",
                                                "Reminder",
                                            )
                                        )

                                        priority = str(
                                            reminder.get(
                                                "priority",
                                                "Medium",
                                            )
                                        )

                                        priority_color = (
                                            _priority_color(
                                                priority
                                            )
                                        )

                                        with ui.element(
                                            "div"
                                        ).classes(
                                            "calendar-reminder"
                                        ).style(
                                            f"border-left: 2px solid "
                                            f"{priority_color};"
                                        ).tooltip(
                                            title
                                        ):

                                            ui.element(
                                                "div"
                                            ).classes(
                                                "calendar-reminder-dot"
                                            ).style(
                                                f"background:{priority_color};"
                                            )

                                            ui.label(
                                                title
                                            ).classes(
                                                "calendar-reminder-title"
                                            ).style(
                                                f"color:{priority_color};"
                                            )

                                    if len(day_reminders) > 3:

                                        ui.label(
                                            f"+{len(day_reminders) - 3} more"
                                        ).classes(
                                            "calendar-more"
                                        )

    # ─────────────────────────────────────────────────────────────────────
    # Navigation handlers
    # ─────────────────────────────────────────────────────────────────────

    def previous_month() -> None:
        """
        Move to previous month.
        """

        if view["month"] == 1:
            view["month"] = 12
            view["year"] -= 1
        else:
            view["month"] -= 1

        render_calendar()

    def next_month() -> None:
        """
        Move to next month.
        """

        if view["month"] == 12:
            view["month"] = 1
            view["year"] += 1
        else:
            view["month"] += 1

        render_calendar()

    def go_today() -> None:
        """
        Return to the user's current month.
        """

        today = datetime.now(
            ZoneInfo(user_timezone)
        )

        view["year"] = today.year
        view["month"] = today.month

        render_calendar()

    # Initial render.
    render_calendar()