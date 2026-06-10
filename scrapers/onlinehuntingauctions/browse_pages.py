# # # scrapers/onlinehuntingauctions/browse_pages.py
# import re
# import logging
# import httpx
# from bs4 import BeautifulSoup

# from config import MAX_PAGES_PER_CATEGORY
# from config.sites.onlinehuntingauctions import (
#     BASE_URL,
#     ACTIVE_CATEGORIES,
#     PAGINATION,
#     LOT_PAGINATION,
#     SKIP_AUCTION_KEYWORDS,
#     TARGET_AUCTION_URL,
# )
# from scrapers.browser import fetch_page

# logger = logging.getLogger(__name__)


# async def collect_listing_urls(client: httpx.AsyncClient) -> list[dict]:
#     """
#     Entry point — mirrors wildlifebuyer pattern.
#     Paginates auction list → enters each auction → collects lot cards.
#     """

#     if TARGET_AUCTION_URL:
#         logger.info("📍 [onlinehuntingauctions] Scraping target auction page only")
#         return await _scrape_single_auction(client, TARGET_AUCTION_URL)

#     all_listings = []

#     for category in ACTIVE_CATEGORIES:
#         logger.info(f"📂 [onlinehuntingauctions] Scraping: {category['name']}")
#         listings = await _scrape_category(client, category)
#         logger.info(f"   ✅ {len(listings)} lots in '{category['name']}'")
#         all_listings.extend(listings)

#     logger.info(f"✅ [onlinehuntingauctions] Total URLs: {len(all_listings)}")
#     return all_listings


# async def _scrape_single_auction(client: httpx.AsyncClient, auction_path: str) -> list[dict]:
#     full_url = auction_path if auction_path.startswith("http") else BASE_URL + auction_path
#     auction = {
#         "auction_title": full_url.split("/")[-1].replace("-", " "),
#         "auction_url": full_url,
#         "auction_type": "online auction",
#         "session_id": None,
#         "category_name": "target auction",
#     }
#     return await _scrape_auction_lots(client, auction)


# # ── Level 1: Paginate auction list ────────────────────────────

# async def _scrape_category(client: httpx.AsyncClient, category: dict) -> list[dict]:
#     all_lots = []
#     base_url = BASE_URL + category["url"]
#     max_pages = PAGINATION.get("max_pages", 20)

#     for page_num in range(1, max_pages + 1):
#         # OHA path-segment pagination: _p2, _p3...
#         url  = base_url if page_num == 1 else f"{base_url}_p{page_num}"
#         html = await fetch_page(url, client)

#         if not html:
#             logger.error(f"  ❌ Fetch failed page {page_num} of '{category['name']}'")
#             break

#         soup     = BeautifulSoup(html, "lxml")
#         auctions = _parse_auction_cards(soup, category["name"])

#         if not auctions:
#             logger.info(f"  No listings at page {page_num} — stopping")
#             break

#         logger.info(f"  Page {page_num}: {len(auctions)} auctions")

#         for auction in auctions:
#             lots = await _scrape_auction_lots(client, auction)
#             all_lots.extend(lots)

#         if not _has_next_page(soup):
#             logger.info(f"  Last page at {page_num}")
#             break

#     return all_lots


# # ── Level 2: Paginate lots inside one auction ─────────────────

# async def _scrape_auction_lots(client: httpx.AsyncClient, auction: dict) -> list[dict]:
#     lots      = []
#     base_url  = auction["auction_url"]
#     max_pages = LOT_PAGINATION.get("max_pages", 30)

#     for page_num in range(1, max_pages + 1):
#         url  = base_url if page_num == 1 else f"{base_url}_p{page_num}"
#         html = await fetch_page(url, client)

#         if not html:
#             break

#         soup      = BeautifulSoup(html, "lxml")
#         page_lots = _parse_lot_cards(soup, auction, page_num)

#         if not page_lots:
#             break

#         lots.extend(page_lots)

#         if not _has_next_page(soup):
#             break

#     return lots


# # ── Parsers ───────────────────────────────────────────────────

# def _parse_auction_cards(soup: BeautifulSoup, category_name: str) -> list[dict]:
#     auctions = []
#     seen     = set()

