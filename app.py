"""
HoofMarketIQ — FastAPI REST API
Starts scraper immediately on server boot, then repeats every 24 h.

Usage:
    uvicorn app:app --host 0.0.0.0 --port 8000

Docs:
    http://localhost:8000/docs
"""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
import math
from collections import defaultdict
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Supabase ───────────────────────────────────────────────────
try:
    from db.supabase_client import get_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# ── Scraper job ───────────────────────────────────────────────
def run_job():
    from orchestrator import run_all_scrapers
    from analytics.engine import run_analytics
    logger.info("🚀 Scrape job started")
    saved = asyncio.run(run_all_scrapers())
    if saved > 0:
        run_analytics()
    logger.info(f"🏁 Scrape job complete — saved={saved}")


# ── Lifespan: start scheduler on boot ─────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = BackgroundScheduler(timezone="America/Chicago")
    scheduler.add_job(run_job, IntervalTrigger(hours=24), id="scrape_job", max_instances=1)
    scheduler.start()
    logger.info("⏰ Scheduler started — every 24 h")

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
    version="1.0.0",
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

# ── Output fields for listings API ───────────────────────────
_LISTING_OUTPUT_FIELDS = [
    "id", "source_site", "listing_id", "source_url",
    "auction_date", "title", "description_raw",
    "species", "sex", "age_class", "bred_status",
    "location",
    "price_current", "price_final", "easy_bid_price",
    "auction_status", "bid_count", "quantity",
    "photo_urls", "reserve_status", "is_active",
]


def _format_listing(row: dict) -> dict:
    return {k: row.get(k) for k in _LISTING_OUTPUT_FIELDS}
PAGE_SIZE = 50
VALID_SPECIES = {"axis", "blackbuck", "aoudad"}
VALID_STATUS = {"active", "closed", "sold", "paused", "unknown"}
VALID_TIER = {"elite", "trophy", "good", "management"}


# ── Health ─────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health():
    """Quick liveness check — also reports Supabase availability."""
    return {
        "status": "ok",
        "supabase": SUPABASE_AVAILABLE,
    }


# ── Listings ───────────────────────────────────────────────────

