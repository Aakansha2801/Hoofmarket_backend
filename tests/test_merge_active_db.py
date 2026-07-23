# tests/test_merge_active_db.py
# Unit tests for db.active_listings.merge_with_active_db
# Run:  python -m pytest tests/test_merge_active_db.py -v
#   or:  python tests/test_merge_active_db.py

"""
These tests stub `db.active_listings.fetch_active_listings` so they
can run without a live Supabase connection.
"""

import sys
import os
from unittest.mock import patch

# Make the repo root importable when run as a plain script.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db import active_listings as al  # noqa: E402
from db.active_listings import DB_ACTIVE_TAG, merge_with_active_db  # noqa: E402


def _make_db_active(rows):
    """Helper: build a fake fetch_active_listings return value."""
    return rows


# ──────────────────────────────────────────────────────────────
# Test 1 — Browse-only (DB has no active rows)
# ──────────────────────────────────────────────────────────────
def test_browse_only():
    browse = [
        {"url": "https://w/a/1", "listing_id": "1", "source_site": "wildlifebuyer"},
        {"url": "https://w/a/2", "listing_id": "2", "source_site": "wildlifebuyer"},
    ]
    with patch.object(al, "fetch_active_listings", return_value=[]):
        merged, stats = merge_with_active_db("wildlifebuyer", browse)

    assert len(merged) == 2
    assert stats["db_active"] == 0
    assert stats["new_urls"] == 2
    assert stats["db_added_back"] == 0
    assert stats["merged_total"] == 2
    # No DB active tags
    assert all(not c.get(DB_ACTIVE_TAG) for c in merged)
    print("✓ test_browse_only")


# ──────────────────────────────────────────────────────────────
# Test 2 — DB-only (browse empty, DB has active rows)
# ──────────────────────────────────────────────────────────────
def test_db_only():
    db_rows = [
        {"listing_id": "100", "source_url": "https://w/x/100", "auction_status": "active"},
        {"listing_id": "101", "source_url": "https://w/x/101", "auction_status": "active"},
    ]
    with patch.object(al, "fetch_active_listings", return_value=db_rows):
        merged, stats = merge_with_active_db("wildlifebuyer", [])

    assert len(merged) == 2
    assert stats["db_active"] == 2
    assert stats["new_urls"] == 0
    assert stats["db_added_back"] == 2
    assert stats["merged_total"] == 2
    # All DB-sourced cards must be tagged
    assert all(c.get(DB_ACTIVE_TAG) for c in merged)
    # Each merged card carries url + listing_id so scraper can re-fetch
    urls = {c["url"] for c in merged}
    assert urls == {"https://w/x/100", "https://w/x/101"}
    print("✓ test_db_only")


# ──────────────────────────────────────────────────────────────
# Test 3 — Overlap by URL AND listing_id (browse and DB fully agree)
# listing_id path takes priority, so this counts as overlap_listing_id.
# ──────────────────────────────────────────────────────────────
def test_overlap_full_match():
    browse = [
        {"url": "https://w/a/1", "listing_id": "1", "source_site": "wildlifebuyer"},
    ]
    db_rows = [
        {"listing_id": "1", "source_url": "https://w/a/1", "auction_status": "active"},
    ]
    with patch.object(al, "fetch_active_listings", return_value=db_rows):
        merged, stats = merge_with_active_db("wildlifebuyer", browse)

    assert len(merged) == 1
    assert stats["db_active"] == 1
    assert stats["new_urls"] == 1
    assert stats["db_added_back"] == 0
    assert stats["overlap_listing_id"] == 1  # listing_id path wins
    assert stats["overlap_url"] == 0
    # The browse card should be tagged so transitions are still detected
    assert merged[0].get(DB_ACTIVE_TAG) is True
    print("✓ test_overlap_full_match")


# ──────────────────────────────────────────────────────────────
# Test 3b — URL-only overlap (DB row has NULL listing_id but URL matches)
# ──────────────────────────────────────────────────────────────
def test_overlap_url_only():
    browse = [
        {"url": "https://w/a/1", "listing_id": "1", "source_site": "wildlifebuyer"},
    ]
    db_rows = [
        {"listing_id": None, "source_url": "https://w/a/1", "auction_status": "active"},
    ]
    with patch.object(al, "fetch_active_listings", return_value=db_rows):
        merged, stats = merge_with_active_db("wildlifebuyer", browse)

    assert len(merged) == 1
    assert stats["db_added_back"] == 0
    assert stats["overlap_listing_id"] == 0  # DB had no listing_id
    assert stats["overlap_url"] == 1
    assert merged[0].get(DB_ACTIVE_TAG) is True
    print("✓ test_overlap_url_only")