#     for a in soup.find_all("a", href=re.compile(r"_as\d+$")):
#         href  = a.get("href", "")
#         title = a.get_text(strip=True)

#         if not href or not title or href in seen or len(title) < 4:
#             continue
#         seen.add(href)

#         if any(kw in title.lower() for kw in SKIP_AUCTION_KEYWORDS):
#             logger.debug(f"  Skipping: {title}")
#             continue

#         full_url   = href if href.startswith("http") else BASE_URL + href
#         session_id = re.search(r"_as(\d+)", href)

#         container  = a.find_parent(["td", "div", "li", "p"]) or a
#         parent_txt = container.get_text(" ", strip=True)
#         type_match = re.search(
#             r"(live auction|online only|online auction|timed bidding|"
#             r"absentee|silent auction|raffle)",
#             parent_txt, re.I
#         )

#         auctions.append({
#             "auction_title": title,
#             "auction_url":   full_url,
#             "auction_type":  type_match.group(0) if type_match else "",
#             "session_id":    session_id.group(1) if session_id else None,
#             "category_name": category_name,
#         })

#     return auctions


# def _parse_lot_cards(soup: BeautifulSoup, auction: dict, page_num: int) -> list[dict]:
#     lots = []
#     seen = set()

#     # Primary: lot links with _al or _i in href (OHA uses _i<id> for item pages)
#     lot_links = soup.find_all("a", href=re.compile(r"_(?:al|i)\d+"))

#     # Fallback: internal links in table rows that aren't auction-nav
#     if not lot_links:
#         for row in soup.find_all("tr"):
#             a = row.find("a", href=True)
#             if not a:
#                 continue
#             href = a.get("href", "")
#             if re.search(r"_as\d+$", href):
#                 continue
#             if href.startswith("/") or href.startswith(BASE_URL):
#                 lot_links.append(a)

#     for a in lot_links:
#         href  = a.get("href", "")
#         title = a.get_text(strip=True)

#         if not href or not title or href in seen or len(title) < 4:
#             continue
#         if re.search(r"_as\d+$", href):
#             continue
#         seen.add(href)

#         full_url   = href if href.startswith("http") else BASE_URL + href
#         row        = a.find_parent("tr") or a.find_parent("div") or a
#         row_txt    = row.get_text(" ", strip=True)
#         bid_match  = re.search(r"\$[\d,]+(?:\.\d+)?", row_txt)
#         lot_match  = re.search(r"lot\s*#?\s*(\d+)", row_txt, re.I)
#         lot_id     = re.search(r"_(?:al|i)(\d+)", href)

#         img     = row.find("img")
#         img_src = ""
#         if img:
#             img_src = img.get("src", "")
#             if img_src and not img_src.startswith("http"):
#                 img_src = BASE_URL + img_src

#         lots.append({
#             # Auction context
#             "auction_title":  auction["auction_title"],
#             "auction_url":    auction["auction_url"],
#             "auction_type":   auction.get("auction_type", ""),
#             "session_id":     auction.get("session_id"),
#             "category_name":  auction.get("category_name"),
#             # Lot fields
#             "listing_id":     f"oha_{lot_id.group(1)}" if lot_id else None,
#             "title":          title,
#             "url":            full_url,
#             "lot_number":     lot_match.group(1) if lot_match else None,
#             "price_current":  _parse_price(bid_match.group(0) if bid_match else ""),
#             "auction_status": _parse_status(row_txt),
#             "image_url":      img_src or None,
#             "source_site":    "onlinehuntingauctions",
#         })

#     return lots


# # ── Helpers ───────────────────────────────────────────────────

# def _parse_price(text: str) -> float | None:
#     """Requires a leading '$' so bare integers (lot numbers, counts) never match."""
#     if not text:
#         return None
#     m = re.search(r"\$([\d,]+(?:\.\d{1,2})?)", text)
#     if not m:
#         return None
#     try:
#         return float(m.group(1).replace(",", ""))
#     except ValueError:
#         return None


# def _parse_status(text: str) -> str:
#     t = text.lower()
#     if "closed" in t or "ended" in t or "complete" in t:
#         return "closed"
#     if "paused" in t:
#         return "paused"
#     if "active" in t or "bid" in t:
#         return "active"
#     return "unknown"


