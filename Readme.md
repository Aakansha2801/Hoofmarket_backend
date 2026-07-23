# HoofMarketIQ

A scraper pipeline that collects exotic hoofstock auction and classified listings from:

* WildlifeBuyer
* BuckTrader
* Online Hunting Auctions (OHA)

The system extracts listing details, tracks status changes, and stores normalized data in Supabase.

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
* Save results to Supabase

---

## Scraping Workflow

For each source:

1. Collect listing URLs from browse pages
2. Load active listings from the database
3. Merge and deduplicate both sets
4. Re-scrape all URLs
5. Extract structured fields
6. Upsert data into Supabase
7. Track status changes

```text
Browse Listings
       ↓
Load Active DB Listings
       ↓
Merge & Deduplicate
       ↓
Scrape Details
       ↓
Field Extraction
       ↓
Status Detection
       ↓
Supabase Upsert
```

### Why Merge With Active Listings?

Many auction sites remove sold or closed listings from browse pages.

Re-checking active database records ensures status changes are detected and listings do not remain incorrectly marked as active.

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

Listings are stored in Supabase using batch upserts.

* Batch Size: 20
* Deduplication by URL
* Fallback deduplication by Listing ID
* Status transition tracking

---

## Status Tracking

The system automatically detects transitions such as:

```text
Active → Sold
Active → Closed
Active → Ended
```

This ensures database records remain accurate even after listings disappear from source websites.

---

## Tech Stack

* Python
* AsyncIO
* HTTPX
* BeautifulSoup
* Supabase
* PostgreSQL

---

## Goal

Provide a reliable and maintainable pipeline for collecting, normalizing, and tracking exotic hoofstock listings across multiple auction and classified platforms.
