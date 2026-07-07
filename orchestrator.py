# orchestrator.py
# Runs all registered site scrapers, normalizes output, upserts to Supabase.
# To add a new site: instantiate its scraper class and add to SCRAPERS list.

import logging

from scrapers.browser import make_httpx_client
from scrapers.wildlifebuyer import WildlifeBuyerScraper
from scrapers.bucktrader import BuckTraderScraper
from scrapers.onlinehuntingauctions import OnlineHuntingAuctionsScraper
from parser.field_extractor import extract_fields
from parser.tier_calculator import apply_tier
from db.upsert import upsert_batch
from db.supabase_client import get_client

logger = logging.getLogger(__name__)

# ── Registered scrapers ───────────────────────────────────────
# Add new site scrapers here — nothing else needs to change
SCRAPERS = [
    WildlifeBuyerScraper(),
    BuckTraderScraper(),
     OnlineHuntingAuctionsScraper(),
]

BATCH_SIZE = 20


async def run_all_scrapers() -> int:
    """Run every registered scraper. Returns total listings saved."""
    total_saved = 0

    async with make_httpx_client() as client:
        for scraper in SCRAPERS:
            site = scraper.source_site
            logger.info(f"━━━ Scraper: {site} ━━━")
            saved = await _run_one(scraper, client)
            logger.info(f"[{site}] saved={saved}")
            total_saved += saved

    logger.info(f"✅ All scrapers done — total saved={total_saved}")
    return total_saved


async def _run_one(scraper, client) -> int:
    cards = await scraper.collect_listing_urls(client)
    logger.info(f"  [{scraper.source_site}] {len(cards)} URLs collected")

    # Add previously-active DB listings not seen in browse — they may have sold
    seen_ids = {c.get("listing_id") for c in cards}
    stale = _fetch_stale_active(scraper.source_site, seen_ids)
    if stale:
        logger.info(f"  [{scraper.source_site}] +{len(stale)} stale active listings to recheck")
        cards = cards + stale

    batch, ok, err = [], 0, 0

    for i, card in enumerate(cards, 1):
        raw = await scraper.scrape_detail(card, client)
        if not raw:
            err += 1
            continue

        enriched = apply_tier(extract_fields(raw))
        batch.append(enriched)

        if len(batch) >= BATCH_SIZE:
            s, f = upsert_batch(batch)
            ok += s; err += f
            batch.clear()
            logger.info(f"  [{scraper.source_site}] {i}/{len(cards)} | saved={ok} errors={err}")

    if batch:
        s, f = upsert_batch(batch)
        ok += s; err += f

    if err:
        logger.warning(f"  [{scraper.source_site}] {err} listings failed")
    return ok


def _fetch_stale_active(source_site: str, seen_ids: set) -> list[dict]:
    """Fetch active DB listings not present in the current browse run."""
    try:
        r = (
            get_client()
            .table("listings")
            .select("listing_id,source_url")
            .eq("source_site", source_site)
            .eq("auction_status", "active")
            .execute()
        )
        return [
            {"listing_id": row["listing_id"], "url": row["source_url"]}
            for row in r.data
            if row["listing_id"] not in seen_ids
        ]
    except Exception as e:
        logger.warning(f"  Could not fetch stale active listings: {e}")
        return []
