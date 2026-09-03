"""
Timora – Background Worker

Timora currently uses APScheduler through:

    app.services.scheduler_service

The scheduler is started automatically by app/main.py.

This module is intentionally kept minimal so that a second
Celery-based scheduler does not process reminders at the same time.

If Timora is migrated to Celery + Redis in the future, the worker
implementation can be restored here.
"""

from __future__ import annotations

import logging


logger = logging.getLogger(__name__)


def worker_status() -> str:
    """Return information about the active background-worker strategy."""

    return "APScheduler is the active Timora reminder scheduler."