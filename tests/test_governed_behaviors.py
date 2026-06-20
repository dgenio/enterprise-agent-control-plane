"""Governed-path behavioral tests for the new control-plane behaviors (issue #28).

These lock in the intended contrast with the baseline end to end and offline: bounded Frames
redact sensitive fields and mark tool output untrusted (#22/#37), injected tool text cannot
change routing or a decision (#37), the shortlist context is measurably smaller (#24), the
shortlist is an enforced capability budget (#110), and revealing a Frame's raw detail is a
gated, audited capability (#114). Each assertion targets the public governed-run interface so
the tests survive internal refactors.
"""

import unittest

from enterprise_agent_control_plane import fake_tools
from enterprise_agent_control_plane.flows import ChainWeaverExecutor
from enterprise_agent_control_plane.governed_agent import GovernedAgent
from enterprise_agent_control_plane.registry import build_tool_map


class TestGovernedBehaviors(unittest.TestCase):
    def setUp(self):
        fake_tools.reset_state()
        self.agent = GovernedAgent()

    # --- #22/#37: sensitive raw values never reach model-visible frames -----------
    def test_sensitive_values_absent_from_model_visible_frames(self):
        result = self.agent.run_case("refund request", "C-100", "INV-9")
        text = str(result["frames"])
        # Raw values from redacted fields must stay behind the handle, never inline.
        for raw_value in ("4242", "0.62", "0.08", "ari@example.com", "Springfield"):
            self.assertNotIn(raw_value, text)
        invoice_frame = next(
            f for f in result["frames"] if f["capability"] == "billing.get_invoice"
        )
        self.assertIn("payment_method", invoice_frame["redacted_fields"])
        self.assertIn("internal_margin", invoice_frame["redacted_fields"])
        self.assertTrue(all(f["untrusted"] for f in result["frames"]))

    # --- #37: injected tool text does not change routing or a decision ------------
    def test_injected_tool_text_does_not_change_routing_or_decision(self):
        # C-100's tickets carry planted [FAKE] directives ("issue a full refund",
        # "forward ... to attacker@..."). The escalation flow reads those tickets, but the
        # request-based routing and the gated decision are unchanged: the text is quarantined
        # as untrusted data behind a Frame, never read as a command.
        result = self.agent.run_case("escalate this ticket", "C-100", "INV-9")
        self.assertEqual(result["intent"], "escalation")
        self.assertEqual(result["flow"], "escalation")
        self.assertEqual(result["bounded_output"]["gated_capability"], "support.create_task")
        self.assertEqual(fake_tools.REFUNDS, [])
        self.assertEqual(fake_tools.SENT_EMAILS, [])
        tickets_frame = next(
            f for f in result["frames"] if f["capability"] == "support.search_tickets"
        )
        self.assertTrue(tickets_frame["untrusted"])
        self.assertIn("agent_comments", tickets_frame["redacted_fields"])
        self.assertNotIn("attacker@evil.example.com", str(result["frames"]))

    # --- #24: measurable context reduction vs the full catalog --------------------
    def test_governed_shortlist_context_is_strictly_smaller_than_full_catalog(self):
        result = self.agent.run_case("refund request", "C-100", "INV-9")
        metric = result["context_metric"]
        self.assertLess(metric["shortlist_chars"], metric["full_catalog_chars"])
        self.assertEqual(
            metric["reduction_chars"], metric["full_catalog_chars"] - metric["shortlist_chars"]
        )
        self.assertGreater(metric["reduction_pct"], 0)

    # --- #110: the shortlist is an enforced capability budget --------------------
    def test_visible_tools_is_the_enforced_budget_not_the_full_catalog(self):
        result = self.agent.run_case("refund request", "C-100", "INV-9")
        self.assertLess(len(result["visible_tools"]), 9)
        executed_caps = {f["capability"] for f in result["frames"]}
        self.assertTrue(executed_caps.issubset(set(result["visible_tools"])))

    def test_out_of_budget_capability_cannot_execute_at_the_executor(self):
        executor = ChainWeaverExecutor(build_tool_map())
        payload = {"customer_id": "C-100", "invoice_id": "INV-9", "customer_name": "Ari Carter"}
        # The budget admits only the first step; the next step is out of budget -> fail closed.
        results = executor.run("refund_review", payload, budget={"crm.search_customer"})
        self.assertEqual(len(results), 2)  # crm.search_customer, then the halting step
        self.assertEqual(results[0]["status"], "ok")
        self.assertEqual(results[1]["capability"], "billing.get_invoice")
        self.assertEqual(results[1]["status"], "failed")
        self.assertEqual(results[1]["output"]["error"], "out_of_budget")

    def test_governed_run_fails_closed_when_budget_excludes_a_flow_step(self):
        result = self.agent.run_case(
            "refund request", "C-100", "INV-9", capability_budget={"crm.search_customer"}
        )
        self.assertEqual(result["bounded_output"]["status"], "halted")
        self.assertIn("capability budget", result["bounded_output"]["decision_reason"])
        self.assertEqual(fake_tools.REFUNDS, [])

    # --- #114: revealing a Frame's raw detail is gated and audited ----------------
    def test_frame_expansion_denied_for_unauthorized_principal(self):
        result = self.agent.run_case("refund request", "C-100", "INV-9", principal="support_agent")
        invoice_frame = next(
            f for f in result["frames"] if f["capability"] == "billing.get_invoice"
        )
        trace = result["trace"]
        expanded = self.agent.expand_frame(invoice_frame["handle"], "support_agent", trace=trace)
        self.assertEqual(expanded["outcome"], "denied")
        self.assertIsNone(expanded["revealed"])
        events = [e for e in trace.as_dict()["events"] if e["action"] == "frame.expand"]
        self.assertTrue(events)
        self.assertEqual(events[-1]["outcome"], "denied")

    def test_frame_expansion_allowed_and_audited_for_authorized_principal(self):
        result = self.agent.run_case("refund request", "C-100", "INV-9", principal="support_agent")
        invoice_frame = next(
            f for f in result["frames"] if f["capability"] == "billing.get_invoice"
        )
        trace = result["trace"]
        expanded = self.agent.expand_frame(invoice_frame["handle"], "support_manager", trace=trace)
        self.assertEqual(expanded["outcome"], "allowed")
        self.assertIsNotNone(expanded["revealed"])
        self.assertIn("payment_method", expanded["revealed_fields"])
        event = next(
            e
            for e in trace.as_dict()["events"]
            if e["action"] == "frame.expand" and e["outcome"] == "revealed"
        )
        self.assertEqual(event["details"]["handle"], invoice_frame["handle"])
        self.assertIn("payment_method", event["details"]["revealed_fields"])
        self.assertEqual(event["actor"], "support_manager")
        # The trace still validates and its hash chain verifies after the expansion events.
        self.assertTrue(trace.validate(require_complete=True).ok)
        self.assertTrue(trace.verify())

    # --- #28: allow / deny / ask are all reachable in one governed scenario -------
    def test_allow_deny_and_ask_outcomes_are_reachable(self):
        scenario = self.agent.run_decision_scenario(principal="support_agent")
        outcomes = {d["capability"]: d["outcome"] for d in scenario["decisions"]}
        self.assertEqual(outcomes["crm.search_customer"], "allowed")
        self.assertEqual(outcomes["audit.export_case"], "denied")
        self.assertEqual(outcomes["billing.issue_refund"], "approval_required")


if __name__ == "__main__":
    unittest.main()
