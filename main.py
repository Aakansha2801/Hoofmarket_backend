# main.py
# Usage:
#   python main.py          → scheduled mode (30 min test / 24 h prod)
#   python main.py --once   → single run then exit

import asyncio
import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from orchestrator import run_all_scrapers
from analytics.engine import run_analytics
from config.base import TESTING_MODE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("hoofmarket.log"),
    ],
)
logger = logging.getLogger(__name__)


def run_job():
    logger.info("🚀 Job started")
    saved = asyncio.run(run_all_scrapers())
    if saved > 0:
        run_analytics()
    else:
        logger.info("⏭️  No new data — skipping analytics")
    logger.info("🏁 Job complete")


def start_scheduler():
    if TESTING_MODE:
        trigger = IntervalTrigger(minutes=30)
        logger.info("⏰ Scheduler: every 30 min (TESTING_MODE)")
    else:
        trigger = IntervalTrigger(hours=24)
        logger.info("⏰ Scheduler: every 24 h (PRODUCTION)")

    scheduler = BlockingScheduler(timezone="America/Chicago")
    scheduler.add_job(run_job, trigger, id="scrape_job", max_instances=1)

    logger.info("▶️  Running first job immediately...")
    run_job()

    logger.info("⏳ Scheduler running — Ctrl+C to stop")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Scheduler stopped")


if __name__ == "__main__":
    if "--once" in sys.argv:
        run_job()
    else:
        start_scheduler()
