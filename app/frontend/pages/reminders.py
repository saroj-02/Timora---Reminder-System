"""
Timora – Reminders Page

Full reminder list with:
- Search
- Filters
- Sorting
- Create
- Edit
- Complete
- Snooze
- Reschedule
- Delete
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from nicegui import ui

from app.frontend.api_client import (
    api_delete,
    api_get,
    api_post,
)
from app.frontend.components.reminder_card import reminder_card
from app.frontend.components.reminder_modal import (
    open_reminder_modal,
)
from app.frontend.components.toast import (
    toast_error,
    toast_success,
)
from app.frontend.layouts.main_layout import main_layout
from app.frontend.state import (
    get_user_data,
    is_authenticated,
)
from app.frontend.theme import (
    inject_global_styles,
    inject_theme,
)


FILTERS = [
    "All",
    "Today",
    "Upcoming",
    "Completed",
    "High Priority",
    "Study",
    "Work",
    "Personal",
    "Meeting",
]

SORT_OPTIONS = [
    "Nearest",
    "Newest",
    "Oldest",
    "Priority",
]


async def reminders_page() -> None:
    """Render the Reminders page."""

    inject_global_styles()

    if not is_authenticated():
        ui.navigate.to("/login")
        return

    user_data = get_user_data() or {}

    inject_theme(
        str(user_data.get("theme") or "dark")
    )

    main_layout("reminders")

    # -------------------------------------------------------------------------
    # Local page state
    #
    # Do NOT use ui.state(...).value here.
    # A simple mutable dictionary is enough because the page itself is
    # re-rendered when needed.
    # -------------------------------------------------------------------------

    page_state: dict[str, str] = {
        "filter": "All",
    }

    # -------------------------------------------------------------------------
    # Page container
    # -------------------------------------------------------------------------

    with ui.column().classes(
        "main-content page-enter"
    ):

        # ── Page Header ──────────────────────────────────────────────────────

        with ui.row().classes(
            "items-center justify-between full-width"
        ).style(
            "gap:16px;"
            "margin-bottom:22px;"
            "flex-wrap:wrap;"
        ):

            with ui.column().classes("gap-xs"):
                ui.label(
                    "Reminders"
                ).classes("page-title")

                ui.label(
                    "Search, filter and manage all your reminders."
                ).classes("page-subtitle")

            ui.button(
                "New Reminder",
                icon="add",
                on_click=lambda: open_reminder_modal(
                    on_saved=lambda: ui.navigate.to(
                        "/reminders"
                    )
                ),
            ).classes(
                "btn-primary"
            ).style(
                "padding:0 18px;"
                "flex-shrink:0;"
            )

        # ── Search + Sort ────────────────────────────────────────────────────

        with ui.row().classes(
            "full-width items-center"
        ).style(
            "gap:12px;"
            "margin-bottom:16px;"
            "flex-wrap:wrap;"
        ):

            search_input = ui.input(
                placeholder="Search reminders..."
            ).props(
                "outlined dense clearable"
            ).classes(
                "search-input"
            ).style(
                "flex:1;"
                "min-width:220px;"
            )

            sort_select = ui.select(
                SORT_OPTIONS,
                value="Nearest",
                label="Sort by",
            ).props(
                "outlined dense"
            ).style(
                "width:170px;"
                "flex-shrink:0;"
            )

        # ── Filters ──────────────────────────────────────────────────────────

        filter_container = ui.row().classes(
            "full-width"
        ).style(
            "gap:8px;"
            "margin-bottom:20px;"
            "flex-wrap:wrap;"
        )

        filter_buttons: dict[str, Any] = {}

        with filter_container:
            for filter_name in FILTERS:

                button = ui.button(
                    filter_name
                ).props(
                    "rounded dense outline"
                ).style(
                    "min-height:34px;"
                    "padding:0 13px;"
                    "border-radius:999px;"
                    "font-size:12px;"
                    "font-weight:600;"
                    "border-color:rgba(124,58,237,.35);"
                    "color:#A78BFA;"
                )

                filter_buttons[filter_name] = button

        # ── Results ──────────────────────────────────────────────────────────

        results_container = ui.column().classes(
            "full-width"
        )

        # ---------------------------------------------------------------------
        # Filter button visual state
        # ---------------------------------------------------------------------

        def update_filter_styles() -> None:
            current = page_state["filter"]

            for name, button in filter_buttons.items():

                if name == current:
                    button.style(
                        "min-height:34px;"
                        "padding:0 13px;"
                        "border-radius:999px;"
                        "font-size:12px;"
                        "font-weight:700;"
                        "border-color:#7C3AED;"
                        "color:white;"
                        "background:"
                        "linear-gradient(135deg,#7C3AED,#2563EB);"
                    )
                else:
                    button.style(
                        "min-height:34px;"
                        "padding:0 13px;"
                        "border-radius:999px;"
                        "font-size:12px;"
                        "font-weight:600;"
                        "border-color:rgba(124,58,237,.35);"
                        "color:#A78BFA;"
                        "background:transparent;"
                    )

        # ---------------------------------------------------------------------
        # Build API parameters
        # ---------------------------------------------------------------------

        def build_params() -> dict[str, Any]:
            params: dict[str, Any] = {
                "limit": 200,
            }

            search = (
                search_input.value or ""
            ).strip()

            sort_value = (
                sort_select.value or "Nearest"
            )

            if search:
                params["search"] = search

            sort_map = {
                "Nearest": "nearest",
                "Newest": "newest",
                "Oldest": "oldest",
                "Priority": "priority",
            }

            params["sort_by"] = sort_map.get(
                sort_value,
                "nearest",
            )

            current_filter = page_state["filter"]

            if current_filter == "Completed":
                params["status"] = "completed"

            elif current_filter == "Today":
                params["date"] = "today"

            elif current_filter == "Upcoming":
                params["status"] = "pending"

            elif current_filter == "High Priority":
                params["priority"] = "High"

            elif current_filter in {
                "Study",
                "Work",
                "Personal",
                "Meeting",
            }:
                params["category"] = current_filter

            return params

        # ---------------------------------------------------------------------
        # Load reminders
        # ---------------------------------------------------------------------

        async def load_reminders() -> None:
            """
            Fetch reminders and redraw only the results section.
            """

            results_container.clear()

            try:
                data = await api_get(
                    "/api/reminders",
                    build_params(),
                )

                if isinstance(data, dict):
                    items = data.get(
                        "items",
                        [],
                    )
                elif isinstance(data, list):
                    items = data
                else:
                    items = []

                if not isinstance(items, list):
                    items = []

            except Exception:
                with results_container:
                    with ui.column().classes(
                        "empty-state items-center"
                    ):
                        ui.icon(
                            "error_outline",
                            size="42px",
                        ).style(
                            "color:#EF4444;"
                        )

                        ui.label(
                            "Unable to load reminders."
                        ).style(
                            "font-size:16px;"
                            "font-weight:700;"
                            "color:#E2E8F0;"
                        )

                        ui.label(
                            "Please check that the backend is running."
                        ).style(
                            "font-size:13px;"
                            "color:#64748B;"
                            "text-align:center;"
                        )

                return

            with results_container:

                # Results count
                with ui.row().classes(
                    "items-center justify-between full-width"
                ).style(
                    "margin-bottom:10px;"
                ):

                    ui.label(
                        f"{len(items)} reminder"
                        + (
                            ""
                            if len(items) == 1
                            else "s"
                        )
                    ).style(
                        "font-size:13px;"
                        "font-weight:600;"
                        "color:#64748B;"
                    )

                if not items:

                    with ui.column().classes(
                        "empty-state items-center"
                    ):

                        ui.icon(
                            "event_busy",
                            size="44px",
                        ).style(
                            "color:#64748B;"
                        )

                        ui.label(
                            "No reminders found"
                        ).style(
                            "font-size:17px;"
                            "font-weight:700;"
                            "color:#CBD5E1;"
                            "margin-top:8px;"
                        )

                        ui.label(
                            "Try changing your search or filter."
                        ).style(
                            "font-size:13px;"
                            "color:#64748B;"
                            "text-align:center;"
                        )

                    return

                # Reminder cards
                for reminder in items:

                    reminder_card(
                        reminder,

                        on_complete=lambda rid: (
                            _complete_and_reload(
                                rid,
                                load_reminders,
                            )
                        ),

                        on_delete=lambda rid: (
                            _delete_and_reload(
                                rid,
                                load_reminders,
                            )
                        ),

                        on_snooze=lambda rid, minutes: (
                            _snooze_and_reload(
                                rid,
                                minutes,
                                load_reminders,
                            )
                        ),

                        on_edit=lambda rid, rs=items: (
                            _edit_reminder(
                                rid,
                                rs,
                                load_reminders,
                            )
                        ),

                        on_reschedule=lambda rid, rs=items: (
                            _reschedule_reminder(
                                rid,
                                rs,
                                load_reminders,
                            )
                        ),
                    )

        # ---------------------------------------------------------------------
        # Filter handlers
        # ---------------------------------------------------------------------

        def make_filter_handler(
            filter_name: str,
        ) -> Callable[[], Awaitable[None]]:

            async def handler() -> None:
                page_state["filter"] = filter_name

                update_filter_styles()

                await load_reminders()

            return handler

        for filter_name, button in filter_buttons.items():
            button.on(
                "click",
                make_filter_handler(
                    filter_name
                ),
            )

        # ---------------------------------------------------------------------
        # Search
        # ---------------------------------------------------------------------

        async def search_changed() -> None:
            await load_reminders()

        search_input.on(
            "update:model-value",
            lambda _event: ui.timer(
                0.35,
                search_changed,
                once=True,
            ),
        )

        # ---------------------------------------------------------------------
        # Sort
        # ---------------------------------------------------------------------

        sort_select.on(
            "update:model-value",
            lambda _event: ui.timer(
                0,
                load_reminders,
                once=True,
            ),
        )

        # Initial state
        update_filter_styles()

        await load_reminders()


# ── Reminder Actions ─────────────────────────────────────────────────────────


async def _complete_and_reload(
    rid: str,
    reload: Callable[[], Awaitable[None]],
) -> None:
    try:
        await api_post(
            f"/api/reminders/{rid}/complete"
        )

        toast_success(
            "Reminder completed."
        )

        await reload()

    except Exception:
        toast_error(
            "Failed to complete reminder."
        )


async def _delete_and_reload(
    rid: str,
    reload: Callable[[], Awaitable[None]],
) -> None:
    try:
        ok = await api_delete(
            f"/api/reminders/{rid}"
        )

        if ok:
            toast_success(
                "Reminder deleted."
            )
            await reload()
        else:
            toast_error(
                "Failed to delete reminder."
            )

    except Exception:
        toast_error(
            "Failed to delete reminder."
        )


async def _snooze_and_reload(
    rid: str,
    minutes: int,
    reload: Callable[[], Awaitable[None]],
) -> None:
    try:
        await api_post(
            f"/api/reminders/{rid}/snooze",
            {"minutes": minutes},
        )

        toast_success(
            f"Snoozed for {minutes} minutes."
        )

        await reload()

    except Exception:
        toast_error(
            "Failed to snooze reminder."
        )


def _edit_reminder(
    rid: str,
    reminders: list,
    reload: Callable[[], Awaitable[None]],
) -> None:

    existing = next(
        (
            reminder
            for reminder in reminders
            if reminder.get("id") == rid
        ),
        None,
    )

    if not existing:
        toast_error(
            "Reminder could not be found."
        )
        return

    open_reminder_modal(
        on_saved=lambda: ui.timer(
            0,
            reload,
            once=True,
        ),
        existing=existing,
    )


def _reschedule_reminder(
    rid: str,
    reminders: list,
    reload: Callable[[], Awaitable[None]],
) -> None:

    existing = next(
        (
            reminder
            for reminder in reminders
            if reminder.get("id") == rid
        ),
        None,
    )

    if not existing:
        toast_error(
            "Reminder could not be found."
        )
        return

    open_reminder_modal(
        on_saved=lambda: ui.timer(
            0,
            reload,
            once=True,
        ),
        existing=existing,
    )