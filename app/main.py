"""
Timora – Main Application Entry Point
NiceGUI wraps FastAPI; all pages registered here.
"""

from __future__ import annotations

import base64
import logging
import pathlib
import re
import sys
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI, Request
from nicegui import ui
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import Response
from starlette.staticfiles import StaticFiles

from app.config import settings
from app.database import close_db, init_db
from app.frontend.theme import inject_global_styles
from app.routes.auth import router as auth_router
from app.routes.notifications import router as notifications_router
from app.routes.reminders import router as reminders_router
from app.routes.users import router as users_router
from app.services.scheduler_service import start_scheduler, stop_scheduler
from app.services.email_service import smtp_configuration_status


# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


# ── Rate Limit Exception Handler ─────────────────────────────────────────────


def rate_limit_exception_handler(
    request: Request,
    exc: Exception,
) -> Response:
    """
    Adapter around slowapi's rate-limit handler.

    FastAPI expects a generic Exception handler signature,
    while slowapi's handler is typed specifically for
    RateLimitExceeded.
    """

    return _rate_limit_exceeded_handler(
        request,
        cast(RateLimitExceeded, exc),
    )


# ── FastAPI Application ───────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Startup
    await init_db()
    start_scheduler()
    _ensure_vapid()

    smtp_status = smtp_configuration_status()
    logger.info(
        "SMTP STARTUP CHECK | host=%s | port=%s | "
        "username_configured=%s | password_configured=%s | "
        "from_email_configured=%s | tls=%s | "
        "resend_configured=%s | resend_from_configured=%s",
        smtp_status["host"],
        smtp_status["port"],
        smtp_status["username_configured"],
        smtp_status["password_configured"],
        smtp_status["from_email_configured"],
        smtp_status["tls"],
        smtp_status["resend_configured"],
        smtp_status["resend_from_configured"],
    )

    logger.info(
        "🚀 Timora started on %s:%s",
        settings.APP_HOST,
        settings.APP_PORT,
    )

    yield

    # Shutdown
    stop_scheduler()
    await close_db()

    logger.info("👋 Timora shut down")


fast_api = FastAPI(
    title=settings.APP_TITLE,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


# ── Rate Limiting ─────────────────────────────────────────────────────────────

limiter = Limiter(
    key_func=get_remote_address,
)

fast_api.state.limiter = limiter

fast_api.add_exception_handler(
    RateLimitExceeded,
    rate_limit_exception_handler,
)


# ── Routers ───────────────────────────────────────────────────────────────────

fast_api.include_router(auth_router)
fast_api.include_router(reminders_router)
fast_api.include_router(users_router)
fast_api.include_router(notifications_router)


# ── Static Files ──────────────────────────────────────────────────────────────

fast_api.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)


# ── VAPID Auto-generation ─────────────────────────────────────────────────────


def _ensure_vapid() -> None:
    """Generate VAPID keys on first run if not configured."""

    if settings.vapid_configured:
        return

    try:
        from py_vapid import Vapid

        vapid = Vapid()
        vapid.generate_keys()

        pub = vapid.public_key
        priv = vapid.private_key

        # Explicitly verify that the keys exist.
        # This removes the Optional/None ambiguity for Pylance.
        if pub is None:
            raise RuntimeError(
                "VAPID public key generation returned None."
            )

        if priv is None:
            raise RuntimeError(
                "VAPID private key generation returned None."
            )

        # Encode public key to URL-safe base64.
        import cryptography.hazmat.primitives.serialization as serialization

        pub_bytes = pub.public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )

        priv_bytes = priv.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )

        pub_b64 = (
            base64.urlsafe_b64encode(pub_bytes)
            .rstrip(b"=")
            .decode()
        )

        priv_pem = priv_bytes.decode()

        # Write to .env
        env_path = pathlib.Path(".env")

        current = (
            env_path.read_text()
            if env_path.exists()
            else ""
        )

        def _set_env_var(
            content: str,
            key: str,
            value: str,
        ) -> str:
            pattern = rf"^{key}=.*$"
            replacement = f"{key}={value}"

            if re.search(
                pattern,
                content,
                re.MULTILINE,
            ):
                return re.sub(
                    pattern,
                    replacement,
                    content,
                    flags=re.MULTILINE,
                )

            return content + f"\n{replacement}\n"

        current = _set_env_var(
            current,
            "VAPID_PUBLIC_KEY",
            pub_b64,
        )

        current = _set_env_var(
            current,
            "VAPID_PRIVATE_KEY",
            priv_pem.replace("\n", "\\n"),
        )

        env_path.write_text(current)

        # Update in-memory settings
        settings.VAPID_PUBLIC_KEY = pub_b64
        settings.VAPID_PRIVATE_KEY = priv_pem

        logger.info(
            "🔑 VAPID keys generated and saved to .env"
        )

    except Exception as exc:
        logger.warning(
            "Could not generate VAPID keys: %s",
            exc,
        )


# ── NiceGUI Pages ─────────────────────────────────────────────────────────────


@ui.page("/")
async def root() -> None:
    from app.frontend.state import is_authenticated

    if is_authenticated():
        ui.navigate.to("/dashboard")
    else:
        ui.navigate.to("/login")


@ui.page("/login")
async def login() -> None:
    from app.frontend.pages.login import login_page

    login_page()


@ui.page("/signup")
async def signup() -> None:
    from app.frontend.pages.signup import signup_page

    signup_page()


@ui.page("/timezone-setup")
async def timezone_setup() -> None:
    from app.frontend.pages.timezone_setup import timezone_setup_page

    timezone_setup_page()


@ui.page("/dashboard")
async def dashboard() -> None:
    from app.frontend.pages.dashboard import dashboard_page

    await dashboard_page()


@ui.page("/reminders")
@ui.page("/reminders/{reminder_id}")
async def reminders(
    reminder_id: str = "",
) -> None:
    from app.frontend.pages.reminders import reminders_page

    await reminders_page()


@ui.page("/calendar")
async def calendar() -> None:
    from app.frontend.pages.calendar_page import calendar_page

    await calendar_page()


@ui.page("/settings")
async def settings_page_route() -> None:
    from app.frontend.pages.settings import settings_page

    await settings_page()


# ── NiceGUI + FastAPI Integration ─────────────────────────────────────────────


ui.run_with(
    fast_api,
    title=settings.APP_TITLE,
    storage_secret=settings.JWT_SECRET,
    favicon="⏰",
    dark=True,
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:fast_api",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_DEBUG,
    )