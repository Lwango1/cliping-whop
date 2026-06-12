import time
import random
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config import AppConfig, UserConfig, load_config, LOGS_DIR
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

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.config: AppConfig = load_config()

    def start(self):
        if not self.config.active_user:
            logger.error("No active user configured. Run setup first.")
            return

        user_cfg = self.config.users.get(self.config.active_user)
        if not user_cfg:
            logger.error(f"User '{self.config.active_user}' not found in config.")
            return

        logger.info(f"Starting scheduler for user: {self.config.active_user}")

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
        logger.info("Scheduler started. Waiting for scheduled jobs...")

        try:
            while True:
                time.sleep(60)
        except (KeyboardInterrupt, SystemExit):
            logger.info("Shutting down scheduler...")
            self.scheduler.shutdown()

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
            applier = WhopAutoApply(user_cfg, headless=self.config.headless_browser)
            applier.run_auto_apply(max_applications=3)
        except Exception as e:
            logger.error(f"Whop auto-apply error: {e}", exc_info=True)


def run_once():
    config = load_config()
    if not config.active_user:
        logger.error("No active user. Run setup first.")
        return

    user_cfg = config.users[config.active_user]
    logger.info("=== Running pipeline once ===")

    pipeline = ContentPipeline(user_cfg)
    results = pipeline.run_daily_pipeline()
    logger.info(f"Results: {results}")
    return results
