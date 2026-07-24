# scrapers/base_scraper.py
from abc import ABC, abstractmethod
import httpx


class BaseScraper(ABC):
    """
    Every site scraper inherits this and implements two async methods.
    Orchestrator calls: await scraper.collect_listing_urls(client)
                        await scraper.scrape_detail(card, client)
    """

    @property
    @abstractmethod
    def source_site(self) -> str:
        """Unique site identifier stored in listings.source_site."""

    @abstractmethod
    async def collect_listing_urls(self, client: httpx.AsyncClient) -> list[dict]:
        """Paginate browse pages. Returns list of card dicts with {url, listing_id, source_site}."""

    @abstractmethod
    async def scrape_detail(self, card: dict, client: httpx.AsyncClient) -> dict | None:
        """Fetch and parse one listing detail page. Returns enriched dict or None."""
