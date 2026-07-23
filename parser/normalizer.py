# ============================================================
# HoofMarketIQ — parser/normalizer.py
# Maps raw scraped dicts (any site) → unified DB schema
# This is the single source of truth for the DB column names
# ============================================================

import re
import logging
from datetime import datetime, timezone
from config.species import SPECIAL_SPECIES_CONFIG, ALL_SPECIAL_KEYWORDS

logger = logging.getLogger(__name__)


# ── Unified DB schema (what goes into Bubble.io) ───────────────
# Every scraper output must map to these keys.
SCHEMA_KEYS = [
    "source_site",       # "bucktrader" | "wildlifebuyer"
    "source_category",   # e.g. "Exotics"
    "listing_id",        # site-specific unique ID (or URL hash)
    "listing_url",
    "title",
    "species",           # normalized species name
    "species_group",     # "deer" | "bovid" | "sheep_goat" | "other"
    "sex",               # "male" | "female" | "mixed" | None
    "quantity",          # int or None
    "age_years",         # float or None
    "price_raw",         # original price string
    "price_usd",         # parsed float or None
    "price_type",        # "each" | "group" | "obo" | "call"
    "location_raw",
    "location_region",   # Texas region or None
    "location_state",
    "status",            # "available" | "sold" | "pending"
    "description",
    "seller_name",
    "seller_phone",
    "seller_email",
    "image_url",
    "gallery_images",    # list[str]
    "measurement_raw",   # any horn/antler measurement string found
    "measurement_inches",# parsed float or None
    "tier",              # "management" | "good" | "trophy" | "elite" | None
    "listed_date",
    "scraped_at",        # UTC timestamp
]


def normalize(raw: dict, site_id: str, category: str) -> dict:
    """
    Convert any site's raw dict into the unified schema.
    Unknowns default to None — never raise, always return a record.
    """
    out = {k: None for k in SCHEMA_KEYS}

    out["source_site"]     = site_id
    out["source_category"] = category
    out["scraped_at"]      = datetime.now(timezone.utc).isoformat()

    # ── Basic fields ──────────────────────────────────────────
    out["listing_url"]     = raw.get("url")
    out["listing_id"]      = _make_id(raw.get("url"), site_id)
    out["title"]           = raw.get("title")
    out["description"]     = raw.get("description")
    out["seller_name"]     = raw.get("seller_name")
    out["seller_phone"]    = raw.get("seller_phone")
    out["seller_email"]    = raw.get("seller_email")
    out["image_url"]       = raw.get("image_url")
    out["gallery_images"]  = raw.get("gallery_images") or []
    out["listed_date"]     = raw.get("listed_date")
    out["location_raw"]    = raw.get("location") or raw.get("location_detail")

    # ── Price parsing ─────────────────────────────────────────
    out["price_raw"]  = raw.get("price_raw")
    price_usd, price_type = _parse_price(raw.get("price_raw", ""))
    out["price_usd"]  = price_usd
    out["price_type"] = price_type

    # ── Species detection ─────────────────────────────────────
    title_lower = (out["title"] or "").lower()
    desc_lower  = (out["description"] or "").lower()
    text        = f"{title_lower} {desc_lower}"

    out["species"]       = _detect_species(text)
    out["species_group"] = _detect_group(out["species"])

    # ── Sex / quantity ────────────────────────────────────────
    out["sex"]      = _detect_sex(text)
    out["quantity"] = _detect_quantity(title_lower)

    # ── Status ───────────────────────────────────────────────
    statuses = raw.get("statuses") or []
    out["status"] = _parse_status(statuses, text)

    # ── Measurements + tier ───────────────────────────────────
    meas_raw, meas_in = _extract_measurement(text)
    out["measurement_raw"]    = meas_raw
    out["measurement_inches"] = meas_in
    out["tier"]               = _calculate_tier(out["species"], meas_in)

    # ── Location region ───────────────────────────────────────
    from config.base import TEXAS_REGIONS
    out["location_region"] = _detect_region(out["location_raw"], TEXAS_REGIONS)
    out["location_state"]  = _detect_state(out["location_raw"])

    return out


# ── Helpers ───────────────────────────────────────────────────

def _make_id(url: str | None, site_id: str) -> str | None:
    if not url:
        return None
    # Use last path segment as ID, fallback to hash
    slug = url.rstrip("/").split("/")[-1]
    return f"{site_id}::{slug}"


