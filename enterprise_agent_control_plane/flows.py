from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class FlowStep:
    name: str
    capability: str


@dataclass(frozen=True)
class FlowDefinition:
    flow_id: str
    steps: list[FlowStep]


FLOW_REGISTRY: dict[str, FlowDefinition] = {
    "refund_review": FlowDefinition(
        flow_id="refund_review",
        steps=[
            FlowStep("lookup_customer", "crm.search_customer"),
            FlowStep("lookup_invoice", "billing.get_invoice"),
            FlowStep("check_policy", "docs.search_policy"),
            FlowStep("draft_reply", "email.draft_reply"),
        ],
    ),
    "customer_reply": FlowDefinition(
        flow_id="customer_reply",
        steps=[FlowStep("lookup_customer", "crm.search_customer"), FlowStep("draft_reply", "email.draft_reply")],
    ),
    # Escalation does only its read-only prep here (search history). The risky write
    # (support.create_task) is NOT a flow step: it is gated separately via the policy
    # decision so it can be held for approval before it ever takes effect — mirroring
    # how refund_review/customer_reply keep their gated action (issue_refund/send_reply)
    # out of the executed steps.
    "escalation": FlowDefinition(
        flow_id="escalation",
        steps=[FlowStep("search_tickets", "support.search_tickets")],
    ),
}


# Intent -> governed flow (issue #25). The governed path makes a single deterministic
# routing decision (which known workflow to run); the inner steps then execute with no
# further per-step model routing.
INTENT_FLOWS: dict[str, str] = {
    "refund": "refund_review",
    "reply": "customer_reply",
    "escalation": "escalation",
}


def classify_intent(request: str) -> "str | None":
    """Map a free-text request to a known intent, or ``None`` if unsupported."""
    text = request.lower()
    if "refund" in text:
        return "refund"
    if "escalat" in text or "ticket" in text:
        return "escalation"
    if "reply" in text or "email" in text or "send" in text:
        return "reply"
    return None


def select_flow(request: str) -> "tuple[str | None, str | None]":
    """Select one registered flow for a request via a single deterministic decision.

    Returns ``(intent, flow_id)``. An unsupported request yields ``(None, None)`` so
    the caller can surface an explicit "no matching governed flow" outcome rather than
    defaulting silently (issue #25).
    """
    intent = classify_intent(request)
    if intent is None:
        return None, None
    return intent, INTENT_FLOWS.get(intent)


class ChainWeaverExecutor:
    """ChainWeaver-style deterministic runner with no LLM between steps."""

    def __init__(self, tools: dict[str, Callable[..., Any]]):
        self.tools = tools

    def run(self, flow_id: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        flow = FLOW_REGISTRY[flow_id]
        results: list[dict[str, Any]] = []
        for step in flow.steps:
            if step.capability == "crm.search_customer":
                out = self.tools[step.capability](payload["customer_id"])
            elif step.capability == "billing.get_invoice":
                out = self.tools[step.capability](payload["invoice_id"])
            elif step.capability == "docs.search_policy":
                out = self.tools[step.capability]("refund")
            elif step.capability == "email.draft_reply":
                out = self.tools[step.capability](payload["customer_name"], "refund review")
            elif step.capability == "support.search_tickets":
                out = self.tools[step.capability](payload["customer_id"])
            elif step.capability == "support.create_task":
                out = self.tools[step.capability](payload["customer_id"], "Escalated by governed flow")
            else:
                out = {"error": "unknown_step"}
            results.append({"step": step.name, "capability": step.capability, "output": out})
        return results
