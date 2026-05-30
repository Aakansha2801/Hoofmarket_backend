# orchestrator.py
# Runs all registered site scrapers, normalizes output, upserts to Supabase.
# To add a new site: instantiate its scraper class and add to SCRAPERS list.

import logging

from scrapers.browser import make_httpx_client, close_browser
from scrapers.wildlifebuyer import WildlifeBuyerScraper
from scrapers.bucktrader import BuckTraderScraper

from parser.field_extractor import extract_fields
from parser.tier_calculator import apply_tier
from db.upsert import upsert_batch

logger = logging.getLogger(__name__)

# ── Registered scrapers ───────────────────────────────────────
# Add new site scrapers here — nothing else needs to change
SCRAPERS = [
    WildlifeBuyerScraper(),
    BuckTraderScraper(),
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

    await close_browser()
    logger.info(f"✅ All scrapers done — total saved={total_saved}")
    return total_saved


async def _run_one(scraper, client) -> int:
    cards = await scraper.collect_listing_urls(client)
    logger.info(f"  [{scraper.source_site}] {len(cards)} URLs collected")

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