def _parse_price(price_str: str) -> tuple[float | None, str | None]:
    if not price_str:
        return None, None
    s = price_str.lower().strip()
    if "call" in s or "contact" in s or "inquire" in s:
        return None, "call"
    price_type = "each"
    if "obo" in s or "best offer" in s:
        price_type = "obo"
    elif "group" in s or "lot" in s or "pair" in s:
        price_type = "group"
    nums = re.findall(r"[\d,]+(?:\.\d+)?", s.replace(",", ""))
    if nums:
        try:
            return float(nums[0].replace(",", "")), price_type
        except ValueError:
            pass
    return None, price_type


def _detect_species(text: str) -> str | None:
    for species, cfg in SPECIAL_SPECIES_CONFIG.items():
        for kw in cfg["keywords"]:
            if kw in text:
                return species
    # Fallback: broad genus matches
    BROAD = {
        "oryx": ["oryx", "scimitar", "gemsbok"],
        "kudu": ["kudu"],
        "elk":  ["elk", "wapiti"],
        "bison":["bison", "buffalo"],
        "zebra":["zebra"],
    }
    for species, kws in BROAD.items():
        if any(k in text for k in kws):
            return species
    return None


def _detect_group(species: str | None) -> str | None:
    DEER    = {"axis", "fallow", "elk", "sika", "red stag", "hog deer", "muntjac",
               "pere david", "barasingha", "whitetail"}
    BOVID   = {"nilgai", "oryx", "kudu", "eland", "bongo", "gemsbok", "roan",
               "sable", "waterbuck", "wildebeest", "bison", "zebra", "impala",
               "springbok", "blackbuck", "addax"}
    SHEEP   = {"aoudad", "mouflon", "corsican", "black hawaiian", "red sheep"}

    if not species:
        return None
    if species in DEER:
        return "deer"
    if species in BOVID:
        return "bovid"
    if species in SHEEP:
        return "sheep_goat"
    return "other"


def _detect_sex(text: str) -> str | None:
    if any(w in text for w in ["buck", "bull", "ram", "stag", "male"]):
        if any(w in text for w in ["doe", "cow", "ewe", "hind", "female"]):
            return "mixed"
        return "male"
    if any(w in text for w in ["doe", "cow", "ewe", "hind", "female"]):
        return "female"
    if any(w in text for w in ["pair", "group", "herd", "mixed"]):
        return "mixed"
    return None


def _detect_quantity(title: str) -> int | None:
    m = re.search(r"^(\d+)\s+", title)
    if m:
        return int(m.group(1))
    words = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    }
    for word, num in words.items():
        if word in title:
            return num
    return None


def _parse_status(statuses: list, text: str) -> str:
    combined = " ".join(statuses).lower() + " " + text
    if "sold" in combined:
        return "sold"
    if "pending" in combined:
        return "pending"
    return "available"


def _extract_measurement(text: str) -> tuple[str | None, float | None]:
    patterns = [
        r'(\d+(?:\.\d+)?)["\u2033]?\s*(?:main\s+beam|horn|rack|antler|curl|score)',
        r'(\d+(?:\.\d+)?)\s*(?:inch|in\.?|")',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return m.group(0), float(m.group(1))
    return None, None


def _calculate_tier(species: str | None, inches: float | None) -> str | None:
    if not species or inches is None:
        return None
    cfg = SPECIAL_SPECIES_CONFIG.get(species)
    if not cfg:
        return None
    for tier_name, (lo, hi) in cfg["tiers"].items():
        if lo <= inches < hi:
            return tier_name
    return None


def _detect_region(location: str | None, regions: dict) -> str | None:
    if not location:
        return None
    loc_lower = location.lower()
    for region, counties in regions.items():
        if any(county in loc_lower for county in counties):
            return region
    # Direct region name match
    for region in regions:
        if region.lower() in loc_lower:
            return region
    return None


def _detect_state(location: str | None) -> str | None:
    if not location:
        return None
    # Common state abbrevs
    m = re.search(
        r'\b(TX|Texas|OK|Oklahoma|NM|New Mexico|CO|Colorado|KS|Kansas)\b',
        location, re.I
    )
    return m.group(0).upper() if m else None