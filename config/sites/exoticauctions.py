# ============================================================
# HoofMarketIQ — config/sites/exoticauctions.py
# PLACEHOLDER — fill in when site is ready to scrape
# ============================================================

SITE_ID  = "exoticauctions"
BASE_URL = "https://exoticauctions.com"   # update to real URL
ENABLED  = False                          # ← flip to True when ready

BROWSE_CATEGORIES = [
    # {"name": "Exotics", "url": "/listings/", "scrape": True},
]

ACTIVE_CATEGORIES = [c for c in BROWSE_CATEGORIES if c["scrape"]]

SELECTORS = {}   # fill in after inspecting site HTML

PAGINATION = {
    "style":      "query_param",
    "param_name": "page",
    "start":      1,
    "max_pages":  50,
}