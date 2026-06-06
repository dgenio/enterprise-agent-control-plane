from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class FlowStep:
    name: str
    capability: str


@dataclass(frozen=True)
class FlowDefinition:
    flow_id: str
    steps: list[FlowStep]
    # The write/destructive capabilities this flow performs, each of which must pass its own
    # policy decision before it can take effect (issue #66). The governed path derives the
    # set of actions to gate from this declaration rather than a per-intent hardcode, so a
    # flow that touches two writes gates both -- no write can run ungated.
    gated_capabilities: tuple[str, ...] = ()


FLOW_REGISTRY: dict[str, FlowDefinition] = {
    "refund_review": FlowDefinition(
        flow_id="refund_review",
        steps=[
            FlowStep("lookup_customer", "crm.search_customer"),
            FlowStep("lookup_invoice", "billing.get_invoice"),
            FlowStep("check_policy", "docs.search_policy"),
            FlowStep("draft_reply", "email.draft_reply"),
        ],
        gated_capabilities=("billing.issue_refund",),
    ),
    "customer_reply": FlowDefinition(
        flow_id="customer_reply",
        steps=[FlowStep("lookup_customer", "crm.search_customer"), FlowStep("draft_reply", "email.draft_reply")],
        gated_capabilities=("email.send_reply",),
    ),
    # Escalation does only its read-only prep here (search history). The risky write
    # (support.create_task) is NOT a flow step: it is gated separately via the policy
    # decision so it can be held for approval before it ever takes effect — mirroring
    # how refund_review/customer_reply keep their gated action (issue_refund/send_reply)
    # out of the executed steps.
    "escalation": FlowDefinition(
        flow_id="escalation",
        steps=[FlowStep("search_tickets", "support.search_tickets")],
        gated_capabilities=("support.create_task",),
    ),
    # A flow that performs TWO writes: issue the refund AND send a confirmation email. It
    # exists to prove gating coverage scales with the workflow (issue #66) -- both writes are
    # gated independently rather than a single per-intent action.
    "refund_and_notify": FlowDefinition(
        flow_id="refund_and_notify",
        steps=[
            FlowStep("lookup_customer", "crm.search_customer"),
            FlowStep("lookup_invoice", "billing.get_invoice"),
            FlowStep("check_policy", "docs.search_policy"),
            FlowStep("draft_reply", "email.draft_reply"),
        ],
        gated_capabilities=("billing.issue_refund", "email.send_reply"),
    ),
}


# Intent -> governed flow (issue #25). The governed path makes a single deterministic
# routing decision (which known workflow to run); the inner steps then execute with no
# further per-step model routing.
INTENT_FLOWS: dict[str, str] = {
    "refund": "refund_review",
    "refund_notify": "refund_and_notify",
    "reply": "customer_reply",
    "escalation": "escalation",
}


def classify_intent(request: str) -> "str | None":
    """Map a free-text request to a known intent, or ``None`` if unsupported."""
    text = request.lower()
    if "refund" in text:
        # A refund that also asks to notify/confirm the customer routes to the two-write
        # flow so both the refund and the confirmation send are gated (issue #66).
        if "notify" in text or "confirm" in text:
            return "refund_notify"
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

    def run(
        self,
        flow_id: str,
        payload: dict[str, Any],
        token_check: Optional[Callable[[str], bool]] = None,
        on_step: Optional[Callable[[dict[str, Any]], None]] = None,
        budget: Optional["set[str] | frozenset[str]"] = None,
    ) -> list[dict[str, Any]]:
        """Run a flow deterministically, optionally gating each step on a capability token.

        ``token_check`` (issue #111) is consulted before a step runs: a step whose
        capability the principal does not hold a token for *fails closed* -- the tool is not
        invoked, and the step record is marked ``token_valid=False`` with a blocked status.
        ``on_step`` is called once per step (executed or blocked) so the caller can record a
        per-step audit event. With neither argument the runner behaves as a plain executor.

        ``budget`` (issue #110) is the case's authoritative capability budget — the bounded
        shortlist made enforceable. When supplied, the executor may only invoke capabilities
        in the budget; a step that needs a capability the shortlist did not surface *fails
        closed* (status ``failed`` with an ``out_of_budget`` error) and halts the flow, rather
        than silently widening exposure to the full tool map. ``budget=None`` disables the
        check (a plain executor).

        A step that fails -- the tool returns an ``{"error": ...}`` payload or raises -- halts
        the flow closed (issue #41): the failing step is recorded with status ``failed`` and
        no later step runs, so a not-found dependency can never reach a downstream write.

        Note the two fail-closed mechanisms are deliberately distinct: a token-blocked step
        (``token_valid=False``) is per-step least privilege (#111) -- it is skipped and the
        flow *continues*, since one un-held read need not abort the run -- whereas a *failed*
        step (#41/#110) halts the whole flow. Either way the tool's side effect never fires.
        """
        flow = FLOW_REGISTRY[flow_id]
        results: list[dict[str, Any]] = []
        for step in flow.steps:
            if budget is not None and step.capability not in budget:
                # Out of budget: the shortlist never surfaced this capability, so the flow
                # fails closed here rather than reaching beyond the bounded budget (issue #110).
                record = {
                    "step": step.name,
                    "capability": step.capability,
                    "output": {
                        "error": "out_of_budget",
                        "detail": f"{step.capability} is outside the case capability budget",
                    },
                    "token_valid": True,
                    "status": "failed",
                }
                results.append(record)
                if on_step is not None:
                    on_step(record)
                break
            token_valid = True if token_check is None else token_check(step.capability)
            if not token_valid:
                # Fail closed: no token, so the tool never runs (issue #111).
                record = {
                    "step": step.name,
                    "capability": step.capability,
                    "output": None,
                    "token_valid": False,
                    "status": "blocked_no_token",
                }
                results.append(record)
                if on_step is not None:
                    on_step(record)
                continue
            try:
                out = self._invoke_step(step.capability, payload)
            except Exception as exc:  # noqa: BLE001 - convert any tool error into a structured failure
                out = {"error": "exception", "detail": str(exc)}
            failed = isinstance(out, dict) and "error" in out
            record = {
                "step": step.name,
                "capability": step.capability,
                "output": out,
                "token_valid": True,
                "status": "failed" if failed else "ok",
            }
            results.append(record)
            if on_step is not None:
                on_step(record)
            if failed:
                # Fail closed on the first failed step: no later (possibly write) step runs.
                break
        return results

    def _invoke_step(self, capability: str, payload: dict[str, Any]) -> Any:
        if capability == "crm.search_customer":
            return self.tools[capability](payload["customer_id"])
        if capability == "billing.get_invoice":
            return self.tools[capability](payload["invoice_id"])
        if capability == "docs.search_policy":
            return self.tools[capability]("refund")
        if capability == "email.draft_reply":
            return self.tools[capability](payload["customer_name"], "refund review")
        if capability == "support.search_tickets":
            return self.tools[capability](payload["customer_id"])
        # support.create_task is a gated write (governed_agent settles it after a decision), not
        # a flow step in any registered flow today. The branch stays so the executor can run a
        # flow that lists it as a step without a code change; it is unreachable via FLOW_REGISTRY.
        if capability == "support.create_task":
            return self.tools[capability](payload["customer_id"], "Escalated by governed flow")
        return {"error": "unknown_step"}
