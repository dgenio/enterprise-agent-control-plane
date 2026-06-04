import csv
import io
import unittest
from contextlib import redirect_stdout
from unittest import mock

from enterprise_agent_control_plane import evals
from enterprise_agent_control_plane.policies import AgentFencePolicy


class TestRouterEval(unittest.TestCase):
    def test_scores_are_computed_from_data(self):
        results = {r.candidate: r for r in evals.evaluate_routers()}
        # v2 drafts the email reply (the safer, expected behaviour) so it matches every
        # golden route; v1 sends instead, missing exactly the email case.
        self.assertEqual(results["route_v2"].score, 1.0)
        self.assertAlmostEqual(results["route_v1"].score, 2 / 3)

    def test_compare_router_candidates_alias_matches(self):
        self.assertEqual(evals.compare_router_candidates(), evals.evaluate_routers())

    def test_dataset_reflects_real_routers(self):
        # Drift guard (issue #75): the committed CSV must equal what the routers produce.
        with open(evals.ROUTING_LOGS, newline="", encoding="utf-8") as handle:
            committed = list(csv.DictReader(handle))
        self.assertEqual(committed, evals.build_routing_rows())

    def test_candidate_names_exist_in_code(self):
        with open(evals.ROUTING_LOGS, newline="", encoding="utf-8") as handle:
            candidates = {row["candidate"] for row in csv.DictReader(handle)}
        self.assertTrue(candidates.issubset(set(evals.ROUTERS)))


class TestPolicyEval(unittest.TestCase):
    def test_golden_cases_pass_against_current_policy(self):
        report = evals.evaluate_policy()
        self.assertEqual(report.accuracy, 1.0)
        self.assertEqual(report.mismatches, [])
        self.assertEqual(report.unsafe_drift, [])
        self.assertEqual(report.total, 9)

    def test_loosened_policy_flags_unsafe_drift(self):
        # A candidate policy that auto-approves any refund amount should flip the 149 (ask)
        # and 9999 (deny) cases to allow -- the dangerous regression the lane exists to catch.
        loosened = AgentFencePolicy(refund_auto_limit=1_000_000, refund_manager_limit=1_000_000)
        report = evals.evaluate_policy(policy=loosened)
        self.assertLess(report.accuracy, 1.0)
        drift_caps = {(c.capability, c.amount) for c in report.unsafe_drift}
        self.assertIn(("billing.issue_refund", 149.0), drift_caps)
        self.assertIn(("billing.issue_refund", 9999.0), drift_caps)
        for case in report.unsafe_drift:
            self.assertEqual(case.actual, "allow")
            self.assertIn(case.expected, {"deny", "ask"})


class TestGate(unittest.TestCase):
    def test_gate_passes_on_committed_state(self):
        # main() is the CLI entry point and prints by design; redirect its output so the
        # exit-code assertion does not spam the test run.
        with redirect_stdout(io.StringIO()):
            self.assertEqual(evals.main([]), 0)

    def test_gate_passes_helper(self):
        passed, failures = evals.run_gate(verbose=False)
        self.assertTrue(passed)
        self.assertEqual(failures, [])

    def test_gate_fails_and_exits_nonzero_on_regression(self):
        # The gate's reason to exist (issue #67) is failing CI on a regression. Raise a
        # floor above the reference router's achievable score to force one, then assert
        # the helper reports it and the CLI exits non-zero.
        with mock.patch.dict(evals.ROUTER_ACCURACY_FLOOR, {"route_v2": 1.01}):
            passed, failures = evals.run_gate(verbose=False)
            self.assertFalse(passed)
            self.assertTrue(any("route_v2" in message for message in failures))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(evals.main([]), 1)


if __name__ == "__main__":
    unittest.main()
