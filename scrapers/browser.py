# scrapers/browser.py
import asyncio
import random
import logging
import httpx
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from config import RATE_LIMIT_MIN, RATE_LIMIT_MAX, HEADLESS

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_playwright = None
_browser: Browser | None = None


async def _get_browser() -> Browser:
    global _playwright, _browser
    if _browser is None or not _browser.is_connected():
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(
            headless=HEADLESS,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        logger.info("🧭 Playwright browser launched")
    return _browser


async def close_browser():
    global _browser, _playwright
    if _browser:
        await _browser.close()
        _browser = None
    if _playwright:
        await _playwright.stop()
        _playwright = None
    logger.info("Browser closed")


async def _rate_limit():
    await asyncio.sleep(random.uniform(RATE_LIMIT_MIN, RATE_LIMIT_MAX))


def _is_valid_html(html: str, url: str) -> bool:
    if not html or len(html) < 500:
        logger.warning(f"  ⚠️  Response too short: {url}")
        return False
    lowered = html.lower()
    hard_blocks = [
        "access denied",
        "unusual traffic",
        "are you human",
        "security check",
        "please wait while we verify",
        "enable javascript and cookies",
    ]
    for signal in hard_blocks:
        if signal in lowered:
            logger.warning(f"  ⚠️  Bot-block '{signal}': {url}")
            return False

    # Real CAPTCHA challenge pages (not just pages that load reCAPTCHA widgets)
    if "captcha" in lowered and ("challenge-form" in lowered or "grecaptcha.execute" in lowered):
        logger.warning(f"  ⚠️  CAPTCHA challenge page: {url}")
        return False
    if "<body" not in lowered:
        logger.warning(f"  ⚠️  No <body>: {url}")
        return False
    return True


async def _fetch_with_httpx(url: str, client: httpx.AsyncClient) -> str | None:
    try:
        r = await client.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
        if r.status_code != 200:
            logger.warning(f"  ⚠️  HTTP {r.status_code}: {url}")
            return None
        return r.text if _is_valid_html(r.text, url) else None
    except Exception as e:
        logger.warning(f"  ⚠️  httpx error {url}: {e}")
        return None


async def _fetch_with_playwright(url: str) -> str | None:
    logger.info(f"  🧭 Playwright fallback: {url}")
    try:
        browser = await _get_browser()
        ctx: BrowserContext = await browser.new_context(
            user_agent=HEADERS["User-Agent"],
            viewport={"width": 1280, "height": 800},
            locale="en-US", timezone_id="America/Chicago",
        )
        page: Page = await ctx.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=30_000)
            html = await page.content()
            if _is_valid_html(html, url):
                logger.info(f"  ✅ Playwright OK: {url}")
                return html
            return None
        finally:
            await page.close()
            await ctx.close()
    except Exception as e:
        logger.error(f"  ❌ Playwright failed {url}: {e}")
        return None


async def fetch_page(url: str, client: httpx.AsyncClient, retries: int = 2) -> str | None:
    await _rate_limit()
    for attempt in range(1, retries + 1):
        html = await _fetch_with_httpx(url, client)
        if html:
            logger.info(f"  ✅ httpx OK (attempt {attempt}): {url}")
            return html
        if attempt < retries:
            await asyncio.sleep(attempt * 3)
    logger.warning(f"  ⚠️  httpx failed — trying Playwright: {url}")
    return await _fetch_with_playwright(url)


def make_httpx_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers=HEADERS,
        timeout=httpx.Timeout(20.0),
        limits=httpx.Limits(max_connections=5, max_keepalive_connections=3),
        follow_redirects=True,
    )
