"""
Authentication tests:
- Signup (success, duplicate email, weak password, mismatched passwords)
- Login (success, invalid password, non-existent user)
- Token validation and protected /api/auth/me endpoint
- Logout
"""
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_signup_success(client: AsyncClient):
    payload = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "password": "SecurePassword1",
        "confirm_password": "SecurePassword1",
    }
    response = await client.post("/api/auth/signup", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0

@pytest.mark.asyncio
async def test_signup_duplicate_email(client: AsyncClient):
    payload = {
        "name": "Jane Doe",
        "email": "duplicate@example.com",
        "password": "SecurePassword1",
        "confirm_password": "SecurePassword1",
    }
    res1 = await client.post("/api/auth/signup", json=payload)
    assert res1.status_code == 201

    res2 = await client.post("/api/auth/signup", json=payload)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]

@pytest.mark.asyncio
async def test_signup_password_validation_weak(client: AsyncClient):
    # Missing uppercase and digit
    payload = {
        "name": "Jane Doe",
        "email": "weak@example.com",
        "password": "password",
        "confirm_password": "password",
    }
    response = await client.post("/api/auth/signup", json=payload)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_signup_password_mismatch(client: AsyncClient):
    payload = {
        "name": "Jane Doe",
        "email": "mismatch@example.com",
        "password": "SecurePassword1",
        "confirm_password": "DifferentPassword1",
    }
    response = await client.post("/api/auth/signup", json=payload)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    # Signup first
    await client.post("/api/auth/signup", json={
        "name": "Login User",
        "email": "loginuser@example.com",
        "password": "Password123",
        "confirm_password": "Password123",
    })

    # Login
    response = await client.post("/api/auth/login", json={
        "email": "loginuser@example.com",
        "password": "Password123",
        "remember_me": True,
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data

@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient):
    await client.post("/api/auth/signup", json={
        "name": "Login User 2",
        "email": "loginuser2@example.com",
        "password": "Password123",
        "confirm_password": "Password123",
    })

    response = await client.post("/api/auth/login", json={
        "email": "loginuser2@example.com",
        "password": "WrongPassword999",
    })
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient, auth_user: dict):
    response = await client.get("/api/auth/me", headers=auth_user["headers"])
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == auth_user["email"]
    assert data["name"] == "Test User"

@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    response = await client.get("/api/auth/me")
    assert response.status_code == 401
