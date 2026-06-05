from typing import Any

from enterprise_agent_control_plane import fake_tools
from enterprise_agent_control_plane.baseline_agent import BaselineAgent
from enterprise_agent_control_plane.baseline_router import (
    route_greedy,
    route_injection_exfil,
    route_injection_naive,
    route_v1,
    route_v2,
)
from enterprise_agent_control_plane.baseline_runner import aggregate_session_side_effects
from enterprise_agent_control_plane.governed_agent import GovernedAgent
from enterprise_agent_control_plane.scenarios import WORKLOAD


def _leaked_field_count(result: dict[str, Any]) -> int:
    """Total raw, task-irrelevant fields the baseline forwarded into model context."""
    return sum(len(extra) for extra in result["leaked_fields"].values())


def print_workload(customer_id: str, invoice_id: str) -> dict[str, Any]:
    """Run the realistic multi-case workload, one annotated block per case (#33, #8).

    Returns the refund case result so later sections can reuse it.
    """
    print("\n[1] Unsafe baseline -- realistic multi-case Customer Operations workload")
    refund_result: dict[str, Any] = {}
    for scenario in WORKLOAD:
        fake_tools.reset_state()
        result = BaselineAgent(router=route_v1).run_case(
            scenario.request, scenario.customer_id, scenario.invoice_id
        )
        caps = [s["capability"] for s in result["steps"]]
        writes = [w["capability"] for w in result["policy_blind_writes"]]
        print(f"\n  case {scenario.name!r}: {scenario.request!r} -> steps {caps or '[]'}")
        print(f"    demonstrates: {scenario.demonstrates}")
        if writes:
            print(f"    RISK policy-blind write(s): {writes}")
        if not caps:
            print("    RISK unbounded router stalled: no flow matched, the agent does nothing useful")
        if result["precondition_gaps"]:
            print(f"    RISK execution-contract gaps: {len(result['precondition_gaps'])} (see [1e])")
        if scenario.name == "refund":
            refund_result = result
    if not refund_result:
        raise ValueError(
            "WORKLOAD must include a scenario named 'refund'; the anatomy and contrast "
            "sections depend on it."
        )
    return refund_result


def print_refund_anatomy(baseline: dict[str, Any]) -> None:
    """Detailed risk anatomy of the refund case (#8), incl. cumulative growth (#42)."""
    print("\n[1a] Risk anatomy of the refund case")
    print(
        f"RISK over-permissioned context: {baseline['tools_offered_each_step']} tools offered every step "
        f"-> full-catalog context = {baseline['full_catalog_context_chars']} chars "
        f"(~{baseline['approx_context_tokens']} tokens)"
    )
    print("Per-step routing (no bounded shortlist):")
    for step in baseline["steps"]:
        print(f"  step {step['step']}: picked {step['capability']} (chose from {step['tools_offered']} tools)")
    print(f"RISK deterministic path run as model steps: {baseline['compilation_note']}")
    print(
        f"RISK per-step model round-trips: {baseline['model_decisions']} router decisions on a "
        f"fixed path (a compiled flow needs ~1) -- {baseline['model_decision_note']}"
    )

    print("RISK raw-output leakage (fields forwarded but not needed for the task):")
    for capability, extra in baseline["leaked_fields"].items():
        if extra:
            print(f"  {capability}: {extra}")

    print("RISK cumulative context growth (full catalog re-sent + raw outputs retained):")
    for point in baseline["context_growth"]:
        print(f"  after step {point['step']}: {point['cumulative_context_chars']} chars of model-visible context")
    growth = baseline["context_growth"]
    if len(growth) >= 2:
        delta = growth[-1]["cumulative_context_chars"] - growth[0]["cumulative_context_chars"]
        print(f"  -> context grew {delta} chars across the run; a bounded shortlist + Frame would flatten this")

    print("RISK policy-blind write/destructive actions (no gate stood between intent and execution):")
    for write in baseline["policy_blind_writes"]:
        print(
            f"  {write['capability']}: principal={write['principal']} token={write['capability_token']} "
            f"policy_decision={write['policy_decision']}"
        )

    print("RISK audit-light logging (flat free-text, not a structured trace):")
    for line in baseline["logs"]:
        print(f"  {line}")
    print("  These logs cannot answer:")
    for question in baseline["audit_open_questions"]:
        print(f"    - {question}")


