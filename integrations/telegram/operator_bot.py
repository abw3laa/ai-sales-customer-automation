"""Access control and command parsing for the Telegram operator bot."""
from __future__ import annotations
import os
from core.handoff.control import ControlMode, parse_control_command

HELP = """أوامر الأدمن:
/help
/product A100
/search adidas
/review
/human <conversation_id>
/ai <conversation_id>
/status <conversation_id>
"""

def authorized_operator(user_id: int, allowlist: str | None = None) -> bool:
    raw = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "") if allowlist is None else allowlist
    return str(user_id) in {item.strip() for item in raw.split(",") if item.strip()}

def parse_operator_text(text: str) -> tuple[str, str] | None:
    if not isinstance(text, str) or not text.strip():
        return None
    raw = text.strip()
    if raw.startswith("/"):
        command, _, argument = raw.partition(" ")
        return command.split("@", 1)[0].lower(), argument.strip()
    legacy = parse_control_command(raw)
    if legacy:
        sender_id, mode = legacy
        return ("/human" if mode is ControlMode.HUMAN else "/ai", sender_id)
    return None
