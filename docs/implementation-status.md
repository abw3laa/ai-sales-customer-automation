# Implementation status

This file is the source of truth for implementation progress.

## Foundation

- [x] Repository baseline and API skeleton (see existing project files).
- [x] Initial tenant-aware PostgreSQL schema.
- [x] Explainable lead-scoring policy.
- [x] Unit tests for scoring and human-request routing signal.
- [x] Data-model invariants and security notes.

## Next implementation gates

- [ ] Inspect and reconcile the existing API package and dependency configuration with the new domain module.
- [ ] Add migration execution and database repository layer.
- [ ] Implement tenant/channel resolution and webhook signature verification.
- [ ] Implement durable inbound event ingestion and idempotent message processing.
- [ ] Implement conversation context storage and contact-field extraction.
- [ ] Implement transactional human/AI mode changes and an outbound-send guard.
- [ ] Add authenticated Telegram operator commands and notifications.
- [ ] Add provider adapters and media processing.
- [ ] Add integration and end-to-end tests.
- [ ] Validate CI on GitHub Actions.
- [ ] Deploy to staging and test with sandbox accounts.

## Release rule

Do not connect production customer accounts or advertise the system as production-ready until security review, tenant isolation tests, provider webhook verification, idempotency tests, backup/restore tests, and human-handoff end-to-end tests pass.
