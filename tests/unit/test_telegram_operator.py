from integrations.telegram.operator_bot import authorized_operator, parse_operator_text

def test_operator_allowlist():
    assert authorized_operator(123, "123,456")
    assert not authorized_operator(12, "123,456")

def test_slash_command_parsing():
    assert parse_operator_text("/product A100") == ("/product", "A100")
    assert parse_operator_text("/search adidas") == ("/search", "adidas")
    assert parse_operator_text("/review") == ("/review", "")
    assert parse_operator_text("/approve A100") == ("/approve", "A100")
    assert parse_operator_text("/reject A100 price unclear") == ("/reject", "A100 price unclear")
    assert parse_operator_text("/status abc-123") == ("/status", "abc-123")

def test_legacy_control_commands():
    assert parse_operator_text("sender-42/Human") == ("/human", "sender-42")
    assert parse_operator_text("sender-42/AI") == ("/ai", "sender-42")

def test_unknown_text_is_rejected():
    assert parse_operator_text("hello") is None
