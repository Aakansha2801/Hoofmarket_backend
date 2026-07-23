import json
import logging
import time
import requests
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv() 
# ---------- Bubble config ----------
BUBBLE_APP_URL = "https://blackdogcattle.bubbleapps.io/version-test"
API_TOKEN = os.getenv("API_TOKEN")
DATA_TYPE = "listing"

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}
HEADERS_NDJSON = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "text/plain"
}

# ---------- Supabase config ----------
SUPABASE_URL = "https://imzqatfkwyeqinvnshem.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_TABLE = "listings"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

logger = logging.getLogger(__name__)

# ── Change detection ──────────────────────────────────────────
# If any of these fields differs between the Supabase row and the
# Bubble record, we trigger an update. Cosmetic fields like
# description_raw are excluded so we don't spam Bubble with no-op
# PATCH calls every time a seller fixes a typo.
WATCHED_FIELDS = [
    "auction_status", "price_current", "price_final", "bid_count",
    "title", "auction_end_date", "auction_start_date",
    "photo_urls", "quantity", "location", "is_active",
    "species", "sex", "age_class", "bred_status",
]

# Bubble API rate limit safety: per-row PATCH delay (seconds).
# Bubble's paid plans allow ~1000 req/min ≈ 16 req/s, so 0.1s is safe.
PATCH_DELAY_SEC = 0.1

# How often to log progress during bulk_update (every N rows).
UPDATE_PROGRESS_EVERY = 25


# ──────────────────────────────────────────────────────────────
# Read existing Bubble state
# ──────────────────────────────────────────────────────────────

def get_existing_bubble_listings():
    """Fetch ALL listings from Bubble with full record data.

    Returns {listing_id: bubble_record} for change detection.
    Rows without a listing_id are skipped (can't match them to Supabase).
    """
    url = f"{BUBBLE_APP_URL}/api/1.1/obj/{DATA_TYPE}"
    existing = {}
    cursor = 0
    while True:
        resp = requests.get(
            url, headers=HEADERS,
            params={"limit": 100, "cursor": cursor},
        )
        resp.raise_for_status()
        data = resp.json()["response"]
        for r in data["results"]:
            lid = r.get("listing_id")
            if lid:
                existing[lid] = r
        if len(data["results"]) < 100:
            break
        cursor += 100
    return existing


def get_existing_listing_ids():
    """Backwards-compatible: return {listing_id: bubble_id} only."""
    return {lid: rec["_id"] for lid, rec in get_existing_bubble_listings().items()}


# ──────────────────────────────────────────────────────────────
# Supabase → Bubble field mapping
# ──────────────────────────────────────────────────────────────

def map_record(item):
    """Convert one Supabase row into the field names Bubble expects."""
    return {
        "listing_id": item["listing_id"],
        "source_site": item.get("source_site"),
        "source_url": item.get("source_url"),
        "auction_date": item.get("auction_date"),
        "species": item.get("species"),
        "sex": item.get("sex"),
        "age_class": item.get("age_class"),
        "bred_status": item.get("bred_status"),
        "price_current": item.get("price_current"),
        "price_final": item.get("price_final"),
        "auction_status": item.get("auction_status"),
        "quantity": item.get("quantity"),
        "bid_count": item.get("bid_count"),
        "title": item.get("title"),
        "description_raw": item.get("description_raw"),
        "photo_urls": item.get("photo_urls", []),
        "is_active": item.get("is_active"),
        "location": item.get("location"),
        "auction_start_date": item.get("auction_start_date"),
        "auction_end_date": item.get("auction_end_date"),
    }


def _normalize_for_compare(value):
    """Normalize a field value for change detection.

    Handles common type mismatches between Supabase and Bubble so we don't
    trigger false-positive updates:
      - None / "" / "null" → None
      - numeric strings → int or float
      - lists → sorted (order shouldn't matter for photo_urls)
    """
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        if v == "" or v.lower() == "null":
            return None
        try:
            f = float(v)
            return int(f) if f == int(f) else f
        except (ValueError, TypeError):
            return v.lower()
    if isinstance(value, (list, tuple)):
        return sorted(_normalize_for_compare(x) for x in value)
    if isinstance(value, (int, float, bool)):
        return value
    return value


def _record_differs(bubble_rec, new_mapped):
    """Return (changed, field_name) — True if any WATCHED_FIELD differs."""
    for field in WATCHED_FIELDS:
        old = _normalize_for_compare(bubble_rec.get(field))
        new = _normalize_for_compare(new_mapped.get(field))
        if old != new:
            return True, field
    return False, None


# ──────────────────────────────────────────────────────────────
# Insert path (bulk create)
# ──────────────────────────────────────────────────────────────

def bulk_insert(new_items):
    """Bulk-create brand new listings in one API call."""
    if not new_items:
        print("No new listings to insert.")
        return None

    lines = [json.dumps(map_record(item)) for item in new_items]
    body = "\n".join(lines)
    url = f"{BUBBLE_APP_URL}/api/1.1/obj/{DATA_TYPE}/bulk"
    resp = requests.post(url, headers=HEADERS_NDJSON, data=body)
    print(f"Bulk insert: {len(new_items)} rows | status: {resp.status_code}")
    if resp.status_code >= 400:
        print(f"  ❌ Error: {resp.text[:500]}")
    return resp


