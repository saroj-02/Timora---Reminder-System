"""Timora – Dashboard Page."""

from __future__ import annotations

import logging

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from zoneinfo import ZoneInfo

from nicegui import ui

from app.frontend.api_client import (
    api_get,
    api_post,
)

from app.frontend.components.reminder_card import (
    reminder_card,
)

from app.frontend.components.reminder_modal import (
    open_reminder_modal,
)

from app.frontend.components.reminder_popup import (
    show_reminder_popup,
)

from app.frontend.components.toast import (
    toast_error,
    toast_success,
)

from app.frontend.layouts.main_layout import (
    main_layout,
)

from app.frontend.state import (
    get_user_data,
    is_authenticated,
)

from app.frontend.theme import (
    inject_global_styles,
    inject_theme,
)

from app.models.reminder import (
    REMINDER_BEFORE_MINUTES,
    ReminderBefore,
)


DEFAULT_TIMEZONE = "Asia/Kolkata"


async def dashboard_page() -> None:

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

    main_layout("dashboard")


    user_tz = (
        user_data.get("timezone")
        or DEFAULT_TIMEZONE
    )

    user_name = (
        user_data.get("name")
        or "User"
    )


    try:

        tz = ZoneInfo(user_tz)

    except Exception:

        user_tz = DEFAULT_TIMEZONE

        tz = ZoneInfo(
            DEFAULT_TIMEZONE
        )


    now_local = datetime.now(tz)

    hour = now_local.hour


    if hour < 12:

        greeting = "Good Morning"

    elif hour < 18:

        greeting = "Good Afternoon"

    else:

        greeting = "Good Evening"


    day_str = now_local.strftime(
        "%A, %B %d"
    )


    with ui.column().classes(
        "main-content page-enter"
    ):

        with ui.row().classes(
            "items-center "
            "justify-between "
            "full-width"
        ).style(
            "gap:20px;"
            "margin-bottom:30px;"
            "flex-wrap:wrap;"
        ):

            with ui.column().classes(
                "gap-xs"
            ):

                ui.label(
                    f"{greeting}, "
                    f"{user_name} 👋"
                ).classes(
                    "page-title"
                )

                ui.label(
                    day_str
                ).classes(
                    "page-subtitle"
                )

                with ui.row().classes(
                    "items-center no-wrap"
                ).style(
                    "gap:6px;"
                    "margin-top:2px;"
                ):

                    ui.icon(
                        "public",
                        size="16px",
                    ).style(
                        "color:#64748B;"
                    )

                    ui.label(
                        user_tz
                    ).style(
                        "font-size:12px;"
                        "color:#64748B;"
                    )


            ui.button(
                "Add Reminder",
                icon="add",
                on_click=lambda:
                open_reminder_modal(
                    on_saved=lambda:
                    ui.navigate.to(
                        "/dashboard"
                    )
                ),
            ).classes(
                "btn-primary"
            ).style(
                "min-height:46px;"
                "padding:0 20px;"
            )


        # ── Load reminders ──────────────────────────────────────────────────

        all_data = await api_get(
            "/api/reminders",
            {"limit": 500},
        )


        if isinstance(
            all_data,
            dict,
        ):

            all_reminders = (
                all_data.get(
                    "items",
                    []
                )
            )

        elif isinstance(
            all_data,
            list,
        ):

            all_reminders = all_data

        else:

            all_reminders = []


        # ── TODAY ───────────────────────────────────────────────────────────
        #
        # IMPORTANT:
        # Do NOT compare formatted strings.
        #
        # Always use the canonical UTC datetime and
        # convert it into the user's timezone.

        today_items = [

            reminder

            for reminder
            in all_reminders

            if _is_today_for_user(
                reminder,
                tz,
                now_local.date(),
            )

        ]


        # ── UPCOMING ────────────────────────────────────────────────────────

        now_utc_value = (
            datetime.now(
                timezone.utc
            )
        )


        upcoming = []


        for reminder in all_reminders:

            if (
                reminder.get("status")
                != "pending"
            ):
                continue


            scheduled_utc = (
                _scheduled_datetime_utc(
                    reminder
                )
            )


            if (
                scheduled_utc is not None
                and scheduled_utc
                > now_utc_value
            ):

                upcoming.append(
                    reminder
                )


        completed = [

            reminder

            for reminder
            in all_reminders

            if (
                reminder.get("status")
                == "completed"
            )

        ]


        # ── Statistics ─────────────────────────────────────────────────────

        with ui.element(
            "div"
        ).classes(
            "stat-grid"
        ).style(
            "margin-bottom:24px;"
        ):

            _stat_card(
                "Total reminders",
                str(
                    len(
                        all_reminders
                    )
                ),
                "task_alt",
                "#A78BFA",
                "stat-total",
            )

            _stat_card(
                "Due today",
                str(
                    len(
                        today_items
                    )
                ),
                "today",
                "#60A5FA",
                "stat-today",
            )

            _stat_card(
                "Upcoming",
                str(
                    len(
                        upcoming
                    )
                ),
                "upcoming",
                "#67E8F9",
                "stat-upcoming",
            )

            _stat_card(
                "Completed",
                str(
                    len(
                        completed
                    )
                ),
                "check_circle",
                "#34D399",
                "stat-completed",
            )


        # ── Notification enable card ───────────────────────────────────────

        if not user_data.get(
            "notification_enabled"
        ):

            with ui.card().classes(
                "notification-card"
            ).style(
                "margin-bottom:28px;"
            ):

                with ui.row().classes(
                    "items-center "
                    "justify-between "
                    "full-width"
                ).style(
                    "gap:16px;"
                    "flex-wrap:wrap;"
                ):

                    with ui.row().classes(
                        "items-center no-wrap"
                    ).style(
                        "gap:12px;"
                    ):

                        with ui.element(
                            "div"
                        ).style(
                            "width:42px;"
                            "height:42px;"
                            "border-radius:12px;"
                            "background:"
                            "rgba(124,58,237,.16);"
                            "display:flex;"
                            "align-items:center;"
                            "justify-content:center;"
                        ):

                            ui.icon(
                                "notifications",
                                size="21px",
                            ).style(
                                "color:#A78BFA;"
                            )


                        with ui.column().classes(
                            "gap-xs"
                        ):

                            ui.label(
                                "Enable notifications"
                            ).style(
                                "font-size:15px;"
                                "font-weight:700;"
                                "color:#F1F5F9;"
                            )

                            ui.label(
                                "Get reminded even when "
                                "Timora is not open."
                            ).style(
                                "font-size:12px;"
                                "color:#94A3B8;"
                            )


                    ui.button(
                        "Enable now",
                        icon="notifications_active",
                        on_click=(
                            _request_push_permission
                        ),
                    ).classes(
                        "btn-primary"
                    ).props(
                        "dense"
                    ).style(
                        "min-height:40px;"
                    )


        # ── TODAY SECTION ───────────────────────────────────────────────────

        with ui.column().classes(
            "full-width"
        ).style(
            "margin-bottom:30px;"
        ):

            _section_header(
                "Today",
                "today",
                len(today_items),
                "#60A5FA",
            )


            if today_items:

                for reminder in sorted(
                    today_items,
                    key=lambda item:
                    item.get(
                        "local_datetime_str",
                        "",
                    ),
                ):

                    reminder_card(
                        reminder,

                        on_complete=_complete,

                        on_delete=_delete,

                        on_snooze=_snooze,

                        on_edit=lambda
                        rid,
                        rs=all_reminders:
                        _open_edit(
                            rid,
                            rs,
                        ),
                    )

            else:

                _empty_state(
                    "Nothing scheduled "
                    "for today. "
                    "Enjoy the breathing room."
                )


        # ── UPCOMING SECTION ────────────────────────────────────────────────

        pending = [

            reminder

            for reminder
            in upcoming

            if not _is_today_for_user(
                reminder,
                tz,
                now_local.date(),
            )

        ]


        with ui.column().classes(
            "full-width"
        ):

            _section_header(
                "Upcoming",
                "upcoming",
                len(pending),
                "#67E8F9",
            )


            if pending:

                for reminder in pending[:10]:

                    reminder_card(
                        reminder,

                        on_complete=_complete,

                        on_delete=_delete,

                        on_snooze=_snooze,

                        on_edit=lambda
                        rid,
                        rs=all_reminders:
                        _open_edit(
                            rid,
                            rs,
                        ),
                    )

            else:

                _empty_state(
                    "No upcoming reminders "
                    "right now."
                )


    # IMPORTANT:
    # Start browser-side fallback polling.
    _setup_in_app_check(
        user_tz,
        bool(
            user_data.get(
                "sound_enabled",
                True,
            )
        ),
    )


