# HoofMarketIQ

A scraper pipeline that collects exotic hoofstock auction and classified listings from:

* WildlifeBuyer
* BuckTrader
* Online Hunting Auctions (OHA)

The system extracts listing details, tracks status changes, and syncs data directly to **Bubble.io** — no intermediate database.

---

## Overview

Each scraper follows the same interface:

```python
class BaseScraper(ABC):
    async def collect_listing_urls(self, client):
        pass

    async def scrape_detail(self, card, client):
        pass
```

### Responsibilities

* Collect listing URLs
* Scrape listing details
* Normalize extracted data
* Detect listing status changes
* Sync results directly to Bubble.io

---

## Scraping & Sync Workflow

For each source:

1. Collect listing URLs from browse pages
2. Scrape each listing detail page
3. Extract structured fields (species, sex, age class, tier)
4. Check existing Bubble listings for deduplication
5. Bulk insert new listings to Bubble.io
6. PATCH changed listings in Bubble.io

```text
Browse Listings
       ↓
Scrape Details
       ↓
Field Extraction & Enrichment
       ↓
Dedup against Bubble (existing listing_ids)
       ↓
Bulk Insert (new) / PATCH (changed)
       ↓
Bubble.io Database
```

---

## Supported Sources

### WildlifeBuyer

Auction marketplace.

**Extracted Data**

* Title
* Description
* Price
* Winning Bid
* Minimum Next Bid
* Bid Count
* Watcher Count
* Seller Information
* Location
* Quantity
* Photos
* Auction Start/End Time

**Status Detection**

* Countdown timer
* Status labels
* Bid form presence
* Page text analysis

---

### BuckTrader

Classified listing platform.

**Extracted Data**

* Title
* Description
* Location
* Seller Phone

**Status Detection**

* Sold
* Active

---

### Online Hunting Auctions (OHA)

Multi-level auction structure:

```text
Auction List
      ↓
Auction Detail
      ↓
Lot Detail
```

**Extracted Data**

* Winning Bid
* Starting Price
* Quantity
* Photos
* Status

**Special Handling**

* Skips non-animal auctions
* Supports auction and lot pagination

---

## Data Processing

Additional fields are generated automatically:

* Species
* Sex
* Age Class
* Bred Status
* Trophy Tier

---

## Reliability Features

* Shared `httpx.AsyncClient`
* Request retry with exponential backoff
* Randomized request delays
* Bot-block detection
* Error logging
* Fault-tolerant execution

A failed listing never stops the entire scraping run.

---

## Storage

Listings are stored directly in **Bubble.io**.

* Bulk Insert via NDJSON API
* Per-row PATCH for changed listings
* Deduplication by listing_id against existing Bubble records
* Change detection across watched fields

---

## Tech Stack

* Python
* AsyncIO
* HTTPX
* BeautifulSoup
* Bubble.io API

---

## Goal

Provide a reliable and maintainable pipeline for collecting, normalizing, and tracking exotic hoofstock listings across multiple auction and classified platforms, with all data stored directly in Bubble.io.
