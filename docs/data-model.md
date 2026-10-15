# Data model

The initial PostgreSQL schema is in `database/migrations/0001_initial.sql`.

## Core entities

- **Tenant**: a business account. Tenant scoping is mandatory for all customer data.
- **Channel**: one connected WhatsApp, Messenger, or Instagram account owned by a tenant. Credentials are referenced by secret-manager key; tokens must not be stored in this table.
- **Contact**: known customer identity and structured attributes.
- **Conversation**: a channel-specific thread for an external sender. `control_mode` is `ai` or `human`.
- **Message**: inbound/outbound event, media metadata, transcription, processing state, and provider idempotency key.
- **Lead**: qualification stage, temperature, score, reasons, collected fields, and follow-up time.

## Required invariants

1. Resolve tenant and channel from trusted integration configuration, never from an untrusted webhook body alone.
2. Enforce tenant scoping in every repository query. Before production, enable and test PostgreSQL row-level security.
3. Verify webhook signatures before accepting events; verify Telegram operator identity before accepting control commands.
4. Deduplicate provider events by provider message ID. If a provider does not supply a stable ID, derive a documented idempotency key.
5. Check conversation control mode immediately before sending an AI response. Human mode must suppress AI outbound messages.
6. Do not store raw access tokens, API keys, or Telegram bot tokens in application tables or logs.
7. Retain only the media and personal data needed for the configured business purpose; define tenant-configurable retention before launch.

## Lead qualification

The initial scoring policy should be transparent and configurable. It is a heuristic, not an AI model's unreviewed assertion. Persist both the score and its reasons so operators can understand why a lead was marked cold, warm, or hot.

## Migration policy

Apply migrations in order using a migration runner or a controlled release step. Back up production before schema changes. Do not rely on application startup to mutate production schemas.
