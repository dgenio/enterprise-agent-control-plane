from dataclasses import dataclass


@dataclass(frozen=True)
class EvalResult:
    candidate: str
    score: float
    notes: str


def compare_router_candidates() -> list[EvalResult]:
    """skdr-eval style offline eval stub."""
    return [
        EvalResult("keyword_router_v1", 0.72, "Simple keyword shortlist baseline."),
        EvalResult("bounded_router_v2", 0.88, "Better precision on refund and escalation scenarios."),
    ]
