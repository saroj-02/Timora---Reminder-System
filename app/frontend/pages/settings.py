from __future__ import annotations

from nicegui import ui

from app.frontend.api_client import api_get, api_post, api_put
from app.frontend.components.toast import toast_error, toast_success
from app.frontend.layouts.main_layout import main_layout
from app.frontend.state import (
    clear_token, clear_user_data,
    get_user_data, is_authenticated, set_user_data,
)
from app.frontend.theme import inject_global_styles, inject_theme
from app.utils.timezone import get_timezones_for_country, list_countries


async def settings_page() -> None:
    inject_global_styles()

    if not is_authenticated():
        ui.navigate.to("/login")
        return

    user_data: dict = get_user_data() or {}

    inject_theme(user_data.get("theme", "dark"))
    main_layout("settings")

    # Refresh user data from API
    fresh = await api_get("/api/users/me")

    if isinstance(fresh, dict):
        user_data = fresh
        set_user_data(fresh)
    countries = list_countries()

    with ui.column().classes("main-content page-enter").style(
        "padding:24px 32px;max-width:800px;margin:0 auto;"
    ):
        ui.label("⚙️ Settings").style(
            "font-size:26px;font-weight:800;color:#E2E8F0;margin-bottom:24px;"
        )

        # ── Profile ───────────────────────────────────────────────────────────
        with _section_card("👤 Profile"):
            name_input = ui.input("Full Name", value=user_data.get("name", "")).props(
                "outlined dense"
            ).classes("full-width q-mb-md")

            email_display = ui.input(
                "Email",
                value=user_data.get("email", ""),
            ).props("outlined dense readonly").classes("full-width q-mb-md")
            email_display.style("opacity:0.6;")

            country_select = ui.select(
                countries,
                label="Country",
                value=user_data.get("country") or "India",
                with_input=True,
            ).props("outlined dense").classes("full-width q-mb-md")

            tz_list = get_timezones_for_country(user_data.get("country") or "India")
            tz_select = ui.select(
                tz_list,
                label="Timezone",
                value=user_data.get("timezone") or tz_list[0],
                with_input=True,
            ).props("outlined dense").classes("full-width q-mb-md")

            def update_tz(country: str) -> None:
                tzs = get_timezones_for_country(country)
                tz_select.options = tzs
                tz_select.value = tzs[0]
                tz_select.update()

            country_select.on("update:model-value", lambda e: update_tz(e.args))

            async def save_profile() -> None:
                try:
                    updated = await api_put("/api/users/me", {
                        "name": name_input.value.strip(),
                        "country": country_select.value,
                        "timezone": tz_select.value,
                    })
                    if updated:
                        set_user_data(updated)
                    toast_success("Profile saved! ✅")
                except Exception:
                    toast_error("Failed to save profile.")

            ui.button("Save Profile", on_click=save_profile).style(
                "background:linear-gradient(135deg,#7C3AED,#2563EB);"
                "color:white;border-radius:10px;font-weight:600;border:none;"
            )

        # ── Notifications ─────────────────────────────────────────────────────
        with _section_card("🔔 Notifications"):
            notif_toggle = ui.switch(
                "Push Notifications",
                value=user_data.get("notification_enabled", False),
            ).style("color:#E2E8F0;font-weight:600;")

            sound_toggle = ui.switch(
                "Reminder Sound (in-app)",
                value=user_data.get("sound_enabled", True),
            ).style("color:#E2E8F0;font-weight:600;margin-top:12px;")

            ui.label("Volume").style("font-size:13px;color:#64748B;margin-top:16px;")
            volume_slider = ui.slider(
                min=0, max=100,
                value=int(user_data.get("sound_volume", 0.7) * 100),
            ).props("color=purple").style("margin-bottom:8px;")

            with ui.row().classes("gap-md items-center q-mt-sm"):
                ui.button("🔊 Preview Sound", on_click=_preview_sound).props("outline").style(
                    "border-color:rgba(124,58,237,0.4);color:#A78BFA;border-radius:8px;"
                )
                ui.button("Send Test Push", on_click=_send_test_push).props("outline").style(
                    "border-color:rgba(37,99,235,0.4);color:#60A5FA;border-radius:8px;"
                )

            async def save_notifications() -> None:
                try:
                    updated = await api_put("/api/users/me", {
                        "notification_enabled": notif_toggle.value,
                        "sound_enabled": sound_toggle.value,
                        "sound_volume": volume_slider.value / 100.0,
                    })
                    if updated:
                        set_user_data(updated)
                    toast_success("Notification settings saved!")
                except Exception:
                    toast_error("Failed to save settings.")

            ui.button("Save", on_click=save_notifications).style(
                "background:linear-gradient(135deg,#7C3AED,#2563EB);"
                "color:white;border-radius:10px;font-weight:600;border:none;margin-top:16px;"
            )

        # ── Appearance ────────────────────────────────────────────────────────
        with _section_card("🎨 Appearance"):
            theme_select = ui.select(
                ["dark", "light", "system"],
                label="Theme",
                value=user_data.get("theme", "dark"),
            ).props("outlined dense").style("width:200px;")

            async def save_theme() -> None:
                try:
                    updated = await api_put("/api/users/me", {"theme": theme_select.value})
                    if updated:
                        set_user_data(updated)
                    toast_success("Theme saved! Reload to apply.")
                except Exception:
                    toast_error("Failed to save theme.")

            ui.button("Apply Theme", on_click=save_theme).style(
                "background:linear-gradient(135deg,#7C3AED,#2563EB);"
                "color:white;border-radius:10px;font-weight:600;border:none;margin-top:12px;"
            )

        # ── Security ──────────────────────────────────────────────────────────
        with _section_card("🔐 Security"):
            current_pw = ui.input("Current Password", password=True).props(
                "outlined dense"
            ).classes("full-width q-mb-md")
            new_pw = ui.input("New Password", password=True).props(
                "outlined dense"
            ).classes("full-width q-mb-md")
            confirm_pw = ui.input("Confirm New Password", password=True).props(
                "outlined dense"
            ).classes("full-width q-mb-lg")

            pw_error = ui.label("").style("color:#EF4444;font-size:13px;display:none;margin-bottom:12px;")

            async def change_password() -> None:
                if new_pw.value != confirm_pw.value:
                    pw_error.text = "Passwords do not match."
                    pw_error.style("display:block;")
                    return
                if len(new_pw.value) < 8:
                    pw_error.text = "Password must be at least 8 characters."
                    pw_error.style("display:block;")
                    return
                pw_error.style("display:none;")
                try:
                    await api_post("/api/users/me/change-password", {
                        "current_password": current_pw.value,
                        "new_password": new_pw.value,
                    })
                    toast_success("Password changed successfully!")
                    current_pw.value = ""
                    new_pw.value = ""
                    confirm_pw.value = ""
                except Exception:
                    pw_error.text = "Failed to change password. Check current password."
                    pw_error.style("display:block;")

            ui.button("Change Password", on_click=change_password).style(
                "background:linear-gradient(135deg,#7C3AED,#2563EB);"
                "color:white;border-radius:10px;font-weight:600;border:none;"
            )

            ui.separator().style("margin:20px 0;background:#2D2D4E;")

            with ui.row().classes("gap-md"):
                ui.button("🚪 Logout", on_click=_do_logout).props("outline").style(
                    "border-color:rgba(239,68,68,0.4);color:#EF4444;border-radius:8px;"
                )


