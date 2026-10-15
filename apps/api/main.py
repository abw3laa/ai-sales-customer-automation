from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from core.config import get_settings
from integrations.telegram.catalog_webhook import router as telegram_catalog_router

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API foundation for the AI Sales & Customer Automation System",
)


class WebhookEnvelope(BaseModel):
    """Provider-neutral scaffold; provider-specific signature checks are still required."""

    event_id: str = Field(min_length=1, max_length=256)
    event_type: str = Field(min_length=1, max_length=128)
    payload: dict = Field(default_factory=dict)


@app.get("/healthz", tags=["operations"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.post("/v1/webhooks/{channel}", status_code=202, tags=["webhooks"])
def receive_webhook(channel: str, event: WebhookEnvelope) -> dict[str, str]:
    """Accept a normalized event shape for development; does not process or persist it yet."""
    allowed_channels = {"whatsapp", "messenger", "instagram", "telegram"}
    if channel not in allowed_channels:
        raise HTTPException(status_code=404, detail="Unsupported channel")
    return {"status": "accepted_for_scaffolding", "channel": channel, "event_id": event.event_id}
