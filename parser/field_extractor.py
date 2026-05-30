# ============================================================
# HoofMarketIQ — parser/field_extractor.py
# Extracts structured fields from raw listing text
# Applied to ALL listings; special species get deeper extraction
# ============================================================

import re
import logging
from config.species import SPECIAL_SPECIES_CONFIG, ALL_SPECIAL_KEYWORDS
from config.base import TEXAS_REGIONS

logger = logging.getLogger(__name__)


# ── Main entry point ──────────────────────────────────────────

def extract_fields(listing: dict) -> dict:
    """
    Takes a raw listing dict from detail_pages.py and extracts
    all structured fields. Returns enriched dict.

    For ALL listings:
      - species detection
      - sex
      - age class
      - bred status
      - color phase
      - location normalization

    For SPECIAL species only (axis / blackbuck / aoudad):
      - primary measurement
      - secondary measurements
    """
    text = _combined_text(listing)

    enriched = listing.copy()

    # ── Universal fields ──────────────────────────────────────
    enriched["species"]      = _detect_species(text, listing.get("title", ""))
    enriched["sex"]          = _detect_sex(text, listing.get("title", ""))
    enriched["age_class"]    = _detect_age_class(text)
    enriched["bred_status"]  = _detect_bred_status(text)
    enriched["color_phase"]  = _detect_color_phase(text)

    # ── Location normalization ────────────────────────────────
    loc_raw = enriched.get("location_raw") or ""
    enriched["location_city"]   = _extract_city(loc_raw)
    enriched["location_county"] = _normalize_county(loc_raw)
    enriched["location_region"] = _lookup_region(enriched["location_county"])
    enriched["location_state"]  = "TX"

    # ── Species filter (for UI 4-option filter) ──────────────
    sp = enriched["species"]
    enriched["species_filter"] = sp if sp in ("axis", "blackbuck", "aoudad") else "other"

    # ── Special species: measurements ─────────────────────────
    species = enriched["species"]
    if species in SPECIAL_SPECIES_CONFIG:
        measurements = _extract_measurements(text, species)
        enriched["primary_measurement_inches"] = measurements.get("primary")
        enriched["secondary_measurements"]     = measurements.get("secondary", {})
    else:
        enriched["primary_measurement_inches"] = None
        enriched["secondary_measurements"]     = {}

    # ── Extraction notes ──────────────────────────────────────
    notes = []
    if not enriched["species"]:
        notes.append("species not detected")
    if enriched["species"] in SPECIAL_SPECIES_CONFIG and enriched["primary_measurement_inches"] is None:
        notes.append("primary measurement missing")
    if not enriched["location_raw"]:
        notes.append("location missing")

    enriched["extraction_notes"]    = "; ".join(notes) if notes else None
    enriched["needs_manual_review"] = bool(notes)

    return enriched


# ── Text helpers ──────────────────────────────────────────────

def _combined_text(listing: dict) -> str:
    parts = [
        listing.get("title") or "",
        listing.get("description_raw") or "",
    ]
    return " ".join(parts).lower()


# ── Species detection ─────────────────────────────────────────

SPECIES_MAP = {
    "axis": "axis", "axis deer": "axis", "axis buck": "axis",
    "axis doe": "axis", "axis hind": "axis", "chital": "axis",
    "blackbuck": "blackbuck", "black buck": "blackbuck",
    "blackbuck antelope": "blackbuck",
    "aoudad": "aoudad", "barbary sheep": "aoudad",
    "oryx": "oryx", "gemsbok": "oryx", "scimitar oryx": "oryx",
    "nilgai": "nilgai", "blue bull": "nilgai",
    "fallow": "fallow deer", "fallow deer": "fallow deer", "fallow buck": "fallow deer",
    "sika": "sika deer", "sika deer": "sika deer",
    "elk": "elk", "red stag": "red stag", "red deer": "red stag",
    "eland": "eland", "kudu": "kudu", "greater kudu": "kudu",
    "waterbuck": "waterbuck", "impala": "impala",
    "blesbok": "blesbok", "springbok": "springbok", "addax": "addax",
    "roan": "roan antelope", "sable": "sable antelope",
    "dama": "dama gazelle", "dama gazelle": "dama gazelle", "gazelle": "gazelle",
    "zebra": "zebra", "wildebeest": "wildebeest", "gnu": "wildebeest",
    "bison": "bison", "buffalo": "buffalo",
    "racka": "racka sheep", "racka sheep": "racka sheep",
    "mouflon": "mouflon", "corsican": "corsican sheep", "corsican sheep": "corsican sheep",
    "four horned": "four horned sheep", "jacob": "jacob sheep",
    "camel": "camel", "llama": "llama", "alpaca": "alpaca",
    "ostrich": "ostrich", "emu": "emu",
    "wallaby": "wallaby", "kangaroo": "kangaroo",
    "fox": "fox", "bat-eared fox": "fox",
    "donkey": "donkey", "mini donkey": "donkey",
    "mini horse": "miniature horse", "miniature horse": "miniature horse",
    "paint": "horse", "horse": "horse",
    "cattle": "cattle", "cow": "cattle", "longhorn": "longhorn cattle",
}

