# # ============================================================
# # HoofMarketIQ — db/active_listings.py
# # ------------------------------------------------------------
# # "Refresh active listings" merge step.
# #
# # Problem this module solves:
# #   WildlifeBuyer (and similar auction sites) remove listings
# #   from their browse pages once the auction closes.  Once a
# #   listing leaves the browse pages, the scraper never sees it
# #   again, so its DB row stays `auction_status = 'active'`
# #   forever — even though the auction is long over.
# #
# # Fix:
# #   Before each scrape run, fetch every active DB row for the
# #   site and merge its URL back into the scrape queue.  The
# #   detail scraper then re-fetches that URL and the upsert
# #   updates `auction_status` to its real value (closed/sold).
# #
# # Dedup contract:
# #   - Primary key: `source_url` (this matches the DB upsert's
# #     `on_conflict="source_url"`, so it is the source of truth
# #     for "do we already have this row?").
# #   - Secondary key: `listing_id` — handles the case where the
# #     seller edited a listing and the URL slug changed but the
# #     underlying site listing_id stayed the same.  In that case
# #     we keep the freshly-discovered browse URL (so the new
# #     detail scrape can run) and tag the card so we still
# #     detect active → closed transitions.
# # ============================================================

# import logging
# from typing import Any

# from db.supabase_client import get_client

# logger = logging.getLogger(__name__)

# # Tag attached to cards that came from (or matched) an active DB row.
# # Used by the orchestrator to detect active → closed/sold transitions.
# # This key is NOT in `db.upsert._LISTING_FIELDS`, so it is stripped
# # automatically before the row reaches the DB.
# DB_ACTIVE_TAG = "_from_db_active"


# def fetch_active_listings(source_site: str) -> list[dict]:
#     """Return every DB row for `source_site` whose auction_status = 'active'.

#     Each row is shaped as: {listing_id, source_url, auction_status}.
#     Failures are logged and an empty list is returned so a DB hiccup
#     never breaks the scrape run.
#     """
#     try:
#         r = (
#             get_client()
#             .table("listings")
#             .select("listing_id,source_url,auction_status")
#             .eq("source_site", source_site)
#             .eq("auction_status", "active")
#             .execute()
#         )
#         return r.data or []
#     except Exception as e:
#         logger.warning(
#             f"  Could not fetch active DB listings for {source_site}: {e}"
#         )
#         return []


# def merge_with_active_db(
#     source_site: str, browse_cards: list[dict]
# ) -> tuple[list[dict], dict]:
#     """Merge browse-discovered cards with active DB listings.

#     Args:
#         source_site: e.g. "wildlifebuyer"
#         browse_cards: cards from `scraper.collect_listing_urls()`.
#             Each must have at least `url`; `listing_id` is optional
#             but recommended.

#     Returns:
#         (merged_cards, stats) where:
#           merged_cards — deduped list to feed back into `scraper.scrape_detail()`.
#                          Cards sourced from the DB are tagged with
#                          `DB_ACTIVE_TAG = True` so the orchestrator can
#                          detect active → closed/sold transitions.
#           stats        — {db_active, new_urls, merged_total, db_added_back,
#                           overlap_listing_id, overlap_url}
#     """
#     merged_by_url: dict[str, dict] = {}
#     browse_listing_ids: dict[str, dict] = {}  # listing_id -> card (for overlap tagging)

#     # 1. Index browse cards by URL (and listing_id where available).
#     for card in browse_cards:
#         url = card.get("url")
#         if not url or url in merged_by_url:
#             continue
#         merged_by_url[url] = card
#         lid = card.get("listing_id")
#         if lid:
#             browse_listing_ids[str(lid)] = card

#     new_urls = len(merged_by_url)

#     # 2. Pull active DB rows for this site.
#     db_active = fetch_active_listings(source_site)

#     db_added_back = 0
#     overlap_listing_id = 0
#     overlap_url = 0

#     # 3. Re-add any DB row that is NOT already covered by the browse set.
#     for row in db_active:
#         url = row.get("source_url")
#         lid = row.get("listing_id")

