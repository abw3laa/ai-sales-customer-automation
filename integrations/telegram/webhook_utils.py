"""Shared defensive parsing helpers for Telegram webhook requests."""
from __future__ import annotations

import json

from fastapi import HTTPException, Request
from starlette.requests import ClientDisconnect

MAX_TELEGRAM_WEBHOOK_BYTES = 256 * 1024


async def read_telegram_update(request: Request) -> dict:
    """Read a bounded JSON object, rejecting oversized or malformed webhook bodies."""
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length") from None
        if declared_length < 0:
            raise HTTPException(status_code=400, detail="Invalid Content-Length")
        if declared_length > MAX_TELEGRAM_WEBHOOK_BYTES:
            raise HTTPException(status_code=413, detail="Telegram webhook payload too large")

    body = bytearray()
    try:
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_TELEGRAM_WEBHOOK_BYTES:
                raise HTTPException(
                    status_code=413, detail="Telegram webhook payload too large"
                )
    except ClientDisconnect:
        raise HTTPException(status_code=400, detail="Incomplete request body") from None

    try:
        update = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from None
    if not isinstance(update, dict):
        raise HTTPException(status_code=400, detail="Telegram update must be a JSON object")
    return update
