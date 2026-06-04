from enterprise_agent_control_plane.baseline_agent import BaselineAgent
from enterprise_agent_control_plane.governed_agent import GovernedAgent


def main() -> None:
    customer_id = "C-100"
    invoice_id = "INV-9"

    baseline = BaselineAgent().run_case(customer_id, invoice_id)
    governed = GovernedAgent().run_case(customer_id, invoice_id)

    print("=== Customer Operations Agent Demo ===")
    print("\n[1] Unsafe baseline")
    print(f"Visible tools: {len(baseline['visible_tools'])} -> {baseline['visible_tools']}")
    print(f"Raw output includes refund attempt: {baseline['raw_outputs']['refund_attempt']}")

    print("\n[2] Governed control plane")
    print(f"Shortlisted tools: {len(governed['visible_tools'])} -> {governed['visible_tools']}")
    print(f"Deterministic flow steps: {governed['bounded_output']['flow_steps']}")
    print(f"Risky action status: {governed['bounded_output']['refund_action']}")
    print(f"Bounded output frame: {governed['bounded_output']}")
    print(f"Audit trace emitted: {governed['audit_trace_path']}")


if __name__ == "__main__":
    main()
