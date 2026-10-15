"""Secure Telegram channel-post ingestion endpoint."""
from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Header, HTTPException, Request

from core.catalog.parser import parse_catalog_post

router = APIRouter(prefix="/v1/webhooks/telegram", tags=["telegram-catalog"])


def _channel_tenant_map() -> dict[str, str]:
    result = {}
    for entry in os.getenv("TELEGRAM_CATALOG_TENANTS", "").split(","):
        if "=" in entry:
            channel_id, tenant_id = entry.split("=", 1)
            result[channel_id.strip()] = tenant_id.strip()
    return result


@router.post("/catalog", status_code=202)
async def receive_catalog_post(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    expected = os.getenv("TELEGRAM_CATALOG_WEBHOOK_SECRET") or os.getenv(
        "TELEGRAM_WEBHOOK_SECRET", ""
    )
    if (
        not expected
        or not x_telegram_bot_api_secret_token
        or not hmac.compare_digest(expected, x_telegram_bot_api_secret_token)
    ):
        raise HTTPException(status_code=401, detail="Invalid Telegram webhook secret")

    update = await request.json()
    message = update.get("channel_post") or update.get("edited_channel_post")
    if not message:
        return {"status": "ignored", "reason": "not_channel_post"}

    channel_id = str((message.get("chat") or {}).get("id", ""))
    tenant_id = _channel_tenant_map().get(channel_id)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Telegram channel is not mapped to a tenant")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured")

    update_id = update.get("update_id")
    message_id = message.get("message_id")
    if update_id is None or message_id is None:
        raise HTTPException(status_code=400, detail="Missing Telegram update/message ID")

    parsed = parse_catalog_post(message.get("text", ""), caption=message.get("caption", ""))
    try:
        import psycopg
        from psycopg.types.json import Jsonb
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="PostgreSQL driver is not installed") from exc

    media = message.get("photo") or []
    file_id = media[-1].get("file_id") if media else None
    parsed_payload = {
        "code": parsed.code,
        "title": parsed.title,
        "price": str(parsed.price) if parsed.price is not None else None,
        "currency": parsed.currency,
        "availability": parsed.availability,
        "status": parsed.status,
        "kind": parsed.kind,
        "attributes": parsed.attributes,
    }

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO product_ingestion_events
                (tenant_id, source_channel_id, source_update_id, source_message_id, status)
                VALUES (%s::uuid, %s, %s, %s, 'processing')
                ON CONFLICT (tenant_id, source_channel_id, source_update_id) DO NOTHING
                RETURNING id""",
                (tenant_id, channel_id, str(update_id), str(message_id)),
            )
            if cur.fetchone() is None:
                return {"status": "duplicate", "update_id": update_id}

            # Missing SKU/title cannot satisfy products' NOT NULL/unique contract.
            # Preserve the original post and parsed fields in a tenant-scoped review queue.
            if not parsed.code or not parsed.title:
                cur.execute(
                    """INSERT INTO product_review_queue
                    (tenant_id, source_channel_id, source_update_id, source_message_id,
                     proposed_sku, proposed_title, raw_text, parsed_payload, warnings)
                    VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        tenant_id, channel_id, str(update_id), str(message_id),
                        parsed.code, parsed.title, parsed.raw_text, Jsonb(parsed_payload),
                        Jsonb(list(parsed.warnings)),
                    ),
                )
                cur.execute(
                    """UPDATE product_ingestion_events
                    SET status='needs_review', error_code=%s, processed_at=now()
                    WHERE tenant_id=%s::uuid AND source_channel_id=%s AND source_update_id=%s""",
                    (
                        ",".join(parsed.warnings) or "incomplete_catalog_post",
                        tenant_id, channel_id, str(update_id),
                    ),
                )
                return {
                    "status": "needs_review",
                    "code": parsed.code,
                    "title": parsed.title,
                    "warnings": list(parsed.warnings),
                }

            cur.execute(
                """INSERT INTO products
                (tenant_id, sku, title, description, price, currency, availability, status,
                 attributes, source_channel_id, source_message_id, last_verified_at, updated_at)
                VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now())
                ON CONFLICT (tenant_id, sku) DO UPDATE SET
                 title=EXCLUDED.title, description=EXCLUDED.description, price=EXCLUDED.price,
                 currency=EXCLUDED.currency, availability=EXCLUDED.availability,
                 status=EXCLUDED.status, attributes=EXCLUDED.attributes,
                 source_channel_id=EXCLUDED.source_channel_id,
                 source_message_id=EXCLUDED.source_message_id,
                 last_verified_at=now(), updated_at=now()""",
                (
                    tenant_id, parsed.code, parsed.title, parsed.raw_text, parsed.price,
                    parsed.currency, parsed.availability, parsed.status, Jsonb(parsed.attributes),
                    channel_id, str(message_id),
                ),
            )
            cur.execute(
                """UPDATE product_review_queue
                SET status='resolved', updated_at=now()
                WHERE tenant_id=%s::uuid AND source_channel_id=%s AND source_message_id=%s
                  AND status='needs_review'""",
                (tenant_id, channel_id, str(message_id)),
            )
            cur.execute(
                """UPDATE product_ingestion_events SET status=%s, error_code=%s, processed_at=now()
                WHERE tenant_id=%s::uuid AND source_channel_id=%s AND source_update_id=%s""",
                (
                    "needs_review" if parsed.status != "active" else "processed",
                    ",".join(parsed.warnings) or None,
                    tenant_id, channel_id, str(update_id),
                ),
            )
            if file_id:
                cur.execute(
                    """INSERT INTO product_media (tenant_id, product_id, telegram_file_id, media_type)
                    SELECT %s::uuid, id, %s, 'photo' FROM products
                    WHERE tenant_id=%s::uuid AND sku=%s""",
                    (tenant_id, file_id, tenant_id, parsed.code),
                )

    return {
        "status": "processed" if parsed.status == "active" else "needs_review",
        "code": parsed.code,
        "kind": parsed.kind,
        "warnings": list(parsed.warnings),
    }
