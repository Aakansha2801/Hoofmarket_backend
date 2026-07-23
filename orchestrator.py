# # orchestrator.py
# # Runs all registered site scrapers, normalizes output, upserts to Supabase.
# # To add a new site: instantiate its scraper class and add to SCRAPERS list.

# import logging

# from scrapers.browser import make_httpx_client
# from scrapers.wildlifebuyer import WildlifeBuyerScraper
# from scrapers.bucktrader import BuckTraderScraper
# from scrapers.onlinehuntingauctions import OnlineHuntingAuctionsScraper
# from parser.field_extractor import extract_fields
# from parser.tier_calculator import apply_tier
# from db.upsert import upsert_batch
# from db.active_listings import (
#     DB_ACTIVE_TAG,
#     merge_with_active_db,
#     log_merge_stats,
# )

# logger = logging.getLogger(__name__)

# # ── Registered scrapers ───────────────────────────────────────
# # Add new site scrapers here — nothing else needs to change
# SCRAPERS = [
#     WildlifeBuyerScraper(),
#     BuckTraderScraper(),
#     OnlineHuntingAuctionsScraper(),
# ]

# BATCH_SIZE = 20

# # auction_status values that count as "the auction is over"
# # — used to detect active → closed/sold transitions
# _TERMINAL_STATUSES = {"closed", "sold"}


# async def run_all_scrapers() -> int:
#     """Run every registered scraper. Returns total listings saved."""
#     total_saved = 0

#     async with make_httpx_client() as client:
#         for scraper in SCRAPERS:
#             site = scraper.source_site
#             logger.info(f"━━━ Scraper: {site} ━━━")
#             saved = await _run_one(scraper, client)
#             logger.info(f"[{site}] saved={saved}")
#             total_saved += saved

#     logger.info(f"✅ All scrapers done — total saved={total_saved}")
#     return total_saved


# async def _run_one(scraper, client) -> int:
#     """Run one site scraper end-to-end.

#     Workflow:
#       1. Collect URLs from browse pages (existing behavior).
#       2. Fetch all listings from DB where auction_status='active'.
#       3. Merge DB active URLs with newly discovered URLs (dedupe by URL,
#          with listing_id as secondary key to handle slug changes).
#       4. Re-scrape every URL in the merged set.
#       5. Upsert — updates status, title, price, auction state, all fields.
#       6. If a previously-active listing is now closed/sold/completed,
#          log the active → terminal transition.
#     """
#     # ── Step 1: browse pages ─────────────────────────────────
#     browse_cards = await scraper.collect_listing_urls(client)
#     logger.info(
#         f"  [{scraper.source_site}] {len(browse_cards)} URLs collected from browse pages"
#     )

#     # ── Steps 2–4: merge with DB active listings ─────────────
#     cards, stats = merge_with_active_db(scraper.source_site, browse_cards)
#     log_merge_stats(scraper.source_site, stats)

#     if not cards:
#         logger.info(f"  [{scraper.source_site}] Nothing to scrape — skipping")
#         return 0

#     # ── Steps 5–6: scrape, upsert, track transitions ─────────
#     batch, ok, err = [], 0, 0
#     closed_transitions = 0
#     transition_samples: list[str] = []

#     for i, card in enumerate(cards, 1):
#         was_active_db = bool(card.get(DB_ACTIVE_TAG))

#         raw = await scraper.scrape_detail(card, client)
#         if not raw:
#             err += 1
#             continue

#         # Detect active → closed/sold transition BEFORE upsert
#         new_status = raw.get("auction_status")
#         if was_active_db and new_status in _TERMINAL_STATUSES:
#             closed_transitions += 1
#             label = raw.get("title") or raw.get("source_url") or card.get("url")
#             sample = f"active → {new_status}: {str(label)[:70]}"
#             transition_samples.append(sample)
#             logger.info(f"  🔄 [{scraper.source_site}] {sample}")

#         enriched = apply_tier(extract_fields(raw))
#         batch.append(enriched)

#         if len(batch) >= BATCH_SIZE:
#             s, f = upsert_batch(batch)
#             ok += s
#             err += f
#             batch.clear()
#             logger.info(
#                 f"  [{scraper.source_site}] {i}/{len(cards)} | saved={ok} errors={err}"
#             )

#     if batch:
#         s, f = upsert_batch(batch)
#         ok += s
#         err += f

#     # ── Final summary log ────────────────────────────────────
#     logger.info(
#         f"  [{scraper.source_site}] 📊 Listings updated active → closed/sold: "
#         f"{closed_transitions}"
#     )
#     if closed_transitions:
#         # Re-emit a compact sample so operators can spot-check
#         for sample in transition_samples[:10]:
#             logger.info(f"     • {sample}")
#         if len(transition_samples) > 10:
#             logger.info(
#                 f"     … and {len(transition_samples) - 10} more"
#             )

#     if err:
#         logger.warning(f"  [{scraper.source_site}] {err} listings failed")
#     return ok



