# ============================================================
# HoofMarketIQ — analytics/engine.py
# V1 Analytics — computation logic only (no database writes)
#
# All Supabase table writes have been removed. The computation
# functions are preserved for future use with Bubble.io or any
# other data store.  For now, analytics results are logged but
# not persisted anywhere.
# ============================================================

import logging
import statistics
from datetime import date, datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────
PRIMARY_SPECIES  = ["axis", "blackbuck", "aoudad"]
ALL_FILTERS      = PRIMARY_SPECIES + ["other", "all"]

SEXES     = ["male", "female", "unknown"]
AGE_CLASSES = ["calf", "yearling", "mature_2_4", "prime_4_6", "mature_6plus"]

PRICE_BUCKETS = [
    (0,      500,   "$0–500"),
    (500,    1000,  "$500–1K"),
    (1000,   2000,  "$1K–2K"),
    (2000,   3500,  "$2K–3.5K"),
    (3500,   5000,  "$3.5K–5K"),
    (5000,   7500,  "$5K–7.5K"),
    (7500,   10000, "$7.5K–10K"),
    (10000,  99999, "$10K+"),
]


# ── Main entry point ──────────────────────────────────────────

def run_analytics(listings: list[dict] | None = None):
    """Run analytics computations on scraped listing data.

    If no listings are provided, this logs a warning and returns.
    In the future, listings can be fetched from Bubble.io.

    Args:
        listings: list of listing dicts with at least the keys:
            species, sex, age_class, location, price_current,
            auction_status, scraped_at, auction_date
    """
    logger.info("📊 Running analytics...")

    if not listings:
        logger.warning("  No listings provided — analytics skipped (no Supabase to read from)")
        return

    priced = [l for l in listings if l.get("price_current")]
    if not priced:
        logger.warning("  No listings with price found — skipping analytics")
        return

    logger.info(f"  Working with {len(priced)} priced listings")

    _compute_market_overview(priced)
    _compute_price_snapshots(priced)
    _compute_sex_age_stats(priced)
    _compute_region_stats(priced)
    _compute_species_comparison(priced)

    logger.info("✅ Analytics complete (results logged, not persisted to DB)")


# ── species_filter helper ─────────────────────────────────────

def _get_filter(species: str | None) -> str:
    """Map DB species value → species_filter bucket."""
    if species in PRIMARY_SPECIES:
        return species
    return "other"


def _filter_listings(listings: list[dict], species_filter: str) -> list[dict]:
    """Return listings matching a species_filter bucket."""
    if species_filter == "all":
        return listings
    if species_filter in PRIMARY_SPECIES:
        return [l for l in listings if l.get("species") == species_filter]
    # "other" = anything not in primary
    return [l for l in listings if l.get("species") not in PRIMARY_SPECIES]


def _prices(listings: list[dict]) -> list[float]:
    return [float(l["price_current"]) for l in listings if l.get("price_current")]


def _agg(prices: list[float]) -> dict:
    if not prices:
        return {"avg_price": None, "median_price": None, "min_price": None, "max_price": None}
    return {
        "avg_price":    round(statistics.mean(prices), 2),
        "median_price": round(statistics.median(prices), 2),
        "min_price":    min(prices),
        "max_price":    max(prices),
    }


def _histogram(prices: list[float]) -> list[dict]:
    return [
        {"bucket": label, "count": sum(1 for p in prices if lo <= p < hi)}
        for lo, hi, label in PRICE_BUCKETS
        if sum(1 for p in prices if lo <= p < hi) > 0
    ]


# ── Module 1: Market Overview ─────────────────────────────────

def _compute_market_overview(listings: list[dict]):
    now   = datetime.now(timezone.utc)
    ago24 = (now - timedelta(hours=24)).isoformat()
    ago7d = (now - timedelta(days=7)).isoformat()
    rows  = []

    for sf in ALL_FILTERS:
        subset = _filter_listings(listings, sf)
        prices = _prices(subset)

        active   = [l for l in subset if l.get("auction_status") == "active"]
        new_24h  = [l for l in subset if (l.get("scraped_at") or "") >= ago24]
        new_7d   = [l for l in subset if (l.get("scraped_at") or "") >= ago7d]

        row = {
            "species_filter":   sf,
            "computed_at":      now.isoformat(),
            "total_listings":   len(subset),
            "active_listings":  len(active),
            "new_listings_24h": len(new_24h),
            "new_listings_7d":  len(new_7d),
            "listing_count":    len(prices),
        }
        row.update(_agg(prices))
        rows.append(row)

    logger.info(f"  ✅ market_overview: {len(rows)} rows computed")


