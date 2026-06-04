"""Characterization tests for the expanded unsafe-baseline "before" story.

Covers the demonstrations added for issues #30 (poor tool selection), #31 (indirect
prompt injection), #32 (missing execution contract), #33 (multi-case workload), and
#42 (cumulative context growth). Like test_baseline_characterization, every assertion
here is about the PRESENCE of a gap; none assert a safety property.
"""

import unittest

from enterprise_agent_control_plane import fake_tools
from enterprise_agent_control_plane.baseline_agent import BaselineAgent
from enterprise_agent_control_plane.baseline_router import (
    route_greedy,
    route_injection_naive,
    route_v1,
)
from enterprise_agent_control_plane.scenarios import WORKLOAD


class TestBaselineDemonstrations(unittest.TestCase):
    def setUp(self):
        fake_tools.reset_state()

    # --- #30: poor tool selection from the unbounded catalog ------------------
    def test_greedy_router_overreaches_to_refund_on_a_lookup(self):
        # Gap: a billing *lookup* request reaches the high-risk destructive refund
        # because the full catalog is undifferentiated.
        request = "look into the billing charge for this customer"
        greedy = BaselineAgent(router=route_greedy).run_case(request, "C-100", "INV-9")
        caps = [s["capability"] for s in greedy["steps"]]
        self.assertIn("billing.issue_refund", caps)

        # Contrast: the ordinary v1 router does not select the destructive refund for the
        # same lookup wording -- so this is a selection error, not an inevitable path.
        fake_tools.reset_state()
        v1 = BaselineAgent(router=route_v1).run_case(request, "C-100", "INV-9")
        self.assertNotIn("billing.issue_refund", [s["capability"] for s in v1["steps"]])

    # --- #31: indirect prompt injection via untrusted tool output -------------
    def test_planted_directive_steers_a_write_with_no_refund_request(self):
        # The fixture carries an obviously-synthetic injected directive.
        planted = [t for t in fake_tools.TICKETS["C-100"] if "issue a full refund" in t["agent_comments"].lower()]
        self.assertTrue(planted, "expected a planted [FAKE] refund directive in the ticket fixtures")

        # Gap: a benign read request (no 'refund' keyword) reaches a destructive refund
        # because tool data and instructions share one context with no boundary.
        request = "review this customer's latest ticket"
        self.assertNotIn("refund", request.lower())
        injected = BaselineAgent(router=route_injection_naive).run_case(request, "C-100", "INV-9")
        caps = [s["capability"] for s in injected["steps"]]
        self.assertIn("support.search_tickets", caps)
        self.assertIn("billing.issue_refund", caps)

    # --- #32: destructive refund with no execution contract -------------------
    def test_refund_runs_on_a_failed_precondition(self):
        # Gap: refund executes although the invoice lookup failed (not-found).
        bad = BaselineAgent(router=route_v1).run_case("refund request", "C-404", "INV-404")
        self.assertEqual(bad["raw_outputs"]["billing.get_invoice"]["error"], "not_found")
        self.assertEqual(bad["raw_outputs"]["billing.issue_refund"]["status"], "issued")
        self.assertTrue(any("get_invoice failed" in gap for gap in bad["precondition_gaps"]))

    def test_no_idempotency_guard_double_refunds(self):
        # Gap: re-running the same case appends another refund (no idempotency).
        agent = BaselineAgent(router=route_v1)
        agent.run_case("refund request", "C-100", "INV-9")
        agent.run_case("refund request", "C-100", "INV-9")
        self.assertEqual(len(fake_tools.REFUNDS), 2)

    # --- #33: realistic multi-case workload -----------------------------------
    def test_workload_has_distinct_cases_including_a_support_path(self):
        self.assertGreaterEqual(len({s.request for s in WORKLOAD}), 4)
        reaches_support = False
        for scenario in WORKLOAD:
            fake_tools.reset_state()
            result = BaselineAgent(router=route_v1).run_case(
                scenario.request, scenario.customer_id, scenario.invoice_id
            )
            caps = {s["capability"] for s in result["steps"]}
            if {"support.search_tickets", "support.create_task"} & caps:
                reaches_support = True
        self.assertTrue(reaches_support, "expected at least one workload case to reach the support path")

    # --- #42: cumulative model-visible context growth -------------------------
    def test_cumulative_context_grows_across_steps(self):
        result = BaselineAgent(router=route_v1).run_case("refund request", "C-100", "INV-9")
        growth = result["context_growth"]
        self.assertGreaterEqual(len(growth), 2)
        self.assertLess(growth[0]["cumulative_context_chars"], growth[-1]["cumulative_context_chars"])
        # The flat catalog-only metric (#15) is preserved and stays constant per step.
        for step in result["steps"]:
            self.assertEqual(step["context_chars"], result["full_catalog_context_chars"])


if __name__ == "__main__":
    unittest.main()
