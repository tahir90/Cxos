"""
Background Job Runner — real cron using APScheduler.

Scheduled jobs run automatically without anyone calling an endpoint.
"""

from __future__ import annotations

import logging
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
    return _scheduler


def start_scheduler() -> BackgroundScheduler:
    """Start the background scheduler."""
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("Background scheduler started")
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped")
    _scheduler = None


def add_daily_job(
    job_id: str,
    func: Any,
    hour: int = 8,
    minute: int = 0,
    **kwargs: Any,
) -> None:
    """Add a job that runs daily at a specific time."""
    scheduler = get_scheduler()
    scheduler.add_job(
        func,
        trigger=CronTrigger(hour=hour, minute=minute),
        id=job_id,
        replace_existing=True,
        **kwargs,
    )
    logger.info("Scheduled daily job: %s at %02d:%02d", job_id, hour, minute)


def add_interval_job(
    job_id: str,
    func: Any,
    hours: int = 1,
    **kwargs: Any,
) -> None:
    """Add a job that runs at fixed intervals."""
    scheduler = get_scheduler()
    scheduler.add_job(
        func,
        trigger=IntervalTrigger(hours=hours),
        id=job_id,
        replace_existing=True,
        **kwargs,
    )
    logger.info("Scheduled interval job: %s every %dh", job_id, hours)


def list_jobs() -> list[dict[str, Any]]:
    scheduler = get_scheduler()
    return [
        {
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
            "trigger": str(job.trigger),
        }
        for job in scheduler.get_jobs()
    ]
