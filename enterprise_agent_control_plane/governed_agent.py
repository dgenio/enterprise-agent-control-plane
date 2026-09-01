import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from . import fake_tools
from .audit import AuditTrace
from .catalog import (
    build_catalog,
    build_tool_definitions,
    context_reduction,
    shortlist_capabilities,
)
from .errors import ErrorCode, error, is_error
from .flows import FLOW_REGISTRY, ChainWeaverExecutor, select_flow
from .frames import Frame, FrameStore, field_names
from .policies import (
    ACTION_CLASSES,
    CASE_TOKEN_TTL_SECONDS,
    AgentFencePolicy,
    CapabilityToken,
    PolicyDecision,
    holds_capability,
    issue_case_tokens,
    issue_tokens,
    may_approve,
)
from .registry import build_tool_map, risk_of, sensitive_fields

# Sentinel so callers can pass ``approver=None`` to mean "no approver" (leave 'ask'
# pending) while omitting it falls back to the agent's configured approver.
_USE_DEFAULT: Any = object()

# Outcomes that mean a gated action is cleared to take effect (issue #38).
_COMMITTABLE_OUTCOMES = frozenset({"allowed", "approved"})

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
    action_class: str | None
    decision: str  # raw policy decision: allow / ask / deny
    outcome: str  # allowed / approved / approval_required / approval_denied / denied
    reason: str
    token_valid: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class GovernedAgent:
    def __init__(
        self,
        policy: AgentFencePolicy | None = None,
        approver: Approver | None = None,
        approver_principal: str = "support_manager",
    ):
        self.catalog = build_catalog()
        self.policy = policy or AgentFencePolicy()
        self.approver = approver
        # The identity an injected approver acts as; used to enforce separation of duties
        # (no self-approval) and approver authority for the action class (issue #64).
        self.approver_principal = approver_principal
        # Case-scoped idempotency ledger: ``(trace_id, capability)`` keys for writes already
        # committed by this agent, so replaying the same case does not double-execute (#113).
        self._committed: set[tuple[str, str]] = set()
        # Capability -> callable, derived from the single registry so the agent's tool map
        # cannot drift from the catalog / action classes (issue #65).
        self.tools = build_tool_map()
        self.executor = ChainWeaverExecutor(self.tools)
        # The bounded Frames from the most recent run, addressable by handle for a later gated
        # expansion (issue #114). Replaced per ``run_case``; starts empty.
        self.frame_store = FrameStore()

    def decide(
        self,
        capability: str,
        principal: str,
        args: dict[str, Any] | None = None,
        trace: AuditTrace | None = None,
        approver: Any = _USE_DEFAULT,
        approver_principal: Any = _USE_DEFAULT,
        tokens: Iterable[CapabilityToken] | None = None,
        scope: str | None = None,
    ) -> GovernedDecision:
        """Gate one capability: token check (issue #23) -> policy (issues #2/#36) ->
        approval routing for 'ask' (issue #5/#64). Records an explainable trace event (#27).

        ``tokens`` lets a caller supply the case-scoped tokens minted for the current run
        (issue #63); when ``None`` the principal's standing role tokens are used, so a direct
        ``decide`` call still works outside a case. ``scope`` (the case/trace id) binds the
        token check to a single case so a case-scoped token cannot be replayed in another
        context (issue #63); ``None`` skips the scope check for standalone/standing-grant calls.
        """
        args = args or {}
        approver = self.approver if approver is _USE_DEFAULT else approver
        approver_principal = (
            self.approver_principal if approver_principal is _USE_DEFAULT else approver_principal
        )

        # Token layer first: an out-of-scope capability for a principal is rejected
        # before any policy evaluation (issue #23). The token set is either the case-scoped
        # grant minted for this run (issue #63) or the standing role grant when called alone.
        tokens = list(tokens) if tokens is not None else issue_tokens(principal)
        if not holds_capability(tokens, capability, scope=scope):
            decision = GovernedDecision(
                capability,
                principal,
                ACTION_CLASSES.get(capability),
                "deny",
                "denied",
                f"{principal} holds no valid capability token for {capability}.",
                False,
            )
            if trace is not None:
                trace.record(
                    principal, "policy.decision", "denied", self._policy_event_details(decision)
                )
            return decision

        policy_decision = self.policy.evaluate(capability, principal, args)
        outcome, reason = self._resolve(
            policy_decision, principal, capability, args, approver, approver_principal, trace
        )
        decision = GovernedDecision(
            capability,
            principal,
            policy_decision.action_class,
            policy_decision.decision,
            outcome,
            reason,
            True,
        )
        if trace is not None:
            trace.record(
                principal, "policy.decision", outcome, self._policy_event_details(decision)
            )
        return decision

    def _policy_event_details(self, decision: GovernedDecision) -> dict[str, Any]:
        """Decision payload stamped with the deciding policy's provenance (issue #70)."""
        provenance = self.policy.provenance()
        return {
            **decision.as_dict(),
            "policy_version": provenance["policy_version"],
            "policy_thresholds": provenance["thresholds"],
        }

    @staticmethod
    def _result_ref(record: dict[str, Any]) -> str | None:
        """A bounded reference to a step's output -- a content digest, not the raw payload.

        Keeping a short hash rather than the raw output in the trace means a per-step event
        is attributable without leaking the sensitive fields the bounded frame redacts.
        """
        output = record.get("output")
        if output is None:
            return None
        canonical = json.dumps(output, sort_keys=True, default=str)
        return f"{record.get('step')}#{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:8]}"

    def _resolve(
        self,
        policy_decision: PolicyDecision,
        principal: str,
        capability: str,
        args: dict[str, Any],
        approver: Approver | None,
        approver_principal: str | None,
        trace: AuditTrace | None,
    ) -> "tuple[str, str]":
        if policy_decision.decision == "allow":
            return "allowed", policy_decision.reason
        if policy_decision.decision == "deny":
            return "denied", policy_decision.reason

        # 'ask' routes through the approval step (issue #5).
        if approver is None:
            if trace is not None:
                trace.record(
                    principal,
                    "approval.request",
                    "pending",
                    {"capability": capability, "reason": policy_decision.reason},
                )
            return (
                "approval_required",
                policy_decision.reason + " No approver configured; left pending.",
            )

        # Separation of duties (issue #64): the approver must be a different, authorized
        # principal. A self-approval or an approver without authority for this action class is
        # rejected with a recorded reason -- it never reaches the approver callable.
        if approver_principal == principal:
            reason = (
                policy_decision.reason
                + f" Rejected: {principal} cannot approve their own {capability} (self-approval)."
            )
            if trace is not None:
                trace.record(
                    principal,
                    "approval.resolved",
                    "denied",
                    {
                        "capability": capability,
                        "approver": approver_principal,
                        "authority_basis": "self_approval_rejected",
                    },
                )
            return "approval_denied", reason
        if not may_approve(approver_principal or "", policy_decision.action_class):
            reason = (
                policy_decision.reason
                + f" Rejected: {approver_principal} is not authorized to approve "
                f"{policy_decision.action_class} actions."
            )
            if trace is not None:
                trace.record(
                    principal,
                    "approval.resolved",
                    "denied",
                    {
                        "capability": capability,
                        "approver": approver_principal,
                        "authority_basis": "unauthorized_approver",
                    },
                )
            return "approval_denied", reason

        if trace is not None:
            trace.record(
                principal,
                "approval.request",
                "requested",
                {"capability": capability, "reason": policy_decision.reason},
            )
        approved = approver(ApprovalRequest(principal, capability, policy_decision.reason, args))
        resolution = "approved" if approved else "denied"
        authority_basis = f"{approver_principal} authorized for {policy_decision.action_class}"
        if trace is not None:
            trace.record(
                principal,
                "approval.resolved",
                resolution,
                {
                    "capability": capability,
                    "approver": approver_principal,
                    "authority_basis": authority_basis,
                },
            )
        if approved:
            return "approved", policy_decision.reason + f" Approved by {approver_principal}."
        return "approval_denied", policy_decision.reason + f" Rejected by {approver_principal}."

    def run_case(
        self,
        request: str,
        customer_id: str,
        invoice_id: str,
        principal: str = "support_agent",
        approver: Any = _USE_DEFAULT,
        approver_principal: Any = _USE_DEFAULT,
        capability_budget: Optional["set[str] | frozenset[str]"] = None,
    ) -> dict[str, Any]:
        """Run one governed case end to end.

        ``capability_budget`` (issue #110) overrides the case's computed capability budget.
        It exists so a caller/test can prove enforcement: a flow step outside the supplied
        budget fails closed before any write. When ``None`` the budget is derived from the
        bounded shortlist plus the selected flow's capabilities.
        """
        approver = self.approver if approver is _USE_DEFAULT else approver
        approver_principal = (
            self.approver_principal if approver_principal is _USE_DEFAULT else approver_principal
        )
        self.frame_store = FrameStore()
        trace = AuditTrace(trace_id=f"trace-{customer_id}-{invoice_id}")

        intent, flow_id = select_flow(request)
        trace.record(
            principal,
            "request.received",
            "ok",
            {"request": request, "intent": intent, "principal": principal},
        )

        if flow_id is None:
            # Unknown/unsupported intent: explicit no-match, no silent default (issue #25).
            trace.record(
                principal,
                "flow.select",
                "no_match",
                {"intent": intent, "reason": "no governed flow registered for this request"},
            )
            # Mirror the matched-flow frame's key set so consumers can index a stable
            # bounded_output schema regardless of whether a flow matched (issue #25).
            frame: dict[str, Any] = {
                "request": request,
                "intent": intent,
                "flow": None,
                "status": "no_matching_flow",
                "flow_steps": [],
                "gated_capability": None,
                "action_status": "no_matching_flow",
                "decision_reason": f"No governed flow matches request {request!r}.",
                "action_class": None,
                "capability_token_valid": None,
                "gated_actions": [],
            }
            trace.record(principal, "output.frame", "no_match", frame)
            path = self._save_trace(trace, customer_id, invoice_id, intent)
            return {
                "mode": "governed",
                "request": request,
                "intent": intent,
                "flow": None,
                "visible_tools": [],
                "decision": None,
                "decisions": [],
                "bounded_output": frame,
                "frames": [],
                "context_metric": None,
                "audit_trace_path": str(path),
                "trace": trace,
            }

        # Bounded shortlist; the why is recorded so the trace is explainable (issue #27). The
        # context-size reduction vs the baseline's full catalog is measured here (issue #24).
        shortlist = shortlist_capabilities(request, self.catalog)
        context_metric = context_reduction(shortlist, build_tool_definitions())

        # The case capability budget (issue #110): the bounded shortlist made enforceable at the
        # executor. It is the union of the model-visible shortlist and the selected flow's step +
        # gated capabilities, computed BEFORE execution and enforced by the executor -- not a
        # post-hoc union reported after running against the full tool map. ``visible_tools`` is
        # this enforced budget. Note the default budget contains the flow's own capabilities by
        # construction, so on a normal case it never spuriously halts a real step; the executor's
        # out-of-budget fail-closed path is exercised by a narrowed ``capability_budget`` override.
        flow = FLOW_REGISTRY[flow_id]
        flow_caps = {step.capability for step in flow.steps}
        if capability_budget is None:
            budget = {c.capability for c in shortlist} | flow_caps | set(flow.gated_capabilities)
        else:
            # An override still always includes the flow's gated capabilities, so a gated write
            # can never be settled outside the enforced budget / visible_tools even when a
            # caller deliberately narrows the budget -- keeping the boundary self-consistent.
            budget = set(capability_budget) | set(flow.gated_capabilities)
        visible_tools = sorted(budget)

        # Just-in-time, case-scoped capability tokens (issue #63): mint only the tokens this
        # case's flow steps plus its gated action need, scoped to this trace and short-lived,
        # rather than the principal's full standing role grant. The role still bounds what can
        # be minted (least privilege twice), so a capability the role grants but this case did
        # not request is never issued for the run.
        needed_caps = flow_caps | set(flow.gated_capabilities)
        case_tokens = issue_case_tokens(principal, needed_caps, scope=trace.trace_id)

        trace.record(
            principal,
            "shortlist",
            "ok",
            {
                "capabilities": [c.capability for c in shortlist],
                "reason": f"keyword shortlist for intent {intent!r}; full catalog kept out of model context",
                "budget": sorted(budget),
                "context_metric": context_metric,
                # Case-scoped token provenance (issue #63): which capabilities were granted just
                # for this case, the scope they are bound to, and their TTL.
                "case_tokens": [t.capability for t in case_tokens],
                "case_token_scope": trace.trace_id,
                "case_token_ttl_seconds": CASE_TOKEN_TTL_SECONDS,
            },
        )

        trace.record(
            principal,
            "flow.select",
            "ok",
            {
                "intent": intent,
                "flow_id": flow_id,
                "reason": f"intent {intent!r} maps to deterministic flow {flow_id!r}",
            },
        )

        # Each flow step is token-checked and recorded as its own audit event so the trace
        # explains the run step-by-step, and read steps are subject to the same
        # least-privilege token check as the gated write (issue #111). The check uses the
        # case-scoped tokens minted above (issue #63), not the standing role grant.
        tokens = case_tokens

        def _on_step(record: dict[str, Any]) -> None:
            outcome = {"ok": "ok", "blocked_no_token": "blocked_no_token"}.get(
                record["status"], record["status"]
            )
            trace.record(
                principal,
                "flow.step",
                outcome,
                {
                    "step": record["step"],
                    "capability": record["capability"],
                    "token_valid": record["token_valid"],
                    "result_ref": self._result_ref(record),
                },
            )

        payload = {
            "customer_id": customer_id,
            "invoice_id": invoice_id,
            "customer_name": "Ari Carter",
        }
        flow_results = self.executor.run(
            flow_id,
            payload,
            token_check=lambda cap: holds_capability(tokens, cap, scope=trace.trace_id),
            on_step=_on_step,
            budget=budget,
        )
        executed = [r for r in flow_results if r["status"] == "ok"]
        trace.record(
            principal,
            "flow.execute",
            "ok",
            {
                "flow_id": flow_id,
                "steps": len(executed),
                "blocked": len(flow_results) - len(executed),
            },
        )

        # Wrap each executed step's raw output in a bounded Frame (issues #22/#37): the raw
        # payload is stashed behind an opaque handle in the frame store, sensitive fields are
        # redacted, and the model-visible record is the value-free summary marked untrusted.
        # The raw ``flow_results`` stay available to the control plane below (e.g. to read the
        # invoice amount for the gate) -- the firewall is on what the MODEL sees, not the agent.
        frames = self._wrap_frames(executed, trace, principal)

        # Fail closed (issue #41/#110): if any step failed, the flow halted -- no gated write
        # runs. An out-of-budget step (#110) is the same fail-closed path with a budget reason.
        failed_step = next((r for r in flow_results if r["status"] == "failed"), None)
        if failed_step is not None:
            out = failed_step.get("output")
            if is_error(out, ErrorCode.OUT_OF_BUDGET):
                reason = (
                    f"step {failed_step['step']!r} ({failed_step['capability']}) is outside the "
                    f"case capability budget {sorted(budget)}; flow halted before any write (issue #110)."
                )
            else:
                reason = f"step {failed_step['step']!r} ({failed_step['capability']}) failed; flow halted before any write."
            trace.record(
                principal,
                "flow.halt",
                "halted",
                {
                    "step": failed_step["step"],
                    "capability": failed_step["capability"],
                    "reason": reason,
                },
            )
            frame = {
                "request": request,
                "intent": intent,
                "flow": flow_id,
                "status": "halted",
                "flow_steps": [r["step"] for r in flow_results],
                "gated_capability": None,
                "action_status": "halted",
                "decision_reason": reason,
                "action_class": None,
                "capability_token_valid": None,
                "gated_actions": [],
            }
            trace.record(principal, "output.frame", "halted", frame)
            path = self._save_trace(trace, customer_id, invoice_id, intent)
            return {
                "mode": "governed",
                "request": request,
                "intent": intent,
                "flow": flow_id,
                "visible_tools": visible_tools,
                "decision": None,
                "decisions": [],
                "bounded_output": frame,
                "frames": [f.as_dict() for f in frames],
                "context_metric": context_metric,
                "audit_trace_path": str(path),
                "trace": trace,
            }

        # Gate EVERY write/destructive capability the flow performs, not one hardcoded action
        # (issue #66). Each gets its own parameter-aware decision; an allowed/approved write is
        # then committed exactly once per case (issues #38/#113).
        decisions: list[GovernedDecision] = []
        gated_actions: list[dict[str, Any]] = []
        for capability in FLOW_REGISTRY[flow_id].gated_capabilities:
            gate_args = self._gate_args(capability, flow_results)
            decision = self.decide(
                capability,
                principal,
                gate_args,
                trace=trace,
                approver=approver,
                approver_principal=approver_principal,
                tokens=case_tokens,
                scope=trace.trace_id,
            )
            commit_mode = self._settle_write(
                capability, decision, trace, principal, payload, flow_results
            )
            decisions.append(decision)
            gated_actions.append(
                {
                    "capability": capability,
                    "action_status": decision.outcome,
                    "action_class": decision.action_class,
                    "decision_reason": decision.reason,
                    "capability_token_valid": decision.token_valid,
                    "commit_mode": commit_mode,
                }
            )

        primary = gated_actions[0] if gated_actions else None
        frame = {
            "request": request,
            "intent": intent,
            "flow": flow_id,
            "status": "ok",
            "flow_steps": [r["step"] for r in flow_results],
            # Singular fields describe the primary gated action (the first the flow performs)
            # for at-a-glance reading; ``gated_actions`` is the authoritative per-write list.
            "gated_capability": primary["capability"] if primary else None,
            "action_status": primary["action_status"] if primary else None,
            "decision_reason": primary["decision_reason"] if primary else None,
            "action_class": primary["action_class"] if primary else None,
            "capability_token_valid": primary["capability_token_valid"] if primary else None,
            "gated_actions": gated_actions,
        }
        trace.record(principal, "output.frame", "ok", frame)

        path = self._save_trace(trace, customer_id, invoice_id, intent)
        return {
            "mode": "governed",
            "request": request,
            "intent": intent,
            "flow": flow_id,
            "visible_tools": visible_tools,
            "decision": decisions[0].as_dict() if decisions else None,
            "decisions": [d.as_dict() for d in decisions],
            "bounded_output": frame,
            "frames": [f.as_dict() for f in frames],
            "context_metric": context_metric,
            "audit_trace_path": str(path),
            "trace": trace,
        }

    @staticmethod
    def _invoice_amount(flow_results: list[dict[str, Any]]) -> float | None:
        """The refund amount from the flow's ``billing.get_invoice`` step, or ``None``.

        Shared by the gate-args builder and the write invocation so the decision and the
        committed side effect read the amount from one place (issue #36/#66).
        """
        invoice: Any = next(
            (r["output"] for r in flow_results if r["capability"] == "billing.get_invoice"), {}
        )
        return invoice.get("amount") if isinstance(invoice, dict) else None

    @staticmethod
    def _gate_args(capability: str, flow_results: list[dict[str, Any]]) -> dict[str, Any]:
        """Build the parameter-aware decision args for a gated write (issue #36/#66)."""
        if capability == "billing.issue_refund":
            return {"amount": GovernedAgent._invoice_amount(flow_results)}
        return {}

    def _settle_write(
        self,
        capability: str,
        decision: GovernedDecision,
        trace: AuditTrace,
        principal: str,
        payload: dict[str, Any],
        flow_results: list[dict[str, Any]],
    ) -> str:
        """Apply the side-effect boundary for one gated write (issues #38/#113).

        The write is committed only on an allowed/approved outcome, and only once per case:
        a replay of the same case is recognized via the idempotency ledger and recorded as a
        no-op. Any other outcome leaves the world unchanged (a dry-run). The mode -- one of
        ``committed`` / ``replay`` / ``dry_run`` -- is recorded as an ``action.commit`` event.
        """
        if decision.outcome not in _COMMITTABLE_OUTCOMES:
            # Not cleared to act: exercise the tool's dry-run path so nothing mutates.
            self._invoke_write(capability, payload, flow_results, commit=False)
            trace.record(
                principal,
                "action.commit",
                "dry_run",
                {
                    "capability": capability,
                    "mode": "dry_run",
                    "reason": f"outcome {decision.outcome!r} is not committable; no side effect.",
                },
            )
            return "dry_run"

        key = (trace.trace_id, capability)
        if key in self._committed:
            trace.record(
                principal,
                "action.commit",
                "replay",
                {
                    "capability": capability,
                    "mode": "replay",
                    "reason": f"{capability} already committed for case {trace.trace_id!r}; replay is a no-op.",
                },
            )
            return "replay"

        self._invoke_write(capability, payload, flow_results, commit=True)
        self._committed.add(key)
        trace.record(
            principal,
            "action.commit",
            "committed",
            {
                "capability": capability,
                "mode": "committed",
                "reason": f"outcome {decision.outcome!r}; side effect committed once for case {trace.trace_id!r}.",
            },
        )
        return "committed"

    def _invoke_write(
        self,
        capability: str,
        payload: dict[str, Any],
        flow_results: list[dict[str, Any]],
        commit: bool,
    ) -> dict[str, Any]:
        """Invoke a gated write tool in dry-run or commit mode (issue #38).

        Dispatched from a table rather than a hand-ordered ``if/elif`` chain (issue #149): each
        gated write derives its arguments differently (a refund reads the invoice amount from
        the prior flow step, a send reads the drafted subject/body), so unlike the read steps
        this is not a uniform payload binding -- but the table shares one structured
        ``unknown_write`` default (issue #174) and adds a write without editing a branch chain.
        """
        invokers: dict[
            str, Callable[[dict[str, Any], list[dict[str, Any]], bool], dict[str, Any]]
        ] = {
            "billing.issue_refund": self._write_refund,
            "email.send_reply": self._write_send_reply,
            "support.create_task": self._write_create_task,
        }
        invoker = invokers.get(capability)
        if invoker is None:
            return error(ErrorCode.UNKNOWN_WRITE, capability=capability)
        return invoker(payload, flow_results, commit)

    def _write_refund(
        self, payload: dict[str, Any], flow_results: list[dict[str, Any]], commit: bool
    ) -> dict[str, Any]:
        amount = self._invoice_amount(flow_results) or 0.0
        return self.tools["billing.issue_refund"](
            payload["invoice_id"], amount, "governed refund", commit=commit
        )

    def _write_send_reply(
        self, payload: dict[str, Any], flow_results: list[dict[str, Any]], commit: bool
    ) -> dict[str, Any]:
        draft: Any = next(
            (r["output"] for r in flow_results if r["capability"] == "email.draft_reply"), {}
        )
        subject = (
            draft.get("subject", "Update on your request") if isinstance(draft, dict) else "Update"
        )
        body = draft.get("body", "") if isinstance(draft, dict) else ""
        return self.tools["email.send_reply"](
            "[FAKE] customer@example.com", subject, body, commit=commit
        )

    def _write_create_task(
        self, payload: dict[str, Any], flow_results: list[dict[str, Any]], commit: bool
    ) -> dict[str, Any]:
        return self.tools["support.create_task"](
            payload["customer_id"], "Escalated by governed flow", commit=commit
        )

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
            ("crm.search_customer", {}),  # read -> allowed
            ("audit.export_case", {}),  # restricted -> denied for support_agent
            (
                "billing.issue_refund",
                {"amount": 149.0},
            ),  # within manager limit -> approval-required
        ]
        decisions = [
            self.decide(cap, principal, args, trace=trace, approver=approver) for cap, args in cases
        ]
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

    def _wrap_frames(
        self,
        executed: list[dict[str, Any]],
        trace: AuditTrace,
        principal: str,
    ) -> list[Frame]:
        """Wrap each executed step's raw output in a bounded, untrusted Frame (issues #22/#37).

        The raw payload is stashed behind an opaque handle in ``self.frame_store``; the trace
        and the returned result carry only the value-free Frame (summary + handle + redacted
        field names), so sensitive raw detail never reaches model-visible context.
        """
        frames: list[Frame] = []
        for record in executed:
            capability = record["capability"]
            frame = self.frame_store.wrap(
                capability,
                record["output"],
                risk=risk_of(capability),
                sensitive_fields=sensitive_fields(capability),
            )
            frames.append(frame)
            trace.record(
                principal,
                "flow.frame",
                "ok",
                {
                    "capability": capability,
                    "handle": frame.handle,
                    "redacted_fields": frame.redacted_fields,
                    "summary": frame.summary,
                    "risk": frame.risk,
                    "untrusted": frame.untrusted,
                },
            )
        return frames

    def expand_frame(
        self,
        handle: str,
        principal: str,
        trace: AuditTrace | None = None,
    ) -> dict[str, Any]:
        """Reveal a Frame's redacted raw detail as a gated, audited capability (issue #114).

        Expansion routes through :meth:`decide` (``frame.expand``): a principal not authorized
        to view raw detail is rejected at the token/policy layer and gets the bounded summary
        only (``revealed=None``). An authorized reveal returns the raw payload and records a
        ``frame.expand`` audit event naming the handle, the revealed fields, and the principal,
        so the trace can always answer who accessed sensitive raw data, when, and why.
        """
        decision = self.decide("frame.expand", principal, {"handle": handle}, trace=trace)
        if decision.outcome not in _COMMITTABLE_OUTCOMES:
            if trace is not None:
                trace.record(
                    principal,
                    "frame.expand",
                    "denied",
                    {
                        "handle": handle,
                        "outcome": decision.outcome,
                        "revealed_fields": [],
                        "reason": decision.reason,
                    },
                )
            return {
                "handle": handle,
                "outcome": decision.outcome,
                "revealed": None,
                "revealed_fields": [],
                "decision": decision.as_dict(),
            }

        if not self.frame_store.has(handle):
            if trace is not None:
                trace.record(
                    principal,
                    "frame.expand",
                    "not_found",
                    {
                        "handle": handle,
                        "outcome": decision.outcome,
                        "revealed_fields": [],
                        "reason": "no such frame handle in the current case",
                    },
                )
            return {
                "handle": handle,
                "outcome": decision.outcome,
                "revealed": None,
                "revealed_fields": [],
                "decision": decision.as_dict(),
            }

        raw = self.frame_store.expand(handle)
        revealed_fields = sorted(field_names(raw))
        if trace is not None:
            trace.record(
                principal,
                "frame.expand",
                "revealed",
                {
                    "handle": handle,
                    "outcome": decision.outcome,
                    "revealed_fields": revealed_fields,
                    "reason": f"{principal} authorized to reveal raw detail behind {handle}.",
                },
            )
        return {
            "handle": handle,
            "outcome": decision.outcome,
            "revealed": raw,
            "revealed_fields": revealed_fields,
            "decision": decision.as_dict(),
        }

    def _save_trace(
        self, trace: AuditTrace, customer_id: str, invoice_id: str, intent: str | None
    ) -> Path:
        # Include the resolved intent so cases that share a customer/invoice id (e.g. the
        # shared-id WORKLOAD scenarios run by the demo) each write a distinct trace file
        # instead of overwriting governed_run_{customer}_{invoice}.json on every run.
        path = Path("traces") / f"governed_run_{customer_id}_{invoice_id}_{intent}.json"
        trace.save(path)
        return path