def print_eval_blind(customer_id: str, invoice_id: str) -> None:
    print("\n[1b] Router change shipped without offline evaluation")
    fake_tools.reset_state()
    email_v1 = BaselineAgent(router=route_v1).run_case("send direct email reply", customer_id, invoice_id)
    fake_tools.reset_state()
    email_v2 = BaselineAgent(router=route_v2).run_case("send direct email reply", customer_id, invoice_id)
    print(f"  v1 route: {[s['capability'] for s in email_v1['steps']]}")
    print(f"  v2 route: {[s['capability'] for s in email_v2['steps']]}")
    print(
        "  v2 quietly changed a send->draft decision and was shipped on intuition, with no offline "
        "comparison (see evals/sample_routing_logs.csv; the eval lane would score this)."
    )


def print_poor_selection(customer_id: str, invoice_id: str) -> None:
    """Poor tool selection caused by the unbounded catalog (#30)."""
    print("\n[1c] Poor tool selection from the unbounded catalog")
    request = "look into the billing charge for this customer"
    fake_tools.reset_state()
    greedy = BaselineAgent(router=route_greedy).run_case(request, customer_id, invoice_id)
    caps = [s["capability"] for s in greedy["steps"]]
    print(f"  request: {request!r} (a lookup; only billing.get_invoice was warranted)")
    print(f"  route_greedy picked: {caps}")
    if "billing.issue_refund" in caps:
        print(
            "  RISK tool-selection error: with all nine tools equally present, the router reached the "
            "high-risk billing.issue_refund instead of stopping at the lookup. A bounded ChoiceCard "
            "shortlist (issue #24) would have excluded the destructive candidate."
        )


def print_injection(customer_id: str, invoice_id: str) -> None:
    """Indirect prompt injection via untrusted tool output (#31)."""
    print("\n[1d] Indirect prompt injection via untrusted tool output")
    request = "review this customer's latest ticket"
    fake_tools.reset_state()
    injected = BaselineAgent(router=route_injection_naive).run_case(request, customer_id, invoice_id)
    caps = [s["capability"] for s in injected["steps"]]
    print(f"  request: {request!r} (a benign read; no write was authorized)")
    print(f"  route picked: {caps}")
    planted = next(
        (t["agent_comments"] for t in fake_tools.TICKETS.get(customer_id, []) if "refund" in t["agent_comments"].lower()),
        "",
    )
    print(f"  planted (untrusted) ticket text: {planted!r}")
    if "billing.issue_refund" in caps:
        print(
            "  RISK no provenance boundary: instructions and tool data share one undifferentiated context, "
            "so the injected directive steered the baseline into a refund the request never asked for. A "
            "safe Frame / context firewall (issue #22) would quarantine ticket text as data."
        )


def print_missing_contract(customer_id: str, invoice_id: str) -> None:
    """Destructive refund with no execution contract (#32)."""
    print("\n[1e] Destructive refund with no execution contract")
    fake_tools.reset_state()
    bad = BaselineAgent(router=route_v1).run_case("refund request", "C-404", "INV-404")
    invoice = bad["raw_outputs"].get("billing.get_invoice")
    refund = bad["raw_outputs"].get("billing.issue_refund")
    print(f"  unknown invoice 'INV-404' -> billing.get_invoice returned: {invoice}")
    print(f"  yet billing.issue_refund still executed: {refund}")
    for gap in bad["precondition_gaps"]:
        print(f"    RISK {gap}")

    fake_tools.reset_state()
    agent = BaselineAgent(router=route_v1)
    agent.run_case("refund request", customer_id, invoice_id)
    agent.run_case("refund request", customer_id, invoice_id)
    print(f"  running the same valid case twice -> {len(fake_tools.REFUNDS)} refunds recorded (no idempotency guard)")


