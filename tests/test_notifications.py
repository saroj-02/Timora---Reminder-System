"""
Notification and Web Push subscription tests:
- Get VAPID public key
- Push subscription registration & deduplication
- Unsubscribe endpoint
"""
import pytest
from httpx import AsyncClient
from app.models.push_subscription import PushSubscription

@pytest.mark.asyncio
async def test_get_vapid_public_key(client: AsyncClient):
    response = await client.get("/api/notifications/vapid-public-key")
    assert response.status_code == 200
    data = response.json()
    assert "public_key" in data

@pytest.mark.asyncio
async def test_push_subscribe_and_unsubscribe(client: AsyncClient, auth_user: dict):
    sub_payload = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/test-endpoint-12345",
        "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QT9t0A38e_Jz_YFwGfGkRj_g4aA",
        "auth": "tBHItJI5svbpez7KI4CCXg",
        "device": "MacBook Pro",
        "browser": "Chrome 128",
    }

    # 1. Subscribe
    res = await client.post("/api/notifications/subscribe", json=sub_payload, headers=auth_user["headers"])
    assert res.status_code == 201
    assert res.json()["message"] == "Subscription saved"

    # Verify saved in MongoDB
    subs = await PushSubscription.find(PushSubscription.endpoint == sub_payload["endpoint"]).to_list()
    assert len(subs) == 1
    assert subs[0].browser == "Chrome 128"

    # 2. Re-subscribing with updated browser info should upsert
    sub_payload["browser"] = "Chrome 129"
    res = await client.post("/api/notifications/subscribe", json=sub_payload, headers=auth_user["headers"])
    assert res.status_code == 201

    subs = await PushSubscription.find(PushSubscription.endpoint == sub_payload["endpoint"]).to_list()
    assert len(subs) == 1
    assert subs[0].browser == "Chrome 129"

    # 3. Unsubscribe
    unsub_payload = {"endpoint": sub_payload["endpoint"]}
    res = await client.request("DELETE", "/api/notifications/unsubscribe", json=unsub_payload, headers=auth_user["headers"])
    assert res.status_code == 200

    subs = await PushSubscription.find(PushSubscription.endpoint == sub_payload["endpoint"]).to_list()
    assert len(subs) == 0
