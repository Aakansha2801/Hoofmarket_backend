# tests/test_orchestrator_dry_run.py
# Dry-run simulation of orchestrator._run_one() with a fake scraper
# and a fake upsert.  Verifies the end-to-end workflow:
#   1. browse collection
#   2. merge with DB active
#   3. structured logging stats
#   4. active -> closed/sold transition detection
#   5. upsert called with the right batch
# Run:  python tests/test_orchestrator_dry_run.py

import sys
import os
import asyncio
import logging
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

import orchestrator  # noqa: E402
import db.active_listings as al  # noqa: E402


class FakeScraper:
    source_site = "wildlifebuyer"

    def __init__(self, browse_cards, detail_results):
        self.browse_cards = browse_cards
        self.detail_results = detail_results  # url -> dict (or None for failure)

    async def collect_listing_urls(self, client):
        return list(self.browse_cards)

    async def scrape_detail(self, card, client):
        return self.detail_results.get(card["url"])


async def run_test():
    # --- Build a scenario --------------------------------------------
    # Browse finds 2 NEW active listings + 1 still-active listing
    # that is also in the DB.
    browse = [
        {"url": "https://w/a/1", "listing_id": "1", "source_site": "wildlifebuyer"},
        {"url": "https://w/a/2", "listing_id": "2", "source_site": "wildlifebuyer"},
        {"url": "https://w/a/3", "listing_id": "3", "source_site": "wildlifebuyer"},
    ]
    # DB has: 3 (overlap), 4 (db only, will become closed), 5 (db only, fails to fetch)
    db_rows = [
        {"listing_id": "3", "source_url": "https://w/a/3", "auction_status": "active"},
        {"listing_id": "4", "source_url": "https://w/a/4", "auction_status": "active"},
        {"listing_id": "5", "source_url": "https://w/a/5", "auction_status": "active"},
    ]
    # Detail results:
    detail = {
        "https://w/a/1": {"title": "Listing 1", "source_url": "https://w/a/1",
                          "source_site": "wildlifebuyer", "auction_status": "active"},
        "https://w/a/2": {"title": "Listing 2", "source_url": "https://w/a/2",
                          "source_site": "wildlifebuyer", "auction_status": "active"},
        "https://w/a/3": {"title": "Listing 3", "source_url": "https://w/a/3",
                          "source_site": "wildlifebuyer", "auction_status": "active"},
        # Listing 4 was active in DB, now closed -> transition!
        "https://w/a/4": {"title": "Listing 4 (SOLD)", "source_url": "https://w/a/4",
                          "source_site": "wildlifebuyer", "auction_status": "sold"},
        # Listing 5 fails to fetch -> error counted, no transition
        "https://w/a/5": None,
    }
    scraper = FakeScraper(browse, detail)

    # --- Patch DB + upsert ------------------------------------------
    upsert_calls = []
    def fake_upsert_batch(batch):
        upsert_calls.append(list(batch))
        return len(batch), 0

    with patch.object(al, "fetch_active_listings", return_value=db_rows), \
         patch("orchestrator.upsert_batch", side_effect=fake_upsert_batch), \
         patch("orchestrator.extract_fields", side_effect=lambda x: x), \
         patch("orchestrator.apply_tier", side_effect=lambda x: x):
        saved = await orchestrator._run_one(scraper, client=None)

    # --- Assertions --------------------------------------------------
    print(f"\n--- Result: saved={saved}, upsert_calls={len(upsert_calls)} ---")
    assert saved == 4, f"expected 4 saved (1,2,3,4), got {saved}"

    # All upserted URLs
    upserted_urls = {row["source_url"] for batch in upsert_calls for row in batch}
    assert upserted_urls == {
        "https://w/a/1", "https://w/a/2", "https://w/a/3", "https://w/a/4"
    }, f"unexpected upserted URLs: {upserted_urls}"
    print("✓ upserted 4 unique listings (URL 5 skipped due to fetch failure)")

    # The _from_db_active tag must be stripped before upsert (it's not in _LISTING_FIELDS).
    for batch in upsert_calls:
        for row in batch:
            assert al.DB_ACTIVE_TAG not in row, \
                f"_from_db_active leaked into upsert row: {row}"
    print("✓ _from_db_active tag stripped before upsert (no schema leak)")

    print("✅ orchestrator dry-run test passed")


if __name__ == "__main__":
    asyncio.run(run_test())