def _section_header(
    title: str,
    icon: str,
    count: int,
    color: str,
) -> None:

    with ui.row().classes(
        "items-center"
    ).style(
        "gap:9px;"
        "margin-bottom:12px;"
    ):

        ui.icon(
            icon,
            size="21px",
        ).style(
            f"color:{color};"
        )

        ui.label(
            title
        ).classes(
            "section-heading"
        )

        if count:

            ui.label(
                str(count)
            ).classes(
                "section-count"
            )


def _stat_card(
    title: str,
    value: str,
    icon: str,
    color: str,
    extra_class: str,
) -> None:

    with ui.card().classes(
        f"stat-card {extra_class}"
    ):

        with ui.row().classes(
            "items-center "
            "justify-between "
            "no-wrap"
        ):

            ui.icon(
                icon,
                size="25px",
            ).style(
                f"color:{color};"
            )

            ui.label(
                value
            ).classes(
                "stat-value"
            ).style(
                f"color:{color};"
            )

        ui.label(
            title
        ).classes(
            "stat-title"
        )


def _empty_state(
    message: str,
) -> None:

    with ui.column().classes(
        "empty-state "
        "items-center "
        "full-width"
    ):

        ui.icon(
            "event_note",
            size="38px",
        ).style(
            "color:#64748B;"
        )

        ui.label(
            message
        ).style(
            "font-size:13px;"
            "color:#64748B;"
            "text-align:center;"
            "margin-top:9px;"
        )