# def _has_next_page(soup: BeautifulSoup) -> bool:
#     if soup.find("a", string=re.compile(r"next|»|›", re.I)):
#         return True
#     pager = soup.find(class_=re.compile(r"pager|pagination", re.I))
#     return bool(pager and pager.find("a", string=re.compile(r"next|»|›", re.I)))

# scrapers/onlinehuntingauctions/browse_pages.py
import re
import logging
import httpx
from bs4 import BeautifulSoup

from config import MAX_PAGES_PER_CATEGORY
from config.sites.onlinehuntingauctions import (
    BASE_URL,
    ACTIVE_CATEGORIES,
    PAGINATION,
    LOT_PAGINATION,
    SKIP_AUCTION_KEYWORDS,
    TARGET_AUCTION_URL,
)
from scrapers.browser import fetch_page

logger = logging.getLogger(__name__)


async def collect_listing_urls(client: httpx.AsyncClient) -> list[dict]:
    """
    Entry point — mirrors wildlifebuyer pattern.
    Paginates auction list → enters each auction → collects lot cards.
    """

    if TARGET_AUCTION_URL:
        logger.info("📍 [onlinehuntingauctions] Scraping target auction page only")
        return await _scrape_single_auction(client, TARGET_AUCTION_URL)

    all_listings = []

    for category in ACTIVE_CATEGORIES:
        logger.info(f"📂 [onlinehuntingauctions] Scraping: {category['name']}")
        listings = await _scrape_category(client, category)
        logger.info(f"   ✅ {len(listings)} lots in '{category['name']}'")
        all_listings.extend(listings)

    logger.info(f"✅ [onlinehuntingauctions] Total URLs: {len(all_listings)}")
    return all_listings


async def _scrape_single_auction(client: httpx.AsyncClient, auction_path: str) -> list[dict]:
    full_url = auction_path if auction_path.startswith("http") else BASE_URL + auction_path
    auction = {
        "auction_title": full_url.split("/")[-1].replace("-", " "),
        "auction_url": full_url,
        "auction_type": "online auction",
        "session_id": None,
        "category_name": "target auction",
    }
    return await _scrape_auction_lots(client, auction)


# ── Level 1: Paginate auction list ────────────────────────────

async def _scrape_category(client: httpx.AsyncClient, category: dict) -> list[dict]:
    all_lots = []
    base_url = BASE_URL + category["url"]
    max_pages = PAGINATION.get("max_pages", 20)

    for page_num in range(1, max_pages + 1):
        # OHA path-segment pagination: _p2, _p3...
        url  = base_url if page_num == 1 else f"{base_url}_p{page_num}"
        html = await fetch_page(url, client)

        if not html:
            logger.error(f"  ❌ Fetch failed page {page_num} of '{category['name']}'")
            break

        soup     = BeautifulSoup(html, "lxml")
        auctions = _parse_auction_cards(soup, category["name"])

        if not auctions:
            logger.info(f"  No listings at page {page_num} — stopping")
            break

        logger.info(f"  Page {page_num}: {len(auctions)} auctions")

        for auction in auctions:
            lots = await _scrape_auction_lots(client, auction)
            all_lots.extend(lots)

        if not _has_next_page(soup):
            logger.info(f"  Last page at {page_num}")
            break

    return all_lots


# ── Level 2: Paginate lots inside one auction ─────────────────

async def _scrape_auction_lots(client: httpx.AsyncClient, auction: dict) -> list[dict]:
    lots      = []
    base_url  = auction["auction_url"]
    max_pages = LOT_PAGINATION.get("max_pages", 30)

    for page_num in range(1, max_pages + 1):
        url  = base_url if page_num == 1 else f"{base_url}_p{page_num}"
        html = await fetch_page(url, client)

        if not html:
            break

        soup      = BeautifulSoup(html, "lxml")
        page_lots = _parse_lot_cards(soup, auction, page_num)

        if not page_lots:
            break

        lots.extend(page_lots)

        if not _has_next_page(soup):
            break

    return lots


# ── Parsers ───────────────────────────────────────────────────

