"""Standalone unsafe-baseline runner (`make baseline`).

Runs the baseline path on its own -- no governed path, no comparison -- and refreshes the
audit-light ``traces/unsafe_run.json`` artifact from a real run (issue #71). It also prints
the aggregate side effects across the multi-case workload to surface the absence of any
run/session-level ceiling on side-effecting actions (issue #109). Offline and key-free.
"""

from enterprise_agent_control_plane.baseline_runner import (
    DEFAULT_ARTIFACT_PATH,
    aggregate_session_side_effects,
    run_unsafe_artifact,
)


def main() -> None:
    print("=== Unsafe baseline (standalone) ===")

    artifact = run_unsafe_artifact()
    print(f"\n[b1] Persisted audit-light artifact: {DEFAULT_ARTIFACT_PATH} (issue #71)")
    print(f"  {len(artifact['logs'])} flat free-text log lines; no structured/queryable trace.")
    print("  Raw payloads with sensitive-looking fields are logged verbatim (issue #106).")
    print("  The artifact cannot answer:")
    for question in artifact["cannot_answer"]:
        print(f"    - {question}")

    agg = aggregate_session_side_effects()
    print(f"\n[b2] Aggregate side effects over the {agg['cases']}-case workload (issue #109)")
    print(
        f"  refunds={agg['refunds']} (total value={agg['total_refund_value']}), "
        f"emails_sent={agg['emails_sent']}, tasks_created={agg['tasks_created']}"
    )
    print(
        f"  total side-effecting actions = {agg['total_side_effecting_actions']}; "
        f"aggregate_ceiling = {agg['aggregate_ceiling']}"
    )
    print(
        "  RISK no aggregate budget: nothing caps the count of writes or the total money "
        "moved across a session. AgentFence budgets / agent-kernel usage-scoped tokens "
        "would supply the missing ceiling."
    )


if __name__ == "__main__":
    main()
