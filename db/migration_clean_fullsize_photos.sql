-- Clean bad photo URLs from existing listings
-- Run once in Supabase SQL editor

UPDATE listings
SET photo_urls = (
    SELECT array_agg(url)
    FROM unnest(photo_urls) AS url
    WHERE url NOT LIKE '%_fullsize%'
      AND url NOT LIKE '%2dad6e28-0cf8-4233-bad5-c2ce2b5a024b%'
)
WHERE EXISTS (
    SELECT 1 FROM unnest(photo_urls) AS url
    WHERE url LIKE '%_fullsize%'
       OR url LIKE '%2dad6e28-0cf8-4233-bad5-c2ce2b5a024b%'
);
