-- Durable holding area for catalog posts that cannot yet become products.
-- This preserves posts with missing SKU/title instead of dropping them before deduplication.
CREATE TABLE IF NOT EXISTS product_review_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    source_channel_id TEXT NOT NULL,
    source_update_id TEXT NOT NULL,
    source_message_id TEXT NOT NULL,
    proposed_sku TEXT,
    proposed_title TEXT,
    raw_text TEXT NOT NULL DEFAULT '',
    parsed_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'needs_review'
        CHECK (status IN ('needs_review', 'resolved', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, source_channel_id, source_update_id)
);

CREATE INDEX IF NOT EXISTS idx_product_review_queue_pending
    ON product_review_queue (tenant_id, created_at DESC)
    WHERE status = 'needs_review';
