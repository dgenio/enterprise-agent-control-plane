"""Characterization tests for the unsafe baseline (issue #21).

These lock in the *intended* gaps of the baseline so a future refactor cannot quietly
make it safe and erase the before/after teaching value. Every assertion here is about
the PRESENCE of a gap; none of them assert any safety property.
"""

import unittest

from enterprise_agent_control_plane import fake_tools
from enterprise_agent_control_plane.baseline_agent import BaselineAgent
from enterprise_agent_control_plane.baseline_router import route_v1, route_v2


class TestBaselineCharacterization(unittest.TestCase):
    def setUp(self):
        fake_tools.reset_state()

    def test_full_catalog_offered_on_every_step(self):
        # Gap: no bounded shortlist -- the full 9-tool catalog is offered every step.
        result = BaselineAgent().run_case("refund request", "C-100", "INV-9")
        self.assertEqual(result["tools_offered_each_step"], 9)
        self.assertTrue(result["steps"])
        for step in result["steps"]:
            self.assertEqual(step["tools_offered"], 9)
            self.assertEqual(step["context_chars"], result["full_catalog_context_chars"])

    def test_raw_sensitive_fields_forwarded_verbatim(self):
        # Gap: raw records (including unneeded internal fields) flow into context as-is.
        result = BaselineAgent().run_case("refund request", "C-100", "INV-9")
        customer = result["raw_outputs"]["crm.search_customer"]
        self.assertIn("internal_notes", customer)
        self.assertIn("risk_flags", customer)
        self.assertIn("payment_method", customer)
        self.assertIn("internal_notes", result["leaked_fields"]["crm.search_customer"])

    def test_write_action_runs_with_no_policy_decision(self):
        # Gap: a destructive action runs with no principal, token, or policy decision.
        result = BaselineAgent().run_case("refund request", "C-100", "INV-9")
        refund_writes = [
            w for w in result["policy_blind_writes"] if w["capability"] == "billing.issue_refund"
        ]
        self.assertEqual(len(refund_writes), 1)
        write = refund_writes[0]
        self.assertIsNone(write["principal"])
        self.assertIsNone(write["capability_token"])
        self.assertIsNone(write["policy_decision"])
        self.assertEqual(result["raw_outputs"]["billing.issue_refund"]["status"], "issued")

    def test_no_structured_audit_trace(self):
        # Gap: only flat free-text logs exist; there is no structured, queryable trace.
        result = BaselineAgent().run_case("refund request", "C-100", "INV-9")
        self.assertIsNone(result["structured_audit_trace"])
        self.assertTrue(result["logs"])
        self.assertEqual(len(result["audit_open_questions"]), 4)

    def test_router_loop_is_deterministic(self):
        # The sequence is re-routed every step yet identical across runs (compile candidate).
        first = BaselineAgent().run_case("refund request", "C-100", "INV-9")
        fake_tools.reset_state()
        second = BaselineAgent().run_case("refund request", "C-100", "INV-9")
        self.assertEqual(
            [s["capability"] for s in first["steps"]],
            [s["capability"] for s in second["steps"]],
        )
        self.assertTrue(first["deterministic_path"])

    def test_router_variants_diverge_on_send_vs_draft(self):
        # v2 was shipped without offline eval; it differs from v1 on the email path (issue #20).
        v1 = BaselineAgent(router=route_v1).run_case("send direct email reply", "C-100", "INV-9")
        fake_tools.reset_state()
        v2 = BaselineAgent(router=route_v2).run_case("send direct email reply", "C-100", "INV-9")
        v1_caps = {s["capability"] for s in v1["steps"]}
        v2_caps = {s["capability"] for s in v2["steps"]}
        self.assertIn("email.send_reply", v1_caps)
        self.assertIn("email.draft_reply", v2_caps)
        self.assertNotEqual(v1_caps, v2_caps)

    def test_escalate_path_runs_create_task_as_policy_blind_write(self):
        # Gap: support.create_task (a write) also runs with no policy decision (issue #17).
        result = BaselineAgent(router=route_v1).run_case("escalate ticket", "C-100", "INV-9")
        caps = [s["capability"] for s in result["steps"]]
        self.assertIn("support.create_task", caps)
        writes = [w["capability"] for w in result["policy_blind_writes"]]
        self.assertIn("support.create_task", writes)

    def test_email_send_is_policy_blind_but_draft_is_not(self):
        # Gap: email.send_reply is a policy-blind write; email.draft_reply is intentionally
        # excluded from WRITE_OR_DESTRUCTIVE because drafting has no external side effect.
        sent = BaselineAgent(router=route_v1).run_case("send direct email reply", "C-100", "INV-9")
        sent_writes = [w["capability"] for w in sent["policy_blind_writes"]]
        self.assertIn("email.send_reply", sent_writes)

        fake_tools.reset_state()
        drafted = BaselineAgent(router=route_v2).run_case(
            "send direct email reply", "C-100", "INV-9"
        )
        draft_writes = [w["capability"] for w in drafted["policy_blind_writes"]]
        self.assertNotIn("email.draft_reply", draft_writes)


if __name__ == "__main__":
    unittest.main()
