# ============================================================
# HoofMarketIQ — analytics/engine.py
# V1 Analytics — all 10 required modules
#
# Tables written:
#   market_overview    → Module 1: Dashboard KPIs
#   price_snapshots    → Module 2: Price trend line charts
#   tier_stats         → Module 3/4/5: Tier + Sex + Age analytics
#   region_stats       → Module 6: Geographic heat map
#   species_comparison → Module 7: Side-by-side species comparison
#
# Modules 8 (filters) and 9 (aggregation strategy) are handled
# by the query layer — data is pre-aggregated here for all
# filter combinations Bubble.io will need.
# ============================================================

import logging
import statistics
from datetime import date, datetime, timezone, timedelta

from db.supabase_client import get_client

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────
PRIMARY_SPECIES  = ["axis", "blackbuck", "aoudad"]
ALL_FILTERS      = PRIMARY_SPECIES + ["other", "all"]

TIERS     = ["management", "good", "trophy", "elite"]
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

def run_analytics():
    logger.info("📊 Running analytics...")
    client = get_client()

    listings = _fetch_all_listings(client)
    if not listings:
        logger.warning("  No listings with price found — skipping analytics")
        return

    logger.info(f"  Working with {len(listings)} priced listings")

    _compute_market_overview(client, listings)   # Module 1
    _compute_price_snapshots(client, listings)   # Module 2
    _compute_tier_stats(client, listings)        # Modules 3 + 4 + 5
    _compute_region_stats(client, listings)      # Module 6
    _compute_species_comparison(client, listings) # Module 7

    logger.info("✅ Analytics complete")


# ── Data fetch ────────────────────────────────────────────────

def _fetch_all_listings(client) -> list[dict]:
    """
    Fetch all listings that have a price.
    Includes active + closed — active prices show market demand,
    closed prices show final sale values.
    """
    try:
        r = (
            client.table("listings")
            .select(
                "species,tier,sex,age_class,location_region,"
                "price_current,auction_status,scraped_at,auction_date"
            )
            .not_.is_("price_current", "null")
            .execute()
        )
        logger.info(f"  Fetched {len(r.data)} priced listings")
        return r.data
    except Exception as e:
        logger.error(f"  Fetch failed: {e}")
        return []


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

def _compute_market_overview(client, listings: list[dict]):
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

    _upsert(client, "market_overview", rows, "species_filter")
    logger.info(f"  ✅ market_overview: {len(rows)} rows")


# ── Module 2: Price Trend Snapshots ──────────────────────────

def _compute_price_snapshots(client, listings: list[dict]):
    today = date.today().isoformat()
    rows  = []

    for sf in ALL_FILTERS:
        subset = _filter_listings(listings, sf)

        # Overall (no tier/sex/region filter)
        rows.append(_snapshot_row(today, sf, None, None, None, subset))

        # Per tier
        for tier in TIERS:
            t_list = [l for l in subset if l.get("tier") == tier]
            if t_list:
                rows.append(_snapshot_row(today, sf, tier, None, None, t_list))

        # Per sex
        for sex in SEXES:
            s_list = [l for l in subset if l.get("sex") == sex]
            if s_list:
                rows.append(_snapshot_row(today, sf, None, sex, None, s_list))

        # Per region
        regions = {l["location_region"] for l in subset if l.get("location_region")}
        for region in regions:
            r_list = [l for l in subset if l.get("location_region") == region]
            rows.append(_snapshot_row(today, sf, None, None, region, r_list))

    _upsert(
        client, "price_snapshots", rows,
        "snapshot_date,species_filter,tier,sex,location_region"
    )
    logger.info(f"  ✅ price_snapshots: {len(rows)} rows")


def _snapshot_row(snapshot_date, sf, tier, sex, region, listings) -> dict:
    prices = _prices(listings)
    row = {
        "snapshot_date":  snapshot_date,
        "species_filter": sf,
        "tier":           tier,
        "sex":            sex,
        "location_region": region,
        "listing_count":  len(prices),
    }
    row.update(_agg(prices))
    return row


