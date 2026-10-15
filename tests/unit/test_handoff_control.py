from core.handoff.control import ControlMode, decide_ai_reply, parse_control_command


def test_ai_mode_allows_reply_for_new_event():
    decision = decide_ai_reply(ControlMode.AI)
    assert decision.may_send_ai_reply is True
    assert decision.reason == "ai_control_enabled"


def test_human_mode_blocks_ai_reply():
    decision = decide_ai_reply(ControlMode.HUMAN)
    assert decision.may_send_ai_reply is False
    assert decision.reason == "human_control_enabled"


def test_duplicate_event_never_triggers_reply():
    decision = decide_ai_reply(ControlMode.AI, inbound_is_duplicate=True)
    assert decision.may_send_ai_reply is False
    assert decision.reason == "duplicate_event"


def test_parse_human_command():
    assert parse_control_command("123456789/Human") == ("123456789", ControlMode.HUMAN)


def test_parse_ai_command_case_insensitively():
    assert parse_control_command("123456789/AI") == ("123456789", ControlMode.AI)


def test_reject_invalid_commands():
    assert parse_control_command(" /human") is None
    assert parse_control_command("123 456/Human") is None
    assert parse_control_command("123456789/auto") is None
    assert parse_control_command("not a command") is None
