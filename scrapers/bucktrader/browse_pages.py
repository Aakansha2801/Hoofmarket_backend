# scrapers/bucktrader/browse_pages.py
import re
import logging
import httpx
from bs4 import BeautifulSoup

from config.sites.bucktrader import BASE_URL, ACTIVE_CATEGORIES, PAGINATION
from scrapers.browser import fetch_page

logger = logging.getLogger(__name__)


async def collect_listing_urls(client: httpx.AsyncClient) -> list[dict]:
    all_listings = []
    seen = set()

    for category in ACTIVE_CATEGORIES:
        logger.info(f"📂 [bucktrader] Category: {category['name']}")
        listings = await _scrape_category(client, category)
        # Deduplicate across categories
        for l in listings:
            if l["url"] not in seen:
                seen.add(l["url"])
                all_listings.append(l)
        logger.info(f"   ✅ {len(listings)} listings in '{category['name']}'")

    logger.info(f"✅ [bucktrader] Total unique URLs: {len(all_listings)}")
    return all_listings


async def _scrape_category(client: httpx.AsyncClient, category: dict) -> list[dict]:
    listings = []
    max_pages = PAGINATION.get("max_pages", 20)
    param     = PAGINATION["param_name"]
    base      = BASE_URL.rstrip("/") + category["url"]

    for page in range(1, max_pages + 1):
        # Always use ?page_number=N — works for page 1 too
        url = f"{base}?{param}={page}"

        html = await fetch_page(url, client)
        if not html:
            logger.error(f"  ❌ [bucktrader] Fetch failed page {page}: {url}")
            break

        soup  = BeautifulSoup(html, "lxml")
        cards = _parse_cards(soup)

        if not cards:
            logger.info(f"  No listings at page {page} — stopping")
            break

        listings.extend(cards)
        logger.info(f"  Page {page}: {len(cards)} listings")

        if not _has_next_page(soup, page):
            logger.info(f"  Last page at {page}")
            break

    return listings


def _parse_cards(soup: BeautifulSoup) -> list[dict]:
    results = []
    seen    = set()

    # BuckTrader card structure: .directorist-listing-card contains
    # an image <a> and a title <h4.directorist-listing-title><a>
    for card in soup.select(".directorist-listing-card, .directorist-listing-single"):
        title_tag = card.select_one(".directorist-listing-title a, h4 a, h3 a, h2 a")
        if not title_tag:
            continue

        href  = title_tag.get("href", "")
        url   = href if href.startswith("http") else BASE_URL.rstrip("/") + href
        if not url or url in seen:
            continue
        seen.add(url)

        title  = title_tag.get_text(strip=True)
        slug   = url.rstrip("/").split("/")[-1]
        loc_el = card.select_one(".directorist-listing-address, .single-location a, .location")
        img_el = card.select_one("img")

        results.append({
            "url":          url,
            "listing_id":   slug,
            "title":        title,
            "location_raw": loc_el.get_text(strip=True) if loc_el else None,
            "image_url":    img_el.get("src") if img_el else None,
            "source_site":  "bucktrader",
        })

    return results


def _has_next_page(soup: BeautifulSoup, current_page: int) -> bool:
    # BuckTrader uses <a class="next page-numbers">
    if soup.select_one("a.next.page-numbers, a.next[href*='page_number']"):
        return True
    # Fallback: any pagination link with higher page number
    for a in soup.find_all("a", href=lambda h: h and "page_number=" in (h or "")):
        m = re.search(r"page_number=(\d+)", a.get("href", ""))
        if m and int(m.group(1)) > current_page:
            return True
    return False
