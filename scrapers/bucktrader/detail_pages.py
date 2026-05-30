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
    data = {}

    # Title
    h = soup.select_one("h1, h2.listing-title")
    data["title"] = h.get_text(strip=True) if h else None

    # Price
    price_el = soup.select_one(".listing-price, .price, [class*='price']")
    data["price_raw"]     = price_el.get_text(strip=True) if price_el else None
    data["price_current"] = _parse_price(data["price_raw"])

    # Description
    desc_el = soup.select_one(".listing-description, .entry-content, .listing-body, .description")
    data["description_raw"] = desc_el.get_text(" ", strip=True) if desc_el else None

    # Seller
    seller_el = soup.select_one(".seller-name, .contact-name, .listing-seller")
    data["seller_id"] = seller_el.get_text(strip=True) if seller_el else None

    # Photos
    imgs = soup.select(".listing-gallery img, .gallery img, .swiper-slide img, .listing-img img")
    data["photo_urls"] = [img["src"] for img in imgs if img.get("src")]

    # Location
    loc_el = soup.select_one(".listing-location, .location-detail, .single-location")
    data["location_raw"] = loc_el.get_text(strip=True) if loc_el else None

    # Auction date / listed date
    date_el = soup.select_one("time, .listing-date, .posted-date")
    if date_el:
        data["auction_date"] = date_el.get("datetime") or date_el.get_text(strip=True)
    else:
        data["auction_date"] = None

    # Status — BuckTrader listings are classifieds, not auctions
    data["auction_status"] = "active"
    data["bid_count"]      = 0
    data["easy_bid_price"] = None
    data["quantity"]       = 1

    return data


def _parse_price(text: str) -> float | None:
    if not text:
        return None
    nums = re.findall(r"[\d,]+(?:\.\d+)?", text.replace(",", ""))
    if nums:
        try:
            return float(nums[0])
        except ValueError:
            pass
    return None
