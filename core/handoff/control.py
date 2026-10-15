"""Conversation-level AI/Human control policy.

Persistence and operator authorization belong to the application/service layer.
This module provides the deterministic rules that layer must enforce.
"""
from dataclasses import dataclass
from enum import StrEnum


class ControlMode(StrEnum):
    AI = "ai"
    HUMAN = "human"


@dataclass(frozen=True)
class ControlDecision:
    mode: ControlMode
    may_send_ai_reply: bool
    reason: str


def decide_ai_reply(mode: ControlMode, *, inbound_is_duplicate: bool = False) -> ControlDecision:
    """Fail closed: duplicate events and human-owned conversations never trigger AI."""
    if inbound_is_duplicate:
        return ControlDecision(mode=mode, may_send_ai_reply=False, reason="duplicate_event")
    if mode is ControlMode.HUMAN:
        return ControlDecision(mode=mode, may_send_ai_reply=False, reason="human_control_enabled")
    return ControlDecision(mode=mode, may_send_ai_reply=True, reason="ai_control_enabled")


def parse_control_command(command: str) -> tuple[str, ControlMode] | None:
    """Parse '<sender-id>/Human' or '<sender-id>/AI'; authorization is checked elsewhere."""
    if not isinstance(command, str) or "/" not in command:
        return None
    sender_id, requested_mode = command.strip().rsplit("/", maxsplit=1)
    sender_id = sender_id.strip()
    requested_mode = requested_mode.strip().casefold()
    if not sender_id or any(ch.isspace() for ch in sender_id):
        return None
    if requested_mode == "human":
        return sender_id, ControlMode.HUMAN
    if requested_mode == "ai":
        return sender_id, ControlMode.AI
    return None
