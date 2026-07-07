-- Merge location columns into single location text column
-- Run once in Supabase SQL editor

ALTER TABLE listings ADD COLUMN IF NOT EXISTS location text;

-- Populate from existing columns
UPDATE listings SET location = TRIM(BOTH ', ' FROM CONCAT_WS(', ',
    NULLIF(location_city, ''),
    NULLIF(location_county, ''),
    NULLIF(location_region, ''),
    NULLIF(location_raw, ''),
    NULLIF(location_state, '')
)) WHERE location IS NULL;

-- Drop old columns
ALTER TABLE listings
    DROP COLUMN IF EXISTS location_raw,
    DROP COLUMN IF EXISTS location_city,
    DROP COLUMN IF EXISTS location_county,
    DROP COLUMN IF EXISTS location_region,
    DROP COLUMN IF EXISTS location_state;