# orchestrator.py
# Runs all registered site scrapers, normalizes output, upserts to Supabase.
# After every scrape cycle, also pushes new listings to Bubble.io.
# To add a new site: instantiate its scraper class and add to SCRAPERS list.

import logging

from scrapers.browser import make_httpx_client
from scrapers.wildlifebuyer import WildlifeBuyerScraper
from scrapers.bucktrader import BuckTraderScraper
from scrapers.onlinehuntingauctions import OnlineHuntingAuctionsScraper
from parser.field_extractor import extract_fields
from parser.tier_calculator import apply_tier
from db.upsert import upsert_batch
from db.active_listings import (
    DB_ACTIVE_TAG,
    merge_with_active_db,
    log_merge_stats,
)

logger = logging.getLogger(__name__)

# ── Registered scrapers ───────────────────────────────────────
# Add new site scrapers here — nothing else needs to change
SCRAPERS = [
    WildlifeBuyerScraper(),
    BuckTraderScraper(),
    OnlineHuntingAuctionsScraper(),
]

BATCH_SIZE = 20

# auction_status values that count as "the auction is over"
# — used to detect active → closed/sold transitions
_TERMINAL_STATUSES = {"closed", "sold"}


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

    # ── Sync new listings to Bubble.io ───────────────────────
    # Runs after every scrape cycle. Wrapped in try/except so a Bubble
    # outage never fails the scrape run.
    _sync_to_bubble_safe()

    return total_saved


def _sync_to_bubble_safe() -> None:
    """Push new Supabase listings to Bubble.io.

    Imports are deferred so the orchestrator module loads cleanly even
    if `bubble_sync` is misconfigured (missing token, network down, etc.).
    Failures are logged but never raised.
    """
    try:
        import bubble_sync
        logger.info("━━━ Bubble.io sync ━━━")
        bubble_sync.sync_to_bubble()
        logger.info("✅ Bubble sync done")
    except Exception as e:
        logger.warning(f"⚠️  Bubble sync failed (scrape still succeeded): {e}")


async def _run_one(scraper, client) -> int:
    """Run one site scraper end-to-end.

    Workflow:
      1. Collect URLs from browse pages (existing behavior).
      2. Fetch all listings from DB where auction_status='active'.
      3. Merge DB active URLs with newly discovered URLs (dedupe by URL,
         with listing_id as secondary key to handle slug changes).
      4. Re-scrape every URL in the merged set.
      5. Upsert — updates status, title, price, auction state, all fields.
      6. If a previously-active listing is now closed/sold/completed,
         log the active → terminal transition.
    """
    # ── Step 1: browse pages ─────────────────────────────────
    browse_cards = await scraper.collect_listing_urls(client)
    logger.info(
        f"  [{scraper.source_site}] {len(browse_cards)} URLs collected from browse pages"
    )

    # ── Steps 2–4: merge with DB active listings ─────────────
    cards, stats = merge_with_active_db(scraper.source_site, browse_cards)
    log_merge_stats(scraper.source_site, stats)

    if not cards:
        logger.info(f"  [{scraper.source_site}] Nothing to scrape — skipping")
        return 0

    # ── Steps 5–6: scrape, upsert, track transitions ─────────
    batch, ok, err = [], 0, 0
    closed_transitions = 0
    transition_samples: list[str] = []

    for i, card in enumerate(cards, 1):
        was_active_db = bool(card.get(DB_ACTIVE_TAG))

        raw = await scraper.scrape_detail(card, client)
        if not raw:
            err += 1
            continue

        # Detect active → closed/sold transition BEFORE upsert
        new_status = raw.get("auction_status")
        if was_active_db and new_status in _TERMINAL_STATUSES:
            closed_transitions += 1
            label = raw.get("title") or raw.get("source_url") or card.get("url")
            sample = f"active → {new_status}: {str(label)[:70]}"
            transition_samples.append(sample)
            logger.info(f"  🔄 [{scraper.source_site}] {sample}")

        enriched = apply_tier(extract_fields(raw))
        batch.append(enriched)

        if len(batch) >= BATCH_SIZE:
            s, f = upsert_batch(batch)
            ok += s
            err += f
            batch.clear()
            logger.info(
                f"  [{scraper.source_site}] {i}/{len(cards)} | saved={ok} errors={err}"
            )

    if batch:
        s, f = upsert_batch(batch)
        ok += s
        err += f

    # ── Final summary log ────────────────────────────────────
    logger.info(
        f"  [{scraper.source_site}] 📊 Listings updated active → closed/sold: "
        f"{closed_transitions}"
    )
    if closed_transitions:
        # Re-emit a compact sample so operators can spot-check
        for sample in transition_samples[:10]:
            logger.info(f"     • {sample}")
        if len(transition_samples) > 10:
            logger.info(
                f"     … and {len(transition_samples) - 10} more"
            )

    if err:
        logger.warning(f"  [{scraper.source_site}] {err} listings failed")
    return ok