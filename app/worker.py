"""Timora background worker for durable reminder scheduling."""

from __future__ import annotations

import asyncio
import logging

from app.database import close_db, init_db
from app.services.scheduler_service import start_scheduler, stop_scheduler


logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)


def worker_status() -> str:
    """Return information about the active background-worker strategy."""

    return "APScheduler is the active Timora reminder scheduler."


async def run_worker() -> None:
    """Run the reminder scheduler as a long-lived background process."""

    logger.info("Timora reminder worker initializing")
    await init_db()
    start_scheduler()
    logger.info("Timora reminder worker started")

    try:
        await asyncio.Event().wait()
    finally:
        stop_scheduler()
        await close_db()


if __name__ == "__main__":
    asyncio.run(run_worker())