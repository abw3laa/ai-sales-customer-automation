-- Enforce tenant consistency in relationships that were previously protected only
-- by application-level predicates. This intentionally fails if legacy rows cross
-- tenant boundaries; repair those rows before retrying the migration.
DO $$
DECLARE
    bad_count BIGINT;
BEGIN
    SELECT count(*) INTO bad_count
    FROM conversations c
    JOIN channels ch ON ch.id = c.channel_id
    WHERE c.tenant_id <> ch.tenant_id;
    IF bad_count > 0 THEN
        RAISE EXCEPTION 'Migration 0006 blocked: % conversations reference another tenant channel', bad_count;
    END IF;

    SELECT count(*) INTO bad_count
    FROM conversations c
    JOIN contacts co ON co.id = c.contact_id
    WHERE c.contact_id IS NOT NULL AND c.tenant_id <> co.tenant_id;
    IF bad_count > 0 THEN
        RAISE EXCEPTION 'Migration 0006 blocked: % conversations reference another tenant contact', bad_count;
    END IF;

    SELECT count(*) INTO bad_count
    FROM messages m
    JOIN conversations c ON c.id = m.conversation_id
    WHERE m.tenant_id <> c.tenant_id;
    IF bad_count > 0 THEN
        RAISE EXCEPTION 'Migration 0006 blocked: % messages reference another tenant conversation', bad_count;
    END IF;

    SELECT count(*) INTO bad_count
    FROM leads l
    JOIN contacts c ON c.id = l.contact_id
    WHERE l.contact_id IS NOT NULL AND l.tenant_id <> c.tenant_id;
    IF bad_count > 0 THEN
        RAISE EXCEPTION 'Migration 0006 blocked: % leads reference another tenant contact', bad_count;
    END IF;

    SELECT count(*) INTO bad_count
    FROM leads l
    JOIN conversations c ON c.id = l.conversation_id
    WHERE l.conversation_id IS NOT NULL AND l.tenant_id <> c.tenant_id;
    IF bad_count > 0 THEN
        RAISE EXCEPTION 'Migration 0006 blocked: % leads reference another tenant conversation', bad_count;
    END IF;

    SELECT count(*) INTO bad_count
    FROM product_media pm
    JOIN products p ON p.id = pm.product_id
    WHERE pm.tenant_id <> p.tenant_id;
    IF bad_count > 0 THEN
        RAISE EXCEPTION 'Migration 0006 blocked: % media rows reference another tenant product', bad_count;
    END IF;
END $$;

ALTER TABLE channels
    ADD CONSTRAINT channels_tenant_id_id_key UNIQUE (tenant_id, id);
ALTER TABLE contacts
    ADD CONSTRAINT contacts_tenant_id_id_key UNIQUE (tenant_id, id);
ALTER TABLE conversations
    ADD CONSTRAINT conversations_tenant_id_id_key UNIQUE (tenant_id, id);
ALTER TABLE products
    ADD CONSTRAINT products_tenant_id_id_key UNIQUE (tenant_id, id);

ALTER TABLE conversations
    DROP CONSTRAINT IF EXISTS conversations_channel_id_fkey;
ALTER TABLE conversations
    ADD CONSTRAINT conversations_tenant_channel_fkey
    FOREIGN KEY (tenant_id, channel_id)
    REFERENCES channels (tenant_id, id) ON DELETE RESTRICT;

ALTER TABLE conversations
    DROP CONSTRAINT IF EXISTS conversations_contact_id_fkey;
ALTER TABLE conversations
    ADD CONSTRAINT conversations_tenant_contact_fkey
    FOREIGN KEY (tenant_id, contact_id)
    REFERENCES contacts (tenant_id, id) ON DELETE SET NULL (contact_id);

ALTER TABLE messages
    DROP CONSTRAINT IF EXISTS messages_conversation_id_fkey;
ALTER TABLE messages
    ADD CONSTRAINT messages_tenant_conversation_fkey
    FOREIGN KEY (tenant_id, conversation_id)
    REFERENCES conversations (tenant_id, id) ON DELETE CASCADE;

ALTER TABLE leads
    DROP CONSTRAINT IF EXISTS leads_contact_id_fkey;
ALTER TABLE leads
    ADD CONSTRAINT leads_tenant_contact_fkey
    FOREIGN KEY (tenant_id, contact_id)
    REFERENCES contacts (tenant_id, id) ON DELETE SET NULL (contact_id);

ALTER TABLE leads
    DROP CONSTRAINT IF EXISTS leads_conversation_id_fkey;
ALTER TABLE leads
    ADD CONSTRAINT leads_tenant_conversation_fkey
    FOREIGN KEY (tenant_id, conversation_id)
    REFERENCES conversations (tenant_id, id) ON DELETE SET NULL (conversation_id);

ALTER TABLE product_media
    ADD CONSTRAINT product_media_tenant_product_fkey
    FOREIGN KEY (tenant_id, product_id)
    REFERENCES products (tenant_id, id) ON DELETE CASCADE;
