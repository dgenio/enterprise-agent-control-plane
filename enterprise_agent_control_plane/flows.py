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
    "escalation": FlowDefinition(
        flow_id="escalation",
        steps=[FlowStep("search_tickets", "support.search_tickets"), FlowStep("create_task", "support.create_task")],
    ),
}


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