def _parse_auction_cards(soup: BeautifulSoup, category_name: str) -> list[dict]:
    auctions = []
    seen     = set()

    for a in soup.find_all("a", href=re.compile(r"_as\d+$")):
        href  = a.get("href", "")
        title = a.get_text(strip=True)

        if not href or not title or href in seen or len(title) < 4:
            continue
        seen.add(href)

        if any(kw in title.lower() for kw in SKIP_AUCTION_KEYWORDS):
            logger.debug(f"  Skipping: {title}")
            continue

        full_url   = href if href.startswith("http") else BASE_URL + href
        session_id = re.search(r"_as(\d+)", href)

        container  = a.find_parent(["td", "div", "li", "p"]) or a
        parent_txt = container.get_text(" ", strip=True)
        type_match = re.search(
            r"(live auction|online only|online auction|timed bidding|"
            r"absentee|silent auction|raffle)",
            parent_txt, re.I
        )

        auctions.append({
            "auction_title": title,
            "auction_url":   full_url,
            "auction_type":  type_match.group(0) if type_match else "",
            "session_id":    session_id.group(1) if session_id else None,
            "category_name": category_name,
        })

    return auctions


def _parse_lot_cards(soup: BeautifulSoup, auction: dict, page_num: int) -> list[dict]:
    lots = []
    seen = set()

    # Primary: lot links with _al or _i in href (OHA uses _i<id> for item pages)
    lot_links = soup.find_all("a", href=re.compile(r"_(?:al|i)\d+"))

    # Fallback: internal links in table rows that aren't auction-nav
    if not lot_links:
        for row in soup.find_all("tr"):
            a = row.find("a", href=True)
            if not a:
                continue
            href = a.get("href", "")
            if re.search(r"_as\d+$", href):
                continue
            if href.startswith("/") or href.startswith(BASE_URL):
                lot_links.append(a)

    for a in lot_links:
        href  = a.get("href", "")
        title = a.get_text(strip=True)

        if not href or not title or href in seen or len(title) < 4:
            continue
        if re.search(r"_as\d+$", href):
            continue
        seen.add(href)

        full_url   = href if href.startswith("http") else BASE_URL + href
        row        = a.find_parent("tr") or a.find_parent("div") or a
        row_txt    = row.get_text(" ", strip=True)
        bid_match  = re.search(r"\$[\d,]+(?:\.\d+)?", row_txt)
        lot_match  = re.search(r"lot\s*#?\s*(\d+)", row_txt, re.I)
        lot_id     = re.search(r"_(?:al|i)(\d+)", href)

        img     = row.find("img")
        img_src = ""
        if img:
            img_src = img.get("src", "")
            if img_src and not img_src.startswith("http"):
                img_src = BASE_URL + img_src

        lots.append({
            # Auction context
            "auction_title":  auction["auction_title"],
            "auction_url":    auction["auction_url"],
            "auction_type":   auction.get("auction_type", ""),
            "session_id":     auction.get("session_id"),
            "category_name":  auction.get("category_name"),
            # Lot fields
            "listing_id":     f"oha_{lot_id.group(1)}" if lot_id else None,
            "title":          title,
            "url":            full_url,
            "lot_number":     lot_match.group(1) if lot_match else None,
            "price_current":  _parse_price(bid_match.group(0) if bid_match else ""),
            "auction_status": _parse_status(row_txt),
            "image_url":      img_src or None,
            "source_site":    "onlinehuntingauctions",
        })

    return lots


# ── Helpers ───────────────────────────────────────────────────

def _parse_price(text: str) -> float | None:
    """Accepts '$20,000.00' or '20,000.00 USD'. Rejects bare integers."""
    if not text:
        return None

    m = re.search(r"\$([\d,]+(?:\.\d{1,2})?)", text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass

    m = re.search(r"([\d,]+(?:\.\d{1,2})?)\s*USD\b", text, re.I)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass

    return None


def _parse_status(text: str) -> str:
    t = text.lower()
    if "closed" in t or "ended" in t or "complete" in t:
        return "closed"
    if "paused" in t:
        return "paused"
    if "active" in t or "bid" in t:
        return "active"
    return "unknown"


def _has_next_page(soup: BeautifulSoup) -> bool:
    if soup.find("a", string=re.compile(r"next|»|›", re.I)):
        return True
    pager = soup.find(class_=re.compile(r"pager|pagination", re.I))
    return bool(pager and pager.find("a", string=re.compile(r"next|»|›", re.I)))