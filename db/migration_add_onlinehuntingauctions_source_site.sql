-- Add the new source_site enum value used by the OnlineHuntingAuctions scraper.
-- Run this in Supabase SQL editor if `listings.source_site` is backed by `source_site_enum`.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        WHERE t.typname = 'source_site_enum'
          AND e.enumlabel = 'onlinehuntingauctions'
    ) THEN
        -- already present
        RETURN;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_type
        WHERE typname = 'source_site_enum'
    ) THEN
        ALTER TYPE source_site_enum ADD VALUE 'onlinehuntingauctions';
    END IF;
END
$$;
