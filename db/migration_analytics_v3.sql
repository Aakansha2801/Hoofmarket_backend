-- migration_analytics_v3.sql
-- Drop and recreate analytics tables to match current schema (no tier, no location_region)

-- price_snapshots: replace tier + location_region with age_class
DROP TABLE IF EXISTS price_snapshots;
CREATE TABLE price_snapshots (
    id               bigserial PRIMARY KEY,
    snapshot_date    date        NOT NULL,
    species_filter   text        NOT NULL,
    sex              text,
    age_class        text,
    listing_count    int,
    avg_price        numeric,
    median_price     numeric,
    min_price        numeric,
    max_price        numeric,
    UNIQUE (snapshot_date, species_filter, sex, age_class)
);

-- tier_stats: repurposed as sex/age stats (no tier column)
DROP TABLE IF EXISTS tier_stats;
CREATE TABLE tier_stats (
    id               bigserial PRIMARY KEY,
    computed_at      timestamptz NOT NULL,
    species_filter   text        NOT NULL,
    sex              text,
    age_class        text,
    listing_count    int,
    avg_price        numeric,
    median_price     numeric,
    min_price        numeric,
    max_price        numeric,
    price_histogram  jsonb
);

-- species_comparison: drop tier_distribution column
ALTER TABLE species_comparison DROP COLUMN IF EXISTS tier_distribution;
