-- ============================================================
-- HoofMarketIQ — db/migration_analytics_v2.sql
-- Run in Supabase SQL Editor (replaces migration_analytics.sql)
-- Covers all 10 V1 analytics modules
-- ============================================================

-- ── 1. market_overview ───────────────────────────────────────
-- Module 1: Market Overview Dashboard
-- One row per species_filter (axis | blackbuck | aoudad | other | ALL)
create table if not exists market_overview (
    id                  bigserial primary key,
    computed_at         timestamptz default now(),
    species_filter      text not null,          -- axis | blackbuck | aoudad | other | all
    total_listings      int  default 0,
    active_listings     int  default 0,
    avg_price           numeric(10,2),
    median_price        numeric(10,2),
    min_price           numeric(10,2),
    max_price           numeric(10,2),
    new_listings_24h    int  default 0,
    new_listings_7d     int  default 0,
    unique (species_filter)
);

-- ── 2. price_snapshots ───────────────────────────────────────
-- Module 2: Price Trend Analytics (7/30/90/365 day line charts)
-- One row per date + species_filter + tier + sex + location_region
create table if not exists price_snapshots (
    id              bigserial primary key,
    snapshot_date   date        not null,
    species_filter  text        not null,   -- axis | blackbuck | aoudad | other | all
    tier            text,                   -- management | good | trophy | elite | null=all
    sex             text,                   -- male | female | unknown | null=all
    location_region text,                   -- TX region or null=all
    avg_price       numeric(10,2),
    median_price    numeric(10,2),
    min_price       numeric(10,2),
    max_price       numeric(10,2),
    listing_count   int default 0,
    created_at      timestamptz default now(),
    unique (snapshot_date, species_filter, tier, sex, location_region)
);

-- ── 3. tier_stats ────────────────────────────────────────────
-- Module 3: Tier-Based Analytics
-- Module 4: Sex-Based Analytics
-- Module 5: Age-Based Analytics
-- One row per species_filter + tier + sex + age_class combo
create table if not exists tier_stats (
    id              bigserial primary key,
    computed_at     timestamptz default now(),
    species_filter  text not null,
    tier            text,           -- null = all tiers
    sex             text,           -- null = all sexes
    age_class       text,           -- null = all ages
    avg_price       numeric(10,2),
    median_price    numeric(10,2),
    min_price       numeric(10,2),
    max_price       numeric(10,2),
    listing_count   int default 0,
    price_histogram jsonb default '[]'  -- [{bucket, count}, ...]
);

-- ── 4. region_stats ──────────────────────────────────────────
-- Module 6: Geographic Analytics / Heat Map
create table if not exists region_stats (
    id              bigserial primary key,
    computed_at     timestamptz default now(),
    species_filter  text not null,
    region          text not null,
    avg_price       numeric(10,2),
    median_price    numeric(10,2),
    min_price       numeric(10,2),
    max_price       numeric(10,2),
    listing_count   int default 0,
    unique (species_filter, region)
);

-- ── 5. species_comparison ────────────────────────────────────
-- Module 7: Species Comparison Analytics
create table if not exists species_comparison (
    id              bigserial primary key,
    computed_at     timestamptz default now(),
    species_filter  text not null unique,
    avg_price       numeric(10,2),
    median_price    numeric(10,2),
    min_price       numeric(10,2),
    max_price       numeric(10,2),
    listing_count   int default 0,
    -- Tier distribution: {management: N, good: N, trophy: N, elite: N}
    tier_distribution jsonb default '{}'
);

-- ── Indexes ───────────────────────────────────────────────────
create index if not exists idx_price_snapshots_filter_date  on price_snapshots(species_filter, snapshot_date);
create index if not exists idx_price_snapshots_date         on price_snapshots(snapshot_date);
create index if not exists idx_tier_stats_filter            on tier_stats(species_filter);
create index if not exists idx_tier_stats_tier              on tier_stats(tier);
create index if not exists idx_region_stats_filter          on region_stats(species_filter);
create index if not exists idx_market_overview_filter       on market_overview(species_filter);
create index if not exists idx_species_comparison_filter    on species_comparison(species_filter);
