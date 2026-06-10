# scrapers/onlinehuntingauctions/__init__.py
import httpx
from scrapers.base_scraper import BaseScraper
from scrapers.onlinehuntingauctions.browse_pages import collect_listing_urls
from scrapers.onlinehuntingauctions.detail_pages import scrape_listing


class OnlineHuntingAuctionsScraper(BaseScraper):
    source_site = "onlinehuntingauctions"

    async def collect_listing_urls(self, client: httpx.AsyncClient) -> list[dict]:
        return await collect_listing_urls(client)

    async def scrape_detail(self, card: dict, client: httpx.AsyncClient) -> dict | None:
        return await scrape_listing(card, client)