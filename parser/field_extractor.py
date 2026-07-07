# ============================================================
# HoofMarketIQ — parser/field_extractor.py
# Extracts structured fields from raw listing text
# Applied to ALL listings; special species get deeper extraction
# ============================================================

import re
import logging

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


    return None