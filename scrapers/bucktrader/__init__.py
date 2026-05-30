# scrapers/bucktrader/__init__.py
import httpx
from scrapers.base_scraper import BaseScraper
from scrapers.bucktrader.browse_pages import collect_listing_urls
from scrapers.bucktrader.detail_pages import scrape_listing


class BuckTraderScraper(BaseScraper):
    source_site = "bucktrader"

    async def collect_listing_urls(self, client: httpx.AsyncClient) -> list[dict]:
        return await collect_listing_urls(client)

    async def scrape_detail(self, card: dict, client: httpx.AsyncClient) -> dict | None:
        return await scrape_listing(card, client)