# ── Modules 3 + 4 + 5: Tier / Sex / Age Stats ────────────────

def _compute_tier_stats(client, listings: list[dict]):
    rows = []

    for sf in ALL_FILTERS:
        subset = _filter_listings(listings, sf)

        # Overall
        rows.append(_tier_row(sf, None, None, None, subset))

        # Per tier (Module 3)
        for tier in TIERS:
            t_list = [l for l in subset if l.get("tier") == tier]
            if not t_list:
                continue
            rows.append(_tier_row(sf, tier, None, None, t_list))

            # Tier × sex (Module 4)
            for sex in SEXES:
                ts_list = [l for l in t_list if l.get("sex") == sex]
                if ts_list:
                    rows.append(_tier_row(sf, tier, sex, None, ts_list))

            # Tier × age (Module 5)
            for age in AGE_CLASSES:
                ta_list = [l for l in t_list if l.get("age_class") == age]
                if ta_list:
                    rows.append(_tier_row(sf, tier, None, age, ta_list))

        # Per sex only (Module 4 — sex overview)
        for sex in SEXES:
            s_list = [l for l in subset if l.get("sex") == sex]
            if s_list:
                rows.append(_tier_row(sf, None, sex, None, s_list))

        # Per age only (Module 5 — age overview)
        for age in AGE_CLASSES:
            a_list = [l for l in subset if l.get("age_class") == age]
            if a_list:
                rows.append(_tier_row(sf, None, None, age, a_list))

    # Full replace each run
    try:
        client.table("tier_stats").delete().neq("id", 0).execute()
        client.table("tier_stats").insert(rows).execute()
        logger.info(f"  ✅ tier_stats: {len(rows)} rows")
    except Exception as e:
        logger.error(f"  tier_stats failed: {e}")


def _tier_row(sf, tier, sex, age_class, listings) -> dict:
    prices = _prices(listings)
    row = {
        "computed_at":      datetime.now(timezone.utc).isoformat(),
        "species_filter":   sf,
        "tier":             tier,
        "sex":              sex,
        "age_class":        age_class,
        "listing_count":    len(prices),
        "price_histogram":  _histogram(prices),
    }
    row.update(_agg(prices))
    return row


# ── Module 6: Geographic / Heat Map ──────────────────────────

def _compute_region_stats(client, listings: list[dict]):
    rows = []

    for sf in ALL_FILTERS:
        subset  = _filter_listings(listings, sf)
        regions = {l["location_region"] for l in subset if l.get("location_region")}

        for region in regions:
            r_list = [l for l in subset if l.get("location_region") == region]
            prices = _prices(r_list)
            row = {
                "computed_at":   datetime.now(timezone.utc).isoformat(),
                "species_filter": sf,
                "region":        region,
                "listing_count": len(r_list),
            }
            row.update(_agg(prices))
            rows.append(row)

    if not rows:
        return
    _upsert(client, "region_stats", rows, "species_filter,region")
    logger.info(f"  ✅ region_stats: {len(rows)} rows")


# ── Module 7: Species Comparison ─────────────────────────────

def _compute_species_comparison(client, listings: list[dict]):
    rows = []

    for sf in ALL_FILTERS:
        subset = _filter_listings(listings, sf)
        prices = _prices(subset)

        # Tier distribution count
        tier_dist = {
            tier: sum(1 for l in subset if l.get("tier") == tier)
            for tier in TIERS
        }

        row = {
            "computed_at":      datetime.now(timezone.utc).isoformat(),
            "species_filter":   sf,
            "listing_count":    len(subset),
            "tier_distribution": tier_dist,
        }
        row.update(_agg(prices))
        rows.append(row)

    _upsert(client, "species_comparison", rows, "species_filter")
    logger.info(f"  ✅ species_comparison: {len(rows)} rows")


# ── Generic upsert helper ─────────────────────────────────────

def _upsert(client, table: str, rows: list[dict], on_conflict: str):
    if not rows:
        return
    try:
        client.table(table).upsert(rows, on_conflict=on_conflict).execute()
    except Exception as e:
        logger.error(f"  {table} upsert failed: {e}")