async def _complete(
    rid: str,
) -> None:

    try:

        await api_post(
            f"/api/reminders/{rid}/complete"
        )

        toast_success(
            "Reminder completed."
        )

        ui.navigate.to(
            "/dashboard"
        )

    except Exception:

        toast_error(
            "Failed to complete reminder."
        )


async def _delete(
    rid: str,
) -> None:

    from app.frontend.api_client import (
        api_delete,
    )

    try:

        ok = await api_delete(
            f"/api/reminders/{rid}"
        )

        if ok:

            toast_success(
                "Reminder deleted."
            )

            ui.navigate.to(
                "/dashboard"
            )

        else:

            toast_error(
                "Failed to delete reminder."
            )

    except Exception:

        toast_error(
            "Failed to delete reminder."
        )


async def _snooze(
    rid: str,
    minutes: int,
) -> None:

    try:

        await api_post(
            f"/api/reminders/{rid}/snooze",
            {
                "minutes": minutes
            },
        )

        toast_success(
            f"Snoozed for {minutes} minutes."
        )

        ui.navigate.to(
            "/dashboard"
        )

    except Exception:

        toast_error(
            "Failed to snooze reminder."
        )


def _open_edit(
    rid: str,
    reminders: list,
) -> None:

    existing = next(
        (
            reminder
            for reminder
            in reminders
            if reminder["id"] == rid
        ),
        None,
    )

    if existing:

        open_reminder_modal(
            on_saved=lambda:
            ui.navigate.to(
                "/dashboard"
            ),
            existing=existing,
        )


