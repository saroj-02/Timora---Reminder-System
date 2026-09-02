"""
Timora – Main Responsive Layout

Desktop:
    Fixed top header + compact left sidebar.

Mobile:
    Fixed bottom navigation.

The layout is intentionally kept simple and predictable so every page
uses the same spacing and navigation behavior.
"""

from __future__ import annotations

from nicegui import ui

from app.frontend.state import clear_token, clear_user_data, get_user_data


NAV_ITEMS = [
    ("dashboard", "grid_view", "Dashboard"),
    ("reminders", "task_alt", "Reminders"),
    ("calendar", "calendar_month", "Calendar"),
    ("settings", "settings", "Settings"),
]


def main_layout(current_page: str = "dashboard") -> None:
    """
    Render the shared Timora application shell.

    Every authenticated page should call:

        main_layout("dashboard")
        main_layout("reminders")
        main_layout("calendar")
        main_layout("settings")
    """

    user_data = get_user_data() or {}
    name = str(user_data.get("name") or "User")
    notifications_enabled = bool(
        user_data.get("notification_enabled", False)
    )

    # ------------------------------------------------------------------
    # Material Icons
    # ------------------------------------------------------------------
    ui.add_head_html(
        """
        <link
            href="https://fonts.googleapis.com/icon?family=Material+Icons"
            rel="stylesheet"
        >
        """
    )

    # ------------------------------------------------------------------
    # Top Header
    # ------------------------------------------------------------------
    with ui.header().classes(
        "timora-header items-center justify-between"
    ):
        # Brand
        with ui.row().classes(
            "timora-brand items-center no-wrap"
        ):
            ui.label("⏰").classes("timora-brand-icon")

            ui.label("Timora").classes(
                "timora-brand-name"
            )

        # User area
        with ui.row().classes(
            "timora-user-area items-center no-wrap"
        ):
            ui.label(
                f"Hi, {name}"
            ).classes("timora-user-name")

            ui.button(
                icon="logout",
                on_click=_do_logout,
            ).props(
                "flat round dense"
            ).classes(
                "timora-logout"
            ).tooltip("Log out")

    # ------------------------------------------------------------------
    # Desktop Sidebar
    # ------------------------------------------------------------------
    with ui.left_drawer(
        fixed=True,
        bordered=False,
    ).classes("sidebar"):

        with ui.column().classes("sidebar-inner"):

            # Workspace label
            ui.label("WORKSPACE").classes(
                "sidebar-heading"
            )

            # Navigation
            with ui.column().classes(
                "sidebar-navigation"
            ):
                for page, icon, label in NAV_ITEMS:
                    _sidebar_item(
                        page=page,
                        icon=icon,
                        label=label,
                        active=(page == current_page),
                    )

            # Push notification status to bottom
            ui.space()

            with ui.element("div").classes(
                "sidebar-status"
            ):
                with ui.row().classes(
                    "items-center no-wrap"
                ):
                    ui.icon(
                        "notifications_active"
                        if notifications_enabled
                        else "notifications_none",
                        size="18px",
                    ).classes(
                        "sidebar-status-icon"
                        if notifications_enabled
                        else "sidebar-status-icon disabled"
                    )

                    with ui.column().classes(
                        "sidebar-status-text"
                    ):
                        ui.label(
                            "Notifications"
                        ).classes(
                            "sidebar-status-title"
                        )

                        ui.label(
                            "Enabled"
                            if notifications_enabled
                            else "Not enabled"
                        ).classes(
                            "sidebar-status-value"
                            if notifications_enabled
                            else "sidebar-status-value disabled"
                        )

    # ------------------------------------------------------------------
    # Mobile Bottom Navigation
    # ------------------------------------------------------------------
    with ui.footer().classes(
        "mobile-nav"
    ):
        for page, icon, label in NAV_ITEMS:
            _mobile_nav_item(
                page=page,
                icon=icon,
                label=label,
                active=(page == current_page),
            )

    # ------------------------------------------------------------------
    # Page offset
    # ------------------------------------------------------------------
    ui.add_head_html(
        """
        <style>
            .main-content {
                padding-top: 88px !important;
            }
        </style>
        """
    )


def _sidebar_item(
    page: str,
    icon: str,
    label: str,
    active: bool,
) -> None:
    """
    Render one desktop sidebar navigation item.

    The entire item is clickable. This avoids the old structure where
    the clickable element and its visible row were separate siblings.
    """

    active_class = "active" if active else ""

    with ui.element(
        "div"
    ).classes(
        f"sidebar-item {active_class}"
    ).on(
        "click",
        lambda _event, p=page: _navigate(p),
    ):

        ui.icon(
            icon,
            size="20px",
        ).classes(
            "sidebar-item-icon"
        )

        ui.label(
            label
        ).classes(
            "sidebar-item-label"
        )


def _mobile_nav_item(
    page: str,
    icon: str,
    label: str,
    active: bool,
) -> None:
    """
    Render one mobile navigation item.
    """

    active_class = "active" if active else ""

    with ui.element(
        "div"
    ).classes(
        f"mobile-nav-item {active_class}"
    ).on(
        "click",
        lambda _event, p=page: _navigate(p),
    ):

        ui.icon(
            icon,
            size="21px",
        ).classes(
            "mobile-nav-icon"
        )

        ui.label(
            label
        ).classes(
            "mobile-nav-label"
        )


def _navigate(page: str) -> None:
    """
    Navigate to an application page.

    Keeping navigation in one function prevents accidental event
    argument/type problems.
    """

    valid_pages = {
        "dashboard",
        "reminders",
        "calendar",
        "settings",
    }

    if page not in valid_pages:
        return

    ui.navigate.to(f"/{page}")


def _do_logout() -> None:
    """
    Clear local authentication state and return to login.
    """

    clear_token()
    clear_user_data()

    ui.navigate.to("/login")