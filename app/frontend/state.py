"""
Timora – Global UI State
Per-connection state managed through NiceGUI's app.storage.user.
"""
from __future__ import annotations

from typing import Optional

from nicegui import app


def get_token() -> Optional[str]:
    return app.storage.user.get("token")


def set_token(token: str) -> None:
    app.storage.user["token"] = token


def clear_token() -> None:
    app.storage.user.pop("token", None)


def get_user_data() -> Optional[dict]:
    return app.storage.user.get("user_data")


def set_user_data(data: dict) -> None:
    app.storage.user["user_data"] = data


def clear_user_data() -> None:
    app.storage.user.pop("user_data", None)


def is_authenticated() -> bool:
    return bool(get_token())


def get_theme() -> str:
    data = get_user_data()
    if data:
        return data.get("theme", "dark")
    return "dark"
