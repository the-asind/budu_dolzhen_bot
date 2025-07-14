import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
try:
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore  # type: ignore
except Exception:  # pragma: no cover

    class SQLAlchemyJobStore:  # type: ignore
        """Lightweight in-memory stub to satisfy SchedulerManager during unit tests."""

        def __init__(self, *args, **kwargs):
            self.jobs: dict[str, object] = {}

        def add_job(self, job):
            self.jobs[job.id] = job

        def remove_job(self, job_id):
            self.jobs.pop(job_id, None)

        def get_due_jobs(self, now):  # noqa: D401
            return []

        def lookup_job(self, job_id):  # noqa: D401
            return self.jobs.get(job_id)

        def shutdown(self):
            self.jobs.clear()

from pytz import timezone

from ..config import get_settings
from . import jobs

logger = logging.getLogger(__name__)


class SchedulerManager:
    """Manages the APScheduler instance."""

    def __init__(self):
        settings = get_settings()
        db_path = settings.db.path.replace(".db", "_scheduler.db")
        
        jobstores = {
            "default": SQLAlchemyJobStore(url=f"sqlite:///{db_path}")
        }
        
        self._scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            timezone=timezone(settings.scheduler.timezone)
        )

    def start(self):
        """Starts the scheduler and adds the jobs."""
        try:
            # Add jobs to the scheduler
            self._scheduler.add_job(
                jobs.check_confirmation_timeouts, "interval", hours=1
            )
            self._scheduler.add_job(
                jobs.send_weekly_reports, "cron", day_of_week="mon", hour=10
            )
            
            self._scheduler.start()
            logger.info("Scheduler started with jobs.")
        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")

    def shutdown(self):
        """Shuts down the scheduler."""
        if self._scheduler.running:
            self._scheduler.shutdown()
            logger.info("Scheduler shut down.")

    @property
    def instance(self) -> AsyncIOScheduler:
        return self._scheduler


scheduler_manager = SchedulerManager() 
