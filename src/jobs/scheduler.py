"""Background job scheduler for the Learner application.

This module provides a centralized scheduler for background tasks such as:
- Content ingestion from configured sources
- Expired token cleanup
- Spaced repetition review scheduling
- Analytics aggregation

The scheduler uses APScheduler with AsyncIO support for non-blocking execution.
"""

import logging
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

from src.shared.config import get_settings
from src.shared.feature_flags import FeatureFlags, get_feature_flags

logger = logging.getLogger(__name__)


class JobScheduler:
    """Centralized background job scheduler.

    Manages scheduled tasks for maintenance, content processing, and other
    background operations. All tasks run asynchronously to avoid blocking.

    Usage:
        scheduler = JobScheduler()
        scheduler.start()

        # Schedule built-in tasks
        scheduler.schedule_content_ingestion(interval_hours=6)
        scheduler.schedule_token_cleanup(interval_hours=24)

        # Or schedule custom tasks
        scheduler.add_job(my_async_func, hours=1, job_id="my-task")
    """

    def __init__(self):
        """Initialize the job scheduler."""
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._is_running = False
        self._settings = get_settings()
        self._flags = get_feature_flags()

    @property
    def scheduler(self) -> AsyncIOScheduler:
        """Get or create the APScheduler instance."""
        if self._scheduler is None:
            jobstores = {
                'default': MemoryJobStore()
            }
            executors = {
                'default': AsyncIOExecutor()
            }
            job_defaults = {
                'coalesce': True,  # Combine missed executions
                'max_instances': 1,  # Prevent concurrent runs of same job
                'misfire_grace_time': 60 * 15,  # 15 min grace for misfires
            }

            self._scheduler = AsyncIOScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone='UTC',
            )
        return self._scheduler

    @property
    def is_running(self) -> bool:
        """Check if the scheduler is currently running."""
        return self._is_running and self._scheduler is not None

    def start(self) -> None:
        """Start the background scheduler.

        Only starts if the FF_ENABLE_BACKGROUND_JOBS feature flag is enabled.
        """
        if not self._flags.is_enabled(FeatureFlags.ENABLE_BACKGROUND_JOBS):
            logger.info("Background jobs disabled by feature flag")
            return

        if self._is_running:
            logger.warning("Scheduler already running")
            return

        try:
            self.scheduler.start()
            self._is_running = True
            logger.info("Background job scheduler started")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the scheduler gracefully.

        Args:
            wait: If True, wait for running jobs to complete.
        """
        if not self._is_running or self._scheduler is None:
            return

        try:
            self._scheduler.shutdown(wait=wait)
            self._is_running = False
            logger.info("Background job scheduler stopped")
        except Exception as e:
            logger.error(f"Error shutting down scheduler: {e}")
            raise

    def add_job(
        self,
        func: Callable,
        *,
        hours: Optional[float] = None,
        minutes: Optional[float] = None,
        seconds: Optional[float] = None,
        cron: Optional[str] = None,
        job_id: Optional[str] = None,
        replace_existing: bool = True,
        **kwargs: Any,
    ) -> str:
        """Add a job to the scheduler.

        Args:
            func: The async function to execute.
            hours: Interval in hours.
            minutes: Interval in minutes.
            seconds: Interval in seconds.
            cron: Cron expression (e.g., "0 6 * * *" for 6 AM daily).
            job_id: Unique identifier for the job.
            replace_existing: Replace if job_id already exists.
            **kwargs: Additional arguments passed to the job function.

        Returns:
            The job ID.

        Raises:
            ValueError: If no schedule is specified.
        """
        if cron:
            trigger = CronTrigger.from_crontab(cron)
        elif hours or minutes or seconds:
            trigger = IntervalTrigger(
                hours=hours or 0,
                minutes=minutes or 0,
                seconds=seconds or 0,
            )
        else:
            raise ValueError("Must specify cron, hours, minutes, or seconds")

        job_id = job_id or f"{func.__module__}.{func.__name__}"

        job = self.scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            replace_existing=replace_existing,
            kwargs=kwargs,
        )

        logger.info(f"Scheduled job '{job_id}' with trigger: {trigger}")
        return job.id

    def remove_job(self, job_id: str) -> bool:
        """Remove a job from the scheduler.

        Args:
            job_id: The job ID to remove.

        Returns:
            True if job was removed, False if not found.
        """
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed job '{job_id}'")
            return True
        except Exception:
            logger.warning(f"Job '{job_id}' not found")
            return False

    def get_jobs(self) -> list[dict[str, Any]]:
        """Get information about all scheduled jobs.

        Returns:
            List of job information dictionaries.
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger),
            })
        return jobs

    def schedule_content_ingestion(
        self,
        interval_hours: int = 6,
        job_id: str = "content-ingestion",
    ) -> str:
        """Schedule periodic content ingestion.

        This job pulls new content from configured sources (arXiv, YouTube, etc.)
        and adds it to the content database with embeddings.

        Args:
            interval_hours: Hours between ingestion runs.
            job_id: Unique identifier for this job.

        Returns:
            The job ID.
        """
        from src.jobs.tasks import run_content_ingestion

        return self.add_job(
            run_content_ingestion,
            hours=interval_hours,
            job_id=job_id,
        )

    def schedule_token_cleanup(
        self,
        interval_hours: int = 24,
        job_id: str = "token-cleanup",
    ) -> str:
        """Schedule periodic cleanup of expired tokens.

        This job removes expired authentication tokens from the database
        to maintain security and reduce storage.

        Args:
            interval_hours: Hours between cleanup runs.
            job_id: Unique identifier for this job.

        Returns:
            The job ID.
        """
        from src.jobs.tasks import run_token_cleanup

        return self.add_job(
            run_token_cleanup,
            hours=interval_hours,
            job_id=job_id,
        )

    def schedule_review_notifications(
        self,
        cron: str = "0 9 * * *",  # 9 AM UTC daily
        job_id: str = "review-notifications",
    ) -> str:
        """Schedule daily review notifications.

        This job identifies users with items due for spaced repetition review
        and queues notifications for them.

        Args:
            cron: Cron expression for when to run.
            job_id: Unique identifier for this job.

        Returns:
            The job ID.
        """
        from src.jobs.tasks import run_review_notifications

        return self.add_job(
            run_review_notifications,
            cron=cron,
            job_id=job_id,
        )

    def schedule_analytics_aggregation(
        self,
        cron: str = "0 0 * * *",  # Midnight UTC daily
        job_id: str = "analytics-aggregation",
    ) -> str:
        """Schedule daily analytics aggregation.

        This job computes daily/weekly/monthly statistics for reporting
        and performance monitoring.

        Args:
            cron: Cron expression for when to run.
            job_id: Unique identifier for this job.

        Returns:
            The job ID.
        """
        from src.jobs.tasks import run_analytics_aggregation

        return self.add_job(
            run_analytics_aggregation,
            cron=cron,
            job_id=job_id,
        )

    def schedule_all_default_jobs(self) -> list[str]:
        """Schedule all default background jobs.

        Convenience method to set up the standard job schedule.

        Returns:
            List of scheduled job IDs.
        """
        job_ids = []

        # Content ingestion every 6 hours
        job_ids.append(self.schedule_content_ingestion(interval_hours=6))

        # Token cleanup daily
        job_ids.append(self.schedule_token_cleanup(interval_hours=24))

        # Review notifications at 9 AM UTC
        job_ids.append(self.schedule_review_notifications())

        # Analytics aggregation at midnight UTC
        job_ids.append(self.schedule_analytics_aggregation())

        logger.info(f"Scheduled {len(job_ids)} default background jobs")
        return job_ids


# Singleton instance
_scheduler_instance: Optional[JobScheduler] = None


@lru_cache(maxsize=1)
def get_scheduler() -> JobScheduler:
    """Get the singleton scheduler instance.

    Returns:
        The global JobScheduler instance.
    """
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = JobScheduler()
    return _scheduler_instance


def reset_scheduler() -> None:
    """Reset the scheduler instance (for testing)."""
    global _scheduler_instance
    if _scheduler_instance is not None:
        if _scheduler_instance.is_running:
            _scheduler_instance.shutdown(wait=False)
        _scheduler_instance = None
    get_scheduler.cache_clear()
