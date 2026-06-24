"""Offline evaluation lane: score candidate routers and policies before deployment.

This is the dependency-free, key-free stand-in for ``skdr-eval``. It demonstrates the
pattern the real library formalises: replay candidate decision logic against committed,
labelled cases and refuse a regression *before* it reaches a live system. Two lanes are
provided:

* **Router lane (issue #7, #75).** Reads ``evals/sample_routing_logs.csv`` and scores how
  often each baseline router (``route_v1`` / ``route_v2``) routes a query the way the
  golden expectation says it should. The dataset is generated from the real routers (see
  :func:`build_routing_rows`) so it cannot drift away from the code it claims to describe
  -- the exact silent drift offline evaluation is meant to catch.
* **Policy lane (issue #40).** Reads ``evals/sample_policy_decisions.csv`` -- a golden set
  of ``principal, capability, amount -> expected_decision`` cases -- and replays them
  through :class:`~enterprise_agent_control_plane.policies.AgentFencePolicy`, reporting
  per-decision accuracy and, crucially, *unsafe drift* (a case the golden set expected to
  be ``deny``/``ask`` that the candidate policy would ``allow``).

Run ``python -m enterprise_agent_control_plane.evals`` (or ``make eval``) to print both
comparisons and exit non-zero on a regression -- this is what wires the lane into CI as a
regression gate (issue #67). Pass ``--generate`` to refresh the routing dataset from the
routers.
"""

import argparse
import csv
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .baseline_router import Router, route_v1, route_v2
from .policies import AgentFencePolicy

# evals/ lives at the repository root, one level above this package.
_ROOT = Path(__file__).resolve().parent.parent
ROUTING_LOGS = _ROOT / "evals" / "sample_routing_logs.csv"
POLICY_DECISIONS = _ROOT / "evals" / "sample_policy_decisions.csv"

# Candidate routers under evaluation, keyed by the identifier used in the dataset. These
# names match the functions in baseline_router.py on purpose (issue #75): the dataset must
# describe routers that actually exist.
ROUTERS: dict[str, Router] = {
    "route_v1": route_v1,
    "route_v2": route_v2,
}

# Golden routing expectations: each query and the sequence of capabilities the *intended*
# router should select for it. v1 and v2 agree on the refund and escalation paths; they
# diverge only on the email path, where the safer expectation is to draft (not send) the
# reply -- the change v2 made and v1 did not (issue #20). Scoring against this golden set is
# what the team skipped when it shipped a router tweak on intuition.
_GOLDEN_ROUTES: list[tuple[int, str, list[str]]] = [
    (1, "refund request", ["crm.search_customer", "billing.get_invoice", "billing.issue_refund"]),
    (2, "send a direct email reply", ["crm.search_customer", "email.draft_reply"]),
    (3, "escalate this ticket", ["support.search_tickets", "support.create_task"]),
]

# Committed per-candidate accuracy floors (issue #67). A candidate scoring below its floor on
# the golden routing set fails the gate. v2 is the reference router and must stay perfect on
# this set; v1 is the legacy router and must not regress below its known-good score.
ROUTER_ACCURACY_FLOOR: dict[str, float] = {
    "route_v1": 0.6,
    "route_v2": 1.0,
}

_SAFE_DECISIONS = {"deny", "ask"}


# --- Router evaluation lane (issues #7, #75) ----------------------------------
@dataclass(frozen=True)
class EvalResult:
    candidate: str
    score: float
    notes: str


def route_to_completion(router: Router, request: str, max_steps: int = 10) -> list[str]:
    """Run a router to completion, returning the ordered capabilities it selects.

    The baseline routers pick the next capability given the ones already called and stop by
    returning ``None``. ``max_steps`` is a loop-safety bound (the routers never repeat a
    capability, so it is not normally reached).
    """
    called: list[str] = []
    for _ in range(max_steps):
        nxt = router(request, called)
        if nxt is None:
            return called
        called.append(nxt)
    return called


def build_routing_rows() -> list[dict[str, str]]:
    """Generate the routing-log rows from the real routers (issue #75, drift-proof).

    For every golden query and every candidate router, record the sequence the router
    actually produces, the golden expectation, and whether they match. Because the
    ``decision`` column is computed from the live routers, the committed CSV cannot drift
    away from the code -- a guard test re-runs this and compares.
    """
    rows: list[dict[str, str]] = []
    for case_id, query, expected in _GOLDEN_ROUTES:
        expected_seq = "|".join(expected)
        for candidate, router in ROUTERS.items():
            decision_seq = "|".join(route_to_completion(router, query))
            rows.append(
                {
                    "case_id": str(case_id),
                    "query": query,
                    "candidate": candidate,
                    "decision": decision_seq,
                    "expected": expected_seq,
                    "match": "true" if decision_seq == expected_seq else "false",
                }
            )
    return rows


ROUTING_FIELDNAMES = ["case_id", "query", "candidate", "decision", "expected", "match"]


def write_routing_logs(path: Path = ROUTING_LOGS) -> Path:
    """Write the generated routing rows to ``path`` so the dataset reflects the routers."""
    rows = build_routing_rows()
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROUTING_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return path


