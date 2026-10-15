-- Product catalog sourced from administrator-owned Telegram channel posts.
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    sku TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    price NUMERIC(14, 2),
    currency CHAR(3),
    availability TEXT NOT NULL DEFAULT 'unknown'
        CHECK (availability IN ('in_stock', 'out_of_stock', 'preorder', 'discontinued', 'unknown')),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'draft', 'needs_review', 'archived')),
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    offer_starts_at TIMESTAMPTZ,
    offer_ends_at TIMESTAMPTZ,
    source_channel_id TEXT,
    source_message_id TEXT,
    source_revision BIGINT,
    last_verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, sku),
    CHECK ((price IS NULL AND currency IS NULL) OR (price IS NOT NULL AND currency IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS product_media (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    telegram_file_id TEXT,
    media_type TEXT NOT NULL CHECK (media_type IN ('photo', 'video', 'document', 'audio', 'other')),
    mime_type TEXT,
    object_storage_ref TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (telegram_file_id IS NOT NULL OR object_storage_ref IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS product_ingestion_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    source_channel_id TEXT NOT NULL,
    source_update_id TEXT NOT NULL,
    source_message_id TEXT,
    status TEXT NOT NULL DEFAULT 'received'
        CHECK (status IN ('received', 'processing', 'processed', 'needs_review', 'failed', 'ignored')),
    error_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ,
    UNIQUE (tenant_id, source_channel_id, source_update_id)
);

CREATE TABLE IF NOT EXISTS operator_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    telegram_user_id TEXT NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    result TEXT NOT NULL CHECK (result IN ('success', 'denied', 'failed')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_products_tenant_status_title
    ON products (tenant_id, status, title);
CREATE INDEX IF NOT EXISTS idx_products_source_message
    ON products (tenant_id, source_channel_id, source_message_id);
CREATE INDEX IF NOT EXISTS idx_product_ingestion_pending
    ON product_ingestion_events (status, created_at)
    WHERE status IN ('received', 'failed');
CREATE INDEX IF NOT EXISTS idx_operator_audit_tenant_created
    ON operator_audit_log (tenant_id, created_at DESC);
