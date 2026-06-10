#!/usr/bin/env python3
"""
Remove duplicate listings from the database.
Keeps the most recent version of each (source_site, listing_id) pair.
"""

from db.supabase_client import get_client
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def cleanup_duplicates():
    """Find and remove duplicate listings, keeping the most recent."""
    client = get_client()
    
    # Get all listings
    response = client.table('listings').select('id, source_site, listing_id, scraped_at').execute()
    rows = response.data or []
    
    # Group by (source_site, listing_id)
    groups = {}
    for row in rows:
        site = row.get('source_site', 'unknown')
        lid = row.get('listing_id')
        if not lid:
            continue
        
        key = (site, lid)
        if key not in groups:
            groups[key] = []
        groups[key].append(row)
    
    # Find duplicates: groups with > 1 row
    duplicates_to_remove = []
    for key, group in groups.items():
        if len(group) > 1:
            # Sort by scraped_at descending (most recent first)
            sorted_group = sorted(group, key=lambda r: r.get('scraped_at', ''), reverse=True)
            # Keep the first (most recent), mark rest for deletion
            duplicates_to_remove.extend(sorted_group[1:])
    
    if not duplicates_to_remove:
        logger.info("✅ No duplicates found")
        return 0
    
    logger.info(f"Found {len(duplicates_to_remove)} duplicate rows to remove")
    
    # Delete old duplicates
    deleted = 0
    for dup in duplicates_to_remove:
        try:
            client.table('listings').delete().eq('id', dup['id']).execute()
            deleted += 1
            logger.info(f"  Deleted: {dup.get('listing_id')} (scraped {dup.get('scraped_at')[:10]})")
        except Exception as e:
            logger.error(f"Failed to delete {dup['id']}: {e}")
    
    logger.info(f"\n✅ Deleted {deleted} duplicate rows")
    return deleted


if __name__ == "__main__":
    cleanup_duplicates()
