# ============================================================
# HoofMarketIQ — config/species.py
# Species definitions, tiers, scoring — site-agnostic
# Add new species here; scrapers will reference this
# ============================================================

SPECIAL_SPECIES_CONFIG = {
    "axis": {
        "keywords": ["axis", "axis deer", "axis buck", "axis doe", "axis hind"],
        "primary_measurement": "main_beam_inches",
        "tiers": {
            "management": (0,    27),
            "good":       (27,   30),
            "trophy":     (30,   34),
            "elite":      (34, 9999),
        },
    },
    "blackbuck": {
        "keywords": ["blackbuck", "black buck", "blackbuck antelope"],
        "primary_measurement": "horn_length_inches",
        "tiers": {
            "management": (0,    18),
            "good":       (18,   20),
            "trophy":     (20,   23),
            "elite":      (23, 9999),
        },
    },
    "aoudad": {
        "keywords": ["aoudad", "barbary sheep", "aoudad sheep"],
        "primary_measurement": "horn_curl_inches",
        "tiers": {
            "management": (0,    30),
            "good":       (30,   35),
            "trophy":     (35,   40),
            "elite":      (40, 9999),
        },
    },
    "fallow": {
        "keywords": ["fallow", "fallow deer", "fallow buck", "fallow doe"],
        "primary_measurement": "main_beam_inches",
        "tiers": {
            "management": (0,    20),
            "good":       (20,   25),
            "trophy":     (25,   30),
            "elite":      (30, 9999),
        },
    },
    "nilgai": {
        "keywords": ["nilgai", "nilgai antelope", "blue bull"],
        "primary_measurement": "horn_length_inches",
        "tiers": {
            "management": (0,    10),
            "good":       (10,   14),
            "trophy":     (14,   18),
            "elite":      (18, 9999),
        },
    },
}

# Flat keyword list for fast species detection in listing titles
ALL_SPECIAL_KEYWORDS = [
    kw
    for cfg in SPECIAL_SPECIES_CONFIG.values()
    for kw in cfg["keywords"]
]