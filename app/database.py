"""
Timora – Database Initialization
Sets up Motor async client and Beanie ODM.

Production:
    Uses the configured MongoDB server.

Local development:
    Can fall back to an in-memory MongoMock database when MongoDB
    is unavailable and APP_DEBUG is enabled.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings


logger = logging.getLogger(__name__)


# The client can be either:
# - a real Motor client
# - a mongomock-motor client during local development
_client: Any = None


async def init_db() -> None:
    """Initialize Beanie and connect to MongoDB."""

    global _client

    from app.models.push_subscription import PushSubscription
    from app.models.reminder import Reminder
    from app.models.user import User

    document_models = [
        User,
        Reminder,
        PushSubscription,
    ]

    # ------------------------------------------------------------------
    # Real MongoDB
    # ------------------------------------------------------------------

    try:
        real_client: AsyncIOMotorClient = AsyncIOMotorClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=5000,
        )

        # Verify that MongoDB is actually reachable.
        await real_client.admin.command("ping")

        database = real_client[
            settings.DATABASE_NAME
        ]

        await init_beanie(
            database=database,
            document_models=document_models,
        )

        _client = real_client

        # IMPORTANT:
        # Do not log the full MONGODB_URL because it can contain
        # username/password credentials.
        logger.info(
            "Connected to MongoDB database: %s",
            settings.DATABASE_NAME,
        )

        return

    except Exception as exc:
        logger.warning(
            "Could not connect to configured MongoDB: %s",
            exc,
        )

    # ------------------------------------------------------------------
    # Development-only in-memory fallback
    # ------------------------------------------------------------------

    if settings.APP_DEBUG:
        try:
            from mongomock_motor import AsyncMongoMockClient

            logger.warning(
                "APP_DEBUG is enabled. "
                "Falling back to in-memory MongoDB."
            )

            mock_client = AsyncMongoMockClient()

            mock_database = mock_client[
                settings.DATABASE_NAME
            ]

            # mongomock-motor intentionally emulates Motor at runtime,
            # but its static type is different from Motor's database type.
            # The cast is only for Pylance/type checking.
            beanie_database = cast(
                AsyncIOMotorDatabase,
                mock_database,
            )

            await init_beanie(
                database=beanie_database,
                document_models=document_models,
            )

            _client = mock_client

            logger.info(
                "In-memory development database initialized."
            )

            return

        except Exception as mock_exc:
            logger.exception(
                "Failed to initialize development MongoDB fallback: %s",
                mock_exc,
            )

    # ------------------------------------------------------------------
    # No database available
    # ------------------------------------------------------------------

    raise RuntimeError(
        "Unable to connect to MongoDB. "
        "Check MONGODB_URL and DATABASE_NAME."
    )


async def close_db() -> None:
    """Close the active MongoDB client."""

    global _client

    if _client is None:
        return

    try:
        close_method = getattr(
            _client,
            "close",
            None,
        )

        if callable(close_method):
            close_method()

    except Exception:
        logger.exception(
            "Error while closing MongoDB connection."
        )

    finally:
        _client = None

    logger.info(
        "Database connection closed."
    )


def get_client() -> Any:
    """Return the active MongoDB client."""

    if _client is None:
        raise RuntimeError(
            "Database not initialized. "
            "Call init_db() first."
        )

    return _client