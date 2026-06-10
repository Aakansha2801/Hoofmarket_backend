# ============================================================
# HoofMarketIQ — config/sites/onlinehuntingauctions.py
# All OnlineHuntingAuctions.com-specific settings
# ============================================================

SITE_ID  = "onlinehuntingauctions"
BASE_URL = "https://www.onlinehuntingauctions.com"
ENABLED  = True

TARGET_AUCTION_URL = "/Super-Exotic-Extravaganza-Year-End-Exotic-Online-Wildlife-Auction_as104129"

# 2-level structure:
#   Level 1 → Auction list pages  (/Hunting-Auctions_aca900000_p2)
#   Level 2 → Lot pages inside each auction (/Auction-Name_as115409_p2)

BROWSE_CATEGORIES = [
    {"name": "Hunting",            "url": "/Hunting-Auctions_aca900000",    "scrape": True},
    # Non-wildlife — skip
    {"name": "Firearms & Military","url": "/Firearms-Gun-Auctions_aca880000","scrape": False},
    {"name": "Raffles",            "url": "/Raffles-Auctions_aca1000637",    "scrape": False},
]

ACTIVE_CATEGORIES = [c for c in BROWSE_CATEGORIES if c["scrape"]]

# Auction name keywords to skip — firearms/gear-only auctions
SKIP_AUCTION_KEYWORDS = [
    "firearm", "gun", "ammo", "ammunition", "mil-surp",
    "archery close", "fishing tackle", "reloading", "gear.com",
]

# Slugs used in auction-nav links — excluded from lot card parsing
# (OHA equivalent of wildlifebuyer CATEGORY_SLUGS)
AUCTION_NAV_PATTERNS = [r"_as\d+$", r"auctionlist", r"register", r"login", r"signup"]

SELECTORS = {
    # Auction list page
    "auction_link":  "a[href*='_as']",
    "auction_title": "a[href*='_as']",
    "next_page":     "a",               # matched via text: Next / »

    # Lot list page inside auction
    "lot_link":      "a[href*='_al']",
    "lot_title":     "a[href*='_al']",
    "lot_bid":       "",                # parsed via regex from row text
    "lot_image":     "img",
}

# Auction-list pagination: /Name_acaXXX on page 1, /Name_acaXXX_p2 on page 2+
PAGINATION = {
    "style":      "path_segment",   # appends _p2, _p3 to base URL
    "start":      1,
    "max_pages":  20,
}

# Lot pagination inside each auction — same path-segment style
LOT_PAGINATION = {
    "style":     "path_segment",
    "start":     1,
    "max_pages": 30,
}