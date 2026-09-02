"""
Timora – Toast Notification Helper
"""
from __future__ import annotations

from nicegui import ui


def toast_success(message: str) -> None:
    ui.notify(message, type="positive", position="top-right", timeout=3000,
              classes="timora-toast")


def toast_error(message: str) -> None:
    ui.notify(message, type="negative", position="top-right", timeout=5000,
              classes="timora-toast")


def toast_warning(message: str) -> None:
    ui.notify(message, type="warning", position="top-right", timeout=4000,
              classes="timora-toast")


def toast_info(message: str) -> None:
    ui.notify(message, type="info", position="top-right", timeout=3000,
              classes="timora-toast")
