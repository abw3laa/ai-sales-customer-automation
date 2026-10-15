from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app

MIGRATIONS = sorted((Path(__file__).parents[2] / "database" / "migrations").glob("*.sql"))
DATABASE_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")


@pytest.fixture(scope="session")
def postgres_schema():
    if not DATABASE_URL:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests")
    migration_env = os.environ.copy()
    migration_env["DATABASE_URL"] = DATABASE_URL
    subprocess.run(
        [sys.executable, "scripts/migrate.py"],
        check=True,
        env=migration_env,
        capture_output=True,
        text=True,
    )
    # A second pass verifies that the migration ledger skips already-applied files.
    second_pass = subprocess.run(
        [sys.executable, "scripts/migrate.py"],
        check=True,
        env=migration_env,
        capture_output=True,
        text=True,
    )
    assert "SKIP 0004_product_media_deduplication.sql" in second_pass.stdout
    return DATABASE_URL


@pytest.fixture
def tenant(postgres_schema):
    tenant_id = str(uuid4())
    with psycopg.connect(postgres_schema) as conn:
        conn.execute(
            "INSERT INTO tenants (id, name, slug) VALUES (%s::uuid, %s, %s)",
            (tenant_id, "Integration Test", f"test-{tenant_id}"),
        )
    yield tenant_id
    with psycopg.connect(postgres_schema) as conn:
        conn.execute("DELETE FROM tenants WHERE id=%s::uuid", (tenant_id,))


def _telegram_update(update_id: int, channel_id: int, message_id: int, text: str) -> dict:
    return {
        "update_id": update_id,
        "channel_post": {
            "message_id": message_id,
            "chat": {"id": channel_id, "type": "channel"},
            "text": text,
        },
    }


def test_catalog_webhook_auth_and_tenant_mapping(monkeypatch, tenant, postgres_schema):
    monkeypatch.setenv("DATABASE_URL", postgres_schema)
    monkeypatch.setenv("TELEGRAM_CATALOG_WEBHOOK_SECRET", "integration-secret")
    monkeypatch.setenv("TELEGRAM_CATALOG_TENANTS", f"-100123={tenant}")
    client = TestClient(app)
    payload = _telegram_update(9001, -100123, 501, "الكود: A501\nاسم المنتج: بجامة رياضية adidas\nالسعر: 1200 TRY")

    assert client.post("/v1/webhooks/telegram/catalog", json=payload).status_code == 401
    forbidden = client.post(
        "/v1/webhooks/telegram/catalog",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "integration-secret"},
    )
    assert forbidden.status_code == 202
    assert forbidden.json()["status"] == "needs_review"

    unmapped = client.post(
        "/v1/webhooks/telegram/catalog",
        json=_telegram_update(9002, -100999, 502, "الكود: A502\nالاسم: منتج\nالسعر: 100 TRY"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "integration-secret"},
    )
    assert unmapped.status_code == 403


def test_missing_sku_is_persisted_for_review_and_deduplicated(
    monkeypatch, tenant, postgres_schema
):
    monkeypatch.setenv("DATABASE_URL", postgres_schema)
    monkeypatch.setenv("TELEGRAM_CATALOG_WEBHOOK_SECRET", "integration-secret")
    monkeypatch.setenv("TELEGRAM_CATALOG_TENANTS", f"-100124={tenant}")
    client = TestClient(app)
    payload = _telegram_update(9101, -100124, 601, "بجامة رياضية adidas\nالسعر: 1200 TRY")
    headers = {"X-Telegram-Bot-Api-Secret-Token": "integration-secret"}

    response = client.post("/v1/webhooks/telegram/catalog", json=payload, headers=headers)
    assert response.status_code == 202
    assert response.json()["status"] == "needs_review"
    assert "missing_code" in response.json()["warnings"]

    duplicate = client.post("/v1/webhooks/telegram/catalog", json=payload, headers=headers)
    assert duplicate.json()["status"] == "duplicate"

    with psycopg.connect(postgres_schema) as conn:
        queued = conn.execute(
            """SELECT status, proposed_sku FROM product_review_queue
            WHERE tenant_id=%s::uuid AND source_update_id='9101'""",
            (tenant,),
        ).fetchone()
        event = conn.execute(
            """SELECT status FROM product_ingestion_events
            WHERE tenant_id=%s::uuid AND source_update_id='9101'""",
            (tenant,),
        ).fetchone()
    assert queued == ("needs_review", None)
    assert event == ("needs_review",)


