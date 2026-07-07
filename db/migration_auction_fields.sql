-- ============================================================
-- HoofMarketIQ — db/migration_auction_fields.sql
-- Run in Supabase SQL Editor
-- Adds: auction_start_date, auction_end_date, reserve_status,
--       watchers_count, created_at, updated_at
-- ============================================================

alter table listings
    add column if not exists auction_start_date  timestamptz,
    add column if not exists auction_end_date    timestamptz,
    add column if not exists reserve_status      text,
    add column if not exists watchers_count      int default 0,
    add column if not exists created_at          timestamptz default now(),
    add column if not exists updated_at          timestamptz default now();

-- Auto-update updated_at on every row update
create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists listings_set_updated_at on listings;
create trigger listings_set_updated_at
    before update on listings
    for each row execute function set_updated_at();

-- Backfill created_at from first_seen_at where available
update listings
set created_at = first_seen_at
where first_seen_at is not null and created_at is null;
