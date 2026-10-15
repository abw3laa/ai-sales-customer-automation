from integrations.telegram.operator_bot import authorized_operator, parse_operator_text
from integrations.telegram.operator_webhook import _tenant_for_operator, _telegram_reply


def test_authorized_operator_uses_explicit_allowlist(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "123, 456")
    assert authorized_operator(123)
    assert authorized_operator(456)
    assert not authorized_operator(789)


def test_authorized_operator_does_not_authorize_when_allowlist_is_empty(monkeypatch):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    assert not authorized_operator(123)


def test_parse_operator_text_supports_commands_and_bot_suffix():
    assert parse_operator_text("/review") == ("/review", "")
    assert parse_operator_text("/approve A100") == ("/approve", "A100")
    assert parse_operator_text("/reject@shop_bot A100 wrong price") == (
        "/reject",
        "A100 wrong price",
    )


def test_parse_operator_text_rejects_empty_or_unrecognized_text():
    assert parse_operator_text("") is None
    assert parse_operator_text("hello") is None


def test_tenant_mapping_is_scoped_to_operator_id(monkeypatch):
    monkeypatch.setenv(
        "TELEGRAM_OPERATOR_TENANTS",
        "123=aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa,456=bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    )
    assert _tenant_for_operator(123) == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert _tenant_for_operator(456) == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    assert _tenant_for_operator(789) == ""


def test_telegram_reply_limits_message_length():
    result = _telegram_reply(123, "x" * 5000)
    assert result["method"] == "sendMessage"
    assert result["chat_id"] == 123
    assert len(result["text"]) == 3900
