# Architecture (initial)

## Components

- **API (FastAPI):** health checks and provider webhook ingress. Current ingress is a scaffold only.
- **Core domain:** conversation state, messages, lead qualification, consent, and human-handoff policies.
- **Channel adapters:** provider-specific signature validation, event normalization, media retrieval, and outbound delivery.
- **PostgreSQL:** durable source of truth for tenants, contacts, conversations, messages, leads, and audit events.
- **Worker/queue:** asynchronous AI calls, media transcription/understanding, retries, and outbound messages.
- **n8n:** optional workflow orchestration; it is not the source of truth for core state.
- **Telegram operator interface:** authorized human/AI mode controls and handoff notifications.

## Message lifecycle (target)

1. Receive provider webhook and verify its signature/token.
2. Normalize the provider event and deduplicate using provider event/message identifiers.
3. Load conversation, contact, consent, and current human/AI mode.
4. If human mode is active, avoid automated replies and route according to policy.
5. Persist inbound message before invoking AI or workflow services.
6. Build context from persisted conversation state; avoid asking again for known fields.
7. Generate a response and update lead qualification using explicit, testable rules.
8. Persist the response and delivery state, then send through the provider adapter.
9. Escalate when requested, confidence is low, or policy requires human review.

## Engineering constraints

- Enforce tenant boundaries in every query and background job.
- Webhook handlers should be idempotent and return quickly; slow tasks belong in a worker.
- Provider signatures, authorization, rate limits, retries, and audit logs are required before production.
- Secrets must be managed via environment/secret manager, never committed.
- Human/AI mode changes must be authenticated, authorized, and auditable.
