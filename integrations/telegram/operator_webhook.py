"""Authenticated Telegram operator update handler."""
from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Header, HTTPException, Request

from core.handoff.repository import get_conversation_status, set_conversation_mode
from integrations.telegram.webhook_utils import read_telegram_update
from integrations.telegram.operator_bot import (
    HELP,
    authorized_operator,
    parse_operator_text,
)
from integrations.telegram.operator_catalog import (
    list_review_products,
    lookup_product,
    review_product,
    search_products,
)

router = APIRouter(prefix="/v1/webhooks/telegram", tags=["telegram-operator"])


def _tenant_for_operator(user_id: int) -> str:
    for item in os.getenv("TELEGRAM_OPERATOR_TENANTS", "").split(","):
        if "=" in item:
            key, value = item.split("=", 1)
            if key.strip() == str(user_id):
                return value.strip()
    return ""


def _telegram_reply(chat_id: int, text: str) -> dict:
    # Telegram supports Bot API methods in the webhook response body.
    return {"method": "sendMessage", "chat_id": chat_id, "text": text[:3900]}


@router.post("/operator", status_code=200)
async def receive_operator_update(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    expected = os.getenv("TELEGRAM_OPERATOR_WEBHOOK_SECRET") or os.getenv(
        "TELEGRAM_WEBHOOK_SECRET", ""
    )
    if (
        not expected
        or not x_telegram_bot_api_secret_token
        or not hmac.compare_digest(expected, x_telegram_bot_api_secret_token)
    ):
        raise HTTPException(status_code=401, detail="Invalid Telegram webhook secret")

    update = await read_telegram_update(request)

    message = update.get("message")
    if not isinstance(message, dict) or not message.get("text"):
        return {"status": "ignored"}

    chat = message.get("chat")
    sender = message.get("from")
    if not isinstance(chat, dict) or not isinstance(sender, dict):
        raise HTTPException(status_code=400, detail="Invalid Telegram message structure")
    text_value = message.get("text")
    if not isinstance(text_value, str):
        return {"status": "ignored"}
    user_id = sender.get("id")
    chat_id = chat.get("id")
    if (
        chat.get("type") != "private"
        or not isinstance(user_id, int)
        or not isinstance(chat_id, int)
    ):
        return {"status": "ignored"}

    if not authorized_operator(user_id):
        return _telegram_reply(chat_id, "غير مصرح لك باستخدام بوت الإدارة.")

    parsed = parse_operator_text(text_value)
    if not parsed:
        return _telegram_reply(chat_id, HELP)

    command, argument = parsed
    tenant_id = _tenant_for_operator(user_id)
    if command in ("/help", "/start"):
        reply = HELP
    elif not tenant_id:
        reply = "لم يتم ربط حسابك بمتجر. راجع TELEGRAM_OPERATOR_TENANTS."
    elif command == "/product":
        reply = lookup_product(argument, tenant_id=tenant_id)
    elif command == "/search":
        reply = search_products(argument, tenant_id=tenant_id)
    elif command == "/review":
        reply = list_review_products(tenant_id=tenant_id)
    elif command == "/approve":
        reply = review_product(
            argument,
            tenant_id=tenant_id,
            telegram_user_id=user_id,
            approve=True,
        )
    elif command == "/reject":
        sku, separator, reason = argument.partition(" ")
        if not separator or not reason.strip():
            reply = "استخدم: /reject <SKU> <سبب الرفض>"
        else:
            reply = review_product(
                sku,
                tenant_id=tenant_id,
                telegram_user_id=user_id,
                approve=False,
                reason=reason.strip(),
            )
    elif command == "/human":
        reply = set_conversation_mode(argument, tenant_id, user_id, "human")
    elif command == "/ai":
        reply = set_conversation_mode(argument, tenant_id, user_id, "ai")
    elif command == "/status":
        reply = get_conversation_status(argument, tenant_id)
    else:
        reply = HELP

    return _telegram_reply(chat_id, reply)