def print_lost_correction(customer_id: str, invoice_id: str) -> None:
    """Recurring operator correction lost -- no lesson capture (#34)."""
    print("\n[1f] Recurring operator correction lost (no lesson capture)")
    fake_tools.reset_state()
    agent = BaselineAgent(router=route_v1)
    run1 = agent.run_case("refund request", customer_id, invoice_id)
    status1 = run1["raw_outputs"]["billing.issue_refund"]["status"]
    print(f"  run 1: refund {status1}; operator correction noted: 'this refund should have required approval'")
    run2 = agent.run_case("refund request", customer_id, invoice_id)
    status2 = run2["raw_outputs"]["billing.issue_refund"]["status"]
    print(f"  run 2 (same case): refund {status2} again -- the correction was never captured")
    print(
        f"  RISK no learning loop: {len(fake_tools.REFUNDS)} identical refunds across runs; nothing persisted "
        "the correction. See docs/lesson-capture-gap.md; lessonweaver (issue #6) is the fix."
    )


def print_silent_failure(customer_id: str, invoice_id: str) -> None:
    """Read failure silently absorbed on a non-destructive path (#73)."""
    print("\n[1g] Silent absorption of a read failure (no execution contract)")
    fake_tools.reset_state()
    # An unknown customer on the email path: the lookup fails, but the agent drafts/sends
    # against placeholder data and the run reports no failure.
    result = BaselineAgent(router=route_v1).run_case("send a direct email reply", "C-404", invoice_id)
    customer = result["raw_outputs"].get("crm.search_customer")
    print(f"  unknown customer 'C-404' -> crm.search_customer returned: {customer}")
    print(f"  steps still run: {[s['capability'] for s in result['steps']]}")
    for gap in result["silent_failures"]:
        print(f"    RISK {gap}")
    print(
        f"  run-level failure_signal = {result['failure_signal']}: the degraded run looks "
        "successful. An execution contract (agent-kernel) + structured trace would surface it."
    )


def print_exfiltration(customer_id: str, invoice_id: str) -> None:
    """Sensitive-data exfiltration via the ungated email send (#103)."""
    print("\n[1h] Sensitive-data exfiltration via ungated email send (no egress boundary)")
    fake_tools.reset_state()
    request = "review this customer's latest ticket"
    result = BaselineAgent(router=route_injection_exfil).run_case(request, customer_id, invoice_id)
    sent = fake_tools.SENT_EMAILS[-1] if fake_tools.SENT_EMAILS else {}
    print(f"  request: {request!r} (a benign read; no external send authorized)")
    print(f"  route picked: {[s['capability'] for s in result['steps']]}")
    print(f"  email.send_reply -> to={sent.get('to')!r} (external address taken from injected [FAKE] data)")
    if "payment_method" in sent.get("body", ""):
        print("  RISK no egress boundary: untrusted in-context data chose BOTH the destination AND the payload;")
        print("    sensitive fields were available only because raw outputs were forwarded verbatim (#16),")
        print("    and no policy decision stood before the send (#17). An AgentFence egress gate is the contrast.")


def print_log_leakage(baseline: dict[str, Any]) -> None:
    """Sensitive fields persisted verbatim in the durable log surface (#106)."""
    print("\n[1i] Sensitive fields leaking into the durable log surface (no redaction)")
    debug_lines = [line for line in baseline["logs"] if "[debug]" in line]
    present = sorted(
        field for field in ("payment_method", "internal_notes", "risk_flags")
        if any(field in line for line in debug_lines)
    )
    print(f"  {len(debug_lines)} raw-payload [debug] log line(s) carry sensitive-looking fields: {present}")
    print(
        "  RISK these persist into traces/unsafe_run.json verbatim -- a second exposure beyond "
        "model context (#16) that outlives the run and could ship to log aggregation. A bounded "
        "Frame would project only task-relevant fields into both context and logs."
    )


def print_no_aggregate_budget() -> None:
    """No run/session-level ceiling on side-effecting actions (#109)."""
    print("\n[1j] No aggregate ceiling/throttle on side-effecting actions")
    agg = aggregate_session_side_effects()
    print(
        f"  over the {agg['cases']}-case workload: refunds={agg['refunds']} "
        f"(value={agg['total_refund_value']}), emails={agg['emails_sent']}, tasks={agg['tasks_created']}"
    )
    print(
        f"  total side-effecting actions = {agg['total_side_effecting_actions']}; "
        f"aggregate_ceiling = {agg['aggregate_ceiling']}"
    )
    print(
        "  RISK nothing caps the count of writes or total money moved across a session; an "
        "AgentFence budget / agent-kernel usage-scoped token would supply the ceiling."
    )


