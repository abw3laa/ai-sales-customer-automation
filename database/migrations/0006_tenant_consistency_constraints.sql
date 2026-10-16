-- Enforce tenant consistency at the database boundary, not only in application queries.
-- Preflight existing rows and stop rather than silently rewriting tenant-owned data.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM conversations c
        JOIN channels ch ON ch.id = c.channel_id
        WHERE c.tenant_id <> ch.tenant_id
    ) THEN
        RAISE EXCEPTION 'Migration 0006 blocked: conversations reference channels owned by another tenant';
    END IF;

    IF EXISTS (
        SELECT 1 FROM conversations c
        JOIN contacts ct ON ct.id = c.contact_id
        WHERE c.contact_id IS NOT NULL AND c.tenant_id <> ct.tenant_id
    ) THEN
        RAISE EXCEPTION 'Migration 0006 blocked: conversations reference contacts owned by another tenant';
    END IF;

    IF EXISTS (
        SELECT 1 FROM messages m
        JOIN conversations c ON c.id = m.conversation_id
        WHERE m.tenant_id <> c.tenant_id
    ) THEN
        RAISE EXCEPTION 'Migration 0006 blocked: messages reference conversations owned by another tenant';
    END IF;

    IF EXISTS (
        SELECT 1 FROM leads l
        JOIN contacts ct ON ct.id = l.contact_id
        WHERE l.contact_id IS NOT NULL AND l.tenant_id <> ct.tenant_id
    ) THEN
        RAISE EXCEPTION 'Migration 0006 blocked: leads reference contacts owned by another tenant';
    END IF;

    IF EXISTS (
        SELECT 1 FROM leads l
        JOIN conversations c ON c.id = l.conversation_id
        WHERE l.conversation_id IS NOT NULL AND l.tenant_id <> c.tenant_id
    ) THEN
        RAISE EXCEPTION 'Migration 0006 blocked: leads reference conversations owned by another tenant';
    END IF;

    IF EXISTS (
        SELECT 1 FROM product_media pm
        JOIN products p ON p.id = pm.product_id
        WHERE pm.tenant_id <> p.tenant_id
    ) THEN
        RAISE EXCEPTION 'Migration 0006 blocked: product media references products owned by another tenant';
    END IF;
END $$;

-- Composite unique keys are required targets for tenant-scoped foreign keys.
ALTER TABLE channels ADD CONSTRAINT uq_channels_tenant_id_id UNIQUE (tenant_id, id);
ALTER TABLE contacts ADD CONSTRAINT uq_contacts_tenant_id_id UNIQUE (tenant_id, id);
ALTER TABLE conversations ADD CONSTRAINT uq_conversations_tenant_id_id UNIQUE (tenant_id, id);
ALTER TABLE products ADD CONSTRAINT uq_products_tenant_id_id UNIQUE (tenant_id, id);

ALTER TABLE conversations
    ADD CONSTRAINT fk_conversations_tenant_channel
    FOREIGN KEY (tenant_id, channel_id)
    REFERENCES channels (tenant_id, id) ON DELETE RESTRICT;

ALTER TABLE conversations
    ADD CONSTRAINT fk_conversations_tenant_contact
    FOREIGN KEY (tenant_id, contact_id)
    REFERENCES contacts (tenant_id, id) ON DELETE SET NULL (contact_id);

ALTER TABLE messages
    ADD CONSTRAINT fk_messages_tenant_conversation
    FOREIGN KEY (tenant_id, conversation_id)
    REFERENCES conversations (tenant_id, id) ON DELETE CASCADE;

ALTER TABLE leads
    ADD CONSTRAINT fk_leads_tenant_contact
    FOREIGN KEY (tenant_id, contact_id)
    REFERENCES contacts (tenant_id, id) ON DELETE SET NULL (contact_id);

ALTER TABLE leads
    ADD CONSTRAINT fk_leads_tenant_conversation
    FOREIGN KEY (tenant_id, conversation_id)
    REFERENCES conversations (tenant_id, id) ON DELETE SET NULL (conversation_id);

ALTER TABLE product_media
    ADD CONSTRAINT fk_product_media_tenant_product
    FOREIGN KEY (tenant_id, product_id)
    REFERENCES products (tenant_id, id) ON DELETE CASCADE;
