"""Example: structured, tamper-evident audit trace export — issue #62.

What this shows
---------------
Every governed run emits an ordered, schema-validated audit trace instead of flat
free-text logs. Each event is hash-chained to the previous one, so the trace is
tamper-evident. This example records a minimal run, validates it against the event
schema, verifies the hash chain, and prints the exported trace.

Maps to
-------
* Module: ``enterprise_agent_control_plane/audit.py``
  (``AuditTrace``, ``AuditEvent``, ``validate_trace``, ``verify_event_chain``).
* dgenio library: ``agent-kernel`` (audit / trace primitives).

Run it
------
    python examples/audit_trace.py

See ``docs/examples.md`` for the gallery, ``docs/adoption-path.md`` (Step 4) for
where this fits, ``docs/audit-trace.md`` for the event schema, and
``docs/glossary.md`` for "audit trace".
"""

import json

from enterprise_agent_control_plane.audit import AuditTrace


def main() -> None:
    trace = AuditTrace(trace_id="example-trace")

    # A few events drawn from the enumerated action vocabulary (audit.ACTION_VOCABULARY).
    trace.record(
        actor="support_agent",
        action="request.received",
        outcome="accepted",
        details={"request": "refund request", "intent": "refund", "principal": "support_agent"},
    )
    trace.record(
        actor="control-plane",
        action="policy.decision",
        outcome="approval_required",
        details={
            "capability": "billing.issue_refund",
            "principal": "support_agent",
            "decision": "ask",
            "outcome": "approval_required",
            "reason": "amount exceeds the auto-approve limit",
            "token_valid": True,
            "policy_version": "af-example",
            "policy_thresholds": {"refund_auto_limit": 50.0},
        },
    )

    result = trace.validate()
    print(f"trace events: {len(trace.events)}")
    print(f"schema valid: {result.ok} (errors: {result.errors})")
    print(f"hash chain verified: {trace.verify()}")
    print(json.dumps(trace.as_dict(), indent=2))


if __name__ == "__main__":
    main()
