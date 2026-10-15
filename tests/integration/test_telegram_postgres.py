from __future__ import annotations

import os
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
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        for migration in MIGRATIONS:
            conn.execute(migration.read_text(encoding="utf-8"), prepare=False)
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
    payload = _telegram_update(9001, -100123, 501, "الكود: A501\nالاسم: بجامة رياضية adidas\nالسعر: 1200 TRY")

    assert client.post("/v1/webhooks/telegram/catalog", json=payload).status_code == 401
    forbidden = client.post(
        "/v1/webhooks/telegram/catalog",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "integration-secret"},
    )
    assert forbidden.status_code == 202
    assert forbidden.json()["status"] == "processed"

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

    payload = _telegram_update(9201, -100125, 701, "الكود: A701\nالاسم: بجامة رياضية adidas")
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
        "الكود: A801\nالاسم: بجامة رياضية adidas\nالسعر: 1200 TRY",
    )
    ingested = client.post("/v1/webhooks/telegram/catalog", json=payload, headers=headers)
    assert ingested.json()["status"] == "processed"

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