def print_contrast(baseline: dict[str, Any], governed: dict[str, Any]) -> None:
    """Side-by-side baseline-vs-governed scorecard on shared dimensions (#8)."""
    print("\n[3] Side-by-side contrast (same refund case, both paths)")
    rows = [
        ("tools exposed to the model", baseline["tools_offered_each_step"], len(governed["visible_tools"])),
        ("raw sensitive fields in model context", _leaked_field_count(baseline), 0),
        ("ungated write/destructive actions", len(baseline["policy_blind_writes"]), 0),
        (
            "policy decisions recorded",
            0,
            1 if governed["decision"] is not None else 0,
        ),
        (
            "structured audit trace",
            "none" if baseline["structured_audit_trace"] is None else "yes",
            "yes",
        ),
    ]
    width = max(len(label) for label, _, _ in rows)
    print(f"  {'dimension'.ljust(width)} | {'baseline':>10} | {'governed':>10}")
    print(f"  {'-' * width} | {'-' * 10} | {'-' * 10}")
    for label, base_val, gov_val in rows:
        print(f"  {label.ljust(width)} | {str(base_val):>10} | {str(gov_val):>10}")
    print(f"  gated action: {governed['bounded_output']['gated_capability']} -> {governed['bounded_output']['action_status']}")


def main() -> None:
    customer_id = "C-100"
    invoice_id = "INV-9"

    print("=== Customer Operations Agent Demo ===")

    baseline = print_workload(customer_id, invoice_id)
    print_refund_anatomy(baseline)
    print_eval_blind(customer_id, invoice_id)
    print_poor_selection(customer_id, invoice_id)
    print_injection(customer_id, invoice_id)
    print_missing_contract(customer_id, invoice_id)
    print_lost_correction(customer_id, invoice_id)
    print_silent_failure(customer_id, invoice_id)
    print_exfiltration(customer_id, invoice_id)
    print_log_leakage(baseline)
    print_no_aggregate_budget()

    print("\n[2] Governed control plane")
    fake_tools.reset_state()
    agent = GovernedAgent()
    governed = agent.run_case("refund request", customer_id, invoice_id, principal="support_agent")
    print(f"Principal: support_agent | intent: {governed['intent']} -> flow: {governed['flow']}")
    metric = governed["context_metric"]
    print(
        f"Context firewall (#24): model-visible shortlist = {metric['shortlist_chars']} chars "
        f"vs full catalog {metric['full_catalog_chars']} chars ({metric['reduction_pct']}% smaller)"
    )
    print(f"Enforced capability budget (#110): {len(governed['visible_tools'])} -> {governed['visible_tools']}")
    print(f"Deterministic flow steps: {governed['bounded_output']['flow_steps']}")
    if governed["frames"]:
        first = governed["frames"][0]
        print(f"Bounded Frame (#22/#37) for {first['capability']}: {first['summary']}")
        print(
            f"  handle={first['handle']} untrusted={first['untrusted']} "
            f"redacted={first['redacted_fields']} (raw detail kept out of model context)"
        )
    print(
        f"Gated action {governed['bounded_output']['gated_capability']} "
        f"({governed['bounded_output']['action_class']}) -> {governed['bounded_output']['action_status']}"
    )
    print(f"  reason: {governed['bounded_output']['decision_reason']}")
    print(f"Bounded output frame: {governed['bounded_output']}")
    print(f"Audit trace emitted: {governed['audit_trace_path']}")

    export = agent.export_case(governed["trace"], principal="support_manager")
    print(f"Explainable case bundle exported: {export['bundle_path']} (decision: {export['decision']['outcome']})")

    print_frame_expansion(agent, governed)

    print("\n[2b] One scenario, three policy outcomes (allow / deny / approval-required)")
    fake_tools.reset_state()
    scenario = agent.run_decision_scenario(principal="support_agent")
    for d in scenario["decisions"]:
        print(f"  {d['capability']} ({d['action_class']}): decision={d['decision']} -> outcome={d['outcome']}")
        print(f"    reason: {d['reason']}")

    print("\n[2c] Approval handling for 'ask' decisions (injectable approver)")
    fake_tools.reset_state()
    approved = GovernedAgent(approver=lambda req: True).run_case(
        "refund request", customer_id, invoice_id, principal="support_agent"
    )
    fake_tools.reset_state()
    rejected = GovernedAgent(approver=lambda req: False).run_case(
        "refund request", customer_id, invoice_id, principal="support_agent"
    )
    print(f"  approver approves -> {approved['bounded_output']['action_status']}")
    print(f"  approver rejects  -> {rejected['bounded_output']['action_status']}")
    print(f"  no approver       -> {governed['bounded_output']['action_status']}")

    print_execution_contract(customer_id, invoice_id)

    print_contrast(baseline, governed)
    print_eval_lane()