# ──────────────────────────────────────────────────────────────
# Update path (per-row PATCH — Bubble has no bulk PATCH endpoint)
# ──────────────────────────────────────────────────────────────

def update_one(bubble_id, mapped_record):
    """PATCH a single existing Bubble listing with new field values."""
    url = f"{BUBBLE_APP_URL}/api/1.1/obj/{DATA_TYPE}/{bubble_id}"
    # Don't send listing_id in PATCH body — it's the unique key, not updatable.
    body = {k: v for k, v in mapped_record.items() if k != "listing_id"}
    return requests.patch(url, headers=HEADERS, json=body)


def bulk_update(updates):
    """Update existing Bubble listings via per-row PATCH.

    Bubble's public API has no bulk PATCH endpoint, so we issue one PATCH
    per row with PATCH_DELAY_SEC between calls to stay under the rate limit.

    Args:
        updates: list of dicts shaped like
            {"bubble_id": str, "record": {...}, "listing_id": str, "changed_field": str}
    """
    if not updates:
        print("No listings to update.")
        return

    print(f"Updating {len(updates)} listings in Bubble (per-row PATCH)...")
    ok, err = 0, 0
    for i, upd in enumerate(updates, 1):
        try:
            resp = update_one(upd["bubble_id"], upd["record"])
            if resp.status_code < 400:
                ok += 1
            else:
                err += 1
                print(f"  ❌ listing_id={upd['listing_id']} "
                      f"(bubble_id={upd['bubble_id']}): "
                      f"{resp.status_code} {resp.text[:200]}")
        except Exception as e:
            err += 1
            print(f"  ❌ Exception updating listing_id={upd['listing_id']}: {e}")

        if i % UPDATE_PROGRESS_EVERY == 0:
            print(f"  Progress: {i}/{len(updates)} (ok={ok}, err={err})")
        time.sleep(PATCH_DELAY_SEC)

    print(f"Update complete: ok={ok}, err={err}")


# ──────────────────────────────────────────────────────────────
# Supabase fetch
# ──────────────────────────────────────────────────────────────

def fetch_all_supabase_listings():
    """Pull all rows from the Supabase listings table (paginated)."""
    all_rows = []
    page_size = 1000
    start = 0
    while True:
        resp = (
            supabase.table(SUPABASE_TABLE)
            .select("*")
            .range(start, start + page_size - 1)
            .execute()
        )
        rows = resp.data
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        start += page_size
    return all_rows


# ──────────────────────────────────────────────────────────────
# Top-level sync entry point
# ──────────────────────────────────────────────────────────────

def sync_to_bubble():
    """Full bidirectional sync: insert new + update changed listings.

    Workflow:
      1. Pull every row from Supabase.
      2. Pull every row from Bubble (with full record for change detection).
      3. For each Supabase row:
         - listing_id missing → skip with warning
         - listing_id not in Bubble → batch for insert
         - listing_id in Bubble AND watched field changed → batch for update
         - listing_id in Bubble AND nothing changed → skip
      4. Run bulk_insert for new rows.
      5. Run bulk_update (per-row PATCH) for changed rows.
    """
    print("Fetching listings from Supabase...")
    supabase_listings = fetch_all_supabase_listings()
    print(f"Fetched {len(supabase_listings)} rows from Supabase.")

    print("Fetching existing listings from Bubble...")
    bubble_existing = get_existing_bubble_listings()
    print(f"Bubble already has {len(bubble_existing)} listings.")

    new_listings = []
    updates = []
    skipped_unchanged = 0
    skipped_no_listing_id = 0

    for item in supabase_listings:
        lid = item.get("listing_id")
        if not lid:
            skipped_no_listing_id += 1
            continue

        mapped = map_record(item)

        if lid not in bubble_existing:
            new_listings.append(item)
            continue

        bubble_rec = bubble_existing[lid]
        changed, field = _record_differs(bubble_rec, mapped)
        if changed:
            updates.append({
                "bubble_id": bubble_rec["_id"],
                "record": mapped,
                "listing_id": lid,
                "changed_field": field,
            })
        else:
            skipped_unchanged += 1

    print(f"  → {len(new_listings)} new listings to insert")
    print(f"  → {len(updates)} existing listings to update")
    print(f"  → {skipped_unchanged} unchanged (skipped)")
    if skipped_no_listing_id:
        print(f"  → {skipped_no_listing_id} Supabase rows skipped (no listing_id)")

    # Show a few sample transitions so operators can spot-check
    if updates:
        status_changes = [u for u in updates
                          if u["changed_field"] == "auction_status"]
        if status_changes:
            print(f"  🔄 auction_status changes: {len(status_changes)}")
            for u in status_changes[:5]:
                # bubble_rec still in scope from the loop above — re-fetch
                old = bubble_existing[u["listing_id"]].get("auction_status")
                new = u["record"].get("auction_status")
                print(f"     • {old} → {new}: {u['listing_id']}")
            if len(status_changes) > 5:
                print(f"     … and {len(status_changes) - 5} more")

    bulk_insert(new_listings)
    bulk_update(updates)

    print(f"\n✅ Sync complete: "
          f"inserted={len(new_listings)}, updated={len(updates)}, "
          f"unchanged={skipped_unchanged}")


if __name__ == "__main__":
    sync_to_bubble()