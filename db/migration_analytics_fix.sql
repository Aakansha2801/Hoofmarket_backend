-- ============================================================
-- HoofMarketIQ — db/migration_analytics_fix.sql
-- Fixes two issues found in production:
--   1. tier_stats missing: age_class, price_histogram, computed_at
--   2. region_stats table does not exist
-- Run in Supabase SQL Editor
-- ============================================================

-- Fix tier_stats missing columns
alter table tier_stats
    add column if not exists age_class       text,
    add column if not exists price_histogram jsonb        default '[]',
    add column if not exists computed_at     timestamptz  default now();

-- Create region_stats (was missing entirely)
create table if not exists region_stats (
    id              bigserial primary key,
    computed_at     timestamptz default now(),
    species_filter  text        not null,
    region          text        not null,
    avg_price       numeric(10,2),
    median_price    numeric(10,2),
    min_price       numeric(10,2),
    max_price       numeric(10,2),
    listing_count   int         default 0,
    unique (species_filter, region)
);

create index if not exists idx_region_stats_filter on region_stats(species_filter);
