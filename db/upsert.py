# db/upsert.py
import logging
from db.supabase_client import get_client

logger = logging.getLogger(__name__)

_LISTING_FIELDS = {
    "listing_id", "source_url", "source_site", "scraped_at",
    "title", "description_raw",
    "price_current", "price_final", "price_start", "easy_bid_price", "bid_count",
    "auction_status", "auction_date",
    "photo_urls", "seller_id", "quantity",
    "species", "sex", "age_class", "bred_status", "color_phase",
    "location_raw", "location_city", "location_county",
    "location_region", "location_state",
    "primary_measurement_inches", "secondary_measurements",
    "tier", "tier_confidence", "quality_score",
    "extraction_notes", "needs_manual_review", "is_active",
}

# Fields that change over time — logged when they differ from existing row
_MUTABLE_FIELDS = {"price_current", "auction_status", "bid_count", "easy_bid_price", "photo_urls"}

_SPECIES_ENUM        = {"axis", "blackbuck", "aoudad"}
_SEX_ENUM            = {"male", "female", "unknown"}
_AUCTION_STATUS_ENUM = {"active", "closed", "paused", "unknown"}
_AGE_CLASS_ENUM      = {"calf", "yearling", "mature_2_4", "prime_4_6", "mature_6plus", "unknown"}
_BRED_STATUS_ENUM    = {"wild", "ranch_bred", "ai", "et", "proven_breeder", "unknown"}
_TIER_ENUM           = {"management", "good", "trophy", "elite"}
_SOURCE_SITE_ENUM    = {"wildlifebuyer", "bucktrader", "exoticauctions"}


def _filter_fields(listing: dict) -> dict:
    row = {k: v for k, v in listing.items() if k in _LISTING_FIELDS}
    if row.get("species")        not in _SPECIES_ENUM:        row["species"]        = None
    if row.get("sex")            not in _SEX_ENUM:            row["sex"]            = "unknown"
    if row.get("auction_status") not in _AUCTION_STATUS_ENUM: row["auction_status"] = "unknown"
    if row.get("age_class")      not in _AGE_CLASS_ENUM:      row["age_class"]      = "unknown"
    if row.get("bred_status")    not in _BRED_STATUS_ENUM:    row["bred_status"]    = "unknown"
    if row.get("tier")           not in _TIER_ENUM:           row["tier"]           = None
    if row.get("source_site")    not in _SOURCE_SITE_ENUM:    row["source_site"]    = None
    return row


def upsert_batch(listings: list[dict]) -> tuple[int, int]:
    """
    Upsert a batch. On conflict with source_url, ALL fields are updated.
    ignoreDuplicates=False ensures existing rows are always overwritten
    with the latest scraped values (price, status, bid_count, etc).
    Returns (success_count, error_count).
    """
    if not listings:
        return 0, 0

    rows = [_filter_fields(l) for l in listings if l.get("source_url")]
    if not rows:
        return 0, len(listings)

    try:
        (
            get_client()
            .table("listings")
            .upsert(rows, on_conflict="source_url", ignore_duplicates=False)
            .execute()
        )
        logger.info(f"✅ Upserted batch of {len(rows)}")
        return len(rows), 0
    except Exception as e:
        logger.error(f"Batch upsert failed: {e}")
        return 0, len(rows)


def upsert_listing(listing: dict) -> bool:
    row = _filter_fields(listing)
    if not row.get("source_url"):
        logger.warning("Skipping listing with no source_url")
        return False
    try:
        (
            get_client()
            .table("listings")
            .upsert(row, on_conflict="source_url", ignore_duplicates=False)
            .execute()
        )
        return True
    except Exception as e:
        logger.error(f"Upsert failed for {row.get('source_url')}: {e}")
        return False
