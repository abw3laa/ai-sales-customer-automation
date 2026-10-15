-- PostgreSQL schema for the AI Sales & Customer Automation platform.
-- Apply with a migration runner; do not execute automatically in production.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    provider TEXT NOT NULL CHECK (provider IN ('whatsapp', 'messenger', 'instagram')),
    external_account_id TEXT NOT NULL,
    display_name TEXT,
    credentials_ref TEXT,
    is_active BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, provider, external_account_id)
);

CREATE TABLE IF NOT EXISTS contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    full_name TEXT,
    phone_e164 TEXT,
    email TEXT,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, phone_e164),
    UNIQUE (tenant_id, email)
);

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE RESTRICT,
    contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,
    external_sender_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'pending', 'closed')),
    control_mode TEXT NOT NULL DEFAULT 'ai' CHECK (control_mode IN ('ai', 'human')),
    summary TEXT,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_message_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (channel_id, external_sender_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    provider_message_id TEXT,
    direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    message_type TEXT NOT NULL CHECK (message_type IN ('text', 'audio', 'image', 'file', 'interactive', 'unknown')),
    text_content TEXT,
    media_ref TEXT,
    media_mime_type TEXT,
    transcription TEXT,
    analysis JSONB NOT NULL DEFAULT '{}'::jsonb,
    processing_status TEXT NOT NULL DEFAULT 'received'
        CHECK (processing_status IN ('received', 'processing', 'processed', 'ignored', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ,
    UNIQUE (tenant_id, provider_message_id)
);

CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    service_interest TEXT,
    stage TEXT NOT NULL DEFAULT 'new'
        CHECK (stage IN ('new', 'qualified', 'contacted', 'won', 'lost', 'disqualified')),
    temperature TEXT NOT NULL DEFAULT 'cold' CHECK (temperature IN ('cold', 'warm', 'hot')),
    score SMALLINT NOT NULL DEFAULT 0 CHECK (score BETWEEN 0 AND 100),
    score_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    collected_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    assigned_to TEXT,
    next_follow_up_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conversations_tenant_updated
    ON conversations (tenant_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_created
    ON messages (conversation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_unprocessed
    ON messages (processing_status, created_at) WHERE processing_status IN ('received', 'failed');
CREATE INDEX IF NOT EXISTS idx_leads_tenant_temperature
    ON leads (tenant_id, temperature, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_leads_follow_up
    ON leads (tenant_id, next_follow_up_at) WHERE next_follow_up_at IS NOT NULL;

-- Keep tenant_id on all tenant-owned records to support explicit tenant scoping.
-- Add PostgreSQL row-level security policies before exposing the database to multiple customers.
