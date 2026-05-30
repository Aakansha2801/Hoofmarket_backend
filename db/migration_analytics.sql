-- ============================================================
-- HoofMarketIQ — db/migration_analytics.sql
-- Run once in Supabase SQL editor
-- ============================================================

-- 1. price_snapshots — one row per species+tier+date
--    Powers line charts (7/30/90/365 day price trends)
create table if not exists price_snapshots (
    id              bigserial primary key,
    snapshot_date   date        not null,
    species         text        not null,   -- axis | blackbuck | aoudad
    tier            text,                   -- management | good | trophy | elite | null
    sex             text,                   -- male | female | unknown
    avg_price       numeric(10,2),
    min_price       numeric(10,2),
    max_price       numeric(10,2),
    median_price    numeric(10,2),
    listing_count   int         default 0,
    created_at      timestamptz default now(),
    unique (snapshot_date, species, tier, sex)
);

-- 2. tier_stats — latest aggregate per species+tier
--    Powers bar charts (avg price by sex/age/tier) and comparison views
create table if not exists tier_stats (
    id              bigserial primary key,
    computed_at     timestamptz default now(),
    species         text        not null,
    tier            text,
    sex             text,
    age_class       text,
    avg_price       numeric(10,2),
    min_price       numeric(10,2),
    max_price       numeric(10,2),
    median_price    numeric(10,2),
    listing_count   int         default 0,
    -- histogram buckets stored as jsonb: [{bucket: "$0-500", count: 3}, ...]
    price_histogram jsonb       default '[]'
);

-- 3. region_stats — latest aggregate per species+region
--    Powers heat map
create table if not exists region_stats (
    id              bigserial primary key,
    computed_at     timestamptz default now(),
    species         text        not null,
    region          text        not null,
    avg_price       numeric(10,2),
    listing_count   int         default 0,
    unique (species, region)
);

create index if not exists idx_price_snapshots_species_date on price_snapshots(species, snapshot_date);
create index if not exists idx_tier_stats_species           on tier_stats(species);
create index if not exists idx_region_stats_species         on region_stats(species);