def evaluate_routers(path: Path = ROUTING_LOGS) -> list[EvalResult]:
    """Score each candidate router from the committed routing log (no hardcoded scores).

    Accuracy is the fraction of a candidate's rows whose recorded decision matches the
    golden expectation, recomputed from the data rather than trusting the ``match`` column.
    """
    totals: dict[str, int] = {}
    matched: dict[str, int] = {}
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            candidate = row["candidate"]
            totals[candidate] = totals.get(candidate, 0) + 1
            if row["decision"] == row["expected"]:
                matched[candidate] = matched.get(candidate, 0) + 1
    results = []
    for candidate in sorted(totals):
        total = totals[candidate]
        hits = matched.get(candidate, 0)
        score = hits / total if total else 0.0
        results.append(EvalResult(candidate, score, f"{hits}/{total} queries routed as expected"))
    return results


def compare_router_candidates(path: Path = ROUTING_LOGS) -> list[EvalResult]:
    """Backwards-compatible alias for :func:`evaluate_routers` (referenced in docs)."""
    return evaluate_routers(path)


# --- Policy evaluation lane (issue #40) ---------------------------------------
@dataclass(frozen=True)
class PolicyEvalCase:
    principal: str
    capability: str
    amount: float | None
    expected: str
    actual: str
    match: bool
    unsafe_drift: bool


@dataclass(frozen=True)
class PolicyEvalReport:
    cases: list[PolicyEvalCase]
    mismatches: list[PolicyEvalCase] = field(default_factory=list)
    unsafe_drift: list[PolicyEvalCase] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def accuracy(self) -> float:
        if not self.cases:
            return 0.0
        return sum(1 for c in self.cases if c.match) / len(self.cases)


def _parse_amount(raw: str) -> float | None:
    raw = (raw or "").strip()
    return float(raw) if raw else None


def evaluate_policy(
    path: Path = POLICY_DECISIONS,
    policy: AgentFencePolicy | None = None,
) -> PolicyEvalReport:
    """Replay golden policy cases through a candidate policy and report drift (issue #40).

    A mismatch is any case whose decision differs from the golden expectation. ``unsafe
    drift`` is the dangerous subset: a case the golden set expected to be denied or held for
    approval that the candidate policy would allow.
    """
    policy = policy or AgentFencePolicy()
    cases: list[PolicyEvalCase] = []
    mismatches: list[PolicyEvalCase] = []
    unsafe_drift: list[PolicyEvalCase] = []
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            amount = _parse_amount(row.get("amount", ""))
            args = {"amount": amount} if amount is not None else None
            expected = row["expected_decision"].strip()
            actual = policy.evaluate(row["capability"], row["principal"], args).decision
            is_match = actual == expected
            drift = expected in _SAFE_DECISIONS and actual == "allow"
            case = PolicyEvalCase(
                principal=row["principal"],
                capability=row["capability"],
                amount=amount,
                expected=expected,
                actual=actual,
                match=is_match,
                unsafe_drift=drift,
            )
            cases.append(case)
            if not is_match:
                mismatches.append(case)
            if drift:
                unsafe_drift.append(case)
    return PolicyEvalReport(cases=cases, mismatches=mismatches, unsafe_drift=unsafe_drift)


# --- Gate / CLI (issue #67) ---------------------------------------------------
def _print_router_table(results: Sequence[EvalResult]) -> None:
    print("Router accuracy (offline, golden routing set):")
    for r in results:
        floor = ROUTER_ACCURACY_FLOOR.get(r.candidate)
        floor_note = f" (floor {floor:.2f})" if floor is not None else ""
        print(f"  {r.candidate:<10} {r.score:>6.2%}  {r.notes}{floor_note}")


def _print_policy_report(report: PolicyEvalReport) -> None:
    print(
        f"Policy decisions (offline, golden set): {report.accuracy:.2%} "
        f"({report.total - len(report.mismatches)}/{report.total} matched expected)"
    )
    for case in report.mismatches:
        flag = "UNSAFE DRIFT" if case.unsafe_drift else "mismatch"
        amount = "" if case.amount is None else f" amount={case.amount}"
        print(
            f"  {flag}: {case.principal} {case.capability}{amount} "
            f"expected={case.expected} got={case.actual}"
        )


def run_gate(verbose: bool = True) -> tuple[bool, list[str]]:
    """Run both lanes and return ``(passed, failure_messages)`` (issue #67).

    Set ``verbose=False`` to suppress the human-readable router/policy tables. The
    pass/fail result and failure messages are returned either way, so callers that use
    the gate programmatically (e.g. the test suite) can stay quiet while the CLI keeps
    its full output.
    """
    failures: list[str] = []

    router_results = evaluate_routers()
    if verbose:
        _print_router_table(router_results)
    for r in router_results:
        floor = ROUTER_ACCURACY_FLOOR.get(r.candidate)
        if floor is not None and r.score + 1e-9 < floor:
            failures.append(
                f"router {r.candidate} accuracy {r.score:.2%} is below the committed floor {floor:.2%}"
            )

    report = evaluate_policy()
    if verbose:
        _print_policy_report(report)
    for case in report.mismatches:
        kind = "unsafe drift" if case.unsafe_drift else "policy mismatch"
        amount = "" if case.amount is None else f" amount={case.amount}"
        failures.append(
            f"{kind}: {case.principal} {case.capability}{amount} expected {case.expected}, got {case.actual}"
        )

    return (not failures), failures


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline router/policy evaluation gate.")
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Regenerate the routing dataset from the real routers and exit.",
    )
    args = parser.parse_args(argv)

    if args.generate:
        path = write_routing_logs()
        print(f"Regenerated routing dataset from routers -> {path}")
        return 0

    passed, failures = run_gate()
    if passed:
        print("\nOffline evaluation gate: PASS")
        return 0
    print("\nOffline evaluation gate: FAIL")
    for message in failures:
        print(f"  - {message}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