def _request_push_permission() -> None:

    ui.run_javascript("""
    (async function() {

        if (
            !('serviceWorker' in navigator)
            ||
            !('PushManager' in window)
        ) {

            alert(
                'Push notifications are '
                'not supported in this browser.'
            );

            return;
        }


        const permission =
            await Notification.requestPermission();


        if (
            permission !== 'granted'
        ) {

            alert(
                'Notification permission '
                'was not granted.'
            );

            return;
        }


        try {

            const reg =
                await navigator.serviceWorker.register(
                    '/static/service-worker.js',
                    {
                        scope: '/'
                    }
                );


            await navigator.serviceWorker.ready;


            const res =
                await fetch(
                    '/api/notifications/vapid-public-key'
                );


            const {
                public_key
            } = await res.json();


            if (!public_key) {

                alert(
                    'Notification service '
                    'is not configured.'
                );

                return;
            }


            const sub =
                await reg.pushManager.subscribe({

                    userVisibleOnly: true,

                    applicationServerKey:
                        urlBase64ToUint8Array(
                            public_key
                        ),
                });


            const subJson =
                sub.toJSON();


            const token =
                document.cookie.match(
                    /timora_token=([^;]+)/
                )?.[1]
                ||
                localStorage.getItem(
                    'timora_token'
                );


            await fetch(
                '/api/notifications/subscribe',
                {

                    method: 'POST',

                    headers: {

                        'Content-Type':
                            'application/json',

                        ...(token
                            ? {
                                'Authorization':
                                    'Bearer ' + token
                            }
                            : {}),
                    },

                    body: JSON.stringify({

                        endpoint:
                            subJson.endpoint,

                        p256dh:
                            subJson.keys.p256dh,

                        auth:
                            subJson.keys.auth,

                        browser:
                            navigator.userAgent.slice(
                                0,
                                100
                            ),
                    }),
                }
            );


            location.reload();


        } catch (err) {

            console.error(
                err
            );

            alert(
                'Failed to enable notifications: '
                + err.message
            );
        }


        function urlBase64ToUint8Array(
            base64String
        ) {

            const padding =
                '='.repeat(
                    (
                        4
                        - base64String.length % 4
                    ) % 4
                );


            const rawData =
                atob(
                    (
                        base64String
                        + padding
                    )
                    .replace(
                        /-/g,
                        '+'
                    )
                    .replace(
                        /_/g,
                        '/'
                    )
                );


            return Uint8Array.from(
                [
                    ...rawData
                ].map(
                    c =>
                    c.charCodeAt(0)
                )
            );
        }

    })();
    """)


def _scheduled_datetime_utc(
    reminder: dict,
) -> datetime | None:

    raw = reminder.get(
        "scheduled_time_utc"
    )

    if not raw:
        return None


    try:

        value = datetime.fromisoformat(
            str(raw).replace(
                "Z",
                "+00:00",
            )
        )


        if value.tzinfo is None:

            value = value.replace(
                tzinfo=timezone.utc
            )


        return value.astimezone(
            timezone.utc
        )


    except (
        TypeError,
        ValueError,
    ):

        return None


def _is_today_for_user(
    reminder: dict,
    user_tz: ZoneInfo,
    today,
) -> bool:

    scheduled = (
        _scheduled_datetime_utc(
            reminder
        )
    )

    if scheduled is None:
        return False


    return (
        scheduled
        .astimezone(user_tz)
        .date()
        == today
    )


def _reminder_due_at_utc(
    reminder: dict,
) -> datetime | None:

    scheduled = (
        _scheduled_datetime_utc(
            reminder
        )
    )

    if scheduled is None:
        return None


    before = reminder.get(
        "reminder_before",
        "at_time",
    )


    try:

        minutes = (
            REMINDER_BEFORE_MINUTES.get(
                ReminderBefore(
                    before
                ),
                0,
            )
        )

    except ValueError:

        minutes = 0


    return (
        scheduled
        - timedelta(
            minutes=minutes
        )
    )


