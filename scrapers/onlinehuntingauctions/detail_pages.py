# scrapers/onlinehuntingauctions/detail_pages.py
import re
import logging
import httpx
from bs4 import BeautifulSoup
from datetime import datetime

from config.sites.onlinehuntingauctions import BASE_URL
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
    result["source_site"] = "onlinehuntingauctions"
    result["scraped_at"]  = datetime.utcnow().isoformat()
    logger.info(f"  ✅ Parsed: {result.get('title', url)[:60]}")
    return result


def _parse_detail(soup: BeautifulSoup, url: str) -> dict:
    data = {}

    # ── Title ─────────────────────────────────────────────────
    h1 = soup.find("h1") or soup.find("h2", class_=re.compile(r"title|lot", re.I))
    data["title"] = h1.get_text(strip=True) if h1 else None

    # ── Description ───────────────────────────────────────────
    desc_el = (
        soup.find("div", class_=re.compile(r"desc|detail|lot.?info|body", re.I))
        or soup.find("div", id=re.compile(r"desc|detail|lot", re.I))
    )
    if desc_el:
        # Remove any inline base64 images to keep text clean
        for img in desc_el.find_all("img"):
            if img.get("src", "").startswith("data:"):
                img.decompose()
        data["description_raw"] = desc_el.get_text(separator=" ", strip=True)
    else:
        data["description_raw"] = None

    # ── Current bid / price ───────────────────────────────────
    # OHA hides the winning bid behind a login wall ("Sign In To View
    # Winning Bid × 2 units").  Only record a price when there is an
    # explicit dollar amount on the page — never parse bare integers.
    bid_el = soup.find(class_=re.compile(r"current.?bid|high.?bid|price|amount", re.I))
    bid_text = bid_el.get_text(strip=True) if bid_el else ""
    # Reject if it looks like "Sign In" / login-wall copy
    if re.search(r"sign.?in|login|view.?winning", bid_text, re.I):
        bid_text = ""
    data["price_current"] = _parse_price(bid_text)

    # Starting / opening bid
    start_text = soup.find(string=re.compile(r"start|opening|minimum", re.I))
    if start_text:
        parent = start_text.find_parent()
        m = re.search(r"\$[\d,]+", parent.get_text() if parent else "")
        data["starting_bid"] = _parse_price(m.group(0) if m else "")
    else:
        data["starting_bid"] = None

    # ── Auction status ────────────────────────────────────────
    data["auction_status"] = _parse_status(soup)

    # ── Bid count ─────────────────────────────────────────────
    data["bid_count"] = _parse_bid_count(soup)

    # ── Close / auction date ──────────────────────────────────
    data["auction_date"] = _parse_auction_date(soup)

    # ── Organization / auctioneer ─────────────────────────────
    org_el = soup.find(class_=re.compile(r"auctioneer|seller|org|organization", re.I))
    data["seller_id"] = org_el.get_text(strip=True) if org_el else _parse_seller_text(soup)

    # ── Location ──────────────────────────────────────────────
    data["location_raw"] = _parse_location(soup, data.get("description_raw", "") or "")

    # ── Photos ────────────────────────────────────────────────
    data["photo_urls"] = _parse_photos(soup)

    # ── Quantity ──────────────────────────────────────────────
    # OHA shows "× 2 units" next to the bid header — prefer that over
    # the title prefix which often encodes a decimal (e.g. "0.2 Gemsbok").
    data["quantity"] = _parse_quantity(data.get("title", "") or "", soup)

    return data


# ── Field parsers ─────────────────────────────────────────────

def _parse_price(text: str) -> float | None:
    """Extract a dollar amount from text.  Requires a leading '$' so bare
    numbers like '2 units' or lot counts never match accidentally."""
    if not text:
        return None
    # Must start with '$'; commas inside the number are allowed
    m = re.search(r"\$([\d,]+(?:\.\d{1,2})?)", text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _parse_status(soup: BeautifulSoup) -> str:
    text = soup.get_text().lower()
    if "bidding has concluded" in text or "auction has ended" in text or "complete" in text:
        return "closed"
    if "paused" in text:
        return "paused"
    if "place bid" in text or "bid here" in text or "timed bidding" in text:
        return "active"
    return "unknown"


def _parse_bid_count(soup: BeautifulSoup) -> int:
    m = re.search(r"(\d+)\s*[Bb]id", soup.get_text())
    try:
        return int(m.group(1)) if m else 0
    except ValueError:
        return 0


def _parse_auction_date(soup: BeautifulSoup) -> str | None:
    # OHA shows dates like "2026 Jun 05 @ 19:00"
    text = soup.get_text()
    for pattern, fmt in [
        (r"\b(\d{4}\s+\w{3}\s+\d{1,2})\s*@",         "%Y %b %d"),
        (r"\b(\d{1,2}/\d{1,2}/\d{4})\b",              "%m/%d/%Y"),
        (r"\b(\w+\s+\d{1,2},?\s*\d{4})\b",            "%B %d, %Y"),
    ]:
        m = re.search(pattern, text)
        if m:
            try:
                return datetime.strptime(m.group(1).strip(), fmt).date().isoformat()
            except ValueError:
                continue
    return None


def _parse_seller_text(soup: BeautifulSoup) -> str | None:
    m = re.search(r"(?:Seller|Auctioneer)[:\s]+([A-Za-z0-9\s\-&]+)", soup.get_text())
    return m.group(1).strip()[:100] if m else None


def _parse_location(soup: BeautifulSoup, description: str) -> str | None:
    # OHA shows "City, State, Country" on auction/lot pages
    loc_el = soup.find(class_=re.compile(r"location|city|venue|aloc", re.I))
    if loc_el:
        return loc_el.get_text(strip=True)

    # Fallback: scan description for Texas location patterns
    for pattern in [
        r"([A-Za-z\s]+,\s*Texas)",
        r"([A-Za-z\s]+,\s*TX)\b",
        r"(?:located in|pickup in|from)\s+([A-Za-z\s]+,\s*\w{2})",
    ]:
        m = re.search(pattern, description, re.I)
        if m:
            return m.group(1).strip()

    # Fallback: grab city/state from page text
    m = re.search(
        r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*,\s*(?:Texas|TX|[A-Z]{2}),\s*United States)",
        soup.get_text()
    )
    return m.group(1) if m else None


def _parse_photos(soup: BeautifulSoup) -> list[str]:
    photos = []
    for img in soup.find_all("img"):
        src = img.get("src", "")
        # OHA images hosted on CloudFront CDN
        if "cloudfront" in src or "lotimg" in src or "dygtyjqp7pi0m" in src:
            full = src if src.startswith("http") else BASE_URL + src
            # Skip thumbnails
            if "_thumb" not in full and "_s." not in full:
                photos.append(full)
    return photos


def _parse_quantity(title: str, soup: BeautifulSoup | None = None) -> int:
    # 1. Prefer the explicit "× N units" / "x N units" shown next to the bid header
    if soup is not None:
        m = re.search(r"[×x]\s*(\d+)\s*unit", soup.get_text(), re.I)
        if m:
            n = int(m.group(1))
            if n > 0:
                return n

    # 2. Title prefix — only match a leading *integer* (not decimals like "0.2")
    #    "3 Axis Bucks" → 3,  "0.2 Gemsbok" → skip → return 1
    if title:
        m = re.match(r"^(\d+)\s+[A-Za-z]", title.strip())
        if m:
            n = int(m.group(1))
            if n > 0:
                return n

    return 1