def _detect_species(text: str, title: str) -> str | None:
    search_text = (title or "").lower() + " " + text
    for keyword in sorted(SPECIES_MAP.keys(), key=len, reverse=True):
        if keyword in search_text:
            return SPECIES_MAP[keyword]
    return None


# ── Sex detection ─────────────────────────────────────────────

def _detect_sex(text: str, title: str) -> str:
    combined = ((title or "") + " " + text).lower()

    mf_match = re.match(r"^\s*(\d+)\.(\d+)", (title or "").strip())
    if mf_match:
        males   = int(mf_match.group(1))
        females = int(mf_match.group(2))
        if males > 0 and females == 0:
            return "male"
        if females > 0 and males == 0:
            return "female"
        if males > 0 and females > 0:
            return "mixed"

    male_signals   = ["buck", " bull", " ram", " stag", " male", " boar", " tom", " jack", " he "]
    female_signals = ["doe", "hind", "cow", " ewe", "female", "hen", " she ", "jenny", "heifer"]

    male_score   = sum(1 for s in male_signals if s in combined)
    female_score = sum(1 for s in female_signals if s in combined)

    if male_score > female_score:
        return "male"
    if female_score > male_score:
        return "female"
    return "unknown"


# ── Age class detection ───────────────────────────────────────

AGE_PATTERNS = [
    (r"\b(4|5|6)\s*[-]?\s*(year|yr)s?\s*old\b",    "prime_4_6"),
    (r"\b(2|3)\s*[-]?\s*(year|yr)s?\s*old\b",      "mature_2_4"),
    (r"\b(6|7|8|9|\d{2})\s*[-]?\s*(year|yr)s?\b",  "mature_6plus"),
    (r"\b1\s*(year|yr)s?\s*old\b",                  "yearling"),
    (r"\bprime\b",                                   "prime_4_6"),
    (r"\bmature\b",                                  "mature_2_4"),
    (r"\byearling\b",                                "yearling"),
    (r"\bcalf\b|\bbottle\s*baby\b|\bbaby\b",        "calf"),
    (r"\b(\d+)\s*months?\s*old\b",                  "calf"),
]

def _detect_age_class(text: str) -> str:
    for pattern, age_class in AGE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return age_class
    return "unknown"


# ── Bred status detection ─────────────────────────────────────

BRED_PATTERNS = [
    (r"\b(embryo\s*transfer|ET)\b",            "et"),
    (r"\bartificial\s*insemination\b|\bAI\b",  "ai"),
    (r"\bproven\s*breeder\b",                  "proven_breeder"),
    (r"\branch[\s-]?bred\b",                   "ranch_bred"),
    (r"\bpen[\s-]?caught\b|\bwild[\s-]?caught\b|\bwild\b", "wild"),
    (r"\bwall[\s-]?trap\b|\btrap[\s-]?caught\b",           "wild"),
]

def _detect_bred_status(text: str) -> str:
    for pattern, status in BRED_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return status
    return "unknown"


# ── Color phase detection ─────────────────────────────────────

COLOR_PATTERNS = [
    (r"\bwhite\b",           "white"),
    (r"\bblack\b",           "black"),
    (r"\bspotted\b",         "spotted"),
    (r"\bpiebald\b",         "piebald"),
    (r"\bmelanistic\b",      "melanistic"),
    (r"\balbino\b",          "albino"),
    (r"\bnon[\s-]?typical\b","non-typical"),
    (r"\btypical\b",         "standard"),
]

def _detect_color_phase(text: str) -> str | None:
    for pattern, color in COLOR_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return color
    return None


# ── Measurement extraction ────────────────────────────────────

def _extract_measurements(text: str, species: str) -> dict:
    primary   = None
    secondary = {}

    if species == "axis":
        primary = _extract_axis_measurements(text, secondary)
    elif species == "blackbuck":
        primary = _extract_blackbuck_measurements(text, secondary)
    elif species == "aoudad":
        primary = _extract_aoudad_measurements(text, secondary)

    return {"primary": primary, "secondary": secondary}


def _extract_axis_measurements(text: str, secondary: dict) -> float | None:
    primary = None
    patterns = [
        (r"measured\s+(\d{2}(?:\.\d)?)\s*(?:\"|\binches?\b|\blive\b)", False),
        (r"(\d{2}(?:\.\d)?)\s*(?:\"|inches?|in\.?)\s*main\s*beam",    False),
        (r"main\s*beam\s*(?:length\s*)?[:\-]?\s*(\d{2}(?:\.\d)?)",    False),
        (r"(\d{2}(?:\.\d)?)\s*[-]\s*(\d{2}(?:\.\d)?)\s*(?:main\s*beam|mb\b)", True),
        (r"(\d{2}(?:\.\d)?)\s+live\s+loaded",                          False),
        (r"frame\s+(\d{2}(?:\.\d)?)",                                  False),
        (r"(\d{2}(?:\.\d)?)\s*[\"\']\s*(?:frame|beam|rack|antler|typical)", False),
    ]
    for pattern, is_range in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                primary = max(float(match.group(1)), float(match.group(2))) if is_range else float(match.group(1))
                break
            except (ValueError, IndexError):
                continue

    tine = re.search(r"(\d+)\s*(?:tines?|points?)\s*(?:per\s*side)?", text, re.IGNORECASE)
    if tine:
        secondary["tine_count"] = int(tine.group(1))

    spread = re.search(r"(\d{1,2}(?:\.\d)?)\s*(?:\"|inches?)?\s*spread", text, re.IGNORECASE)
    if spread:
        secondary["spread_inches"] = float(spread.group(1))

    return primary


