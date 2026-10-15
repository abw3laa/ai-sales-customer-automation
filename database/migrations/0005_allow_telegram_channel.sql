-- Telegram is a supported inbound/operator channel and must be representable
-- by the same channel registry used by conversations.
ALTER TABLE channels
    DROP CONSTRAINT IF EXISTS channels_provider_check;

ALTER TABLE channels
    ADD CONSTRAINT channels_provider_check
    CHECK (provider IN ('whatsapp', 'messenger', 'instagram', 'telegram'));
