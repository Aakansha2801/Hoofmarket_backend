# orchestrator.py
# Runs all registered site scrapers, enriches listings, and syncs
# them directly to Bubble.io.  No intermediate database layer.
# To add a new site: instantiate its scraper class and add to SCRAPERS list.

import asyncio
import logging

from scrapers.browser import make_httpx_client
from scrapers.wildlifebuyer import WildlifeBuyerScraper
from scrapers.bucktrader import BuckTraderScraper
from scrapers.onlinehuntingauctions import OnlineHuntingAuctionsScraper
from parser.field_extractor import extract_fields
from parser.tier_calculator import apply_tier

logger = logging.getLogger(__name__)

# ── Registered scrapers ───────────────────────────────────────
# Add new site scrapers here — nothing else needs to change
SCRAPERS = [
    WildlifeBuyerScraper(),
    BuckTraderScraper(),
    OnlineHuntingAuctionsScraper(),
]


async def run_all_scrapers() -> int:
    """Run every registered scraper. Returns total listings scraped."""
    total_scraped = 0

    async with make_httpx_client() as client:
        for scraper in SCRAPERS:
            site = scraper.source_site
            logger.info(f"━━━ Scraper: {site} ━━━")
            scraped = await _run_one(scraper, client)
            logger.info(f"[{site}] scraped={scraped}")
            total_scraped += scraped

    logger.info(f"✅ All scrapers done — total scraped={total_scraped}")

    # ── Sync scraped listings to Bubble.io ───────────────────────
    # Runs after every scrape cycle. Wrapped in try/except so a Bubble
    # outage never fails the scrape run.
    _sync_to_bubble_safe()

    return total_scraped


def _sync_to_bubble_safe() -> None:
    """Push freshly scraped listings to Bubble.io.

    Imports are deferred so the orchestrator module loads cleanly even
    if `bubble_sync` is misconfigured (missing token, network down, etc.).
    Failures are logged but never raised.
    """
    try:
        import bubble_sync
        logger.info("━━━ Bubble.io sync ━━━")
        asyncio.run(bubble_sync.sync_to_bubble())
        logger.info("✅ Bubble sync done")
    except Exception as e:
        logger.warning(f"⚠️  Bubble sync failed (scrape still succeeded): {e}")


async def _run_one(scraper, client) -> int:
    """Run one site scraper end-to-end.

    Workflow:
      1. Collect URLs from browse pages.
      2. Scrape detail for each card.
      3. Enrich with extract_fields() + apply_tier().
      4. Log progress and return count of successful scrapes.
    """
    browse_cards = await scraper.collect_listing_urls(client)
    logger.info(
        f"  [{scraper.source_site}] {len(browse_cards)} URLs collected from browse pages"
    )

    if not browse_cards:
        logger.info(f"  [{scraper.source_site}] Nothing to scrape — skipping")
        return 0

    ok, err = 0, 0

    for i, card in enumerate(browse_cards, 1):
        raw = await scraper.scrape_detail(card, client)
        if not raw:
            err += 1
            continue

        # Enrich: extract species/sex/age_class/bred_status, then apply tier
        enriched = apply_tier(extract_fields(raw))

        ok += 1

        if i % 20 == 0:
            logger.info(
                f"  [{scraper.source_site}] {i}/{len(browse_cards)} | ok={ok} err={err}"
            )

    logger.info(f"  [{scraper.source_site}] Scrape complete: ok={ok} err={err}")

    if err:
        logger.warning(f"  [{scraper.source_site}] {err} listings failed")
    return ok