#         # 3a. Same listing_id already in browse (URL slug may have changed) —
#         #     tag the existing browse card so transitions are still detected,
#         #     and don't add a duplicate card.
#         if lid and str(lid) in browse_listing_ids:
#             browse_listing_ids[str(lid)][DB_ACTIVE_TAG] = True
#             overlap_listing_id += 1
#             continue

#         # 3b. Same URL already in browse — tag and skip.
#         if url and url in merged_by_url:
#             merged_by_url[url][DB_ACTIVE_TAG] = True
#             overlap_url += 1
#             continue

#         # 3c. Genuinely missing from this browse run — re-queue it.
#         if not url:
#             # No URL means we cannot re-scrape; skip with a warning.
#             logger.warning(
#                 f"  Active DB row has no source_url "
#                 f"(listing_id={lid!r}, site={source_site}) — skipping"
#             )
#             continue

#         merged_by_url[url] = {
#             "listing_id": lid,
#             "url": url,
#             "source_site": source_site,
#             DB_ACTIVE_TAG: True,
#         }
#         db_added_back += 1

#     stats = {
#         "db_active": len(db_active),
#         "new_urls": new_urls,
#         "merged_total": len(merged_by_url),
#         "db_added_back": db_added_back,
#         "overlap_listing_id": overlap_listing_id,
#         "overlap_url": overlap_url,
#     }
#     return list(merged_by_url.values()), stats


# def log_merge_stats(source_site: str, stats: dict) -> None:
#     """Emit the structured log lines the orchestrator contract requires."""
#     logger.info(f"  [{source_site}] Active listings loaded from DB : {stats['db_active']}")
#     logger.info(f"  [{source_site}] New URLs discovered (browse)  : {stats['new_urls']}")
#     logger.info(f"  [{source_site}] DB active re-queued           : {stats['db_added_back']}")
#     logger.info(f"  [{source_site}] Overlap (same listing_id)     : {stats['overlap_listing_id']}")
#     logger.info(f"  [{source_site}] Overlap (same URL)            : {stats['overlap_url']}")
#     logger.info(f"  [{source_site}] Total merged URLs to scrape   : {stats['merged_total']}")





# ============================================================
# HoofMarketIQ — db/active_listings.py
# ------------------------------------------------------------
# "Refresh active listings" merge step.
#
# Problem this module solves:
#   WildlifeBuyer (and similar auction sites) remove listings
#   from their browse pages once the auction closes.  Once a
#   listing leaves the browse pages, the scraper never sees it
#   again, so its DB row stays `auction_status = 'active'`
#   forever — even though the auction is long over.
#
# Fix:
#   Before each scrape run, fetch every active DB row for the
#   site and merge its URL back into the scrape queue.  The
#   detail scraper then re-fetches that URL and the upsert
#   updates `auction_status` to its real value (closed/sold).
#
# Dedup contract:
#   - Primary key: `source_url` (this matches the DB upsert's
#     `on_conflict="source_url"`, so it is the source of truth
#     for "do we already have this row?").
#   - Secondary key: `listing_id` — handles the case where the
#     seller edited a listing and the URL slug changed but the
#     underlying site listing_id stayed the same.  In that case
#     we keep the freshly-discovered browse URL (so the new
#     detail scrape can run) and tag the card so we still
#     detect active → closed transitions.
# ============================================================

import logging
from typing import Any

from db.supabase_client import get_client

logger = logging.getLogger(__name__)

# Tag attached to cards that came from (or matched) an active DB row.
# Used by the orchestrator to detect active → closed/sold transitions.
# This key is NOT in `db.upsert._LISTING_FIELDS`, so it is stripped
# automatically before the row reaches the DB.
DB_ACTIVE_TAG = "_from_db_active"


