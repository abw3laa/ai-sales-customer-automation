"""PostgreSQL persistence and tenant-scoped retrieval for the product catalog."""
from __future__ import annotations

import json
from typing import Any

from core.catalog.models import ProductRecord


class CatalogRepository:
    """Small psycopg-backed repository. Pass an open psycopg connection."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def upsert_product(self, product: ProductRecord) -> str:
        product.validate()
        from psycopg.types.json import Jsonb

        query = """
        INSERT INTO products (
            tenant_id, sku, title, description, price, currency, availability, status,
            attributes, offer_starts_at, offer_ends_at, source_channel_id,
            source_message_id, source_revision, last_verified_at, updated_at
        ) VALUES (
            %(tenant_id)s, %(sku)s, %(title)s, %(description)s, %(price)s, %(currency)s,
            %(availability)s, %(status)s, %(attributes)s, %(offer_starts_at)s,
            %(offer_ends_at)s, %(source_channel_id)s, %(source_message_id)s,
            %(source_revision)s, now(), now()
        )
        ON CONFLICT (tenant_id, sku) DO UPDATE SET
            title = EXCLUDED.title, description = EXCLUDED.description,
            price = EXCLUDED.price, currency = EXCLUDED.currency,
            availability = EXCLUDED.availability, status = EXCLUDED.status,
            attributes = EXCLUDED.attributes, offer_starts_at = EXCLUDED.offer_starts_at,
            offer_ends_at = EXCLUDED.offer_ends_at, source_channel_id = EXCLUDED.source_channel_id,
            source_message_id = EXCLUDED.source_message_id, source_revision = EXCLUDED.source_revision,
            last_verified_at = now(), updated_at = now()
        RETURNING id::text
        """
        values = {
            "tenant_id": product.tenant_id, "sku": product.sku, "title": product.title,
            "description": product.description, "price": product.price, "currency": product.currency,
            "availability": product.availability, "status": product.status,
            "attributes": Jsonb(product.attributes or {}),
            "offer_starts_at": product.offer_starts_at, "offer_ends_at": product.offer_ends_at,
            "source_channel_id": product.source_channel_id, "source_message_id": product.source_message_id,
            "source_revision": None,
        }
        with self.connection.cursor() as cur:
            cur.execute(query, values)
            row = cur.fetchone()
        return row[0]

    def search(self, *, tenant_id: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search only active records belonging to the specified tenant."""
        if not tenant_id.strip():
            raise ValueError("tenant_id is required")
        limit = max(1, min(limit, 20))
        sql = """
        SELECT sku, title, description, price::text AS price, currency,
               availability, attributes, offer_starts_at, offer_ends_at
        FROM products
        WHERE tenant_id = %s::uuid AND status = 'active'
          AND (offer_ends_at IS NULL OR offer_ends_at > now())
          AND (
            sku ILIKE %s OR title ILIKE %s OR COALESCE(description, '') ILIKE %s
            OR attributes::text ILIKE %s
          )
        ORDER BY CASE WHEN sku ILIKE %s THEN 0 ELSE 1 END, updated_at DESC
        LIMIT %s
        """
        needle = f"%{query.strip()}%"
        with self.connection.cursor() as cur:
            cur.execute(sql, (tenant_id, needle, needle, needle, needle, query.strip(), limit))
            columns = [d.name for d in cur.description]
            return [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]
