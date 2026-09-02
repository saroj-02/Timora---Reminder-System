"""
Reminder CRUD and lifecycle tests:
- Create reminder with local timezone & future validation
- Read reminder / list reminders with filtering
- Update reminder
- Delete reminder
- Complete reminder
- Snooze reminder
- Reschedule reminder
- Past-time validation (reject past times)
- Authorization isolation (user A cannot access user B's reminder)
"""
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_reminder_success(client: AsyncClient, auth_user: dict):
    future_time = datetime.now() + timedelta(days=2)
    payload = {
        "title": "Complete Python Project",
        "description": "Build modern SaaS app",
        "category": "Project",
        "priority": "High",
        "local_datetime": future_time.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": "Asia/Kolkata",
        "repeat_type": "Never",
        "reminder_before": "15 minutes before",
    }
    response = await client.post("/api/reminders", json=payload, headers=auth_user["headers"])
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Complete Python Project"
    assert data["priority"] == "High"
    assert data["status"] == "pending"
    assert "id" in data

@pytest.mark.asyncio
async def test_create_reminder_past_time_fails(client: AsyncClient, auth_user: dict):
    past_time = datetime.now() - timedelta(hours=2)
    payload = {
        "title": "Past reminder",
        "category": "Personal",
        "priority": "Medium",
        "local_datetime": past_time.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": "Asia/Kolkata",
        "repeat_type": "Never",
        "reminder_before": "At scheduled time",
    }
    response = await client.post("/api/reminders", json=payload, headers=auth_user["headers"])
    assert response.status_code == 422
    assert "already passed" in response.text

@pytest.mark.asyncio
async def test_reminder_lifecycle(client: AsyncClient, auth_user: dict):
    # 1. Create
    future_time = datetime.now() + timedelta(days=1)
    payload = {
        "title": "Lifecycle Test",
        "category": "Work",
        "priority": "Medium",
        "local_datetime": future_time.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": "Asia/Kolkata",
        "repeat_type": "Never",
        "reminder_before": "At scheduled time",
    }
    res = await client.post("/api/reminders", json=payload, headers=auth_user["headers"])
    assert res.status_code == 201
    reminder_id = res.json()["id"]

    # 2. Get by ID
    res = await client.get(f"/api/reminders/{reminder_id}", headers=auth_user["headers"])
    assert res.status_code == 200
    assert res.json()["title"] == "Lifecycle Test"

    # 3. Update
    res = await client.put(f"/api/reminders/{reminder_id}", json={"title": "Updated Title", "priority": "High"}, headers=auth_user["headers"])
    assert res.status_code == 200
    assert res.json()["title"] == "Updated Title"
    assert res.json()["priority"] == "High"

    # 4. Snooze
    res = await client.post(f"/api/reminders/{reminder_id}/snooze", json={"minutes": 15}, headers=auth_user["headers"])
    assert res.status_code == 200
    assert res.json()["status"] == "snoozed"
    assert res.json()["snooze_until"] is not None

    # 5. Reschedule
    new_future = datetime.now() + timedelta(days=3)
    res = await client.post(
        f"/api/reminders/{reminder_id}/reschedule",
        json={"local_datetime": new_future.strftime("%Y-%m-%d %H:%M:%S"), "timezone": "Asia/Kolkata"},
        headers=auth_user["headers"],
    )
    assert res.status_code == 200
    assert res.json()["status"] == "pending"

    # 6. Complete
    res = await client.post(f"/api/reminders/{reminder_id}/complete", headers=auth_user["headers"])
    assert res.status_code == 200
    assert res.json()["status"] == "completed"
    assert res.json()["completed_at"] is not None

    # 7. Delete
    res = await client.delete(f"/api/reminders/{reminder_id}", headers=auth_user["headers"])
    assert res.status_code == 204

    # 8. Verify deleted
    res = await client.get(f"/api/reminders/{reminder_id}", headers=auth_user["headers"])
    assert res.status_code == 404

@pytest.mark.asyncio
async def test_user_isolation(client: AsyncClient, auth_user: dict):
    # Create reminder for User A
    future_time = datetime.now() + timedelta(days=1)
    res = await client.post("/api/reminders", json={
        "title": "User A Private Reminder",
        "category": "Personal",
        "priority": "High",
        "local_datetime": future_time.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": "Asia/Kolkata",
    }, headers=auth_user["headers"])
    reminder_id = res.json()["id"]

    # Create User B
    res_b = await client.post("/api/auth/signup", json={
        "name": "User B",
        "email": "userb@example.com",
        "password": "Password123",
        "confirm_password": "Password123",
    })
    token_b = res_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User B tries to view User A's reminder -> 404
    res = await client.get(f"/api/reminders/{reminder_id}", headers=headers_b)
    assert res.status_code == 404

    # User B tries to delete User A's reminder -> 404
    res = await client.delete(f"/api/reminders/{reminder_id}", headers=headers_b)
    assert res.status_code == 404
