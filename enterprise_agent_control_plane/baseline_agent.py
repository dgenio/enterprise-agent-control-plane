import json
from typing import Any

from .baseline_router import Router, route_v1
from .catalog import build_tool_definitions, context_size, serialize_tool_catalog
from . import fake_tools

# Action classes the baseline does NOT distinguish: these move money / send external
# email / create work, yet the baseline reaches them with no principal, token, or
# policy decision (issue #17). email.draft_reply is intentionally excluded -- drafting
# is not an external side effect.
WRITE_OR_DESTRUCTIVE = {"billing.issue_refund", "email.send_reply", "support.create_task"}

# The minimal fields each tool's caller actually needs for the task. Everything a tool
# returns beyond these is forwarded into context anyway -- that surplus is the leakage
# the baseline demonstrates (issue #16).
REQUIRED_FIELDS: dict[str, set[str]] = {
    "crm.search_customer": {"customer_id", "name"},
    "billing.get_invoice": {"invoice_id", "amount", "status"},
    "billing.issue_refund": {"invoice_id", "amount", "status"},
    "support.search_tickets": {"ticket_id", "status"},
    "support.create_task": {"task_id"},
    "email.draft_reply": {"subject"},
    "email.send_reply": {"status"},
    "docs.search_policy": {"policy_id"},
    "audit.export_case": {"case_id", "export_status"},
}

# Loop safety bound so the router can never spin forever. Set to the full catalog
# size (9 tools) so that even a future request that legitimately walked every
# capability once would not be silently truncated; today's deterministic paths end
# (router returns None) in at most 3 steps, well before this.
MAX_STEPS = 9