@app.get("/api/listings", tags=["Listings"])
def get_listings(
    site:    Optional[str] = Query(None, description="Filter by source_site (e.g. wildlifebuyer, bucktrader)"),
    species: Optional[str] = Query(None, description="Filter by species (axis, blackbuck, aoudad)"),
    status:  Optional[str] = Query(None, description="Filter by auction_status (active, closed)"),
    tier:    Optional[str] = Query(None, description="Filter by tier (elite, trophy, good, management)"),
    page:    int           = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int         = Query(PAGE_SIZE, ge=1, le=200, description="Items per page"),
):
    """
    Paginated list of listings with optional filters.

    Returns listings + pagination metadata + KPI summary for the current page.
    """
    if not SUPABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Supabase not available")

    # ── Validate filters BEFORE hitting the DB ──
    # Bad input (typos, malformed query params like "[axis]") should be 400,
    # not 500 — a 500 should mean "our server broke", not "you sent garbage".
    if species is not None:
        species = species.strip()
        if species not in VALID_SPECIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid species '{species}'. Must be one of {sorted(VALID_SPECIES)}",
            )

    if status is not None:
        status = status.strip()
        if status not in VALID_STATUS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Must be one of {sorted(VALID_STATUS)}",
            )

    if tier is not None:
        tier = tier.strip()
        if tier not in VALID_TIER:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tier '{tier}'. Must be one of {sorted(VALID_TIER)}",
            )

    if site is not None:
        site = site.strip()
        if not site:
            raise HTTPException(status_code=400, detail="site cannot be empty")

    try:
        client = get_client()
        q = client.table("listings").select("*", count="exact")

        if site:    q = q.eq("source_site",   site)
        if species: q = q.eq("species",        species)
        if status:  q = q.eq("auction_status", status)
        if tier:    q = q.eq("tier",           tier)

        offset = (page - 1) * page_size
        q = q.order("scraped_at", desc=True).range(offset, offset + page_size - 1)

        r = q.execute()
        listings   = [_format_listing(l) for l in (r.data or [])]
        total      = r.count or 0
        total_pages = max(1, math.ceil(total / page_size))

        # Page-level KPIs
        prices = [float(l["price_current"]) for l in listings if l.get("price_current")]

        return {
            "listings": listings,
            "pagination": {
                "page":        page,
                "page_size":   page_size,
                "total":       total,
                "total_pages": total_pages,
                "has_prev":    page > 1,
                "has_next":    page < total_pages,
            },
            "kpis": {
                "total_all_pages": total,
                "active_this_page":   sum(1 for l in listings if l.get("auction_status") == "active"),
                "needs_review_this_page": sum(1 for l in listings if l.get("needs_manual_review")),
                "tiered_this_page":   sum(1 for l in listings if l.get("tier")),
                "avg_price_this_page": round(sum(prices) / len(prices), 2) if prices else None,
                "priced_count_this_page": len(prices),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        # Log the real exception server-side; don't leak internals to the client.
        logger.exception("Unexpected error in get_listings")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/listings/{listing_id}", tags=["Listings"])
def get_listing(listing_id: str):
    """
    Fetch full detail for a single listing by its UUID (id column).
    """
    if not SUPABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Supabase not available")

    # Basic UUID sanity check — malformed IDs should 400, not 500.
    import uuid
    try:
        uuid.UUID(listing_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"'{listing_id}' is not a valid listing id (expected a UUID)")

    try:
        client = get_client()
        r = client.table("listings").select("*").eq("id", listing_id).limit(1).execute()
        rows = r.data or []
        if not rows:
            raise HTTPException(status_code=404, detail="Listing not found")
        return _format_listing(rows[0])

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in get_listing")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Stats ──────────────────────────────────────────────────────

@app.get("/api/stats", tags=["Stats"])
def get_stats():
    """
    Aggregate stats across all listings:
    totals, price distribution, and breakdowns by site / species / tier.
    """
    if not SUPABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Supabase not available")

    try:
        client = get_client()
        r = client.table("listings").select(
            "species,tier,auction_status,source_site,price_current,needs_manual_review"
        ).execute()
        rows = r.data or []

        prices = [float(x["price_current"]) for x in rows if x.get("price_current")]
        sorted_prices = sorted(prices)

        by_site:    dict = defaultdict(int)
        by_species: dict = defaultdict(int)
        by_tier:    dict = defaultdict(int)

        for x in rows:
            by_site   [x.get("source_site") or "unknown"] += 1
            by_species[x.get("species")     or "unknown"] += 1
            by_tier   [x.get("tier")        or "untiered"] += 1

        return {
            "totals": {
                "total":        len(rows),
                "active":       sum(1 for x in rows if x.get("auction_status") == "active"),
                "with_tier":    sum(1 for x in rows if x.get("tier")),
                "needs_review": sum(1 for x in rows if x.get("needs_manual_review")),
            },
            "prices": {
                "avg":    round(sum(prices) / len(prices), 2) if prices else None,
                "median": sorted_prices[len(sorted_prices) // 2] if prices else None,
                "min":    sorted_prices[0]  if prices else None,
                "max":    sorted_prices[-1] if prices else None,
                "count":  len(prices),
            },
            "by_site":    dict(by_site),
            "by_species": dict(by_species),
            "by_tier":    dict(by_tier),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in get_stats")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Scraper trigger (manual) ───────────────────────────────────

@app.post("/api/run-job", tags=["System"])
def trigger_job():
    """
    Manually trigger one scrape + analytics cycle outside the 24h schedule.
    """
    import threading
    threading.Thread(target=run_job, daemon=True).start()
    return {"status": "triggered"}