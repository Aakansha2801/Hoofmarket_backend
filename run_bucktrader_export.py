# run_bucktrader_export.py
# Runs ONLY BuckTrader scraper and exports all results to CSV

import asyncio
import csv
import logging
import sys
from datetime import datetime

from scrapers.browser import make_httpx_client, close_browser
from scrapers.bucktrader import BuckTraderScraper
from parser.field_extractor import extract_fields
from parser.tier_calculator import apply_tier
from db.upsert import upsert_batch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

CSV_FIELDS = [
    "listing_id", "title", "source_url", "source_site",
    "species", "sex", "age_class", "tier",
    "price_current", "easy_bid_price",
    "auction_status", "auction_date",
    "location_raw", "location_city", "location_county", "location_region",
    "bred_status", "color_phase", "quantity",
    "primary_measurement_inches", "extraction_notes",
    "photo_urls", "scraped_at",
]


async def run():
    scraper = BuckTraderScraper()
    all_enriched = []

    async with make_httpx_client() as client:
        cards = await scraper.collect_listing_urls(client)
        logger.info(f"📋 {len(cards)} URLs collected")

        for i, card in enumerate(cards, 1):
            raw = await scraper.scrape_detail(card, client)
            if not raw:
                continue
            enriched = apply_tier(extract_fields(raw))
            all_enriched.append(enriched)
            logger.info(f"  [{i}/{len(cards)}] {enriched.get('title','')[:60]}")

    await close_browser()

    # Save to Supabase
    if all_enriched:
        s, f = upsert_batch(all_enriched)
        logger.info(f"✅ Supabase: saved={s} errors={f}")

    # Export to CSV
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"bucktrader_listings_{ts}.csv"

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in all_enriched:
            # Flatten photo_urls list to string
            row = row.copy()
            if isinstance(row.get("photo_urls"), list):
                row["photo_urls"] = " | ".join(row["photo_urls"])
            writer.writerow(row)

    logger.info(f"📄 CSV exported: {filename} ({len(all_enriched)} rows)")
    return filename


if __name__ == "__main__":
    asyncio.run(run())
