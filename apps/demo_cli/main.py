from typing import Any

from enterprise_agent_control_plane import fake_tools
from enterprise_agent_control_plane.baseline_agent import BaselineAgent
from enterprise_agent_control_plane.baseline_router import (
    route_greedy,
    route_injection_naive,
    route_v1,
    route_v2,
)
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

    print("\n[2] Governed control plane")
    fake_tools.reset_state()
    agent = GovernedAgent()
    governed = agent.run_case("refund request", customer_id, invoice_id, principal="support_agent")
    print(f"Principal: support_agent | intent: {governed['intent']} -> flow: {governed['flow']}")
    print(f"Shortlisted tools: {len(governed['visible_tools'])} -> {governed['visible_tools']}")
    print(f"Deterministic flow steps: {governed['bounded_output']['flow_steps']}")
    print(
        f"Gated action {governed['bounded_output']['gated_capability']} "
        f"({governed['bounded_output']['action_class']}) -> {governed['bounded_output']['action_status']}"
    )
    print(f"  reason: {governed['bounded_output']['decision_reason']}")
    print(f"Bounded output frame: {governed['bounded_output']}")
    print(f"Audit trace emitted: {governed['audit_trace_path']}")

    export = agent.export_case(governed["trace"], principal="support_manager")
    print(f"Explainable case bundle exported: {export['bundle_path']} (decision: {export['decision']['outcome']})")

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

    print_contrast(baseline, governed)
    print_eval_lane()


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
