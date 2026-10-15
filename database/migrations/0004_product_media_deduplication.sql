-- Keep the oldest reference for each repeated Telegram photo before adding uniqueness.
-- Earlier versions could insert the same file_id every time a channel post was edited.
WITH ranked AS (
    SELECT ctid,
           row_number() OVER (
               PARTITION BY tenant_id, product_id, telegram_file_id
               ORDER BY created_at, id
           ) AS position
    FROM product_media
    WHERE telegram_file_id IS NOT NULL
)
DELETE FROM product_media AS media
USING ranked
WHERE media.ctid = ranked.ctid
  AND ranked.position > 1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_product_media_telegram_file
    ON product_media (tenant_id, product_id, telegram_file_id)
    WHERE telegram_file_id IS NOT NULL;
