from enterprise_agent_control_plane import fake_tools
from enterprise_agent_control_plane.baseline_agent import BaselineAgent
from enterprise_agent_control_plane.baseline_router import route_v1, route_v2
from enterprise_agent_control_plane.governed_agent import GovernedAgent


def main() -> None:
    customer_id = "C-100"
    invoice_id = "INV-9"

    print("=== Customer Operations Agent Demo ===")

    print("\n[1] Unsafe baseline (model-routed loop over the full catalog)")
    fake_tools.reset_state()
    baseline = BaselineAgent(router=route_v1).run_case("refund request", customer_id, invoice_id)

    print(f"Request: {baseline['request']!r} (router: {baseline['router']})")
    print(
        f"RISK over-permissioned context: {baseline['tools_offered_each_step']} tools offered every step "
        f"-> full-catalog context = {baseline['full_catalog_context_chars']} chars "
        f"(~{baseline['approx_context_tokens']} tokens)"
    )
    print("Per-step routing (no bounded shortlist):")
    for step in baseline["steps"]:
        print(f"  step {step['step']}: picked {step['capability']} (chose from {step['tools_offered']} tools)")
    print(
        f"RISK deterministic path run as model steps: {baseline['compilation_note']}"
    )

    print("RISK raw-output leakage (fields forwarded but not needed for the task):")
    for capability, extra in baseline["leaked_fields"].items():
        if extra:
            print(f"  {capability}: {extra}")

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

    print("\n[1b] Router change shipped without offline evaluation")
    fake_tools.reset_state()
    email_v1 = BaselineAgent(router=route_v1).run_case("send direct email reply", customer_id, invoice_id)
    fake_tools.reset_state()
    email_v2 = BaselineAgent(router=route_v2).run_case("send direct email reply", customer_id, invoice_id)
    v1_caps = [s["capability"] for s in email_v1["steps"]]
    v2_caps = [s["capability"] for s in email_v2["steps"]]
    print(f"  v1 route: {v1_caps}")
    print(f"  v2 route: {v2_caps}")
    print(
        "  v2 quietly changed a send->draft decision and was shipped on intuition, with no offline "
        "comparison (see evals/sample_routing_logs.csv; the eval lane would score this)."
    )

    print("\n[2] Governed control plane")
    fake_tools.reset_state()
    governed = GovernedAgent().run_case(customer_id, invoice_id)
    print(f"Shortlisted tools: {len(governed['visible_tools'])} -> {governed['visible_tools']}")
    print(f"Deterministic flow steps: {governed['bounded_output']['flow_steps']}")
    print(f"Risky action status: {governed['bounded_output']['refund_action']}")
    print(f"Bounded output frame: {governed['bounded_output']}")
    print(f"Audit trace emitted: {governed['audit_trace_path']}")


if __name__ == "__main__":
    main()
