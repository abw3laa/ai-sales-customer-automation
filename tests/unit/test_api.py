from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_health_check_returns_ok() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_webhook_scaffold_accepts_normalized_event() -> None:
    response = client.post("/v1/webhooks/whatsapp", json={"event_id": "evt-local-001", "event_type": "message.received", "payload": {"text": "Hello"}})
    assert response.status_code == 202
    assert response.json()["event_id"] == "evt-local-001"


def test_webhook_rejects_unknown_channel() -> None:
    response = client.post("/v1/webhooks/unknown", json={"event_id": "evt-1", "event_type": "message.received", "payload": {}})
    assert response.status_code == 404
