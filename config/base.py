# ============================================================
# HoofMarketIQ — config/base.py
# Global settings shared across ALL scrapers/sites
# ============================================================
import os

from dotenv import load_dotenv
# Load local environment variables from .env when running locally.
load_dotenv()

# ── Supabase ──────────────────────────────────────────────────
SUPABASE_URL         = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# ── Run mode ──────────────────────────────────────────────────
# True  → scheduler every 30 min (testing/local)
# False → scheduler every 24 h  (production / CI)
# CI sets TESTING_MODE=false via workflow env
TESTING_MODE = os.getenv("TESTING_MODE", "true").lower() != "false"

# ── Scraper behavior ──────────────────────────────────────────
RATE_LIMIT_MIN        = 5    # seconds between requests (min)
RATE_LIMIT_MAX        = 10   # seconds between requests (max)
MAX_PAGES_PER_CATEGORY = 100 # safety cap

# ── Texas regions (county → region) ──────────────────────────
TEXAS_REGIONS = {
    "Hill Country": [
        "kerr", "gillespie", "kendall", "bandera", "real", "edwards",
        "kimble", "mason", "llano", "blanco", "comal", "hays",
    ],
    "South Texas": [
        "webb", "zapata", "starr", "hidalgo", "cameron", "willacy",
        "kenedy", "brooks", "jim hogg", "duval", "jim wells", "nueces",
        "kleberg", "mcmullen", "lasalle", "frio", "zavala", "maverick",
    ],
    "West Texas": [
        "presidio", "brewster", "terrell", "val verde", "kinney",
        "uvalde", "medina", "pecos", "reeves", "jeff davis",
    ],
    "Central Texas": [
        "travis", "williamson", "bastrop", "caldwell", "guadalupe",
        "bexar", "wilson", "atascosa", "fayette", "gonzales", "de witt",
    ],
    "East Texas": [
        "nacogdoches", "shelby", "panola", "rusk", "cherokee",
        "smith", "wood", "upshur", "gregg", "harrison",
    ],
    "North Texas": [
        "tarrant", "dallas", "collin", "denton", "wise", "parker",
        "johnson", "ellis", "kaufman", "rockwall",
    ],
    "Panhandle": [
        "potter", "randall", "moore", "hartley", "oldham", "deaf smith",
        "armstrong", "carson", "gray", "wheeler",
    ],
}