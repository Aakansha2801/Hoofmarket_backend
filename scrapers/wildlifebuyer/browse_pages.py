# scrapers/wildlifebuyer/browse_pages.py
import re
import logging
import httpx
from bs4 import BeautifulSoup

from config import MAX_PAGES_PER_CATEGORY
from config.sites.wildlifebuyer import BASE_URL, ACTIVE_CATEGORIES, CATEGORY_SLUGS
from scrapers.browser import fetch_page

logger = logging.getLogger(__name__)


async def collect_listing_urls(client: httpx.AsyncClient) -> list[dict]:
    all_listings = []
    for category in ACTIVE_CATEGORIES:
        logger.info(f"📂 [wildlifebuyer] Scraping: {category['name']}")
        listings = await _scrape_category(client, category)
        logger.info(f"   ✅ {len(listings)} listings in '{category['name']}'")
        all_listings.extend(listings)
    logger.info(f"✅ [wildlifebuyer] Total URLs: {len(all_listings)}")
    return all_listings


async def _scrape_category(client: httpx.AsyncClient, category: dict) -> list[dict]:
    listings, page_num = [], 1
    base = BASE_URL + category["url"]

    while page_num <= MAX_PAGES_PER_CATEGORY:
        url = base if page_num == 1 else f"{base}?page={page_num}"
        html = await fetch_page(url, client)
        if not html:
            logger.error(f"  ❌ Fetch failed page {page_num} of '{category['name']}'")
            break

        soup  = BeautifulSoup(html, "lxml")
        cards = _parse_listing_cards(soup, category["name"])

        if not cards:
            logger.info(f"  No listings at page {page_num} — stopping")
            break

        listings.extend(cards)
        logger.info(f"  Page {page_num}: {len(cards)} listings")

        if not _has_next_page(soup):
            logger.info(f"  Last page at {page_num}")
            break
        page_num += 1

    return listings


def _parse_listing_cards(soup: BeautifulSoup, category_name: str) -> list[dict]:
    listings, seen = [], set()
    slug_pattern = "|".join(re.escape(s) for s in CATEGORY_SLUGS)
    cards = soup.find_all("a", href=re.compile(rf"^/Listing/Details/\d+/(?!{slug_pattern})"))

    for card in cards:
        href     = card.get("href", "")
        full_url = BASE_URL + href
        if full_url in seen:
            continue
        seen.add(full_url)

        listing_id = _extract_listing_id(href)
        if not listing_id:
            continue

        listings.append({
            "listing_id":     listing_id,
            "url":            full_url,
            "title":          _extract_card_title(card),
            "price_current":  _extract_card_price(card),
            "auction_status": _extract_card_status(card),
            "source_site":    "wildlifebuyer",
        })
    return listings


def _extract_listing_id(href: str) -> str | None:
    m = re.search(r"/Listing/Details/(\d+)", href)
    return m.group(1) if m else None


def _extract_card_title(card) -> str | None:
    text = card.get_text(separator=" ", strip=True)
    if text and len(text) > 3 and not text.lower().startswith("img"):
        return text[:200]
    parent = card.find_parent(class_=re.compile(r"listing|item|card|detail", re.I))
    return parent.get_text(separator=" ", strip=True)[:200] if parent else None


def _extract_card_price(card) -> float | None:
    text = (card.find_parent() or card).get_text()
    m = re.search(r"\$\s?[\d,]+(?:\.\d{2})?", text)
    if m:
        try:
            return float(m.group().replace("$", "").replace(",", "").strip())
        except ValueError:
            pass
    return None


def _extract_card_status(card) -> str:
    text = (card.find_parent() or card).get_text().lower()
    if "paused"  in text: return "paused"
    if "closed"  in text or "sold" in text or "ended" in text: return "closed"
    if "active"  in text or "live" in text: return "active"
    return "unknown"


def _has_next_page(soup: BeautifulSoup) -> bool:
    if soup.find("a", string=re.compile(r"next|»|›", re.I)):
        return True
    pager = soup.find(class_=re.compile(r"pager|pagination", re.I))
    return bool(pager and pager.find("a", string=re.compile(r"next|»|›", re.I)))