def test_product_with_missing_price_cannot_be_approved(monkeypatch, tenant, postgres_schema):
    monkeypatch.setenv("DATABASE_URL", postgres_schema)
    monkeypatch.setenv("TELEGRAM_CATALOG_WEBHOOK_SECRET", "integration-secret")
    monkeypatch.setenv("TELEGRAM_CATALOG_TENANTS", f"-100125={tenant}")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "777")
    monkeypatch.setenv("TELEGRAM_OPERATOR_TENANTS", f"777={tenant}")
    monkeypatch.setenv("TELEGRAM_OPERATOR_WEBHOOK_SECRET", "operator-secret")
    client = TestClient(app)

    payload = _telegram_update(9201, -100125, 701, "الكود: A701\nاسم المنتج: بجامة رياضية adidas")
    catalog_response = client.post(
        "/v1/webhooks/telegram/catalog",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "integration-secret"},
    )
    assert catalog_response.json()["status"] == "needs_review"

    operator_response = client.post(
        "/v1/webhooks/telegram/operator",
        json={
            "message": {
                "chat": {"id": 777, "type": "private"},
                "from": {"id": 777},
                "text": "/approve A701",
            }
        },
        headers={"X-Telegram-Bot-Api-Secret-Token": "operator-secret"},
    )
    assert "السعر والعملة" in operator_response.json()["text"]

    with psycopg.connect(postgres_schema) as conn:
        row = conn.execute(
            "SELECT status, price, currency FROM products WHERE tenant_id=%s::uuid AND sku='A701'",
            (tenant,),
        ).fetchone()
    assert row == ("needs_review", None, None)


def test_approved_product_is_audited_and_becomes_searchable(monkeypatch, tenant, postgres_schema):
    monkeypatch.setenv("DATABASE_URL", postgres_schema)
    monkeypatch.setenv("TELEGRAM_CATALOG_WEBHOOK_SECRET", "integration-secret")
    monkeypatch.setenv("TELEGRAM_CATALOG_TENANTS", f"-100126={tenant}")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "778")
    monkeypatch.setenv("TELEGRAM_OPERATOR_TENANTS", f"778={tenant}")
    monkeypatch.setenv("TELEGRAM_OPERATOR_WEBHOOK_SECRET", "operator-secret")
    client = TestClient(app)
    headers = {"X-Telegram-Bot-Api-Secret-Token": "integration-secret"}

    payload = _telegram_update(
        9301, -100126, 801,
        "الكود: A801\nاسم المنتج: بجامة رياضية adidas\nالسعر: 1200 TRY",
    )
    ingested = client.post("/v1/webhooks/telegram/catalog", json=payload, headers=headers)
    assert ingested.json()["status"] == "needs_review"

    approved = client.post(
        "/v1/webhooks/telegram/operator",
        json={
            "message": {
                "chat": {"id": 778, "type": "private"},
                "from": {"id": 778},
                "text": "/approve A801",
            }
        },
        headers={"X-Telegram-Bot-Api-Secret-Token": "operator-secret"},
    )
    assert "تم اعتماد المنتج A801" in approved.json()["text"]

    with psycopg.connect(postgres_schema) as conn:
        product = conn.execute(
            "SELECT status FROM products WHERE tenant_id=%s::uuid AND sku='A801'",
            (tenant,),
        ).fetchone()
        audit = conn.execute(
            """SELECT action, result FROM operator_audit_log
            WHERE tenant_id=%s::uuid AND target_id='A801' ORDER BY created_at DESC LIMIT 1""",
            (tenant,),
        ).fetchone()
    assert product == ("active",)
    assert audit == ("approve_product", "success")


def test_edited_post_resolves_previous_review_and_deduplicates_media(
    monkeypatch, tenant, postgres_schema
):
    monkeypatch.setenv("DATABASE_URL", postgres_schema)
    monkeypatch.setenv("TELEGRAM_CATALOG_WEBHOOK_SECRET", "integration-secret")
    monkeypatch.setenv("TELEGRAM_CATALOG_TENANTS", f"-100127={tenant}")
    client = TestClient(app)
    headers = {"X-Telegram-Bot-Api-Secret-Token": "integration-secret"}

    incomplete = _telegram_update(9401, -100127, 901, "بجامة رياضية adidas\nالسعر: 1200 TRY")
    first = client.post("/v1/webhooks/telegram/catalog", json=incomplete, headers=headers)
    assert first.json()["status"] == "needs_review"

    edited = {
        "update_id": 9402,
        "edited_channel_post": {
            "message_id": 901,
            "chat": {"id": -100127, "type": "channel"},
            "text": "الكود: A901\nاسم المنتج: بجامة رياضية adidas\nالسعر: 1200 TRY",
            "photo": [{"file_id": "telegram-photo-901"}],
        },
    }
    second = client.post("/v1/webhooks/telegram/catalog", json=edited, headers=headers)
    assert second.json()["status"] == "needs_review"

    edited_again = {
        "update_id": 9403,
        "edited_channel_post": edited["edited_channel_post"],
    }
    third = client.post("/v1/webhooks/telegram/catalog", json=edited_again, headers=headers)
    assert third.json()["status"] == "needs_review"

    with psycopg.connect(postgres_schema) as conn:
        queue_statuses = conn.execute(
            """SELECT status FROM product_review_queue
            WHERE tenant_id=%s::uuid AND source_channel_id='-100127'
              AND source_message_id='901' ORDER BY source_update_id""",
            (tenant,),
        ).fetchall()
        product_status = conn.execute(
            """SELECT status FROM products
            WHERE tenant_id=%s::uuid AND sku='A901'""",
            (tenant,),
        ).fetchone()
        media_count = conn.execute(
            """SELECT count(*) FROM product_media
            WHERE tenant_id=%s::uuid AND telegram_file_id='telegram-photo-901'""",
            (tenant,),
        ).fetchone()[0]

    # Only incomplete posts belong in product_review_queue. Once edited with a
    # SKU and title, that queue item is resolved and the product awaits approval
    # in products.status='needs_review'.
    assert queue_statuses == [("resolved",)]
    assert product_status == ("needs_review",)
    assert media_count == 1


