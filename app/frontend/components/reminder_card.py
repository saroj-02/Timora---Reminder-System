"""Timora – Reminder Card Component."""
from __future__ import annotations

from typing import Callable, Optional
from nicegui import ui

CATEGORY_ICONS = {
    "Personal": "person",
    "Study": "school",
    "Work": "work",
    "Meeting": "groups",
    "Project": "rocket_launch",
    "Birthday": "cake",
    "Other": "label",
}
PRIORITY_COLORS = {"High": "#EF4444", "Medium": "#F59E0B", "Low": "#10B981"}
STATUS_COLORS = {"pending": "#60A5FA", "sent": "#67E8F9", "completed": "#10B981", "snoozed": "#F59E0B", "failed": "#EF4444"}


def _action_style(color: str) -> str:
    return f"color:{color};border:1px solid {color}33;border-radius:9px;font-size:12px;font-weight:600;min-height:34px;"


def reminder_card(
    reminder: dict,
    on_complete: Optional[Callable] = None,
    on_edit: Optional[Callable] = None,
    on_snooze: Optional[Callable] = None,
    on_delete: Optional[Callable] = None,
    on_reschedule: Optional[Callable] = None,
) -> None:
    rid = reminder["id"]
    category = reminder.get("category", "Other")
    priority = reminder.get("priority", "Medium")
    status = reminder.get("status", "pending")
    icon = CATEGORY_ICONS.get(category, "label")
    p_color = PRIORITY_COLORS.get(priority, "#F59E0B")
    s_color = STATUS_COLORS.get(status, "#60A5FA")
    completed = status == "completed"
    local_str = reminder.get("local_datetime_str", "") or "Time not set"
    timezone = reminder.get("timezone", "UTC") or "UTC"

    with ui.card().classes(f"reminder-card q-pa-md q-mb-sm {'completed' if completed else ''}"):
        with ui.row().classes("items-start no-wrap full-width").style("gap:14px;"):
            with ui.element("div").classes("icon-box").style(
                f"background:linear-gradient(135deg,{p_color}18,{p_color}35);"
            ):
                ui.icon(icon, size="22px").style(f"color:{p_color};")

            with ui.column().classes("gap-xs").style("min-width:0;flex:1;"):
                with ui.row().classes("items-start justify-between no-wrap full-width").style("gap:12px;"):
                    with ui.column().classes("gap-xs").style("min-width:0;flex:1;"):
                        ui.label(reminder.get("title", "Untitled reminder")).classes(
                            f"reminder-title {'completed' if completed else ''}"
                        )
                        with ui.row().classes("items-center flex-wrap").style("gap:6px;"):
                            ui.badge(category).style("background:rgba(124,58,237,.12);color:#C4B5FD;border:1px solid rgba(124,58,237,.18);border-radius:999px;font-size:10px;padding:4px 8px;")
                            ui.badge(priority).style(f"background:{p_color}18;color:{p_color};border:1px solid {p_color}30;border-radius:999px;font-size:10px;padding:4px 8px;")
                            ui.badge(status.capitalize()).style(f"background:{s_color}16;color:{s_color};border:1px solid {s_color}30;border-radius:999px;font-size:10px;padding:4px 8px;")

                with ui.row().classes("items-center flex-wrap").style("gap:12px;margin-top:5px;"):
                    with ui.row().classes("items-center no-wrap").style("gap:5px;"):
                        ui.icon("event", size="16px").style("color:#64748B;")
                        ui.label(local_str).classes("reminder-meta")
                    with ui.row().classes("items-center no-wrap").style("gap:5px;"):
                        ui.icon("public", size="15px").style("color:#64748B;")
                        ui.label(timezone).classes("reminder-meta")

                if reminder.get("description"):
                    ui.label(str(reminder["description"])).classes("reminder-description").style("margin-top:3px;")

        with ui.separator().style("margin:14px 0 10px;background:#26324A;"):
            pass

        with ui.row().classes("items-center flex-wrap reminder-actions").style("gap:7px;"):
            if not completed and on_complete:
                ui.button("Done", icon="check", on_click=lambda r=rid: on_complete(r)).props("flat dense").style(_action_style("#10B981"))
            if on_edit:
                ui.button("Edit", icon="edit", on_click=lambda r=rid: on_edit(r)).props("flat dense").style(_action_style("#A78BFA"))
            if not completed and on_snooze:
                with ui.button("Snooze", icon="schedule").props("flat dense").style(_action_style("#F59E0B")):
                    with ui.menu():
                        for mins, label in [(5, "5 minutes"), (10, "10 minutes"), (15, "15 minutes"), (30, "30 minutes"), (60, "1 hour")]:
                            ui.menu_item(label, on_click=lambda m=mins, r=rid: on_snooze(r, m))
            if on_reschedule:
                ui.button("Reschedule", icon="event", on_click=lambda r=rid: on_reschedule(r)).props("flat dense").style(_action_style("#60A5FA"))
            if on_delete:
                ui.button(icon="delete_outline", on_click=lambda r=rid: on_delete(r)).props("flat round dense").style("color:#EF4444;margin-left:auto;").tooltip("Delete reminder")
