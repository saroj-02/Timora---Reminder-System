"""
Timora – In-App Reminder Popup + Web Audio Tone
Shows when the website is open and a reminder fires.
"""
from __future__ import annotations

from typing import Callable, Optional

from nicegui import ui


def show_reminder_popup(
    reminder_id: str,
    title: str,
    description: Optional[str] = None,
    on_done: Optional[Callable] = None,
    on_snooze: Optional[Callable] = None,
) -> None:
    """Display a beautiful animated reminder popup with sound."""

    # ── Web Audio tone ────────────────────────────────────────────────────────
    ui.run_javascript("""
    (function() {
        try {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (!AudioCtx) return;

            window.timoraAudioContext =
                window.timoraAudioContext || new AudioCtx();

            const ctx = window.timoraAudioContext;

            if (!window.timoraAudioUnlockInstalled) {
                window.timoraAudioUnlockInstalled = true;

                const unlock = async function() {
                    try {
                        if (ctx.state === 'suspended') {
                            await ctx.resume();
                        }
                    } catch (_) {}
                };

                // cspell:disable-next-line
                document.addEventListener(
                    'pointerdown',
                    unlock,
                    {passive: true}
                );

                document.addEventListener(
                    'keydown',
                    unlock,
                    {passive: true}
                );

                // cspell:disable-next-line
                document.addEventListener(
                    'touchstart',
                    unlock,
                    {passive: true}
                );
            }

            const play = async function() {
                try {
                    if (ctx.state === 'suspended') {
                        await ctx.resume();
                    }

                    if (ctx.state !== 'running') {
                        return;
                    }

                    const now = ctx.currentTime;

                    const notes = [
                        [523.25, 0.00, 0.55, 0.34],
                        [659.25, 0.16, 0.55, 0.29],
                        [783.99, 0.32, 0.75, 0.24],
                        [1046.50, 0.50, 1.00, 0.20],
                    ];

                    for (const [freq, start, duration, volume] of notes) {
                        const osc = ctx.createOscillator();
                        const gain = ctx.createGain();

                        osc.connect(gain);
                        gain.connect(ctx.destination);

                        osc.type = 'sine';

                        osc.frequency.setValueAtTime(
                            freq,
                            now + start
                        );

                        gain.gain.setValueAtTime(
                            0.0001,
                            now + start
                        );

                        gain.gain.exponentialRampToValueAtTime(
                            volume,
                            now + start + 0.04
                        );

                        gain.gain.exponentialRampToValueAtTime(
                            0.0001,
                            now + start + duration
                        );

                        osc.start(now + start);
                        osc.stop(now + start + duration + 0.02);
                    }
                } catch (_) {}
            };

            play();

        } catch (_) {}
    })();
    """)

    with ui.dialog().props("persistent") as dialog:
        dialog.open()

        with ui.card().classes(
            "reminder-popup q-pa-lg"
        ).style(
            "min-width: 380px; max-width: 480px;"
        ):

            # Header
            with ui.row().classes(
                "items-center justify-between q-mb-md"
            ):
                with ui.row().classes(
                    "items-center gap-sm"
                ):
                    ui.label("🔔").style(
                        "font-size: 28px;"
                    )

                    ui.label("REMINDER").style(
                        "font-size: 11px;"
                        "font-weight: 800;"
                        "letter-spacing: 3px;"
                        "color: #A78BFA;"
                    )

                ui.html("""
                <div style="
                    width:10px;
                    height:10px;
                    border-radius:50%;
                    background:#7C3AED;
                    box-shadow:0 0 0 0 rgba(124,58,237,0.7);
                    animation:ripple 1.5s infinite;
                "></div>

                <style>
                @keyframes ripple {
                    0% {
                        box-shadow:
                            0 0 0 0 rgba(124,58,237,0.7);
                    }

                    70% {
                        box-shadow:
                            0 0 0 10px rgba(124,58,237,0);
                    }

                    100% {
                        box-shadow:
                            0 0 0 0 rgba(124,58,237,0);
                    }
                }
                </style>
                """)

            ui.separator().style(
                "background: rgba(124,58,237,0.3);"
                "margin: 8px 0;"
            )

            # Title
            ui.label(title).style(
                "font-size: 20px;"
                "font-weight: 700;"
                "color: #E2E8F0;"
                "margin-bottom: 8px;"
            )

            if description:
                ui.label(description).style(
                    "font-size: 14px;"
                    "color: #94A3B8;"
                    "margin-bottom: 16px;"
                )

            ui.label(
                "Your task is due now."
            ).style(
                "font-size: 13px;"
                "color: #94A3B8;"
                "margin-bottom: 20px;"
            )

            # Actions
            with ui.row().classes(
                "gap-sm justify-end items-center"
            ):

                with ui.button_group():

                    snooze_options = [
                        5,
                        10,
                        15,
                        30,
                        60,
                    ]

                    with ui.button(
                        "⏰ Snooze"
                    ).props("flat").style(
                        "color: #A78BFA;"
                        "border: 1px solid rgba(124,58,237,0.4);"
                        "border-radius: 8px;"
                        "padding: 8px 16px;"
                    ):

                        with ui.menu():

                            for mins in snooze_options:
                                label = (
                                    f"{mins} min"
                                    if mins < 60
                                    else "1 hour"
                                )

                                # IMPORTANT:
                                # NiceGUI passes ClickEventArguments.
                                # Capture the integer separately.
                                with ui.menu_item(
                                    label,
                                    on_click=lambda
                                    _event,
                                    m=mins:
                                    _do_snooze(
                                        dialog,
                                        reminder_id,
                                        m,
                                        on_snooze,
                                    ),
                                ):
                                    pass

                ui.button(
                    "✅ DONE",
                    on_click=lambda:
                    _do_done(
                        dialog,
                        reminder_id,
                        on_done,
                    ),
                ).style(
                    "background: linear-gradient("
                    "135deg, #7C3AED, #2563EB);"
                    "color: white;"
                    "border-radius: 8px;"
                    "font-weight: 700;"
                    "padding: 8px 24px;"
                    "border: none;"
                )


def _do_done(
    dialog,
    reminder_id: str,
    on_done,
) -> None:
    dialog.close()

    if on_done:
        on_done(reminder_id)


def _do_snooze(
    dialog,
    reminder_id: str,
    minutes: int,
    on_snooze,
) -> None:
    dialog.close()

    if on_snooze:
        on_snooze(
            reminder_id,
            minutes,
        )