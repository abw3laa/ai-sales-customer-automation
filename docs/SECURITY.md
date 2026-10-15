# Security baseline

This checklist is a work in progress; the project is not production-ready.

- Do not commit `.env`, access tokens, app secrets, customer messages, or production data.
- Verify webhook signatures and replay/timestamp rules for each provider before processing events.
- Authorize Telegram commands against a server-side allowlist of numeric user IDs; never trust a sender ID supplied in command text alone.
- Enforce tenant-scoped access checks for contacts, conversations, media, and audit events.
- Validate payload sizes and types; limit media downloads, timeouts, and content types.
- Redact secrets and sensitive customer content from logs.
- Apply rate limits, retries with backoff, idempotency, and dead-letter handling.
- Encrypt traffic in transit; restrict database/network exposure; use managed secrets in deployment.
- Define retention, deletion, consent, and data export procedures before commercial launch.
- Add dependency scanning, backup/restore drills, access review, and incident response documentation.
