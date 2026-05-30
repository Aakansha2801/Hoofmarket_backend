# ============================================================
# HoofMarketIQ — config/sites/bucktrader.py
# All BuckTrader.com-specific settings
# ============================================================

SITE_ID  = "bucktrader"
BASE_URL = "https://bucktrader.com"
ENABLED  = True

# Main paginated categories — each page has ~12 unique listings
BROWSE_CATEGORIES = [
    {"name": "Exotics",   "url": "/exotics/",   "scrape": True},
    {"name": "Whitetail", "url": "/whitetail/",  "scrape": True},
]

ACTIVE_CATEGORIES = [c for c in BROWSE_CATEGORIES if c["scrape"]]

# Pagination: ?page_number=N, max 13 pages (confirmed from site)
PAGINATION = {
    "style":      "query_param",
    "param_name": "page_number",
    "start":      1,
    "max_pages":  20,   # set above known max as safety buffer
}