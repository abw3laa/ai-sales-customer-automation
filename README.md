# AI Sales & Customer Automation System

A multi-channel customer engagement platform for sales qualification, conversation context, and human handoff. This repository is an early foundation, not a production-ready system.

## Initial scope

- FastAPI service with health and webhook-ingress endpoints.
- PostgreSQL as the durable data store.
- Separation between channel adapters, conversation logic, lead qualification, and human handoff.
- n8n workflows for orchestration where appropriate.
- Telegram-based operator controls, with authorization enforced server-side.
- Automated tests and CI.

## Development

Requirements: Python 3.11+ and Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

The API will be available at `http://localhost:8000`; OpenAPI docs at `/docs`; health check at `/healthz`.

For local Python development, create and activate a virtual environment, then run:

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

## Configuration and security

- Never commit credentials, access tokens, customer data, or production environment files.
- Provider webhook signatures must be verified before processing real messages. The current generic ingress endpoint is a scaffold and does not yet authenticate provider requests.
- Telegram operator commands must be restricted to explicitly configured authorized user IDs.
- Follow applicable platform policies, privacy requirements, and message-consent rules before launch.

## Project status

Phase 1: repository foundation and API skeleton. Channel integrations, durable conversation storage, AI orchestration, media understanding, lead scoring, operator controls, and production deployment are not yet implemented.

See `docs/ROADMAP_AR.md`, `docs/ARCHITECTURE.md`, and `docs/SECURITY.md`.