def print_execution_contract(customer_id: str, invoice_id: str) -> None:
    """Governed write-path execution contract (#38, #41, #64, #66, #113)."""
    print("\n[2d] Governed write-path execution contract")

    # #66 — a two-write flow gates each write independently.
    fake_tools.reset_state()
    two_write = GovernedAgent().run_case("refund and notify the customer", customer_id, invoice_id)
    print("  gate every write a flow touches (#66):")
    for action in two_write["bounded_output"]["gated_actions"]:
        print(f"    {action['capability']} -> {action['action_status']} (commit: {action['commit_mode']})")

    # #41 — a not-found dependency halts the flow before any write.
    fake_tools.reset_state()
    halted = GovernedAgent().run_case("refund request", "C-100", "INV-404")
    print(
        f"  fail-closed steps (#41): INV-404 -> status={halted['bounded_output']['status']}, "
        f"refunds recorded={len(fake_tools.REFUNDS)} (no write ran)"
    )

    # #38 + #113 — commit only on allow, and at most once per case.
    fake_tools.reset_state()
    agent = GovernedAgent(approver=lambda req: True)
    first = agent.run_case("refund request", customer_id, invoice_id)
    second = agent.run_case("refund request", customer_id, invoice_id)
    print(
        f"  commit boundary + idempotency (#38/#113): run1={first['bounded_output']['gated_actions'][0]['commit_mode']}, "
        f"run2={second['bounded_output']['gated_actions'][0]['commit_mode']}, "
        f"refunds recorded={len(fake_tools.REFUNDS)}"
    )

    # #64 — self-approval is rejected even with an approver that would say yes.
    fake_tools.reset_state()
    self_approved = GovernedAgent(approver=lambda req: True, approver_principal="support_agent").run_case(
        "refund request", customer_id, invoice_id, principal="support_agent"
    )
    print(
        f"  separation of duties (#64): support_agent self-approval -> "
        f"{self_approved['bounded_output']['action_status']}"
    )


def print_frame_expansion(agent: GovernedAgent, governed: dict[str, Any]) -> None:
    """Gated, audited access to a Frame's redacted raw detail (#114)."""
    print("\n[2e] Gated Frame expansion (controlled access to redacted detail)")
    invoice_frame = next(
        (f for f in governed["frames"] if f["capability"] == "billing.get_invoice"), None
    )
    if invoice_frame is None:
        print("  (no invoice frame in this case)")
        return
    handle = invoice_frame["handle"]
    print(f"  frame {handle} redacts: {invoice_frame['redacted_fields']}")
    denied = agent.expand_frame(handle, "support_agent", trace=governed["trace"])
    print(f"  support_agent expand -> {denied['outcome']}: summary only, raw detail withheld")
    allowed = agent.expand_frame(handle, "support_manager", trace=governed["trace"])
    print(
        f"  support_manager expand -> {allowed['outcome']}: revealed {allowed['revealed_fields']} "
        "(who/what/when recorded in the audit trace)"
    )


def print_eval_lane() -> None:
    """One-line summary of the offline evaluation lane (#7, #40)."""
    from enterprise_agent_control_plane import evals

    print("\n[4] Offline evaluation lane (scored before deployment; run `make eval`)")
    for r in evals.evaluate_routers():
        print(f"  router {r.candidate}: {r.score:.0%} ({r.notes})")
    report = evals.evaluate_policy()
    print(
        f"  policy golden set: {report.accuracy:.0%} matched "
        f"({report.total} cases, {len(report.unsafe_drift)} unsafe-drift)"
    )


if __name__ == "__main__":
    main()
