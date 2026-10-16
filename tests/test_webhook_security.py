from fastapi.testclient import TestClient

from apps.api.main import app


def test_catalog_webhook_rejects_oversized_payload(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CATALOG_WEBHOOK_SECRET", "test-secret")
    client = TestClient(app)
    body = b'{"message":"' + (b"x" * (256 * 1024)) + b'"}'
    response = client.post(
        "/v1/webhooks/telegram/catalog",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Telegram-Bot-Api-Secret-Token": "test-secret",
        },
    )
    assert response.status_code == 413


def test_operator_webhook_rejects_malformed_nested_objects(monkeypatch):
    monkeypatch.setenv("TELEGRAM_OPERATOR_WEBHOOK_SECRET", "test-secret")
    client = TestClient(app)
    response = client.post(
        "/v1/webhooks/telegram/operator",
        json={"message": {"chat": "not-an-object", "from": {}, "text": "/help"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert response.status_code == 400
