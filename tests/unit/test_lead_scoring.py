from src.ai_sales_automation.domain.lead_scoring import LeadSignals, assess_lead


def test_general_question_is_cold():
    result = assess_lead(LeadSignals(asks_only_general_question=True))
    assert result.score == 0
    assert result.temperature == "cold"
    assert "general_question_only" in result.reasons
    assert result.requires_human is False


def test_specific_need_and_price_question_is_warm():
    result = assess_lead(LeadSignals(asks_for_price=True, describes_specific_need=True))
    assert result.score == 35
    assert result.temperature == "warm"


def test_booking_and_purchase_intent_is_hot():
    result = assess_lead(LeadSignals(asks_for_demo_or_booking=True, states_purchase_intent=True))
    assert result.score == 65
    assert result.temperature == "hot"


def test_requesting_human_does_not_inflate_purchase_score():
    result = assess_lead(LeadSignals(requests_human=True))
    assert result.score == 0
    assert result.temperature == "cold"
    assert result.requires_human is True
    assert "requests_human" in result.reasons


def test_score_is_capped_at_one_hundred():
    result = assess_lead(LeadSignals(
        asks_for_price=True,
        asks_for_demo_or_booking=True,
        states_purchase_intent=True,
        provides_contact_details=True,
        describes_specific_need=True,
    ))
    assert result.score == 100
