import json
import unittest
from pathlib import Path

from enterprise_agent_control_plane import fake_tools
from enterprise_agent_control_plane.governed_agent import GovernedAgent
from enterprise_agent_control_plane.policies import AgentFencePolicy


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

    # --- escalation gates its write instead of executing it -------------------
    def test_escalation_holds_gated_write_without_approval(self):
        result = self.agent.run_case("escalate this ticket", "C-100", "INV-9", principal="support_agent")
        self.assertEqual(result["intent"], "escalation")
        self.assertEqual(result["flow"], "escalation")
        # support.create_task is the gated risky action; with no approver it is held for
        # approval and must NOT have been executed as a flow side effect.
        self.assertEqual(result["bounded_output"]["gated_capability"], "support.create_task")
        self.assertEqual(result["bounded_output"]["action_status"], "approval_required")
        self.assertEqual(fake_tools.TASKS, [])

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

    # --- per-step audit events + token check (issue #111) ---------------------
    def test_each_flow_step_is_a_token_checked_audit_event(self):
        result = self.agent.run_case("refund request", "C-100", "INV-9", principal="support_agent")
        steps = [e for e in result["trace"].as_dict()["events"] if e["action"] == "flow.step"]
        # refund_review runs its four steps in order, each a token-checked event.
        self.assertEqual(
            [e["details"]["step"] for e in steps],
            ["lookup_customer", "lookup_invoice", "check_policy", "draft_reply"],
        )
        for event in steps:
            self.assertTrue(event["details"]["token_valid"])
            self.assertEqual(event["outcome"], "ok")

    def test_missing_token_fails_step_closed(self):
        # billing_admin holds crm.search_customer / billing.get_invoice / billing.issue_refund
        # but NOT docs.search_policy or email.draft_reply, so those refund_review steps must
        # be blocked with no tool run (issue #111).
        result = self.agent.run_case("refund request", "C-100", "INV-9", principal="billing_admin")
        steps = {e["details"]["step"]: e for e in result["trace"].as_dict()["events"] if e["action"] == "flow.step"}
        self.assertTrue(steps["lookup_customer"]["details"]["token_valid"])
        for blocked in ("check_policy", "draft_reply"):
            self.assertFalse(steps[blocked]["details"]["token_valid"])
            self.assertEqual(steps[blocked]["outcome"], "blocked_no_token")
            # Fail closed: no tool ran, so there is no bounded result reference.
            self.assertIsNone(steps[blocked]["details"]["result_ref"])

    # --- policy provenance on decisions (issue #70) ---------------------------
    def test_policy_decision_records_provenance(self):
        result = self.agent.run_case("refund request", "C-100", "INV-9", principal="support_agent")
        decision = next(e for e in result["trace"].as_dict()["events"] if e["action"] == "policy.decision")
        self.assertTrue(decision["details"]["policy_version"].startswith("af-"))
        self.assertEqual(decision["details"]["policy_thresholds"]["refund_auto_limit"], 50.0)

    def test_changing_a_threshold_changes_recorded_policy_version(self):
        base = self.agent.run_case("refund request", "C-100", "INV-9", principal="support_agent")
        loosened = GovernedAgent(policy=AgentFencePolicy(refund_auto_limit=999.0)).run_case(
            "refund request", "C-100", "INV-9", principal="support_agent"
        )

        def version(result):
            return next(
                e["details"]["policy_version"]
                for e in result["trace"].as_dict()["events"]
                if e["action"] == "policy.decision"
            )

        self.assertNotEqual(version(base), version(loosened))

    # --- explainable trace + case export (issue #27) --------------------------
    def test_trace_is_explainable_and_exportable(self):
        result = self.agent.run_case("refund request", "C-100", "INV-9", principal="support_agent")
        trace = result["trace"]
        actions = [e["action"] for e in trace.as_dict()["events"]]
        for expected in ("request.received", "shortlist", "flow.select", "policy.decision", "output.frame"):
            self.assertIn(expected, actions)
        # The completed run validates against the schema and its hash chain verifies
        # (issues #112, #39).
        self.assertTrue(trace.validate(require_complete=True).ok)
        self.assertTrue(trace.verify())

        export = self.agent.export_case(result["trace"], principal="support_manager")
        self.assertEqual(export["decision"]["outcome"], "allowed")
        bundle = json.loads(Path(export["bundle_path"]).read_text(encoding="utf-8"))
        self.assertEqual(bundle["case_id"], result["trace"].trace_id)
        self.assertIn("events", bundle["trace"])


if __name__ == "__main__":
    unittest.main()
