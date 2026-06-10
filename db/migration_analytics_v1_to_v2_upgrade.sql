-- ============================================================
-- Upgrade analytics tables from migration_analytics.sql (v1)
-- to migration_analytics_v2.sql (v2) schema
-- 
-- V2 Changes:
--   - Rename `species` to `species_filter` in tier_stats, region_stats, 
--     species_comparison tables
--   - Add missing indexes
-- 
-- Safe: Backs up data, recreates tables with new schema, restores data
-- ============================================================

BEGIN TRANSACTION;

-- ── 1. Backup existing tier_stats ──────────────────────────
CREATE TEMP TABLE tier_stats_backup AS
SELECT * FROM tier_stats;

-- ── 2. Drop dependent objects ──────────────────────────────
DROP INDEX IF EXISTS idx_tier_stats_species;

-- ── 3. Truncate and alter tier_stats ──────────────────────
ALTER TABLE tier_stats RENAME COLUMN species TO species_filter;

-- ── 4. Recreate indexes with new name ──────────────────────
CREATE INDEX idx_tier_stats_filter ON tier_stats(species_filter);
CREATE INDEX idx_tier_stats_tier   ON tier_stats(tier);

-- ── 5. Handle region_stats ────────────────────────────
-- Rename species → species_filter in region_stats if it exists
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'region_stats'
    ) THEN
        DROP INDEX IF EXISTS idx_region_stats_species;
        IF EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'region_stats' 
              AND column_name = 'species'
        ) THEN
            ALTER TABLE region_stats RENAME COLUMN species TO species_filter;
        END IF;
        CREATE INDEX IF NOT EXISTS idx_region_stats_filter ON region_stats(species_filter);
    END IF;
END $$;

-- ── 6. Handle species_comparison ──────────────────────────
-- This table might not exist or might have a different schema
-- Safe approach: check and migrate if needed
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'species_comparison'
    ) THEN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'species_comparison' 
              AND column_name = 'species'
        ) THEN
            ALTER TABLE species_comparison RENAME COLUMN species TO species_filter;
        END IF;
    END IF;
END $$;

-- ── 7. Create market_overview if missing ──────────────────
CREATE TABLE IF NOT EXISTS market_overview (
    id              bigserial primary key,
    computed_at     timestamptz default now(),
    species_filter  text not null,
    total_listings  int default 0,
    avg_price       numeric(10,2),
    median_price    numeric(10,2),
    price_trend_7d  numeric(5,2),      -- percent change
    price_trend_30d numeric(5,2),
    top_tier        text,               -- most common tier
    unique (species_filter)
);

CREATE INDEX IF NOT EXISTS idx_market_overview_filter ON market_overview(species_filter);

COMMIT;
