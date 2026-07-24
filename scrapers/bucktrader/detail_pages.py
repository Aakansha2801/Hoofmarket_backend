# scrapers/bucktrader/detail_pages.py
import re
import logging
import httpx
from bs4 import BeautifulSoup
from datetime import datetime

from config.sites.bucktrader import BASE_URL
from scrapers.browser import fetch_page

logger = logging.getLogger(__name__)


async def scrape_listing(card: dict, client: httpx.AsyncClient) -> dict | None:
    url  = card["url"]
    html = await fetch_page(url, client)
    if not html:
        logger.error(f"  ❌ [bucktrader] Fetch failed: {url}")
        return None

    soup = BeautifulSoup(html, "lxml")
    try:
        detail = _parse_detail(soup)
    except Exception as e:
        logger.error(f"  ❌ [bucktrader] Parse error {url}: {e}")
        return None

    result = {**card, **detail}
    result["source_url"]  = url
    result["source_site"] = "bucktrader"
    result["scraped_at"]  = datetime.utcnow().isoformat()
    logger.info(f"  ✅ [bucktrader] Parsed: {result.get('title', url)[:60]}")
    return result


def _parse_detail(soup: BeautifulSoup) -> dict:
    """
    Confirmed BuckTrader detail page structure (from live page inspection):
      Title:       h1 (page-level, not inside wrapper)
      Description: .tagline  (the listing body text)
      Location:    .directorist-listing-location
      Phone:       .directorist-single-info-phone .directorist-single-info__value
      Images:      .image-slider img  (src attribute, full URL)
      Status:      .tagline text — "SOLD!" indicates sold
      Price:       Not present — BuckTrader is a classifieds board (contact seller)
    """
    data = {}

    # ── Title ─────────────────────────────────────────────────
    h1 = soup.select_one("h1.directorist-listing-title, h1.entry-title, h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # ── Description (tagline = listing body) ──────────────────
    tagline = soup.select_one(".tagline")
    if tagline:
        raw = tagline.get_text(" ", strip=True)
        # "SOLD!" as sole content means listing is sold — keep it as description too
        data["description_raw"] = raw
    else:
        data["description_raw"] = None

    # ── Auction status ────────────────────────────────────────
    tagline_text = (data["description_raw"] or "").lower()
    if "sold" in tagline_text:
        data["auction_status"] = "sold"
    else:
        data["auction_status"] = "active"

    # ── Price — not on BuckTrader (classifieds board) ─────────
    # price_current stays None; seller is contacted by phone
    data["price_current"]  = None
    data["easy_bid_price"] = None
    data["bid_count"]      = 0
    data["price_start"]    = None

    # ── Location ──────────────────────────────────────────────
    loc = soup.select_one(".directorist-listing-location")
    data["location"] = loc.get_text(strip=True) if loc else None

    # ── Seller contact (phone as seller_id) ───────────────────
    phone = soup.select_one(
        ".directorist-single-info-phone .directorist-single-info__value"
    )
    data["seller_id"] = phone.get_text(strip=True) if phone else None

    # ── Images (.image-slider img) ────────────────────────────
    imgs = soup.select(".image-slider img")
    photos = []
    for img in imgs:
        src = (
            img.get("src")
            or img.get("data-src")
            or img.get("data-lazy-src")
            or ""
        )
        if src and not src.endswith(("placeholder", "blank.gif")):
            photos.append(src if src.startswith("http") else BASE_URL + src)
    data["photo_urls"] = photos

    # ── Auction date — not present, use None ──────────────────
    data["auction_date"] = None

    # ── Quantity from title ───────────────────────────────────
    title = data["title"] or ""
    m = re.match(r"^(\d+)\s+[A-Za-z]", title.strip())
    data["quantity"] = int(m.group(1)) if m and int(m.group(1)) > 0 else 1

    return data
