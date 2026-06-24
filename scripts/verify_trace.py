"""End-to-end audit-trace verification (issue #201).

Runs one governed case and asserts the emitted trace is both schema-complete
(:meth:`AuditTrace.validate` with ``require_complete=True``, issue #112) and tamper-evident
(:meth:`AuditTrace.verify` over the hash chain, issue #39). Unit tests already cover these
properties; this top-level guard re-checks them on a real emitted artifact so an orchestration
regression -- a dropped required event, a broken or reordered chain -- fails the build even if a
unit test misses it. Fully offline; no API keys or network.

Run it directly (``python scripts/verify_trace.py`` or ``make verify-trace``) or import
:func:`verify_governed_case` from a test. It returns a list of human-readable error strings;
an empty list means the trace verified.
"""

from __future__ import annotations

import sys

from enterprise_agent_control_plane.governed_agent import GovernedAgent


def verify_governed_case() -> list[str]:
    """Run a representative governed case; return failure messages (empty list == verified).

    A refund request matches a governed flow, so the run must emit the full set of
    ``REQUIRED_GOVERNED_ACTIONS`` -- completeness is asserted precisely because a flow ran.
    """
    result = GovernedAgent().run_case("refund request", "C-100", "INV-9")
    trace = result["trace"]
    errors: list[str] = []

    validation = trace.validate(require_complete=True)
    if not validation.ok:
        errors.append("schema validation failed: " + "; ".join(validation.errors))
    if not trace.verify():
        errors.append(
            "hash-chain verification failed: the trace chain is not internally consistent"
        )
    return errors


def main() -> int:
    errors = verify_governed_case()
    if errors:
        print("verify-trace: FAILED")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("verify-trace: OK (governed trace is schema-complete and the hash chain verifies)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
