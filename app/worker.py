"""
Timora – Production Background Worker (Celery + Redis)
Can be used in production as an alternative to APScheduler.
"""
from __future__ import annotations

import asyncio
import logging
from celery import Celery
from celery.schedules import crontab

from app.config import settings

logger = logging.getLogger(__name__)

# Initialize Celery app
celery_app = Celery(
    "timora_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "process-due-reminders-every-30-seconds": {
            "task": "app.worker.process_due_reminders_task",
            "schedule": 30.0,  # Run every 30 seconds
        },
    },
)

@celery_app.task
def process_due_reminders_task():
    """Celery task that initializes Beanie and processes due reminders."""
    from app.database import init_db, close_db
    from app.services.scheduler_service import _process_due_reminders

    async def _runner():
        await init_db()
        await _process_due_reminders()
        await close_db()

    try:
        asyncio.run(_runner())
        logger.info("Celery periodic reminder check completed successfully.")
    except Exception as e:
        logger.error(f"Error in Celery reminder task: {e}")
        raise e
