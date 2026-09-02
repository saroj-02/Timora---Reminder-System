"""
Timora – Timezone Setup Page

Shown once after signup.

Features:
- Country selection
- Global IANA timezone selection
- Searchable timezone dropdown
- Browser timezone auto-detection
- UTC offset display
- Saves country + timezone to user profile
"""

from __future__ import annotations

from typing import Any

from nicegui import ui

from app.frontend.api_client import api_get, api_put
from app.frontend.components.toast import toast_error, toast_success
from app.frontend.state import is_authenticated, set_user_data
from app.frontend.theme import inject_global_styles, inject_theme
from app.utils.timezone import (
    get_timezone_offset,
    list_countries,
    list_timezones,
)


def timezone_setup_page() -> None:
    """
    Render the timezone setup page.
    """

    inject_global_styles()
    inject_theme("dark")

    # ---------------------------------------------------------
    # Authentication check
    # ---------------------------------------------------------

    if not is_authenticated():
        ui.navigate.to("/login")
        return

    # ---------------------------------------------------------
    # Load countries and ALL timezones
    # ---------------------------------------------------------

    countries = list_countries()
    all_timezones = list_timezones()

    # ---------------------------------------------------------
    # Browser detected timezone
    #
    # Using a mutable dictionary instead of ui.state()
    # avoids the NiceGUI/Pylance tuple typing problem.
    # ---------------------------------------------------------

    detected_tz: dict[str, str] = {
        "value": "",
    }

    # ---------------------------------------------------------
    # Helper: timezone display text
    # ---------------------------------------------------------

    def timezone_info_text(timezone_name: str) -> str:
        """
        Return a readable timezone offset.
        """
        if not timezone_name:
            return ""

        try:
            offset = get_timezone_offset(timezone_name)

            if offset:
                return f"UTC {offset}"

        except Exception:
            pass

        return ""

    # ---------------------------------------------------------
    # Main page
    # ---------------------------------------------------------

    with ui.column().classes(
        "full-width items-center justify-center"
    ).style(
        "min-height:100vh;"
        "background:linear-gradient(135deg,#0F0F1A 0%,#16213E 100%);"
        "padding:24px;"
        "box-sizing:border-box;"
    ):

        # -----------------------------------------------------
        # Main card
        # -----------------------------------------------------

        with ui.card().classes("q-pa-xl").style(
            "width:520px;"
            "max-width:100%;"
            "border-radius:28px;"
            "background:rgba(26,26,46,0.95);"
            "border:1px solid rgba(124,58,237,0.3);"
            "box-shadow:0 30px 80px rgba(0,0,0,0.5);"
            "box-sizing:border-box;"
        ):

            # -------------------------------------------------
            # Header
            # -------------------------------------------------

            with ui.column().classes(
                "items-center q-mb-xl"
            ):

                ui.label("🌍").style(
                    "font-size:52px;"
                    "line-height:1;"
                    "margin-bottom:12px;"
                )

                ui.label("Set Your Timezone").style(
                    "font-size:26px;"
                    "font-weight:800;"
                    "color:#E2E8F0;"
                    "text-align:center;"
                )

                ui.label(
                    "We'll use this to schedule your reminders accurately."
                ).style(
                    "font-size:14px;"
                    "color:#64748B;"
                    "text-align:center;"
                    "margin-top:8px;"
                    "line-height:1.5;"
                )

            # -------------------------------------------------
            # Browser detection area
            # -------------------------------------------------

            detected_label = ui.html("").style(
                "width:100%;"
                "margin-bottom:16px;"
            )

            use_detected_btn = ui.button(
                "",
            ).props(
                "flat dense"
            ).style(
                "display:none;"
                "color:#A78BFA;"
                "font-size:13px;"
                "margin-bottom:16px;"
            )

            # -------------------------------------------------
            # Country selector
            #
            # Country is stored as profile information.
            # It NO LONGER filters the timezone list.
            # -------------------------------------------------

            country_select = ui.select(
                countries,
                label="Country",
                value="India",
                with_input=True,
            ).props(
                "outlined dense"
            ).classes(
                "full-width q-mb-md"
            )

            # -------------------------------------------------
            # Global timezone selector
            #
            # IMPORTANT:
            # This uses ALL IANA timezones.
            # Country does not restrict this list.
            # -------------------------------------------------

            tz_select = ui.select(
                all_timezones,
                label="Timezone",
                value="Asia/Kolkata",
                with_input=True,
            ).props(
                "outlined dense"
            ).classes(
                "full-width"
            )

            # -------------------------------------------------
            # Timezone offset information
            # -------------------------------------------------

            tz_offset_label = ui.label(
                timezone_info_text("Asia/Kolkata")
            ).style(
                "width:100%;"
                "font-size:13px;"
                "font-weight:600;"
                "color:#A78BFA;"
                "margin-top:8px;"
                "margin-bottom:24px;"
                "padding-left:4px;"
            )

            # -------------------------------------------------
            # Update timezone information
            # -------------------------------------------------

            def update_timezone_info(timezone_name: Any) -> None:
                """
                Update the UTC offset displayed below
                the timezone selector.
                """

                if not isinstance(timezone_name, str):
                    timezone_name = ""

                tz_offset_label.text = timezone_info_text(
                    timezone_name
                )

                tz_offset_label.update()

            # -------------------------------------------------
            # Timezone selection changed
            # -------------------------------------------------

            def on_timezone_change(event: Any) -> None:
                """
                Handle timezone dropdown changes.
                """

                value = event.args

                if isinstance(value, str):
                    update_timezone_info(value)

            tz_select.on(
                "update:model-value",
                on_timezone_change,
            )

            # -------------------------------------------------
            # Country change
            #
            # IMPORTANT:
            # We intentionally DO NOT change timezone options.
            #
            # The user can choose any timezone regardless of
            # their selected country.
            # -------------------------------------------------

            def on_country_change(event: Any) -> None:
                """
                Country is independent from timezone.

                We only keep the selected country as profile
                information.
                """

                _ = event

            country_select.on(
                "update:model-value",
                on_country_change,
            )

            # -------------------------------------------------
            # Detect browser timezone using JavaScript
            # -------------------------------------------------

            ui.run_javascript(
                """
                (function() {
                    try {
                        const tz =
                            Intl.DateTimeFormat()
                                .resolvedOptions()
                                .timeZone;

                        if (tz) {
                            emitEvent(
                                'browser_tz',
                                {tz: tz}
                            );
                        }
                    } catch (error) {
                        console.error(
                            'Timezone detection failed:',
                            error
                        );
                    }
                })();
                """
            )

            # -------------------------------------------------
            # Receive browser timezone
            # -------------------------------------------------

            def on_browser_tz(event: Any) -> None:
                """
                Receive timezone detected by the browser.
                """

                timezone_name = ""

                args = event.args

                if isinstance(args, dict):
                    value = args.get("tz", "")

                    if isinstance(value, str):
                        timezone_name = value

                if not timezone_name:
                    return

                # Save detected timezone
                detected_tz["value"] = timezone_name

                # Check whether the browser timezone exists
                # in our global IANA timezone list.
                if timezone_name in all_timezones:

                    # Automatically select it.
                    tz_select.value = timezone_name
                    tz_select.update()

                    # Update UTC offset.
                    update_timezone_info(
                        timezone_name
                    )

                # -------------------------------------------------
                # Browser detection card
                # -------------------------------------------------

                offset = timezone_info_text(
                    timezone_name
                )

                detected_label.content = f"""
                    <div style="
                        background:rgba(124,58,237,0.10);
                        border:1px solid rgba(124,58,237,0.30);
                        border-radius:14px;
                        padding:14px 16px;
                        margin-bottom:10px;
                        display:flex;
                        align-items:center;
                        justify-content:space-between;
                        gap:12px;
                        box-sizing:border-box;
                    ">
                        <div style="
                            min-width:0;
                            flex:1;
                        ">
                            <div style="
                                font-size:12px;
                                color:#64748B;
                                margin-bottom:4px;
                            ">
                                🔍 Browser detected timezone
                            </div>

                            <div style="
                                font-size:15px;
                                font-weight:700;
                                color:#A78BFA;
                                word-break:break-word;
                            ">
                                {timezone_name}
                            </div>

                            <div style="
                                font-size:12px;
                                color:#64748B;
                                margin-top:3px;
                            ">
                                {offset}
                            </div>
                        </div>
                    </div>
                """

                detected_label.update()

                # -------------------------------------------------
                # Show use detected button
                # -------------------------------------------------

                use_detected_btn.text = (
                    f"✨ Use {timezone_name}"
                )

                use_detected_btn.style(
                    "display:inline-flex;"
                    "margin-bottom:16px;"
                )

                use_detected_btn.update()

            ui.on(
                "browser_tz",
                on_browser_tz,
            )

            # -------------------------------------------------
            # Use detected timezone button
            # -------------------------------------------------

            def use_detected() -> None:
                """
                Manually apply browser-detected timezone.
                """

                timezone_name = detected_tz["value"]

                if not timezone_name:
                    return

                if timezone_name not in all_timezones:
                    toast_error(
                        "Detected timezone is not available."
                    )
                    return

                tz_select.value = timezone_name
                tz_select.update()

                update_timezone_info(
                    timezone_name
                )

                toast_success(
                    f"Timezone set to {timezone_name}"
                )

            use_detected_btn.on(
                "click",
                use_detected,
            )

            # -------------------------------------------------
            # Error message
            # -------------------------------------------------

            error_label = ui.label("").style(
                "width:100%;"
                "color:#EF4444;"
                "font-size:13px;"
                "margin-bottom:12px;"
                "display:none;"
            )

            # -------------------------------------------------
            # Save timezone
            # -------------------------------------------------

            async def save_timezone() -> None:
                """
                Save country + timezone to the backend.
                """

                country = country_select.value
                timezone = tz_select.value

                # ---------------------------------------------
                # Validate country
                # ---------------------------------------------

                if not country:
                    error_label.text = (
                        "Please select your country."
                    )

                    error_label.style(
                        "display:block;"
                    )

                    error_label.update()

                    return

                # ---------------------------------------------
                # Validate timezone
                # ---------------------------------------------

                if not timezone:
                    error_label.text = (
                        "Please select a timezone."
                    )

                    error_label.style(
                        "display:block;"
                    )

                    error_label.update()

                    return

                if not isinstance(timezone, str):
                    error_label.text = (
                        "Invalid timezone selected."
                    )

                    error_label.style(
                        "display:block;"
                    )

                    error_label.update()

                    return

                if timezone not in all_timezones:
                    error_label.text = (
                        "Please select a valid timezone."
                    )

                    error_label.style(
                        "display:block;"
                    )

                    error_label.update()

                    return

                # ---------------------------------------------
                # Hide previous error
                # ---------------------------------------------

                error_label.style(
                    "display:none;"
                )

                error_label.update()

                # ---------------------------------------------
                # Loading state
                # ---------------------------------------------

                save_btn.props(
                    "loading"
                )

                save_btn.update()

                try:

                    # -----------------------------------------
                    # Save to backend
                    # -----------------------------------------

                    await api_put(
                        "/api/users/me",
                        {
                            "country": country,
                            "timezone": timezone,
                        },
                    )

                    # -----------------------------------------
                    # Refresh user data
                    # -----------------------------------------

                    user_data = await api_get(
                        "/api/auth/me"
                    )

                    if isinstance(
                        user_data,
                        dict,
                    ):
                        set_user_data(
                            user_data
                        )

                    # -----------------------------------------
                    # Success
                    # -----------------------------------------

                    toast_success(
                        "Timezone saved! 🌍"
                    )

                    ui.navigate.to(
                        "/dashboard"
                    )

                except Exception as exc:

                    print(
                        "Failed to save timezone:",
                        exc,
                    )

                    error_label.text = (
                        "Failed to save timezone. "
                        "Please try again."
                    )

                    error_label.style(
                        "display:block;"
                    )

                    error_label.update()

                    toast_error(
                        "Failed to save timezone."
                    )

                finally:

                    save_btn.props(
                        remove="loading"
                    )

                    save_btn.update()

            # -------------------------------------------------
            # Save button
            # -------------------------------------------------

            save_btn = ui.button(
                "Continue to Dashboard →",
                on_click=save_timezone,
            ).classes(
                "full-width btn-primary"
            ).style(
                "height:52px;"
                "font-size:16px;"
                "font-weight:700;"
                "border-radius:14px;"
            )

            # -------------------------------------------------
            # Skip button
            # -------------------------------------------------

            ui.button(
                "Skip for now",
                on_click=lambda: ui.navigate.to(
                    "/dashboard"
                ),
            ).props(
                "flat"
            ).classes(
                "full-width q-mt-sm"
            ).style(
                "color:#64748B;"
                "font-size:13px;"
            )