def fetch_active_listings(source_site: str) -> list[dict]:
    """Return every DB row for `source_site` whose auction_status = 'active'.

    Each row is shaped as: {listing_id, source_url, auction_status}.
    Failures are logged and an empty list is returned so a DB hiccup
    never breaks the scrape run.
    """
    try:
        r = (
            get_client()
            .table("listings")
            .select("listing_id,source_url,auction_status")
            .eq("source_site", source_site)
            .eq("auction_status", "active")
            .execute()
        )
        return r.data or []
    except Exception as e:
        logger.warning(
            f"  Could not fetch active DB listings for {source_site}: {e}"
        )
        return []


def merge_with_active_db(
    source_site: str, browse_cards: list[dict]
) -> tuple[list[dict], dict]:
    """Merge browse-discovered cards with active DB listings.

    Args:
        source_site: e.g. "wildlifebuyer"
        browse_cards: cards from `scraper.collect_listing_urls()`.
            Each must have at least `url`; `listing_id` is optional
            but recommended.

    Returns:
        (merged_cards, stats) where:
          merged_cards — deduped list to feed back into `scraper.scrape_detail()`.
                         Cards sourced from the DB are tagged with
                         `DB_ACTIVE_TAG = True` so the orchestrator can
                         detect active → closed/sold transitions.
          stats        — {db_active, new_urls, merged_total, db_added_back,
                          overlap_listing_id, overlap_url}
    """
    merged_by_url: dict[str, dict] = {}
    browse_listing_ids: dict[str, dict] = {}  # listing_id -> card (for overlap tagging)

    # 1. Index browse cards by URL (and listing_id where available).
    for card in browse_cards:
        url = card.get("url")
        if not url or url in merged_by_url:
            continue
        merged_by_url[url] = card
        lid = card.get("listing_id")
        if lid:
            browse_listing_ids[str(lid)] = card

    new_urls = len(merged_by_url)

    # 2. Pull active DB rows for this site.
    db_active = fetch_active_listings(source_site)

    db_added_back = 0
    overlap_listing_id = 0
    overlap_url = 0

    # 3. Re-add any DB row that is NOT already covered by the browse set.
    for row in db_active:
        url = row.get("source_url")
        lid = row.get("listing_id")

        # 3a. Same listing_id already in browse (URL slug may have changed) —
        #     tag the existing browse card so transitions are still detected,
        #     and don't add a duplicate card.
        if lid and str(lid) in browse_listing_ids:
            browse_listing_ids[str(lid)][DB_ACTIVE_TAG] = True
            overlap_listing_id += 1
            continue

        # 3b. Same URL already in browse — tag and skip.
        if url and url in merged_by_url:
            merged_by_url[url][DB_ACTIVE_TAG] = True
            overlap_url += 1
            continue

        # 3c. Genuinely missing from this browse run — re-queue it.
        if not url:
            # No URL means we cannot re-scrape; skip with a warning.
            logger.warning(
                f"  Active DB row has no source_url "
                f"(listing_id={lid!r}, site={source_site}) — skipping"
            )
            continue

        merged_by_url[url] = {
            "listing_id": lid,
            "url": url,
            "source_site": source_site,
            DB_ACTIVE_TAG: True,
        }
        db_added_back += 1

    stats = {
        "db_active": len(db_active),
        "new_urls": new_urls,
        "merged_total": len(merged_by_url),
        "db_added_back": db_added_back,
        "overlap_listing_id": overlap_listing_id,
        "overlap_url": overlap_url,
    }
    return list(merged_by_url.values()), stats


def log_merge_stats(source_site: str, stats: dict) -> None:
    """Emit the structured log lines the orchestrator contract requires."""
    logger.info(f"  [{source_site}] Active listings loaded from DB : {stats['db_active']}")
    logger.info(f"  [{source_site}] New URLs discovered (browse)  : {stats['new_urls']}")
    logger.info(f"  [{source_site}] DB active re-queued           : {stats['db_added_back']}")
    logger.info(f"  [{source_site}] Overlap (same listing_id)     : {stats['overlap_listing_id']}")
    logger.info(f"  [{source_site}] Overlap (same URL)            : {stats['overlap_url']}")
    logger.info(f"  [{source_site}] Total merged URLs to scrape   : {stats['merged_total']}")