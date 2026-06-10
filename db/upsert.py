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
_SOURCE_SITE_ENUM    = {"wildlifebuyer", "bucktrader", "exoticauctions", "onlinehuntingauctions"}


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
    Upsert a batch with deduplication within the batch.
    Uses (source_site, listing_id) as composite key for duplicate detection.
    For wildlifebuyer, the same listing_id can have multiple URL variants;
    we keep the most recent one.
    
    Returns (success_count, error_count).
    """
    if not listings:
        return 0, 0

    # Deduplicate by composite key (source_site, listing_id)
    # This handles cases like wildlifebuyer where listing_id is stable
    # but URL slug changes over time
    seen = {}
    for listing in listings:
        site = listing.get("source_site", "unknown")
        lid = listing.get("listing_id")
        url = listing.get("source_url")
        
        if url:
            # Use composite key but prefer by scraped_at (most recent)
            key = (site, lid)
            existing = seen.get(key)
            
            if existing:
                existing_time = existing.get("scraped_at", "")
                new_time = listing.get("scraped_at", "")
                if new_time > existing_time:
                    seen[key] = listing
            else:
                seen[key] = listing
    
    rows = [_filter_fields(l) for l in seen.values()]
    skipped_duplicates = len(listings) - len(rows)
    if skipped_duplicates > 0:
        logger.info(f"⚠️  Skipped {skipped_duplicates} duplicates within batch")
    
    if not rows:
        return 0, len(listings)

    try:
        response = (
            get_client()
            .table("listings")
            .upsert(rows, on_conflict="source_url", ignore_duplicates=False)
            .execute()
        )
        # Fetch what was inserted/updated to log changes
        _log_batch_changes(rows, response.data or [])
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


def _log_batch_changes(new_rows: list[dict], result_rows: list[dict]) -> None:
    """
    Compare new rows with result to detect and log updates to mutable fields.
    """
    if not result_rows:
        return
    
    result_by_url = {row.get("source_url"): row for row in result_rows}
    
    for new_row in new_rows:
        url = new_row.get("source_url")
        result_row = result_by_url.get(url)
        if not result_row:
            continue
        
        # Check for changes in mutable fields
        changes = {}
        for field in _MUTABLE_FIELDS:
            new_val = new_row.get(field)
            old_val = result_row.get(field)
            if new_val != old_val:
                changes[field] = f"{old_val} → {new_val}"
        
        if changes:
            title = new_row.get("title", url)
            logger.info(f"  📝 Updated: {title[:60]}")
            for field, change in changes.items():
                logger.info(f"     {field}: {change}")
