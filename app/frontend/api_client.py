"""
Timora – API Client (frontend side)
Helper for NiceGUI pages to call FastAPI endpoints with the stored token.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.config import settings
from app.frontend.state import get_token

logger = logging.getLogger(__name__)

BASE_URL = f"http://127.0.0.1:{settings.APP_PORT}"


async def api_get(path: str, params: Optional[dict] = None) -> dict | list | None:
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.get(f"{BASE_URL}{path}", headers=headers, params=params)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("API GET %s failed: %s %s", path, exc.response.status_code, exc.response.text)
            return None
        except Exception as exc:
            logger.error("API GET %s error: %s", path, exc)
            return None


async def api_post(path: str, data: Optional[dict] = None) -> dict | None:
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.post(f"{BASE_URL}{path}", json=data, headers=headers)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("API POST %s failed: %s %s", path, exc.response.status_code, exc.response.text)
            raise
        except Exception as exc:
            logger.error("API POST %s error: %s", path, exc)
            raise


async def api_put(path: str, data: Optional[dict] = None) -> dict | None:
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.put(f"{BASE_URL}{path}", json=data, headers=headers)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("API PUT %s failed: %s %s", path, exc.response.status_code, exc.response.text)
            raise
        except Exception as exc:
            logger.error("API PUT %s error: %s", path, exc)
            raise


async def api_delete(path: str) -> bool:
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.delete(f"{BASE_URL}{path}", headers=headers)
            return r.status_code in (200, 204)
        except Exception as exc:
            logger.error("API DELETE %s error: %s", path, exc)
            return False
