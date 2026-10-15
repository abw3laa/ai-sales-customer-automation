# Telegram product catalog and operator bot

## Product concept

Use two separate Telegram surfaces with separate responsibilities:

1. **Product source channel**: an administrator publishes product posts containing a stable product code, name, price and currency, specifications, availability, offer dates, and optionally photos/documents. The application bot is added as a channel administrator with the minimum permissions needed to receive channel posts.
2. **Private operator bot chat**: authorized staff receive human-handoff alerts and can issue commands. The bot must verify Telegram numeric user IDs against a server-side allowlist before accepting any command.

A Telegram channel and a Telegram bot are different Telegram objects. The bot's private chat is not a shared group chat. For multi-operator collaboration, optionally add a private Telegram group later, while retaining an allowlist and audit log.

## Recommended ingestion flow

Telegram channel post -> webhook update -> verify Telegram secret token -> validate channel ID -> normalize post/caption/media -> parse structured product data -> persist product version -> acknowledge processing.

Do not make the language model the source of truth for prices or availability. Store products in PostgreSQL and retrieve matching, current records for answering customer questions. The model may explain stored details, but should not invent a price, discount, stock level, or specification.

## Publishing format

Prefer a structured template, for example:

```text
[PRODUCT]
Code: SKU-1001
Name: Product name
Price: 129.90 TRY
Availability: in_stock
Specifications:
- Color: black
- Warranty: 2 years
Offer ends: 2026-11-01
```

Natural-language posts and images can be supported, but any uncertain price, currency, SKU, or validity date should be marked for human review. Editing or deleting a Telegram post must update/deactivate the matching product record. Store Telegram channel ID and message ID as the source reference.

## Data model additions

- `products`: tenant, SKU, title, description, currency, price, availability, attributes JSON, status, validity window, source channel/message IDs, source revision, created/updated timestamps.
- `product_media`: product, Telegram file ID, media type, MIME type, optional durable object-storage reference.
- `product_ingestion_events`: tenant, channel ID, Telegram update/message ID, status, error, timestamps; unique key for idempotency.
- `operator_audit_log`: tenant, Telegram user ID, command, target conversation/product, result, timestamp.

Product SKU must be unique within a tenant. Money should be stored as NUMERIC/Decimal plus an explicit ISO currency code, never floating point.

## Operator commands (proposed)

- `/help`: show supported commands.
- `/human <conversation_id>`: transfer a conversation to a human.
- `/ai <conversation_id>`: return a conversation to AI mode.
- `/status <conversation_id>`: show mode and recent activity.
- `/product <SKU>`: show the current catalog record.
- `/reindex`: request catalog reprocessing, restricted to authorized operators.

Existing `sender-id/Human` and `sender-id/AI` syntax can be retained as an alias, but it must resolve an unambiguous tenant/channel/conversation and be authorized. Never trust a sender ID alone when multiple channels or tenants exist.

## Security and reliability

- Keep bot tokens in a secret manager/environment, never in source control or product posts.
- Validate Telegram webhook secret token, expected bot/channel IDs, and operator allowlist.
- Use idempotency keys and retry-safe processing.
- Escape untrusted content before rendering Telegram HTML/Markdown.
- Do not download media to a public location; validate file type and size.
- Log operator actions without logging secrets.
- Apply tenant scoping to every product lookup.
- On ambiguous catalog information, hand off to a human instead of guessing.

## Implementation stages

1. Add product tables and ingestion event idempotency.
2. Implement Telegram webhook receiver and signature/secret validation.
3. Normalize channel posts and structured product fields.
4. Add catalog search/retrieval service.
5. Implement operator bot commands, access control, notifications, and audit log.
6. Add image/media support and human review for uncertain extraction.
7. Test with a private staging channel and test bot before production.
