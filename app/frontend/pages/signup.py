"""
Timora – Signup Page
"""
from __future__ import annotations

from nicegui import ui

from app.frontend.api_client import api_get, api_post
from app.frontend.components.toast import toast_error, toast_success
from app.frontend.state import is_authenticated, set_token, set_user_data
from app.frontend.theme import inject_global_styles, inject_theme


def signup_page() -> None:
    inject_global_styles()
    inject_theme("dark")

    if is_authenticated():
        ui.navigate.to("/dashboard")
        return

    with ui.column().classes("full-width items-center justify-center").style(
        "min-height:100vh;"
        "background:linear-gradient(135deg,#0F0F1A 0%,#1A0A2E 50%,#0F1A2E 100%);"
    ):
        ui.html("""
        <div style="position:fixed;top:-80px;right:-80px;width:400px;height:400px;
            border-radius:50%;background:radial-gradient(circle,rgba(124,58,237,0.12),transparent 70%);
            pointer-events:none;"></div>
        <div style="position:fixed;bottom:-80px;left:-80px;width:500px;height:500px;
            border-radius:50%;background:radial-gradient(circle,rgba(6,182,212,0.08),transparent 70%);
            pointer-events:none;"></div>
        """)

        with ui.card().classes("glass-card q-pa-xl").style(
            "width:480px;max-width:95vw;border-radius:28px;"
            "background:rgba(26,26,46,0.9);border:1px solid rgba(124,58,237,0.3);"
            "box-shadow:0 30px 80px rgba(0,0,0,0.5);"
        ):
            with ui.column().classes("items-center q-mb-lg"):
                ui.label("⏰").style("font-size:44px;margin-bottom:6px;")
                ui.label("Timora").style(
                    "font-size:28px;font-weight:800;"
                    "background:linear-gradient(135deg,#7C3AED,#06B6D4);"
                    "-webkit-background-clip:text;-webkit-text-fill-color:transparent;"
                )

            ui.label("Create your account").style(
                "font-size:22px;font-weight:700;color:#E2E8F0;margin-bottom:4px;"
            )
            ui.label("Start organizing your life 🚀").style(
                "font-size:14px;color:#64748B;margin-bottom:28px;"
            )

            name_input = ui.input("Full Name", placeholder="John Doe").props(
                "outlined dense"
            ).classes("full-width q-mb-md")

            email_input = ui.input("Email Address", placeholder="you@example.com").props(
                "outlined dense type=email"
            ).classes("full-width q-mb-md")

            password_input = ui.input(
                "Password",
                password=True,
                placeholder="Min 8 chars, uppercase, lowercase, digit",
            ).props("outlined dense").classes("full-width q-mb-md")

            confirm_input = ui.input("Confirm Password", password=True).props(
                "outlined dense"
            ).classes("full-width q-mb-md")

            # Password strength indicator
            strength_bar = ui.html("").style("margin-bottom:16px;")

            def update_strength(value: str) -> None:
                score = 0
                checks = [
                    len(value) >= 8,
                    any(c.isupper() for c in value),
                    any(c.islower() for c in value),
                    any(c.isdigit() for c in value),
                    any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in value),
                ]
                score = sum(checks)
                colors = ["#EF4444", "#F59E0B", "#F59E0B", "#10B981", "#10B981"]
                labels = ["Very Weak", "Weak", "Fair", "Strong", "Very Strong"]
                color = colors[min(score, 4)]
                label = labels[min(score, 4)]
                width = (score / 5) * 100
                strength_bar.content = f"""
                <div style="margin-bottom:8px;">
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                        <span style="font-size:12px;color:#64748B;">Password strength</span>
                        <span style="font-size:12px;color:{color};font-weight:600;">{label}</span>
                    </div>
                    <div style="height:4px;border-radius:2px;background:#2D2D4E;">
                        <div style="height:100%;width:{width}%;border-radius:2px;
                            background:{color};transition:all 0.3s ease;"></div>
                    </div>
                </div>
                """

            password_input.on("update:model-value", lambda e: update_strength(e.args if isinstance(e.args, str) else ""))

            error_label = ui.label("").style(
                "color:#EF4444;font-size:13px;margin-bottom:12px;display:none;"
            )

            async def do_signup() -> None:
                name = name_input.value.strip()
                email = email_input.value.strip()
                password = password_input.value
                confirm = confirm_input.value

                # Client-side validation
                if not name:
                    error_label.text = "Full name is required."
                    error_label.style("display:block;"); return
                if not email or "@" not in email:
                    error_label.text = "Please enter a valid email address."
                    error_label.style("display:block;"); return
                if len(password) < 8:
                    error_label.text = "Password must be at least 8 characters."
                    error_label.style("display:block;"); return
                if password != confirm:
                    error_label.text = "Passwords do not match."
                    error_label.style("display:block;"); return
                if not any(c.isupper() for c in password):
                    error_label.text = "Password must contain at least one uppercase letter."
                    error_label.style("display:block;"); return
                if not any(c.isdigit() for c in password):
                    error_label.text = "Password must contain at least one digit."
                    error_label.style("display:block;"); return

                signup_btn.props("loading")
                error_label.style("display:none;")

                try:
                    data = await api_post("/api/auth/signup", {
                        "name": name,
                        "email": email,
                        "password": password,
                        "confirm_password": confirm,
                    })
                    if data and "access_token" in data:
                        set_token(data["access_token"])
                        user_data = await api_get("/api/auth/me")
                        if isinstance(user_data, dict):
                            set_user_data(user_data)
                        toast_success("Account created! Welcome to Timora 🎉")
                        ui.navigate.to("/timezone-setup")
                    else:
                        error_label.text = "Signup failed. Please try again."
                        error_label.style("display:block;")
                except Exception as exc:
                    err = str(exc)
                    if "409" in err or "already exists" in err.lower():
                        error_label.text = "An account with this email already exists."
                    elif "422" in err:
                        error_label.text = "Please check your password requirements."
                    else:
                        error_label.text = "Signup failed. Please try again."
                    error_label.style("display:block;")
                finally:
                    signup_btn.props(remove="loading")

            signup_btn = ui.button(
                "Create Account",
                on_click=do_signup,
            ).classes("full-width btn-primary").style(
                "height:52px;font-size:16px;border-radius:14px;"
            )

            ui.separator().style("margin:24px 0;background:#2D2D4E;")

            with ui.row().classes("justify-center items-center gap-xs"):
                ui.label("Already have an account?").style("color:#64748B;font-size:14px;")
                ui.link("Sign in", "/login").style(
                    "color:#A78BFA;font-weight:600;font-size:14px;"
                )