class BaselineAgent:
    """Unsafe baseline: a naive, model-routed agent loop.

    On every step it is handed the *full* serialized tool catalog (no shortlist),
    a deterministic router stands in for the model and picks the next tool, raw tool
    outputs are forwarded verbatim, write/destructive actions run with no policy or
    capability gate, and only flat free-text logs are emitted (no structured trace).
    Each weakness is intentional and demonstrates a gap the governed path closes.
    """

    def __init__(self, router: Router = route_v1):
        self.router = router
        self.tool_definitions = build_tool_definitions()
        self.tools = {
            "crm.search_customer": fake_tools.crm_search_customer,
            "billing.get_invoice": fake_tools.billing_get_invoice,
            "billing.issue_refund": fake_tools.billing_issue_refund,
            "support.search_tickets": fake_tools.support_search_tickets,
            "support.create_task": fake_tools.support_create_task,
            "email.draft_reply": fake_tools.email_draft_reply,
            "email.send_reply": fake_tools.email_send_reply,
            "docs.search_policy": fake_tools.docs_search_policy,
            "audit.export_case": fake_tools.audit_export_case,
        }

    def run_case(self, request: str, customer_id: str, invoice_id: str) -> dict[str, Any]:
        # The whole catalog is serialized into context once and re-offered every step.
        catalog_context = serialize_tool_catalog(self.tool_definitions)
        size = context_size(catalog_context)
        tools_offered = len(self.tool_definitions)

        logs: list[str] = [f"[baseline] handling request: {request!r}"]
        called: list[str] = []
        raw_outputs: dict[str, Any] = {}
        steps: list[dict[str, Any]] = []
        leaked_fields: dict[str, list[str]] = {}
        policy_blind_writes: list[dict[str, Any]] = []

        while len(steps) < MAX_STEPS:
            # The router sees the accumulated raw output too: the baseline has no
            # boundary between operator intent and tool data, so injected text can steer
            # it (issue #31).
            capability = self.router(request, called, raw_outputs)
            if capability is None:
                break

            # Audit-light: the log names the tool but not the principal, the exact
            # arguments, the returned payload, or any policy decision (issue #19).
            logs.append(f"[baseline] step {len(steps) + 1}: model picked {capability} from {tools_offered} tools")

            output = self._invoke(capability, customer_id, invoice_id, raw_outputs)

            # Raw output forwarded verbatim into accumulated context (issue #16).
            raw_outputs[capability] = output
            leaked_fields[capability] = _excess_fields(capability, output)

            # Cumulative model-visible context grows every step: the whole catalog is
            # re-offered AND every raw output is retained (issue #42). ``context_chars``
            # stays the flat catalog-only figure from #15; this is the compounding cost.
            accumulated = catalog_context + json.dumps(raw_outputs, default=str)
            cumulative = context_size(accumulated)

            steps.append(
                {
                    "step": len(steps) + 1,
                    "capability": capability,
                    "tools_offered": tools_offered,
                    "context_chars": size["chars"],
                    "cumulative_context_chars": cumulative["chars"],
                    "cumulative_approx_tokens": cumulative["approx_tokens"],
                    "output": output,
                }
            )
            called.append(capability)

            if capability in WRITE_OR_DESTRUCTIVE:
                # No principal, no scoped capability token, no policy decision, no
                # approval -- a model decision alone moved money / sent email (issue #17).
                policy_blind_writes.append(
                    {
                        "capability": capability,
                        "principal": None,
                        "capability_token": None,
                        "policy_decision": None,
                        "approval": None,
                    }
                )
                logs.append(f"[baseline] executed {capability} with no policy or approval check")

        # Execution-contract gaps (issue #32): a destructive refund that ran with no
        # successful precondition, no amount bound, no refundability check, and no
        # idempotency guard. The presence of any entry is the demonstrated gap.
        precondition_gaps: list[str] = []
        if "billing.issue_refund" in raw_outputs:
            invoice = raw_outputs.get("billing.get_invoice")
            refund = raw_outputs["billing.issue_refund"]
            if invoice is None:
                precondition_gaps.append(
                    "billing.issue_refund ran even though billing.get_invoice was never called "
                    "(no precondition that the invoice exists)"
                )
            elif isinstance(invoice, dict) and invoice.get("error"):
                precondition_gaps.append(
                    f"billing.issue_refund ran even though billing.get_invoice failed "
                    f"({invoice.get('error')}); the refund fell back to a hardcoded amount"
                )
            if isinstance(refund, dict):
                precondition_gaps.append(
                    f"refund amount {refund.get('amount')} was never bounded or checked "
                    "against the invoice total"
                )
            precondition_gaps.append(
                "no idempotency guard on billing.issue_refund: re-running the same case "
                "appends another refund"
            )

        # Per-step cumulative context size (issue #42), so the growth curve is inspectable.
        context_growth = [
            {"step": s["step"], "cumulative_context_chars": s["cumulative_context_chars"]}
            for s in steps
        ]

        return {
            "mode": "unsafe",
            "request": request,
            "router": self.router.__name__,
            "tools_offered_each_step": tools_offered,
            "full_catalog_context_chars": size["chars"],
            "approx_context_tokens": size["approx_tokens"],
            "context_growth": context_growth,
            "precondition_gaps": precondition_gaps,
            "steps": steps,
            # The sequence is re-decided by the "model" each step yet is identical across
            # runs -- a deterministic path that could be compiled into a flow (issue #18).
            "deterministic_path": True,
            "compilation_note": (
                "This fixed sequence is re-routed by the model every step; it never varies "
                "and is a prime candidate for compilation into a deterministic flow."
            ),
            "raw_outputs": raw_outputs,
            "leaked_fields": leaked_fields,
            "policy_blind_writes": policy_blind_writes,
            "logs": logs,
            # The baseline emits only the flat logs above -- no structured, queryable trace.
            "structured_audit_trace": None,
            "audit_open_questions": [
                "Who (which principal) requested this?",
                "Which tool ran with exactly which arguments?",
                "What did each tool return?",
                "Was anything blocked, and if so why?",
            ],
        }

    def _invoke(self, capability: str, customer_id: str, invoice_id: str, raw_outputs: dict[str, Any]) -> Any:
        tool = self.tools[capability]
        customer = raw_outputs.get("crm.search_customer", {})
        invoice = raw_outputs.get("billing.get_invoice", {})
        if capability == "crm.search_customer":
            return tool(customer_id)
        if capability == "billing.get_invoice":
            return tool(invoice_id)
        if capability == "billing.issue_refund":
            amount = invoice.get("amount", 149.0) if isinstance(invoice, dict) else 149.0
            return tool(invoice_id, amount, "customer requested")
        if capability == "support.search_tickets":
            return tool(customer_id)
        if capability == "support.create_task":
            return tool(customer_id, "Escalated by baseline agent")
        if capability == "email.draft_reply":
            name = customer.get("name", "Customer") if isinstance(customer, dict) else "Customer"
            return tool(name, "your request")
        if capability == "email.send_reply":
            to = customer.get("email", "unknown@example.com") if isinstance(customer, dict) else "unknown@example.com"
            return tool(to, "Re: your request", "We have processed your request.")
        if capability == "docs.search_policy":
            return tool("refund")
        if capability == "audit.export_case":
            return tool(customer_id)
        return {"error": "unknown_capability", "capability": capability}


def _excess_fields(capability: str, output: Any) -> list[str]:
    """Fields present in a tool output that were not required for the task."""
    required = REQUIRED_FIELDS.get(capability, set())
    if isinstance(output, dict):
        return sorted(k for k in output if k not in required)
    return []