# ── Module 2: Price Trend Snapshots ──────────────────────────

def _compute_price_snapshots(listings: list[dict]):
    today = date.today().isoformat()
    rows  = []

    for sf in ALL_FILTERS:
        subset = _filter_listings(listings, sf)

        rows.append(_snapshot_row(today, sf, None, None, subset))

        for sex in SEXES:
            s_list = [l for l in subset if l.get("sex") == sex]
            if s_list:
                rows.append(_snapshot_row(today, sf, sex, None, s_list))

        for age in AGE_CLASSES:
            a_list = [l for l in subset if l.get("age_class") == age]
            if a_list:
                rows.append(_snapshot_row(today, sf, None, age, a_list))

    logger.info(f"  ✅ price_snapshots: {len(rows)} rows computed")


def _snapshot_row(snapshot_date, sf, sex, age_class, listings) -> dict:
    prices = _prices(listings)
    row = {
        "snapshot_date":  snapshot_date,
        "species_filter": sf,
        "sex":            sex,
        "age_class":      age_class,
        "listing_count":  len(prices),
    }
    row.update(_agg(prices))
    return row


# ── Modules 3 + 4 + 5: Tier / Sex / Age Stats ────────────────

def _compute_sex_age_stats(listings: list[dict]):
    rows = []

    for sf in ALL_FILTERS:
        subset = _filter_listings(listings, sf)

        rows.append(_sex_age_row(sf, None, None, subset))

        for sex in SEXES:
            s_list = [l for l in subset if l.get("sex") == sex]
            if not s_list:
                continue
            rows.append(_sex_age_row(sf, sex, None, s_list))
            for age in AGE_CLASSES:
                sa_list = [l for l in s_list if l.get("age_class") == age]
                if sa_list:
                    rows.append(_sex_age_row(sf, sex, age, sa_list))

        for age in AGE_CLASSES:
            a_list = [l for l in subset if l.get("age_class") == age]
            if a_list:
                rows.append(_sex_age_row(sf, None, age, a_list))

    logger.info(f"  ✅ tier_stats: {len(rows)} rows computed")


def _sex_age_row(sf, sex, age_class, listings) -> dict:
    prices = _prices(listings)
    row = {
        "computed_at":     datetime.now(timezone.utc).isoformat(),
        "species_filter":  sf,
        "sex":             sex,
        "age_class":       age_class,
        "listing_count":   len(prices),
        "price_histogram": _histogram(prices),
    }
    row.update(_agg(prices))
    return row


# ── Module 6: Geographic / Heat Map ──────────────────────────

def _compute_region_stats(listings: list[dict]):
    """Derive region from the free-text location field (state abbreviation or name)."""
    import re
    rows = []

    for sf in ALL_FILTERS:
        subset = _filter_listings(listings, sf)
        def _state(loc):
            if not loc:
                return None
            m = re.search(r'\b([A-Z]{2})\b', loc)
            return m.group(1) if m else None

        regions = {_state(l.get("location")) for l in subset} - {None}
        for region in regions:
            r_list = [l for l in subset if _state(l.get("location")) == region]
            prices = _prices(r_list)
            row = {
                "computed_at":    datetime.now(timezone.utc).isoformat(),
                "species_filter": sf,
                "region":         region,
                "listing_count":  len(r_list),
            }
            row.update(_agg(prices))
            rows.append(row)

    if not rows:
        return
    logger.info(f"  ✅ region_stats: {len(rows)} rows computed")


# ── Module 7: Species Comparison ─────────────────────────────

def _compute_species_comparison(listings: list[dict]):
    rows = []

    for sf in ALL_FILTERS:
        subset = _filter_listings(listings, sf)
        prices = _prices(subset)
        row = {
            "computed_at":    datetime.now(timezone.utc).isoformat(),
            "species_filter": sf,
            "listing_count":  len(subset),
        }
        row.update(_agg(prices))
        rows.append(row)

    logger.info(f"  ✅ species_comparison: {len(rows)} rows computed")
