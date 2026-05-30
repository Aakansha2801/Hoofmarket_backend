# scrapers/wildlifebuyer/detail_pages.py
import re
import logging
import httpx
from bs4 import BeautifulSoup
from datetime import datetime

from config.sites.wildlifebuyer import BASE_URL, IMAGE_CDN
from scrapers.browser import fetch_page

logger = logging.getLogger(__name__)


async def scrape_listing(card: dict, client: httpx.AsyncClient) -> dict | None:
    url  = card["url"]
    html = await fetch_page(url, client)
    if not html:
        logger.error(f"  ❌ Fetch failed: {url}")
        return None

    soup = BeautifulSoup(html, "lxml")
    try:
        detail = _parse_detail(soup, url)
    except Exception as e:
        logger.error(f"  ❌ Parse error {url}: {e}")
        return None

    result = {**card, **detail}
    result["source_url"]  = url
    result["source_site"] = "wildlifebuyer"
    result["scraped_at"]  = datetime.utcnow().isoformat()
    logger.info(f"  ✅ Parsed: {result.get('title', url)[:60]}")
    return result


def _parse_detail(soup: BeautifulSoup, url: str) -> dict:
    data = {}

    title_tag = soup.find("h3", class_="detail__title")
    data["title"] = title_tag.get_text(strip=True) if title_tag else None

    desc_tag = (
        soup.find("div", id="collapsedescriptionlgmd")
        or soup.find("div", class_=re.compile(r"description", re.I))
    )
    if desc_tag:
        for img in desc_tag.find_all("img"):
            if img.get("src", "").startswith("data:"):
                img.decompose()
        data["description_raw"] = desc_tag.get_text(separator=" ", strip=True)
    else:
        data["description_raw"] = None

    price_tag = soup.find("span", class_=re.compile(r"awe-rt-CurrentPrice|detail__price--current", re.I))
    data["price_current"] = _parse_price(price_tag.get_text(strip=True) if price_tag else "")

    easy_bid = soup.find("a", id="PlaceQuickBid")
    if easy_bid:
        span = easy_bid.find("span", class_="NumberPart")
        data["easy_bid_price"] = _parse_price(span.get_text(strip=True) if span else "")
    else:
        data["easy_bid_price"] = None

    data["auction_status"]     = _parse_status(soup)
    data["bid_count"]          = _parse_bid_count(soup)
    data["photo_urls"]         = _parse_photos(soup)
    data["location_raw"]       = _parse_location(soup, data.get("description_raw", ""))
    data["seller_id"]          = _parse_seller(soup)
    data["auction_date"]       = _parse_auction_date(soup)
    data["quantity"]           = _parse_quantity(data.get("title", ""))
    return data


def _parse_price(text: str) -> float | None:
    if not text:
        return None
    m = re.search(r"[\d,]+(?:\.\d{2})?", text.replace(",", ""))
    try:
        return float(m.group().replace(",", "")) if m else None
    except ValueError:
        return None


def _parse_status(soup: BeautifulSoup) -> str:
    text = soup.get_text().lower()
    if "bidding has ended" in text or "auction has ended" in text:
        return "closed"
    if "paused" in text:
        return "paused"
    if soup.find("input", id="BidAmount"):
        return "active"
    return "unknown"


def _parse_bid_count(soup: BeautifulSoup) -> int:
    m = re.search(r"(\d+)\s*Bid\(s\)", soup.get_text(), re.IGNORECASE)
    try:
        return int(m.group(1)) if m else 0
    except ValueError:
        return 0


def _parse_photos(soup: BeautifulSoup) -> list[str]:
    imgs = soup.find_all("img", src=re.compile(re.escape(IMAGE_CDN)))
    full = [img["src"] for img in imgs if "_thumbfit" not in img["src"]]
    if full:
        return full
    return [img["src"].replace("_thumbfit", "") for img in imgs]


def _parse_location(soup: BeautifulSoup, description: str) -> str | None:
    meta = soup.find("meta", attrs={"name": "keywords"})
    state_hint = None
    if meta:
        parts = [p.strip() for p in meta.get("content", "").split(",")]
        extras = [p for p in parts if p not in ("Exotics & Deer", "Livestock", "Classifieds")]
        state_hint = extras[0] if extras else None

    for pattern in [
        r"(?:located|pickup|pick up|delivery from|located in|in)\s+([A-Za-z\s]+,\s*TX)",
        r"([A-Za-z\s]+,\s*Texas)",
        r"([A-Za-z\s]+,\s*TX)\b",
    ]:
        m = re.search(pattern, description or "", re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return state_hint


def _parse_seller(soup: BeautifulSoup) -> str | None:
    m = re.search(r"Seller[:\s]+([a-zA-Z0-9*_\-]+)", soup.get_text())
    return m.group(1).strip() if m else None


def _parse_auction_date(soup: BeautifulSoup) -> str | None:
    text = soup.get_text()
    for pattern, fmt in [
        (r"\b(\d{1,2}/\d{1,2}/\d{4})\b", "%m/%d/%Y"),
        (r"\b(\w+ \d{1,2},\s*\d{4})\b",   "%B %d, %Y"),
    ]:
        m = re.search(pattern, text)
        if m:
            try:
                return datetime.strptime(m.group(1).strip(), fmt).date().isoformat()
            except ValueError:
                continue
    return None


def _parse_quantity(title: str) -> int:
    if title:
        m = re.match(r"^(\d+)\.(\d+)", title.strip())
        if m:
            total = int(m.group(1)) + int(m.group(2))
            return total if total > 0 else 1
    return 1
