import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from .audit import AuditTrace
from .catalog import build_catalog, shortlist_capabilities
from . import fake_tools
from .flows import ChainWeaverExecutor, FLOW_REGISTRY, select_flow
from .policies import ACTION_CLASSES, AgentFencePolicy, holds_capability, issue_tokens

# Sentinel so callers can pass ``approver=None`` to mean "no approver" (leave 'ask'
# pending) while omitting it falls back to the agent's configured approver.
_USE_DEFAULT: Any = object()

# The risky action each intent gates before it could take effect (issue #25/#26).
GATED_ACTION: dict[str, str] = {
    "refund": "billing.issue_refund",
    "reply": "email.send_reply",
    "escalation": "support.create_task",
}

# An approver receives an ApprovalRequest and returns True to approve, False to reject.
Approver = Callable[["ApprovalRequest"], bool]


@dataclass(frozen=True)
class ApprovalRequest:
    principal: str
    capability: str
    reason: str
    args: dict[str, Any]


@dataclass(frozen=True)
class GovernedDecision:
    """The full, explainable result of gating one capability invocation."""

    capability: str
    principal: str
    action_class: Optional[str]
    decision: str   # raw policy decision: allow / ask / deny
    outcome: str    # allowed / approved / approval_required / approval_denied / denied
    reason: str
    token_valid: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class GovernedAgent:
    def __init__(self, policy: Optional[AgentFencePolicy] = None, approver: Optional[Approver] = None):
        self.catalog = build_catalog()
        self.policy = policy or AgentFencePolicy()
        self.approver = approver
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

    def decide(
        self,
        capability: str,
        principal: str,
        args: Optional[dict[str, Any]] = None,
        trace: Optional[AuditTrace] = None,
        approver: Any = _USE_DEFAULT,
    ) -> GovernedDecision:
        """Gate one capability: token check (issue #23) -> policy (issues #2/#36) ->
        approval routing for 'ask' (issue #5). Records an explainable trace event (#27).
        """
        args = args or {}
        approver = self.approver if approver is _USE_DEFAULT else approver

        # Token layer first: an out-of-scope capability for a principal is rejected
        # before any policy evaluation (issue #23).
        tokens = issue_tokens(principal)
        if not holds_capability(tokens, capability):
            decision = GovernedDecision(
                capability, principal, ACTION_CLASSES.get(capability), "deny", "denied",
                f"{principal} holds no valid capability token for {capability}.", False,
            )
            if trace is not None:
                trace.record(principal, "policy.decision", "denied", decision.as_dict())
            return decision

        policy_decision = self.policy.evaluate(capability, principal, args)
        outcome, reason = self._resolve(policy_decision, principal, capability, args, approver, trace)
        decision = GovernedDecision(
            capability, principal, policy_decision.action_class,
            policy_decision.decision, outcome, reason, True,
        )
        if trace is not None:
            trace.record(principal, "policy.decision", outcome, decision.as_dict())
        return decision

    def _resolve(self, policy_decision, principal, capability, args, approver, trace):
        if policy_decision.decision == "allow":
            return "allowed", policy_decision.reason
        if policy_decision.decision == "deny":
            return "denied", policy_decision.reason

        # 'ask' routes through the approval step (issue #5).
        if approver is None:
            if trace is not None:
                trace.record(principal, "approval.request", "pending",
                             {"capability": capability, "reason": policy_decision.reason})
            return "approval_required", policy_decision.reason + " No approver configured; left pending."

        if trace is not None:
            trace.record(principal, "approval.request", "requested",
                         {"capability": capability, "reason": policy_decision.reason})
        approved = approver(ApprovalRequest(principal, capability, policy_decision.reason, args))
        resolution = "approved" if approved else "denied"
        if trace is not None:
            trace.record(principal, "approval.resolved", resolution, {"capability": capability})
        if approved:
            return "approved", policy_decision.reason + " Approved by approver."
        return "approval_denied", policy_decision.reason + " Rejected by approver."

    def run_case(
        self,
        request: str,
        customer_id: str,
        invoice_id: str,
        principal: str = "support_agent",
        approver: Any = _USE_DEFAULT,
    ) -> dict[str, Any]:
        approver = self.approver if approver is _USE_DEFAULT else approver
        trace = AuditTrace(trace_id=f"trace-{customer_id}-{invoice_id}")

        intent, flow_id = select_flow(request)
        trace.record(principal, "request.received", "ok",
                     {"request": request, "intent": intent, "principal": principal})

        if flow_id is None:
            # Unknown/unsupported intent: explicit no-match, no silent default (issue #25).
            trace.record(principal, "flow.select", "no_match",
                         {"intent": intent, "reason": "no governed flow registered for this request"})
            frame = {
                "request": request, "intent": intent, "flow": None,
                "status": "no_matching_flow",
                "reason": f"No governed flow matches request {request!r}.",
            }
            trace.record(principal, "output.frame", "no_match", frame)
            path = self._save_trace(trace, customer_id, invoice_id)
            return {
                "mode": "governed", "request": request, "intent": intent, "flow": None,
                "visible_tools": [], "decision": None, "bounded_output": frame,
                "audit_trace_path": str(path), "trace": trace,
            }

        # Bounded shortlist; the why is recorded so the trace is explainable (issue #27).
        shortlist = shortlist_capabilities(request, self.catalog)
        trace.record(principal, "shortlist", "ok", {
            "capabilities": [c.capability for c in shortlist],
            "reason": f"keyword shortlist for intent {intent!r}; full catalog kept out of model context",
        })

        flow_results = self.executor.run(
            flow_id, {"customer_id": customer_id, "invoice_id": invoice_id, "customer_name": "Ari Carter"}
        )
        trace.record(principal, "flow.select", "ok",
                     {"intent": intent, "flow_id": flow_id,
                      "reason": f"intent {intent!r} maps to deterministic flow {flow_id!r}"})
        trace.record(principal, "flow.execute", "ok", {"flow_id": flow_id, "steps": len(flow_results)})

        # Gate the risky action for this intent with a parameter-aware decision.
        gated_capability = GATED_ACTION[intent]
        gate_args: dict[str, Any] = {}
        if gated_capability == "billing.issue_refund":
            invoice = next((r["output"] for r in flow_results if r["capability"] == "billing.get_invoice"), {})
            gate_args = {"amount": invoice.get("amount") if isinstance(invoice, dict) else None}
        decision = self.decide(gated_capability, principal, gate_args, trace=trace, approver=approver)

        flow_caps = {step.capability for step in FLOW_REGISTRY[flow_id].steps}
        visible_tools = sorted({c.capability for c in shortlist} | flow_caps)

        frame = {
            "request": request, "intent": intent, "flow": flow_id,
            "flow_steps": [r["step"] for r in flow_results],
            "gated_capability": gated_capability,
            "action_status": decision.outcome,
            "decision_reason": decision.reason,
            "action_class": decision.action_class,
            "capability_token_valid": decision.token_valid,
        }
        trace.record(principal, "output.frame", "ok", frame)

        path = self._save_trace(trace, customer_id, invoice_id)
        return {
            "mode": "governed", "request": request, "intent": intent, "flow": flow_id,
            "visible_tools": visible_tools, "decision": decision.as_dict(),
            "bounded_output": frame, "audit_trace_path": str(path), "trace": trace,
        }

    def run_decision_scenario(
        self,
        principal: str = "support_agent",
        approver: Any = _USE_DEFAULT,
    ) -> dict[str, Any]:
        """One coherent scenario surfacing allow, deny, and approval-required outcomes,
        each with a stated reason (issue #26).
        """
        approver = self.approver if approver is _USE_DEFAULT else approver
        trace = AuditTrace(trace_id=f"decisions-{principal}")
        cases = [
            ("crm.search_customer", {}),                  # read -> allowed
            ("audit.export_case", {}),                    # restricted -> denied for support_agent
            ("billing.issue_refund", {"amount": 149.0}),  # within manager limit -> approval-required
        ]
        decisions = [self.decide(cap, principal, args, trace=trace, approver=approver) for cap, args in cases]
        path = Path("traces") / f"decisions_{principal}.json"
        trace.save(path)
        return {
            "principal": principal,
            "decisions": [d.as_dict() for d in decisions],
            "audit_trace_path": str(path),
            "trace": trace,
        }

    def export_case(self, trace: AuditTrace, principal: str = "support_manager") -> dict[str, Any]:
        """Produce a single inspectable case bundle from a trace (issue #27).

        The export itself is a governed capability, so it is gated like any other; the
        gate decision is recorded into the same trace before the snapshot is taken.
        """
        decision = self.decide("audit.export_case", principal, trace=trace)
        export = fake_tools.audit_export_case(trace.trace_id)
        bundle = {
            "case_id": trace.trace_id,
            "export_status": export["export_status"],
            "exported_by": principal,
            "export_decision": decision.outcome,
            "trace": trace.as_dict(),
        }
        path = Path("traces") / f"case_{trace.trace_id}.json"
        path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        return {"bundle_path": str(path), "bundle": bundle, "decision": decision.as_dict()}

    def _save_trace(self, trace: AuditTrace, customer_id: str, invoice_id: str) -> Path:
        path = Path("traces") / f"governed_run_{customer_id}_{invoice_id}.json"
        trace.save(path)
        return path
