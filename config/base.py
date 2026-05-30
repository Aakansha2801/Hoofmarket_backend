# ============================================================
# HoofMarketIQ — config/base.py
# Global settings shared across ALL scrapers/sites
# ============================================================

# ── Supabase ──────────────────────────────────────────────────
SUPABASE_URL         = "https://imzqatfkwyeqinvnshem.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImltenFhdGZrd3llcWludm5zaGVtIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTk0NTgwOSwiZXhwIjoyMDk1NTIxODA5fQ.9Qc71dyX1sNQisGPSGyG00U4u99R2cOwlGoqg1EvsU0"

# ── Run mode ──────────────────────────────────────────────────
# True  → runs every 30 min (testing)
# False → runs every 24 hrs  (production)
TESTING_MODE = True

# ── Scraper behavior ──────────────────────────────────────────
RATE_LIMIT_MIN        = 5    # seconds between requests (min)
RATE_LIMIT_MAX        = 10   # seconds between requests (max)
MAX_PAGES_PER_CATEGORY = 100 # safety cap
HEADLESS              = True  # False = watch browser during debug

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