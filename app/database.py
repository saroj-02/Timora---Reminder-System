"""
Timora – Database Initialisation
Sets up Motor async client and Beanie ODM.
Includes automatic in-memory fallback for local dev when MongoDB is offline.
"""
import logging

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings

logger = logging.getLogger(__name__)

_client = None


async def init_db() -> None:
    """Initialise Beanie with all document models."""
    global _client

    from app.models.push_subscription import PushSubscription
    from app.models.reminder import Reminder
    from app.models.user import User

    # Try connecting to real MongoDB with short timeout
    try:
        real_client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=2000,
        )
        # Test connection
        await real_client.admin.command("ping")
        _client = real_client
        db = _client[settings.DATABASE_NAME]
        await init_beanie(
            database=db,
            document_models=[User, Reminder, PushSubscription],
        )
        logger.info("✅ Connected to MongoDB: %s / %s", settings.MONGODB_URL, settings.DATABASE_NAME)
        return
    except Exception as exc:
        logger.warning(
            "⚠️  Could not connect to MongoDB at %s (%s).",
            settings.MONGODB_URL,
            exc,
        )

    # In development mode, fallback to in-memory MongoMock so the app runs immediately
    if settings.APP_DEBUG:
        try:
            from mongomock_motor import AsyncMongoMockClient

            logger.info("💡 Falling back to in-memory MongoDB (mongomock-motor) for development.")
            _client = AsyncMongoMockClient()
            db = _client[settings.DATABASE_NAME]
            await init_beanie(
                database=db,
                document_models=[User, Reminder, PushSubscription],
            )
            logger.info("✅ In-memory database initialized successfully.")
            return
        except Exception as mock_exc:
            logger.error("Failed to initialize mock database: %s", mock_exc)

    raise RuntimeError(
        f"Unable to connect to MongoDB at {settings.MONGODB_URL}. "
        "Please start MongoDB (`brew services start mongodb-community@7.0` or run MongoDB via Docker)."
    )


async def close_db() -> None:
    global _client
    if _client:
        try:
            _client.close()
        except Exception:
            pass
        logger.info("🔌 Database connection closed")


def get_client():
    if _client is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    return _client
