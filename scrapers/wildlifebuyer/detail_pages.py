# scrapers/wildlifebuyer/detail_pages.py
import re
import logging
import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config.sites.wildlifebuyer import BASE_URL, IMAGE_CDN
from scrapers.browser import fetch_page

logger = logging.getLogger(__name__)

_DATE_FMT   = "%m/%d/%Y %H:%M:%S"
_WLB_TZ     = ZoneInfo("America/Chicago")   # Texas = US Central (CDT/CST auto-handled)


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

    # ── Title ─────────────────────────────────────────────────
    title_tag = soup.find("h3", class_="detail__title")
    data["title"] = title_tag.get_text(strip=True) if title_tag else None

    # ── Description ───────────────────────────────────────────
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

    # ── Current price (awe-rt-CurrentPrice) ───────────────────
    price_tag = soup.find("span", class_=re.compile(r"awe-rt-CurrentPrice|detail__price--current", re.I))
    data["price_current"] = _parse_price(price_tag.get_text(strip=True) if price_tag else "")

    # ── Winning bid (closed-details panel) ───────────────────
    closed_panel = soup.select_one(".closed-details")
    if closed_panel:
        winning_li = closed_panel.select_one("li:first-child")
        if winning_li:
            num = winning_li.select_one("span.NumberPart")
            winning = _parse_price(num.get_text(strip=True) if num else "")
            if winning:
                data["price_final"]   = winning
                data["price_current"] = winning
    else:
        data["price_final"] = None

    # ── Easy bid / minimum next bid ───────────────────────────
    # Confirmed: <span class="awe-rt-MinimumBid Bidding_Listing_MinPrice">$4,220.00</span>
    min_bid = soup.find("span", class_=re.compile(r"Bidding_Listing_MinPrice|awe-rt-MinimumBid", re.I))
    if min_bid:
        data["easy_bid_price"] = _parse_price(min_bid.get_text(strip=True))
    else:
        # Fallback: PlaceQuickBid button
        easy_bid = soup.find("a", id="PlaceQuickBid")
        if easy_bid:
            span = easy_bid.find("span", class_="NumberPart")
            data["easy_bid_price"] = _parse_price(span.get_text(strip=True) if span else "")
        else:
            data["easy_bid_price"] = None

    # ── Auction start date ────────────────────────────────────
    # Confirmed: <span class="awe-rt-startingDTTM" data-initial-dttm="06/26/2026 09:50:00">
    start_el = soup.find(class_=re.compile(r"awe-rt-startingDTTM", re.I))
    data["auction_start_date"] = _parse_dttm(
        start_el.get("data-initial-dttm", "") if start_el else ""
    )

    # ── Auction end date ──────────────────────────────────────
    # Confirmed: <span class="awe-rt-endingDTTM" data-initial-dttm="06/29/2026 13:00:00">
    end_el = soup.find(class_=re.compile(r"awe-rt-endingDTTM", re.I))
    data["auction_end_date"] = _parse_dttm(
        end_el.get("data-initial-dttm", "") if end_el else ""
    )
    # auction_date = end date (for backwards compatibility)
    data["auction_date"] = (
        data["auction_end_date"].split("T")[0]
        if data["auction_end_date"] else _parse_auction_date_text(soup)
    )

    # ── Reserve status ────────────────────────────────────────
    # Confirmed: <span class="reserve-not-met awe-rt-ReserveStatus">Reserve Price Not Met</span>
    reserve_el = soup.find(class_=re.compile(r"awe-rt-ReserveStatus", re.I))
    data["reserve_status"] = reserve_el.get_text(strip=True) if reserve_el else None

    # ── Watchers count ────────────────────────────────────────
    # Confirmed: <span class="awe-rt-AcceptedListingActionCount">24</span>
    watchers_el = soup.find(class_=re.compile(r"awe-rt-AcceptedListingActionCount", re.I))
    try:
        data["watchers_count"] = int(watchers_el.get_text(strip=True)) if watchers_el else 0
    except ValueError:
        data["watchers_count"] = 0

    # ── Auction status ────────────────────────────────────────
    data["auction_status"] = _parse_status(soup)

    # ── Bid count ─────────────────────────────────────────────
    data["bid_count"] = _parse_bid_count(soup)

    # ── Photos ────────────────────────────────────────────────
    data["photo_urls"] = _parse_photos(soup)

    # ── Location ──────────────────────────────────────────────
    data["location"] = _parse_location(soup, data.get("description_raw", ""))

    # ── Seller ────────────────────────────────────────────────
    data["seller_id"] = _parse_seller(soup)

    # ── Quantity ──────────────────────────────────────────────
    data["quantity"] = _parse_quantity(data.get("title", ""))

    return data


# ── Field parsers ─────────────────────────────────────────────

def _parse_price(text: str) -> float | None:
    if not text:
        return None
    m = re.search(r"[\d,]+(?:\.\d{2})?", text.replace(",", ""))
    try:
        return float(m.group().replace(",", "")) if m else None
    except ValueError:
        return None


def _parse_dttm(dttm_str: str) -> str | None:
    """
    Parse WildlifeBuyer datetime string → UTC ISO 8601.
    Site uses Texas time = America/Chicago (CDT UTC-5 in summer, CST UTC-6 in winter).
    ZoneInfo handles the DST boundary precisely.
    """
    if not dttm_str:
        return None
    try:
        naive  = datetime.strptime(dttm_str.strip(), _DATE_FMT)
        local  = naive.replace(tzinfo=_WLB_TZ)          # attach Texas tz
        utc_dt = local.astimezone(timezone.utc)          # convert to UTC
        return utc_dt.isoformat()
    except ValueError:
        return None


def _parse_status(soup: BeautifulSoup) -> str:
    """
    Priority order:
      1. Remaining time span — if it has a non-zero countdown, auction is OPEN
         (most reliable — JS-rendered value captured by httpx)
      2. awe-rt-ColoredStatus — explicit Active/Closed label
      3. BidAmount input present — active
      4. Text signals — LAST resort, and only on elements NOT marked awe-hidden
         (the closed-banner is always in HTML but hidden via awe-hidden class)
    """
    # 1. Remaining time — detail__time span has data-action-time and live countdown
    time_el = soup.find('span', class_=re.compile(r'detail__time|awe-rt-Extended', re.I))
    if time_el:
        remaining = time_el.get_text(strip=True)
        # Any non-zero digit in remaining = auction is still open
        if re.search(r'[1-9]', remaining):
            return 'active'

    # 2. awe-rt-ColoredStatus real-time label (never hidden)
    status_el = soup.find(class_=re.compile(r'awe-rt-ColoredStatus', re.I))
    if status_el:
        txt = status_el.get_text(strip=True).lower()
        if 'active' in txt:
            return 'active'
        if 'ended' in txt or 'closed' in txt or 'sold' in txt:
            return 'sold'
        if 'paused' in txt:
            return 'paused'

    # 3. Bid input present = active
    if soup.find('input', id='BidAmount'):
        return 'active'

    # 4. Text scan — skip ANY element that has awe-hidden class
    #    The closed-banner "Bidding has ended" is always in HTML but
    #    marked awe-hidden on open auctions — we must not read it
    for el in soup.find_all(class_=re.compile(r'awe-hidden', re.I)):
        el.decompose()   # remove hidden elements from the tree

    text = soup.get_text().lower()
    if 'bidding has ended' in text or 'auction has ended' in text:
        return 'closed'
    if 'paused' in text:
        return 'paused'

    return 'unknown'


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


def _parse_auction_date_text(soup: BeautifulSoup) -> str | None:
    """Fallback: extract date from visible page text."""
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
