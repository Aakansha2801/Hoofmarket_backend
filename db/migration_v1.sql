-- ============================================================
-- HoofMarketIQ — db/migration_v1.sql
-- Run once in Supabase SQL editor to create the listings table
-- ============================================================

create table if not exists listings (
    id                          bigserial primary key,

    -- Source
    listing_id                  text,
    source_url                  text not null unique,
    source_site                 text,
    scraped_at                  timestamptz,

    -- Raw listing
    title                       text,
    description_raw             text,
    category                    text,
    price_current               numeric(10,2),
    easy_bid_price              numeric(10,2),
    bid_count                   int default 0,
    auction_status              text,          -- active | closed | paused | unknown
    auction_date                date,
    photo_urls                  text[],
    seller_id                   text,
    quantity                    int default 1,

    -- Extracted fields
    species                     text,          -- axis | blackbuck | aoudad | oryx | ...
    sex                         text,          -- male | female | mixed | unknown
    age_class                   text,          -- calf | yearling | mature_2_4 | prime_4_6 | mature_6plus | unknown
    bred_status                 text,          -- wild | ranch_bred | ai | et | proven_breeder | unknown
    color_phase                 text,
    location_raw                text,
    location_city               text,
    location_county             text,
    location_region             text,          -- Hill Country | South Texas | ...
    location_state              text default 'TX',

    -- Measurements (special species only)
    primary_measurement_inches  numeric(5,1),
    secondary_measurements      jsonb default '{}',

    -- Tier (special species only)
    -- axis/blackbuck/aoudad: management | good | trophy | elite
    -- other species: filter tag (see below)
    tier                        text,
    species_filter              text,          -- axis | blackbuck | aoudad | other

    -- QA
    extraction_notes            text,
    needs_manual_review         boolean default false,

    created_at                  timestamptz default now(),
    updated_at                  timestamptz default now()
);

-- Auto-update updated_at on upsert
create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists listings_updated_at on listings;
create trigger listings_updated_at
    before update on listings
    for each row execute function set_updated_at();

-- Populate species_filter from species
create or replace function compute_species_filter(s text)
returns text language sql immutable as $$
    select case
        when s in ('axis')      then 'axis'
        when s in ('blackbuck') then 'blackbuck'
        when s in ('aoudad')    then 'aoudad'
        else                         'other'
    end;
$$;

-- Indexes for common query patterns
create index if not exists idx_listings_species        on listings(species);
create index if not exists idx_listings_species_filter on listings(species_filter);
create index if not exists idx_listings_tier           on listings(tier);
create index if not exists idx_listings_auction_status on listings(auction_status);
create index if not exists idx_listings_auction_date   on listings(auction_date);
create index if not exists idx_listings_location_region on listings(location_region);
create index if not exists idx_listings_price          on listings(price_current);
create index if not exists idx_listings_scraped_at     on listings(scraped_at);
