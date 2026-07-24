"""
HoofMarketIQ — FastAPI REST API
Starts scraper immediately on server boot, then repeats on the configured
production interval (default: every 6 h, override via SCRAPE_INTERVAL_HOURS).

Usage:
    uvicorn app:app --host 0.0.0.0 --port 8010

Docs:
    http://localhost:8010/docs
"""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import os

SCRAPE_INTERVAL_HOURS = int(
    os.getenv("SCRAPE_INTERVAL_HOURS", "6")
)

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Scraper job ───────────────────────────────────────────────
def run_job():
    from orchestrator import run_all_scrapers
    logger.info("🚀 Scrape job started")
    scraped = asyncio.run(run_all_scrapers())
    logger.info(f"🏁 Scrape job complete — scraped={scraped}")


# ── Lifespan: start scheduler on boot ─────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = BackgroundScheduler(timezone="America/Chicago")
    scheduler.add_job(
        run_job,
        IntervalTrigger(hours=SCRAPE_INTERVAL_HOURS),
        id="scrape_job",
        max_instances=1,
    )
    scheduler.start()
    logger.info(
        f"⏰ Scheduler started — every {SCRAPE_INTERVAL_HOURS} h"
    )

    # Run immediately on boot in a thread so uvicorn doesn't block
    import threading
    threading.Thread(target=run_job, daemon=True).start()
    logger.info("▶️  First scrape triggered on boot")

    yield

    scheduler.shutdown(wait=False)
    logger.info("🛑 Scheduler stopped")


# ── App setup ─────────────────────────────────────────────────
app = FastAPI(
    title="HoofMarketIQ API",
    description="REST API for scraped hoofstock listings — Texas Market Intelligence",
    version="2.0.0",
    lifespan=lifespan,
)

# Allow all origins during development; tighten this in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ─────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health():
    """Quick liveness check."""
    return {"status": "ok"}


# ── Scraper trigger (manual) ───────────────────────────────────

@app.post("/api/run-job", tags=["System"])
def trigger_job():
    """Manually trigger one scrape + Bubble sync cycle outside the schedule."""
    import threading
    threading.Thread(target=run_job, daemon=True).start()
    return {"status": "triggered"}
