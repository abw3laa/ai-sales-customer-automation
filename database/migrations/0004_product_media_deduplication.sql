-- Prevent duplicate Telegram photo references when a post is edited or retried.
-- NULL object-storage references are unaffected; the index only covers Telegram file IDs.
CREATE UNIQUE INDEX IF NOT EXISTS uq_product_media_telegram_file
    ON product_media (tenant_id, product_id, telegram_file_id)
    WHERE telegram_file_id IS NOT NULL;
