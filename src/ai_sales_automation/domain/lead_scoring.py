"""Small, deterministic lead-scoring policy; business-specific rules can override it."""
from dataclasses import dataclass

@dataclass(frozen=True)
class LeadSignals:
    asks_for_price: bool = False
    asks_for_demo_or_booking: bool = False
    states_purchase_intent: bool = False
    provides_contact_details: bool = False
    describes_specific_need: bool = False
    asks_only_general_question: bool = False
    requests_human: bool = False


@dataclass(frozen=True)
class LeadAssessment:
    score: int
    temperature: str
    reasons: tuple[str, ...]
    requires_human: bool


def assess_lead(signals: LeadSignals) -> LeadAssessment:
    """Assess a lead with a transparent 0..100 heuristic.

    Thresholds are initial defaults and should be tenant-configurable before launch.
    A human request is a routing signal, not proof of purchase intent.
    """
    weighted = (
        (signals.asks_for_price, 20, "asks_for_price"),
        (signals.asks_for_demo_or_booking, 30, "asks_for_demo_or_booking"),
        (signals.states_purchase_intent, 35, "states_purchase_intent"),
        (signals.provides_contact_details, 10, "provides_contact_details"),
        (signals.describes_specific_need, 15, "describes_specific_need"),
    )
    score = min(100, sum(points for active, points, _ in weighted if active))
    reasons = [label for active, _, label in weighted if active]

    if signals.asks_only_general_question and score == 0:
        reasons.append("general_question_only")
    if signals.requests_human:
        reasons.append("requests_human")

    if score >= 60:
        temperature = "hot"
    elif score >= 25:
        temperature = "warm"
    else:
        temperature = "cold"

    return LeadAssessment(
        score=score,
        temperature=temperature,
        reasons=tuple(reasons),
        requires_human=signals.requests_human,
    )
