# Database migration and recovery runbook

This procedure is required before applying migrations to any database that contains business data.

## Rules

- Never point migration smoke tests at a production database.
- Take a verified backup and confirm the restore procedure before deploying a schema change.
- Do not create rows in `schema_migrations` manually just to make the migration runner proceed.
- Migration `0004_product_media_deduplication.sql` deletes duplicate media references. Review the affected rows before applying it to an existing database.
- Migration `0006_enforce_tenant_relationships.sql` deliberately fails if it finds relationships that cross tenant boundaries. Repair those records explicitly; do not disable the constraints to force deployment.

## Inspect duplicate Telegram media before migration 0004

Run this query against a read-only session or a restored copy first:

```sql
SELECT tenant_id, product_id, telegram_file_id, count(*) AS duplicate_count,
       array_agg(id ORDER BY created_at, id) AS media_ids
FROM product_media
WHERE telegram_file_id IS NOT NULL
GROUP BY tenant_id, product_id, telegram_file_id
HAVING count(*) > 1
ORDER BY duplicate_count DESC;
```

The migration retains the oldest reference per tenant/product/file ID and deletes the remaining rows. Export the query result and obtain approval before applying it if any business data is present.

## Check tenant relationship violations before migration 0006

```sql
SELECT 'conversation_channel' AS relation, count(*) AS violations
FROM conversations c JOIN channels ch ON ch.id = c.channel_id
WHERE c.tenant_id <> ch.tenant_id
UNION ALL
SELECT 'conversation_contact', count(*)
FROM conversations c JOIN contacts co ON co.id = c.contact_id
WHERE c.contact_id IS NOT NULL AND c.tenant_id <> co.tenant_id
UNION ALL
SELECT 'message_conversation', count(*)
FROM messages m JOIN conversations c ON c.id = m.conversation_id
WHERE m.tenant_id <> c.tenant_id
UNION ALL
SELECT 'lead_contact', count(*)
FROM leads l JOIN contacts co ON co.id = l.contact_id
WHERE l.contact_id IS NOT NULL AND l.tenant_id <> co.tenant_id
UNION ALL
SELECT 'lead_conversation', count(*)
FROM leads l JOIN conversations c ON c.id = l.conversation_id
WHERE l.conversation_id IS NOT NULL AND l.tenant_id <> c.tenant_id;
```

All counts must be zero before applying migration 0006.

## Existing databases without a migration ledger

The migration runner refuses to apply all numbered migrations when it finds application tables but an empty `schema_migrations` ledger. This avoids blindly replaying the full migration history against a pre-existing schema.

For such a database:

1. Take and verify a backup.
2. Restore a copy into an isolated staging database.
3. Compare the actual schema and constraints with the full migration history.
4. Determine the exact baseline only after the comparison is reviewed.
5. Record a reviewed baseline using a separately tested, auditable procedure. Do not guess that every migration has already run.
6. Run the remaining migrations against the restored copy and test the application before production rollout.

The repository intentionally does not automatically baseline an existing database because the correct baseline cannot be inferred safely from the presence of a few tables.

## Rollout and recovery checklist

1. Record the current database version and migration ledger.
2. Back up the database and verify that a restore succeeds in staging.
3. Run preflight queries above and retain the output.
4. Apply migrations during a controlled deployment window.
5. Verify `schema_migrations`, application health, tenant-scoped reads/writes, and Telegram ingestion.
6. If a migration fails, stop rollout and investigate. Do not delete ledger rows or manually drop constraints as a first response.
7. Prefer restoring the verified backup when a data-changing migration cannot be safely reversed.
