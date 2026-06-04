from pathlib import Path
from typing import Any

from .audit import AuditTrace
from .catalog import build_catalog, shortlist_capabilities
from . import fake_tools
from .flows import ChainWeaverExecutor, FLOW_REGISTRY
from .policies import AgentFencePolicy, CapabilityToken, check_capability, PolicyDecision


class GovernedAgent:
    def __init__(self):
        self.catalog = build_catalog()
        self.policy = AgentFencePolicy()
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
        self.executor = ChainWeaverExecutor(self.tools)

    def run_case(self, customer_id: str, invoice_id: str, principal: str = "agent") -> dict[str, Any]:
        trace = AuditTrace(trace_id=f"trace-{customer_id}-{invoice_id}")
        shortlist = shortlist_capabilities("refund customer reply", self.catalog)
        trace.record(principal, "shortlist", "ok", {"capabilities": [c.capability for c in shortlist]})

        flow_results = self.executor.run(
            "refund_review",
            {"customer_id": customer_id, "invoice_id": invoice_id, "customer_name": "Ari Carter"},
        )
        trace.record(principal, "flow.execute", "ok", {"flow_id": "refund_review", "steps": len(flow_results)})

        token = CapabilityToken(principal=principal, capability="billing.issue_refund")
        can_invoke = check_capability(token, "billing.issue_refund")
        if not can_invoke:
            decision = PolicyDecision("deny", "Capability token invalid.")
        else:
            decision = self.policy.evaluate("billing.issue_refund", principal)
        outcome = "blocked" if decision.decision != "allow" else "allowed"
        trace.record(principal, "policy.check", outcome, {"capability": "billing.issue_refund", "decision": decision.decision, "token_valid": can_invoke})

        flow_caps = {step.capability for step in FLOW_REGISTRY["refund_review"].steps}
        visible_tools = sorted({c.capability for c in shortlist} | flow_caps)

        bounded_frame = {
            "customer_id": customer_id,
            "invoice_id": invoice_id,
            "flow_steps": [r["step"] for r in flow_results],
            "refund_action": outcome,
            "policy_reason": decision.reason,
            "capability_token_valid": can_invoke,
        }

        trace_filename = f"governed_run_{customer_id}_{invoice_id}.json"
        trace_path = Path("traces") / trace_filename
        trace.save(trace_path)
        return {
            "mode": "governed",
            "visible_tools": visible_tools,
            "bounded_output": bounded_frame,
            "audit_trace_path": str(trace_path),
        }