def _extract_blackbuck_measurements(text: str, secondary: dict) -> float | None:
    primary = None
    patterns = [
        (r"(\d{1,2}(?:\.\d)?)\s*(?:\"|inches?|in\.?)\s*horn",             False),
        (r"horn\s*(?:length\s*)?[:\-]?\s*(\d{1,2}(?:\.\d)?)",             False),
        (r"(\d{1,2}(?:\.\d)?)\s*[-]\s*(\d{1,2}(?:\.\d)?)\s*inch\s*horn", True),
        (r"measured\s+(\d{1,2}(?:\.\d)?)\s*(?:\"|\binches?\b)",            False),
        (r"(\d{1,2}(?:\.\d)?)\s*[\"\']\s*(?:horn|horns)",                 False),
    ]
    for pattern, is_range in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                primary = max(float(match.group(1)), float(match.group(2))) if is_range else float(match.group(1))
                break
            except (ValueError, IndexError):
                continue

    spiral = re.search(r"(\d(?:\.\d)?)\s*(?:full\s*)?spiral", text, re.IGNORECASE)
    if spiral:
        secondary["spiral_count"] = float(spiral.group(1))

    return primary


def _extract_aoudad_measurements(text: str, secondary: dict) -> float | None:
    primary = None
    patterns = [
        (r"(\d{2}(?:\.\d)?)\s*(?:\"|inches?|in\.?)\s*(?:curl|horn|mass)",  False),
        (r"(?:curl|horn)\s*(?:length\s*)?[:\-]?\s*(\d{2}(?:\.\d)?)",       False),
        (r"(\d{2}(?:\.\d)?)\s*[-]\s*(\d{2}(?:\.\d)?)\s*(?:curl|horn)",    True),
        (r"measured\s+(\d{2}(?:\.\d)?)\s*(?:\"|\binches?\b)",              False),
        (r"(\d{2}(?:\.\d)?)\s*[\"\']\s*(?:curl|horn)",                     False),
    ]
    for pattern, is_range in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                primary = max(float(match.group(1)), float(match.group(2))) if is_range else float(match.group(1))
                break
            except (ValueError, IndexError):
                continue

    mass = re.search(r"(\d{1,2}(?:\.\d)?)\s*(?:\"|inches?)?\s*(?:base|mass|circumference)", text, re.IGNORECASE)
    if mass:
        secondary["base_circumference_inches"] = float(mass.group(1))

    return primary


# ── Location normalization ────────────────────────────────────

CITY_TO_COUNTY = {
    "kerrville": "kerr", "comfort": "kendall", "fredericksburg": "gillespie",
    "mountain home": "kerr", "boerne": "kendall", "bandera": "bandera",
    "uvalde": "uvalde", "leakey": "real", "rocksprings": "edwards",
    "sonora": "sutton", "junction": "kimble", "mason": "mason",
    "llano": "llano", "marble falls": "burnet", "blanco": "blanco",
    "johnson city": "blanco", "new braunfels": "comal", "seguin": "guadalupe",
    "san antonio": "bexar", "laredo": "webb", "cotulla": "lasalle",
    "del rio": "val verde", "brackettville": "kinney", "hondo": "medina",
    "castroville": "medina", "pleasanton": "atascosa", "jourdanton": "atascosa",
    "pearsall": "frio", "carrizo springs": "dimmit", "eagle pass": "maverick",
    "crystal city": "zavala", "austin": "travis", "kyle": "hays",
    "buda": "hays", "wimberley": "hays", "san marcos": "hays",
    "lockhart": "caldwell", "luling": "caldwell", "gonzales": "gonzales",
    "cuero": "de witt", "yoakum": "de witt", "shiner": "lavaca",
    "hallettsville": "lavaca",
}

def _extract_city(location_raw: str) -> str | None:
    if not location_raw:
        return None
    match = re.match(r"^([A-Za-z\s]+),\s*(?:TX|Texas)", location_raw.strip(), re.IGNORECASE)
    return match.group(1).strip().title() if match else None

def _normalize_county(location_raw: str) -> str | None:
    city = _extract_city(location_raw)
    if city:
        return CITY_TO_COUNTY.get(city.lower())
    return None

def _lookup_region(county: str | None) -> str | None:
    if not county:
        return None
    for region, counties in TEXAS_REGIONS.items():
        if county.lower() in counties:
            return region
    return None