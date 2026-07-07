-- 1. Drop the dependent view
DROP VIEW IF EXISTS v_price_trend_daily;

-- 2. Run your column drops
ALTER TABLE listings
    DROP COLUMN IF EXISTS price_start,
    DROP COLUMN IF EXISTS auction_start_date,
    DROP COLUMN IF EXISTS auction_end_date,
    DROP COLUMN IF EXISTS watchers_count,
    DROP COLUMN IF EXISTS seller_id,
    DROP COLUMN IF EXISTS color_phase,
    DROP COLUMN IF EXISTS primary_measurement_inches,
    DROP COLUMN IF EXISTS secondary_measurements,
    DROP COLUMN IF EXISTS tier,
    DROP COLUMN IF EXISTS tier_confidence,
    DROP COLUMN IF EXISTS quality_score,
    DROP COLUMN IF EXISTS extraction_notes,
    DROP COLUMN IF EXISTS needs_manual_review;

-- 3. Recreate the view without tier
CREATE VIEW v_price_trend_daily AS
SELECT
    species,
    auction_date AS sale_date,
    count(*) AS sales_count,
    round(avg(price_final), 2) AS avg_price,
    round(percentile_cont(0.5::double precision) WITHIN GROUP (ORDER BY (price_final::double precision))::numeric, 2) AS median_price
FROM listings
WHERE auction_status = 'closed'::auction_status_enum
  AND price_final IS NOT NULL
  AND auction_date IS NOT NULL
GROUP BY species, auction_date
ORDER BY auction_date DESC;