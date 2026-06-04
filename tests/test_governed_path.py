import json
import unittest
from pathlib import Path

from enterprise_agent_control_plane import fake_tools
from enterprise_agent_control_plane.governed_agent import GovernedAgent


class TestGovernedPath(unittest.TestCase):
    def setUp(self):
        fake_tools.reset_state()
        self.agent = GovernedAgent()

    # --- intent-based flow selection (issue #25) ------------------------------
    def test_intent_selects_matching_flow(self):
        refund = self.agent.run_case("refund request", "C-100", "INV-9")
        self.assertEqual(refund["intent"], "refund")
        self.assertEqual(refund["flow"], "refund_review")

        reply = self.agent.run_case("send a customer email reply", "C-100", "INV-9")
        self.assertEqual(reply["flow"], "customer_reply")

    def test_unknown_intent_yields_no_matching_flow(self):
        result = self.agent.run_case("do something undefined", "C-100", "INV-9")
        self.assertIsNone(result["flow"])
        self.assertEqual(result["bounded_output"]["status"], "no_matching_flow")

    # --- principal-scoped capability tokens (issue #23) -----------------------
    def test_out_of_scope_capability_rejected_at_token_layer(self):
        decision = self.agent.decide("audit.export_case", "support_agent")
        self.assertFalse(decision.token_valid)
        self.assertEqual(decision.outcome, "denied")

    # --- allow / deny / ask in one scenario (issue #26) -----------------------
    def test_scenario_produces_allow_deny_and_approval_required(self):
        scenario = self.agent.run_decision_scenario(principal="support_agent")
        outcomes = {d["capability"]: d["outcome"] for d in scenario["decisions"]}
        self.assertEqual(outcomes["crm.search_customer"], "allowed")
        self.assertEqual(outcomes["audit.export_case"], "denied")
        self.assertEqual(outcomes["billing.issue_refund"], "approval_required")

    # --- approval handling for 'ask' (issue #5) -------------------------------
    def test_approver_approve_and_reject(self):
        approved = GovernedAgent(approver=lambda req: True).run_case(
            "refund request", "C-100", "INV-9", principal="support_agent"
        )
        self.assertEqual(approved["bounded_output"]["action_status"], "approved")

        rejected = GovernedAgent(approver=lambda req: False).run_case(
            "refund request", "C-100", "INV-9", principal="support_agent"
        )
        self.assertEqual(rejected["bounded_output"]["action_status"], "approval_denied")

    # --- explainable trace + case export (issue #27) --------------------------
    def test_trace_is_explainable_and_exportable(self):
        result = self.agent.run_case("refund request", "C-100", "INV-9", principal="support_agent")
        actions = [e["action"] for e in result["trace"].as_dict()["events"]]
        for expected in ("request.received", "shortlist", "flow.select", "policy.decision", "output.frame"):
            self.assertIn(expected, actions)

        export = self.agent.export_case(result["trace"], principal="support_manager")
        self.assertEqual(export["decision"]["outcome"], "allowed")
        bundle = json.loads(Path(export["bundle_path"]).read_text(encoding="utf-8"))
        self.assertEqual(bundle["case_id"], result["trace"].trace_id)
        self.assertIn("events", bundle["trace"])


if __name__ == "__main__":
    unittest.main()