def test_catalog_webhook_rejects_non_object_and_invalid_json(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CATALOG_WEBHOOK_SECRET", "integration-secret")
    client = TestClient(app)
    headers = {"X-Telegram-Bot-Api-Secret-Token": "integration-secret"}

    invalid_json = client.post(
        "/v1/webhooks/telegram/catalog",
        content=b"{",
        headers={**headers, "Content-Type": "application/json"},
    )
    non_object = client.post(
        "/v1/webhooks/telegram/catalog",
        json=["not", "an", "object"],
        headers=headers,
    )

    assert invalid_json.status_code == 400
    assert non_object.status_code == 400


def test_schema_accepts_telegram_as_a_conversation_channel(tenant, postgres_schema):
    with psycopg.connect(postgres_schema) as conn:
        row = conn.execute(
            """INSERT INTO channels (tenant_id, provider, external_account_id, display_name)
            VALUES (%s::uuid, 'telegram', '-100987', 'Integration Telegram')
            RETURNING provider, external_account_id""",
            (tenant,),
        ).fetchone()
    assert row == ("telegram", "-100987")


def test_catalog_webhook_persists_offer_validity(monkeypatch, tenant, postgres_schema):
    monkeypatch.setenv("DATABASE_URL", postgres_schema)
    monkeypatch.setenv("TELEGRAM_CATALOG_WEBHOOK_SECRET", "integration-secret")
    monkeypatch.setenv("TELEGRAM_CATALOG_TENANTS", f"-100128={tenant}")
    client = TestClient(app)
    response = client.post(
        "/v1/webhooks/telegram/catalog",
        json=_telegram_update(
            9501,
            -100128,
            951,
            """Code: A951
Name: Adidas tracksuit offer
Price: 900 TRY
Offer starts: 2026-10-20
Offer ends: 2026-10-31T23:59:00+03:00""",
        ),
        headers={"X-Telegram-Bot-Api-Secret-Token": "integration-secret"},
    )
    assert response.status_code == 202
    with psycopg.connect(postgres_schema) as conn:
        row = conn.execute(
            """SELECT offer_starts_at, offer_ends_at FROM products
            WHERE tenant_id=%s::uuid AND sku='A951'""",
            (tenant,),
        ).fetchone()
    assert row is not None
    assert row[0].isoformat() == "2026-10-20T00:00:00+00:00"
    assert row[1].isoformat() == "2026-10-31T20:59:00+00:00"


def test_product_lookup_is_isolated_by_tenant(postgres_schema):
    from integrations.telegram.operator_catalog import lookup_product

    tenant_a, tenant_b = str(uuid4()), str(uuid4())
    with psycopg.connect(postgres_schema) as conn:
        conn.execute(
            "INSERT INTO tenants (id, name, slug) VALUES (%s::uuid, %s, %s), (%s::uuid, %s, %s)",
            (tenant_a, "Tenant A", f"test-{tenant_a}", tenant_b, "Tenant B", f"test-{tenant_b}"),
        )
        conn.execute(
            """INSERT INTO products (tenant_id, sku, title, price, currency, status)
            VALUES (%s::uuid, 'SHARED-SKU', 'Tenant A Product', 10, 'TRY', 'active'),
                   (%s::uuid, 'SHARED-SKU', 'Tenant B Product', 20, 'TRY', 'active')""",
            (tenant_a, tenant_b),
        )
    try:
        result_a = lookup_product("SHARED-SKU", tenant_id=tenant_a, database_url=postgres_schema)
        result_b = lookup_product("SHARED-SKU", tenant_id=tenant_b, database_url=postgres_schema)
        assert "Tenant A Product" in result_a and "Tenant B Product" not in result_a
        assert "Tenant B Product" in result_b and "Tenant A Product" not in result_b
    finally:
        with psycopg.connect(postgres_schema) as conn:
            conn.execute("DELETE FROM tenants WHERE id IN (%s::uuid, %s::uuid)", (tenant_a, tenant_b))