def _setup_in_app_check(
    user_tz: str,
    sound_enabled: bool = True,
) -> None:

    """
    Browser-side fallback notification system.

    Checks every 5 seconds.

    It handles:
    - SENT reminders
    - pending reminders whose notification time arrived
    - snoozed reminders
    """

    shown_ids: set[str] = set()


    async def check_due() -> None:

        try:

            data = await api_get(
                "/api/reminders",
                {
                    "limit": 500
                },
            )


            if isinstance(
                data,
                dict,
            ):

                items = data.get(
                    "items",
                    []
                )

            elif isinstance(
                data,
                list,
            ):

                items = data

            else:

                items = []


            now = datetime.now(
                timezone.utc
            )


            for reminder in items:

                rid = reminder.get(
                    "id"
                )


                if (
                    not rid
                    or rid in shown_ids
                ):

                    continue


                status = str(
                    reminder.get(
                        "status",
                        "",
                    )
                ).lower()


                due_at = (
                    _reminder_due_at_utc(
                        reminder
                    )
                )


                is_due = (

                    status == "sent"

                    or (

                        status
                        in {
                            "pending",
                            "snoozed",
                        }

                        and due_at is not None

                        and due_at <= now
                    )
                )


                if not is_due:

                    continue


                # Snoozed reminder:
                # wait until snooze_until.

                snooze_raw = (
                    reminder.get(
                        "snooze_until"
                    )
                )


                if (
                    status == "snoozed"
                    and snooze_raw
                ):

                    try:

                        snooze_until = (
                            datetime.fromisoformat(
                                str(
                                    snooze_raw
                                ).replace(
                                    "Z",
                                    "+00:00",
                                )
                            )
                        )


                        if (
                            snooze_until.tzinfo
                            is None
                        ):

                            snooze_until = (
                                snooze_until.replace(
                                    tzinfo=timezone.utc
                                )
                            )


                        if (
                            snooze_until
                            .astimezone(
                                timezone.utc
                            )
                            > now
                        ):

                            continue


                    except (
                        TypeError,
                        ValueError,
                    ):

                        pass


                shown_ids.add(
                    rid
                )


                show_reminder_popup(

                    reminder_id=rid,

                    title=reminder.get(
                        "title",
                        "Reminder",
                    ),

                    description=reminder.get(
                        "description"
                    ),

                    on_done=lambda
                    r=rid:
                    ui.timer(
                        0,
                        lambda:
                        _complete(r),
                        once=True,
                    ),

                    on_snooze=lambda
                    r=rid:
                    ui.timer(
                        0,
                        lambda:
                        _snooze(
                            r,
                            10,
                        ),
                        once=True,
                    ),
                )


        except Exception as exc:

            logging.getLogger(
                __name__
            ).debug(
                "Reminder notification "
                "poll failed: %s",
                exc,
            )


    # ── Unlock browser audio ────────────────────────────────────────────────

    ui.run_javascript("""
    (function() {

        try {

            const AudioCtx =
                window.AudioContext ||
                window.webkitAudioContext;


            if (
                !AudioCtx
                ||
                window.timoraAudioUnlockInstalled
            ) {

                return;
            }


            window.timoraAudioContext =
                window.timoraAudioContext ||
                new AudioCtx();


            const ctx =
                window.timoraAudioContext;


            const unlock =
                async function() {

                    try {

                        if (
                            ctx.state
                            === 'suspended'
                        ) {

                            await ctx.resume();
                        }

                    } catch (_) {}
                };


            // cspell:disable-next-line
            document.addEventListener(
                'pointerdown',
                unlock,
                {
                    passive: true
                }
            );


            document.addEventListener(
                'keydown',
                unlock,
                {
                    passive: true
                }
            );


            // cspell:disable-next-line
            document.addEventListener(
                'touchstart',
                unlock,
                {
                    passive: true
                }
            );


            window.timoraAudioUnlockInstalled =
                true;


        } catch (_) {}
    })();
    """)


    # Immediate check
    ui.timer(
        0.2,
        check_due,
        once=True,
    )


    # Check every 5 seconds
    ui.timer(
        5.0,
        check_due,
    )