def _section_card(title: str):
    """Context manager for a settings section card."""
    card = ui.card().style(
        "border-radius:20px;background:#1A1A2E;border:1px solid #2D2D4E;"
        "padding:28px;margin-bottom:20px;width:100%;"
    )

    class CM:
        def __enter__(self):
            card.__enter__()
            ui.label(title).style(
                "font-size:18px;font-weight:700;color:#E2E8F0;margin-bottom:20px;"
            )
            return self

        def __exit__(self, *args):
            card.__exit__(*args)

    return CM()


def _preview_sound() -> None:
    ui.run_javascript("""
    (function() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            function playNote(f, s, d, v) {
                const o = ctx.createOscillator();
                const g = ctx.createGain();
                o.connect(g); g.connect(ctx.destination);
                o.type = 'sine'; o.frequency.setValueAtTime(f, ctx.currentTime + s);
                g.gain.setValueAtTime(0, ctx.currentTime + s);
                g.gain.linearRampToValueAtTime(v, ctx.currentTime + s + 0.05);
                g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + s + d);
                o.start(ctx.currentTime + s); o.stop(ctx.currentTime + s + d);
            }
            playNote(523.25, 0, 0.6, 0.3); playNote(659.25, 0.15, 0.6, 0.25);
            playNote(783.99, 0.3, 0.8, 0.2); playNote(1046.5, 0.5, 1.0, 0.15);
        } catch(e) {}
    })();
    """)


async def _send_test_push() -> None:
    try:
        await api_post("/api/notifications/test")
        toast_success("Test push sent! Check your browser.")
    except Exception:
        toast_error("No subscriptions found. Enable notifications first.")


def _do_logout() -> None:
    clear_token()
    clear_user_data()
    ui.navigate.to("/login")
