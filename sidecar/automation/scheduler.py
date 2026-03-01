"""APScheduler setup and job registry.

Jobs are registered here and started/stopped with the FastAPI lifespan.

Integration with main.py:
    In the lifespan context manager, call start_scheduler() after DB init
    and stop_scheduler() in the cleanup phase.

Job design (D4):
    All jobs use async functions. Jobs catch their own exceptions and log
    them — they never crash the scheduler process.
    Each job writes a lightweight job_run log entry (dict) via structlog
    so failures are observable without a separate job_runs DB table in v1.

Cron expressions (from Settings):
    daily_digest_cron  — default "0 7 * * *"  (7am daily)
    weekly_review_cron — default "0 8 * * MON" (Monday 8am)
    Milestone watch and PM health watch run hourly (hardcoded; not yet configurable).
"""

from __future__ import annotations

from typing import Any, Callable, Coroutine

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from sidecar.config import Settings

logger = structlog.get_logger(__name__)

# Module-level scheduler instance — one per process
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """Return (creating if needed) the shared APScheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
    return _scheduler


def start_scheduler(settings: Settings, session_factory: Any) -> AsyncIOScheduler:
    """Register all jobs and start the scheduler.

    Called once during FastAPI startup (lifespan). Imports job functions
    here to avoid circular imports at module level.

    Args:
        settings:        Application settings (cron expressions, thresholds).
        session_factory: SQLAlchemy async_sessionmaker passed to jobs.

    Returns:
        The running AsyncIOScheduler instance.
    """
    from sidecar.automation.daily_digest import run_daily_digest
    from sidecar.automation.weekly_review_prep import run_weekly_review_prep
    from sidecar.automation.milestone_watch import run_milestone_watch
    from sidecar.automation.pm_health_watch import run_pm_health_watch

    scheduler = get_scheduler()

    def _wrap(job_fn: Callable[..., Coroutine]) -> Callable:
        """Wrap a job so it catches all exceptions and logs them."""
        async def _safe_job():
            job_name = job_fn.__name__
            logger.info("job_start", job=job_name)
            try:
                await job_fn(settings=settings, session_factory=session_factory)
                logger.info("job_complete", job=job_name)
            except Exception as exc:
                logger.error("job_failed", job=job_name, error=str(exc), exc_info=True)
        _safe_job.__name__ = job_fn.__name__
        return _safe_job

    # Daily digest — configurable cron
    scheduler.add_job(
        _wrap(run_daily_digest),
        CronTrigger.from_crontab(settings.daily_digest_cron, timezone="UTC"),
        id="daily_digest",
        replace_existing=True,
    )

    # Weekly review prep — configurable cron
    scheduler.add_job(
        _wrap(run_weekly_review_prep),
        CronTrigger.from_crontab(settings.weekly_review_cron, timezone="UTC"),
        id="weekly_review_prep",
        replace_existing=True,
    )

    # Milestone watch — every hour
    scheduler.add_job(
        _wrap(run_milestone_watch),
        IntervalTrigger(hours=1),
        id="milestone_watch",
        replace_existing=True,
    )

    # PM health watch — every hour (offset by 15 min to avoid pile-up)
    scheduler.add_job(
        _wrap(run_pm_health_watch),
        IntervalTrigger(hours=1, minutes=15),
        id="pm_health_watch",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "scheduler_started",
        jobs=[job.id for job in scheduler.get_jobs()],
    )
    return scheduler


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler. Called during FastAPI shutdown."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")
    _scheduler = None
