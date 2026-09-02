"""
Pytest configuration and shared fixtures for Timora test suite.
Uses AsyncMongoMockClient from mongomock_motor for fully self-contained testing.
"""

from __future__ import annotations

import os
from typing import Any, cast

import pytest
import pytest_asyncio
from beanie import init_beanie
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.main import fast_api
from app.models.push_subscription import PushSubscription
from app.models.reminder import Reminder
from app.models.user import User


# ── Test Environment ──────────────────────────────────────────────────────────

os.environ["DATABASE_NAME"] = "timora_test"

os.environ["JWT_SECRET"] = (
    "test-secret-key-for-testing-timora-application-12345"
)

os.environ["RATE_LIMIT_AUTH"] = "1000/minute"


TEST_DB_NAME = "timora_test"


# ── Database Fixture ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture(
    scope="function",
    autouse=True,
)
async def init_test_db():
    """
    Create a fresh in-memory MongoDB database for every test.

    mongomock_motor provides an async MongoDB-compatible mock.
    Beanie expects an AsyncIOMotorDatabase type, so cast the mock
    database for static type checking only.
    """

    mock_client = AsyncMongoMockClient()

    db = mock_client[TEST_DB_NAME]

    # mongomock_motor's AsyncMongoMockDatabase is runtime-compatible
    # with the database interface required by Beanie, but its type
    # annotation does not match Beanie's Motor database annotation.
    #
    # cast() changes only the static type seen by Pylance.
    # It does NOT change the runtime object.
    beanie_db = cast(
        Any,
        db,
    )

    await init_beanie(
        database=beanie_db,
        document_models=[
            User,
            Reminder,
            PushSubscription,
        ],
    )

    yield db

    # ── Cleanup ───────────────────────────────────────────────────────────────

    try:
        await User.delete_all()
        await Reminder.delete_all()
        await PushSubscription.delete_all()

    except Exception:
        pass


# ── HTTP Client Fixture ───────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client():
    """
    Async HTTP client connected directly to the FastAPI application.
    """

    transport = ASGITransport(
        app=fast_api
    )

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        yield ac


# ── Authenticated User Fixture ────────────────────────────────────────────────


@pytest_asyncio.fixture
async def auth_user(
    client: AsyncClient,
):
    """
    Create a test user and return authentication details.
    """

    signup_data = {
        "name": "Test User",
        "email": "testuser@example.com",
        "password": "Password123",
        "confirm_password": "Password123",
    }

    # ── Signup ────────────────────────────────────────────────────────────────

    res = await client.post(
        "/api/auth/signup",
        json=signup_data,
    )

    assert res.status_code == 201

    data = res.json()

    token = data["access_token"]

    # ── Authentication Headers ────────────────────────────────────────────────

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # ── Set User Timezone ─────────────────────────────────────────────────────

    await client.put(
        "/api/users/me",
        json={
            "country": "India",
            "timezone": "Asia/Kolkata",
        },
        headers=headers,
    )

    return {
        "email": signup_data["email"],
        "token": token,
        "headers": headers,
    }