import time
import random
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config import UserConfig, LOGS_DIR
from modules.whop.auto_apply import WhopAutoApply
from pipeline import ContentPipeline


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "scheduler.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("scheduler")


class BotScheduler:

    def __init__(self, username: str = ""):
        self.scheduler = BackgroundScheduler()
        self.username = username
        self.active_user = username

    def _get_user_cfg(self) -> UserConfig | None:
        try:
            from database import init_db, get_user_by_username
            init_db()
            user = get_user_by_username(self.username or self.active_user)
            if not user:
                return None
            from api import user_to_config
            return user_to_config(user)
        except Exception as e:
            logger.error(f"Failed to load user config: {e}")
            return None

    def start(self):
        if not self.username and not self.active_user:
            logger.error("No active user configured. Run setup first.")
            return False

        user_cfg = self._get_user_cfg()
        if not user_cfg:
            logger.error(f"User '{self.username or self.active_user}' not found.")
            return False

        if self.scheduler.running:
            logger.info("Scheduler already running")
            return True

        logger.info(f"Starting scheduler for user: {self.username or self.active_user}")

        self.scheduler.add_job(
            self._run_pipeline,
            CronTrigger(hour=10, minute=0),
            args=[user_cfg],
            id="pipeline_morning",
            name="Morning content pipeline",
        )

        self.scheduler.add_job(
            self._run_pipeline,
            CronTrigger(hour=14, minute=0),
            args=[user_cfg],
            id="pipeline_afternoon",
            name="Afternoon content pipeline",
        )

        self.scheduler.add_job(
            self._run_pipeline,
            CronTrigger(hour=18, minute=0),
            args=[user_cfg],
            id="pipeline_evening",
            name="Evening content pipeline",
        )

        self.scheduler.add_job(
            self._run_pipeline,
            CronTrigger(hour=21, minute=0),
            args=[user_cfg],
            id="pipeline_night",
            name="Night content pipeline",
        )

        self.scheduler.add_job(
            self._run_whop_apply,
            CronTrigger(hour=9, minute=30, day_of_week="mon,wed,fri"),
            args=[user_cfg],
            id="whop_apply",
            name="Whop auto-apply check",
        )

        self.scheduler.start()
        logger.info("Scheduler started.")
        return True

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped.")
            return True
        return False

    @property
    def is_running(self) -> bool:
        return self.scheduler.running

    def get_status(self) -> dict:
        jobs = []
        if self.scheduler.running:
            for job in self.scheduler.get_jobs():
                next_run = job.next_run_time.isoformat() if job.next_run_time else None
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run": next_run,
                })
        return {
            "running": self.scheduler.running,
            "active_user": self.active_user,
            "jobs": jobs,
        }

    def _run_pipeline(self, user_cfg: UserConfig):
        logger.info("=== Starting content pipeline ===")
        pipeline = ContentPipeline(user_cfg)

        try:
            results = pipeline.run_daily_pipeline()
            logger.info(
                f"Pipeline complete: {results['clips_created']} clips, "
                f"{results['posts_published']} posts published, "
                f"{results['applied_campaigns']} campaigns applied"
            )
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)

    def _run_whop_apply(self, user_cfg: UserConfig):
        logger.info("=== Running Whop auto-apply ===")
        try:
            applier = WhopAutoApply(user_cfg, headless=True)
            applier.run_auto_apply(max_applications=3)
        except Exception as e:
            logger.error(f"Whop auto-apply error: {e}", exc_info=True)


def run_once(username: str = ""):
    from database import init_db, get_user_by_username
    init_db()
    user = get_user_by_username(username)
    if not user:
        logger.error(f"User '{username}' not found.")
        return

    from api import user_to_config
    user_cfg = user_to_config(user)
    logger.info(f"=== Running pipeline once for {username} ===")

    pipeline = ContentPipeline(user_cfg)
    results = pipeline.run_daily_pipeline()
    logger.info(f"Results: {results}")
    return results
