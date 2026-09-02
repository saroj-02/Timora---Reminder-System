"""
Timora – Login Page
"""
from __future__ import annotations

from nicegui import ui

from app.frontend.api_client import api_post
from app.frontend.components.toast import toast_error, toast_success
from app.frontend.state import is_authenticated, set_token, set_user_data
from app.frontend.theme import inject_global_styles, inject_theme


def login_page() -> None:
    inject_global_styles()
    inject_theme("dark")

    if is_authenticated():
        ui.navigate.to("/dashboard")
        return

    with ui.column().classes("full-width items-center justify-center").style(
        "min-height:100vh;"
        "background:linear-gradient(135deg,#0F0F1A 0%,#1A0A2E 50%,#0F1A2E 100%);"
    ):
        # Decorative background orbs
        ui.html("""
        <div style="position:fixed;top:-100px;left:-100px;width:400px;height:400px;
            border-radius:50%;background:radial-gradient(circle,rgba(124,58,237,0.15),transparent 70%);
            pointer-events:none;"></div>
        <div style="position:fixed;bottom:-100px;right:-100px;width:500px;height:500px;
            border-radius:50%;background:radial-gradient(circle,rgba(6,182,212,0.1),transparent 70%);
            pointer-events:none;"></div>
        """)

        with ui.card().classes("glass-card q-pa-xl").style(
            "width:460px;max-width:95vw;border-radius:28px;"
            "background:rgba(26,26,46,0.9);border:1px solid rgba(124,58,237,0.3);"
            "box-shadow:0 30px 80px rgba(0,0,0,0.5);"
        ):
            # Brand
            with ui.column().classes("items-center q-mb-xl"):
                ui.label("⏰").style("font-size:52px;margin-bottom:8px;")
                ui.label("Timora").style(
                    "font-size:32px;font-weight:800;"
                    "background:linear-gradient(135deg,#7C3AED,#06B6D4);"
                    "-webkit-background-clip:text;-webkit-text-fill-color:transparent;"
                )
                ui.label("Smart Task Reminder").style(
                    "font-size:14px;color:#64748B;margin-top:4px;"
                )

            ui.label("Welcome back 👋").style(
                "font-size:22px;font-weight:700;color:#E2E8F0;margin-bottom:4px;"
            )
            ui.label("Sign in to your account").style(
                "font-size:14px;color:#64748B;margin-bottom:28px;"
            )

            email_input = ui.input("Email Address", placeholder="you@example.com").props(
                "outlined dense type=email"
            ).classes("full-width q-mb-md").style("border-radius:12px;")

            password_input = ui.input("Password", password=True).props(
                "outlined dense"
            ).classes("full-width q-mb-sm").style("border-radius:12px;")

            remember_check = ui.checkbox("Remember me for 30 days").style(
                "color:#94A3B8;font-size:13px;margin-bottom:24px;"
            )

            error_label = ui.label("").style(
                "color:#EF4444;font-size:13px;margin-bottom:12px;display:none;"
            )

            async def do_login() -> None:
                email = email_input.value.strip()
                password = password_input.value

                if not email or not password:
                    error_label.text = "Please enter your email and password."
                    error_label.style("display:block;")
                    return

                login_btn.props("loading")
                error_label.style("display:none;")

                try:
                    data = await api_post("/api/auth/login", {
                        "email": email,
                        "password": password,
                        "remember_me": remember_check.value,
                    })
                    if data and "access_token" in data:
                        set_token(data["access_token"])
                        # Fetch user profile
                        from app.frontend.api_client import api_get
                        user_data = await api_get("/api/auth/me")

                        if isinstance(user_data, dict):
                            set_user_data(user_data)
                        else:
                            toast_error("Failed to load user profile.")
                            return
                        toast_success("Welcome back! 🎉")
                        ui.navigate.to("/dashboard")
                    else:
                        error_label.text = "Invalid email or password."
                        error_label.style("display:block;")
                except Exception:
                    error_label.text = "Invalid email or password."
                    error_label.style("display:block;")
                finally:
                    login_btn.props(remove="loading")

            login_btn = ui.button(
                "Sign In",
                on_click=do_login,
            ).classes("full-width btn-primary").style(
                "height:52px;font-size:16px;border-radius:14px;"
            )

            # Allow pressing Enter
            password_input.on("keydown.enter", do_login)
            email_input.on("keydown.enter", do_login)

            ui.separator().style("margin:24px 0;background:#2D2D4E;")

            with ui.row().classes("justify-center items-center gap-xs"):
                ui.label("Don't have an account?").style("color:#64748B;font-size:14px;")
                ui.link("Sign up", "/signup").style(
                    "color:#A78BFA;font-weight:600;font-size:14px;"
                )
