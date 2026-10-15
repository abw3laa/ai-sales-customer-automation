# Product catalog module

This module defines the initial product value object. It does not yet connect to Telegram or PostgreSQL.

The intended pipeline is:

1. Receive channel post from the Telegram Bot API webhook.
2. Validate the Telegram webhook secret and configured channel ID.
3. Normalize text/caption/media metadata.
4. Parse structured product fields; mark uncertain price/currency/SKU/offer dates as `needs_review`.
5. Upsert by tenant and SKU, recording the source channel/message and an idempotent ingestion event.
6. Make only active, current, tenant-scoped product records available to the answer-generation/retrieval layer.

The product database is the source of truth. Do not rely on the language model's conversation memory for current prices, stock, or offers.