# ──────────────────────────────────────────────────────────────
# Test 4 — Overlap by listing_id with DIFFERENT URL (slug changed)
# This simulates the seller editing a listing and the URL slug
# changing while listing_id stays the same.
# ──────────────────────────────────────────────────────────────
def test_overlap_by_listing_id_url_changed():
    browse = [
        {
            "url": "https://w/Listing/Details/12345/new-slug",
            "listing_id": "12345",
            "source_site": "wildlifebuyer",
        },
    ]
    db_rows = [
        {
            "listing_id": "12345",
            "source_url": "https://w/Listing/Details/12345/old-slug",
            "auction_status": "active",
        },
    ]
    with patch.object(al, "fetch_active_listings", return_value=db_rows):
        merged, stats = merge_with_active_db("wildlifebuyer", browse)

    # We keep the NEW url (browse) — no duplicate, no DB card added back.
    assert len(merged) == 1
    assert stats["db_added_back"] == 0
    assert stats["overlap_listing_id"] == 1
    assert merged[0]["url"] == "https://w/Listing/Details/12345/new-slug"
    # Tagged so we still detect active → closed transition
    assert merged[0].get(DB_ACTIVE_TAG) is True
    print("✓ test_overlap_by_listing_id_url_changed")


# ──────────────────────────────────────────────────────────────
# Test 5 — Mixed: some browse-only, some db-only, some overlap
# ──────────────────────────────────────────────────────────────
def test_mixed():
    browse = [
        {"url": "https://w/a/1", "listing_id": "1", "source_site": "wildlifebuyer"},
        {"url": "https://w/a/2", "listing_id": "2", "source_site": "wildlifebuyer"},
    ]
    db_rows = [
        # 1 → overlap by listing_id + URL (URL also matches)
        {"listing_id": "1", "source_url": "https://w/a/1", "auction_status": "active"},
        # 3 → DB only
        {"listing_id": "3", "source_url": "https://w/a/3", "auction_status": "active"},
        # 4 → DB only, no listing_id (edge case)
        {"listing_id": None, "source_url": "https://w/a/4", "auction_status": "active"},
    ]
    with patch.object(al, "fetch_active_listings", return_value=db_rows):
        merged, stats = merge_with_active_db("wildlifebuyer", browse)

    urls = {c["url"] for c in merged}
    assert urls == {"https://w/a/1", "https://w/a/2", "https://w/a/3", "https://w/a/4"}
    assert stats["db_active"] == 3
    assert stats["new_urls"] == 2
    assert stats["db_added_back"] == 2  # rows 3 and 4
    assert stats["overlap_listing_id"] == 1  # row 1 (matched by listing_id first)
    assert stats["overlap_url"] == 0  # row 1 took the listing_id path
    assert stats["merged_total"] == 4

    # Row 1 (browse card) must be tagged
    by_url = {c["url"]: c for c in merged}
    assert by_url["https://w/a/1"].get(DB_ACTIVE_TAG) is True
    assert by_url["https://w/a/3"].get(DB_ACTIVE_TAG) is True
    assert by_url["https://w/a/4"].get(DB_ACTIVE_TAG) is True
    # Row 2 is brand new — not tagged
    assert by_url["https://w/a/2"].get(DB_ACTIVE_TAG) in (None, False)
    print("✓ test_mixed")


# ──────────────────────────────────────────────────────────────
# Test 6 — DB row with NULL source_url is skipped (defensive)
# ──────────────────────────────────────────────────────────────
def test_db_row_without_url_is_skipped():
    db_rows = [
        {"listing_id": "999", "source_url": None, "auction_status": "active"},
        {"listing_id": "1000", "source_url": "https://w/a/1000", "auction_status": "active"},
    ]
    with patch.object(al, "fetch_active_listings", return_value=db_rows):
        merged, stats = merge_with_active_db("wildlifebuyer", [])

    urls = {c["url"] for c in merged}
    assert urls == {"https://w/a/1000"}
    assert stats["db_added_back"] == 1
    print("✓ test_db_row_without_url_is_skipped")


# ──────────────────────────────────────────────────────────────
# Test 7 — Duplicate browse URLs are deduped
# ──────────────────────────────────────────────────────────────
def test_duplicate_browse_urls_deduped():
    browse = [
        {"url": "https://w/a/1", "listing_id": "1", "source_site": "wildlifebuyer"},
        {"url": "https://w/a/1", "listing_id": "1", "source_site": "wildlifebuyer"},  # dup
    ]
    with patch.object(al, "fetch_active_listings", return_value=[]):
        merged, stats = merge_with_active_db("wildlifebuyer", browse)

    assert len(merged) == 1
    assert stats["new_urls"] == 1
    print("✓ test_duplicate_browse_urls_deduped")


# ──────────────────────────────────────────────────────────────
# Test 8 — DB hiccup returns empty list, scrape continues
# ──────────────────────────────────────────────────────────────
def test_db_failure_is_safe():
    with patch.object(al, "fetch_active_listings", return_value=[]):
        merged, stats = merge_with_active_db("wildlifebuyer", [
            {"url": "https://w/a/1", "listing_id": "1", "source_site": "wildlifebuyer"},
        ])
    assert len(merged) == 1
    assert stats["db_active"] == 0
    print("✓ test_db_failure_is_safe")


if __name__ == "__main__":
    test_browse_only()
    test_db_only()
    test_overlap_full_match()
    test_overlap_url_only()
    test_overlap_by_listing_id_url_changed()
    test_mixed()
    test_db_row_without_url_is_skipped()
    test_duplicate_browse_urls_deduped()
    test_db_failure_is_safe()
    print("\nAll merge tests passed ✅")
