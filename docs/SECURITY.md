# Security baseline

This checklist tracks implemented controls and remaining production work. Passing CI is not a production security certification.

## Implemented in the hardening branch

- Telegram catalog and operator webhook secrets are compared with `hmac.compare_digest`; missing configured secrets fail closed.
- Telegram webhook request bodies are capped at 256 KiB, including chunked bodies without a trustworthy `Content-Length`.
- Telegram JSON must be an object; selected nested message, chat, sender, text, caption, and photo fields receive type checks.
- Telegram operator commands require a server-side numeric user allowlist and a configured operator-to-tenant mapping.
- Migration runner refuses to replay all migrations against an existing application schema when the migration ledger is empty.
- Migration `0006` adds composite foreign keys to prevent cross-tenant channel/conversation/message/contact/lead relationships. The migration intentionally fails when pre-existing cross-tenant relationships are found.
- Docker Compose no longer silently supplies a default PostgreSQL password. The sample `.env` value is explicitly local-development-only.
- n8n image tag is pinned to `2.43.6` rather than `latest`; this tag still needs periodic review and patch updates.
- Database migration preflight, backup, baseline, and recovery steps are documented in `docs/DATABASE_MIGRATIONS.md`.

## Required before production

- Verify actual HTTPS termination and Telegram webhook registration, including secret handling at the proxy/load balancer.
- Add rate limiting at the edge or application layer; a body-size limit does not limit request rate.
- Review operator authorization, per-tenant configuration, and every database query that touches contacts, conversations, messages, media, leads, or audit records.
- Run the new tenant-constraint migration on a restored staging copy; investigate any migration failure rather than bypassing constraints.
- Test backups and restores, including a recovery drill after migrations that change or delete data.
- Configure n8n encryption key, authentication/owner setup, external URL, persistent storage, access policy, and backup. Do not expose its editor publicly without TLS and access controls.
- Add dependency and container vulnerability scanning, log redaction, monitoring/alerting, retention/deletion procedures, and incident response documentation.
- Implement provider-specific signature/replay checks and durable processing for non-Telegram channels before enabling them.
- Run integration and end-to-end tests on the release commit and conduct a staging pilot before connecting real customer accounts.

Never commit `.env`, access tokens, application secrets, customer messages, or production data. Do not treat a green CI run as proof that these operational controls are configured.
