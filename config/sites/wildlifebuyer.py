# ============================================================
# HoofMarketIQ — config/sites/wildlifebuyer.py
# All WildlifeBuyer.com-specific settings
# ============================================================

SITE_ID   = "wildlifebuyer"
BASE_URL  = "https://wildlifebuyer.com"
ENABLED   = True
IMAGE_CDN = "wildlifebuyerimages.blob.core.windows.net"

BROWSE_CATEGORIES = [
    {"name": "Exotics & Deer",  "url": "/Browse/C160535/Exotics-Deer",  "scrape": True},
    {"name": "Livestock",       "url": "/Browse/C160829/Livestock",      "scrape": True},
    {"name": "Classifieds",     "url": "/Browse/C160536/Classifieds",    "scrape": True},
    {"name": "Taxidermy",       "url": "/Browse/C160832/Taxidermy-Related-Products", "scrape": False},
    {"name": "Equipment",       "url": "/Browse/C160825/Equipment",      "scrape": False},
    {"name": "Advertising",     "url": "/Browse/C160814/Advertising",    "scrape": False},
    {"name": "Hunting Accessories", "url": "/Browse/C160826/Hunting-Accessories", "scrape": False},
]

ACTIVE_CATEGORIES = [c for c in BROWSE_CATEGORIES if c["scrape"]]

# Slugs used in bid-button links — excluded from listing card parsing
CATEGORY_SLUGS = {"Exotics-Deer", "Livestock", "Classifieds"}

SELECTORS = {
    "listing_card": ".listing-card",
    "title":        ".listing-title",
    "price":        ".listing-price",
    "location":     ".listing-location",
    "link":         "a.listing-link",
    "next_page":    "a.next-page",
}

PAGINATION = {
    "style":      "query_param",
    "param_name": "page",
    "start":      1,
}