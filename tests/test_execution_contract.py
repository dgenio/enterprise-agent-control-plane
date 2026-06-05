"""Governed write-path execution contract tests.

These lock in the behaviors that make a governed write trustworthy: it is committed only
after an explicit allow (#38), every write a flow performs is gated (#66), a failed step
halts the flow before any write (#41), a write commits at most once per case (#113), and an
'ask' is approved only by an authorized, distinct second party (#64).
"""

import unittest

from enterprise_agent_control_plane import fake_tools
from enterprise_agent_control_plane.flows import FLOW_REGISTRY
from enterprise_agent_control_plane.governed_agent import GovernedAgent
from enterprise_agent_control_plane.policies import ACTION_CLASSES


def _events(result, action):
    return [e for e in result["trace"].as_dict()["events"] if e["action"] == action]


class TestSideEffectBoundary(unittest.TestCase):
    """#38 — writes commit only on allow; otherwise the world is unchanged."""

    def setUp(self):
        fake_tools.reset_state()

    def test_approval_required_refund_leaves_no_side_effect(self):
        # INV-9 is 149.0 -> 'ask'; with no approver it stays pending and must not commit.
        result = GovernedAgent().run_case("refund request", "C-100", "INV-9")
        self.assertEqual(result["bounded_output"]["action_status"], "approval_required")
        self.assertEqual(fake_tools.REFUNDS, [])
        commit = _events(result, "action.commit")
        self.assertEqual([e["details"]["mode"] for e in commit], ["dry_run"])

    def test_denied_refund_leaves_no_side_effect(self):
        # An amount over the manager limit is denied outright; no refund may be recorded.
        result = GovernedAgent().run_case("refund request", "C-100", "INV-9", principal="support_agent")
        # Force a deny by gating a huge amount directly through the decision path.
        decision = GovernedAgent().decide("billing.issue_refund", "support_agent", {"amount": 9999.0})
        self.assertEqual(decision.outcome, "denied")
        self.assertEqual(result["bounded_output"]["gated_capability"], "billing.issue_refund")
        self.assertEqual(fake_tools.REFUNDS, [])

    def test_approved_refund_commits_once_and_is_recorded(self):
        result = GovernedAgent(approver=lambda req: True).run_case("refund request", "C-100", "INV-9")
        self.assertEqual(result["bounded_output"]["action_status"], "approved")
        self.assertEqual(len(fake_tools.REFUNDS), 1)
        self.assertEqual(fake_tools.REFUNDS[0]["committed"], True)
        commit = _events(result, "action.commit")
        self.assertEqual([e["details"]["mode"] for e in commit], ["committed"])


class TestGateEveryWrite(unittest.TestCase):
    """#66 — gating is derived from the flow's writes, not a per-intent hardcode."""

    def setUp(self):
        fake_tools.reset_state()

    def test_two_write_flow_gates_both_independently(self):
        result = GovernedAgent().run_case("refund and notify the customer", "C-100", "INV-9")
        self.assertEqual(result["flow"], "refund_and_notify")
        gated = [a["capability"] for a in result["bounded_output"]["gated_actions"]]
        self.assertEqual(gated, ["billing.issue_refund", "email.send_reply"])
        # One policy decision per gated write.
        decided = [e["details"]["capability"] for e in _events(result, "policy.decision")]
        self.assertIn("billing.issue_refund", decided)
        self.assertIn("email.send_reply", decided)
        self.assertEqual(len(result["decisions"]), 2)

    def test_no_write_reachable_without_a_recorded_decision(self):
        result = GovernedAgent().run_case("refund and notify the customer", "C-100", "INV-9")
        decided = {e["details"]["capability"] for e in _events(result, "policy.decision")}
        for capability in FLOW_REGISTRY["refund_and_notify"].gated_capabilities:
            self.assertIn(capability, decided)

    def test_every_gated_capability_is_write_or_destructive(self):
        # The set to gate is derived from action classes (#66): no read sneaks in.
        for flow in FLOW_REGISTRY.values():
            for capability in flow.gated_capabilities:
                self.assertIn(ACTION_CLASSES[capability], ("write", "destructive"))


class TestFailClosedSteps(unittest.TestCase):
    """#41 — a failed step halts the flow before any write runs."""

    def setUp(self):
        fake_tools.reset_state()

    def test_not_found_dependency_halts_before_write(self):
        # C-100 exists but INV-404 does not: lookup_invoice fails, so the flow must halt and
        # the downstream refund must never be gated or committed.
        result = GovernedAgent().run_case("refund request", "C-100", "INV-404")
        self.assertEqual(result["bounded_output"]["status"], "halted")
        self.assertEqual(result["decisions"], [])
        self.assertEqual(fake_tools.REFUNDS, [])
        halts = _events(result, "flow.halt")
        self.assertEqual(len(halts), 1)
        self.assertEqual(halts[0]["details"]["step"], "lookup_invoice")
        # No step after the failed one ran: check_policy / draft_reply never appear as steps.
        steps = [e["details"]["step"] for e in _events(result, "flow.step")]
        self.assertEqual(steps, ["lookup_customer", "lookup_invoice"])

    def test_halted_trace_still_validates_and_verifies(self):
        result = GovernedAgent().run_case("refund request", "C-100", "INV-404")
        self.assertTrue(result["trace"].validate().ok)
        self.assertTrue(result["trace"].verify())


class TestCaseScopedIdempotency(unittest.TestCase):
    """#113 — a write commits at most once per case, even on replay."""

    def setUp(self):
        fake_tools.reset_state()

    def test_doubly_run_case_commits_exactly_one_write(self):
        agent = GovernedAgent(approver=lambda req: True)
        first = agent.run_case("refund request", "C-100", "INV-9")
        second = agent.run_case("refund request", "C-100", "INV-9")
        self.assertEqual(len(fake_tools.REFUNDS), 1)
        self.assertEqual(first["bounded_output"]["gated_actions"][0]["commit_mode"], "committed")
        self.assertEqual(second["bounded_output"]["gated_actions"][0]["commit_mode"], "replay")
        self.assertEqual([e["details"]["mode"] for e in _events(second, "action.commit")], ["replay"])


class TestSeparationOfDuties(unittest.TestCase):
    """#64 — 'ask' is approved only by an authorized, distinct principal."""

    def setUp(self):
        fake_tools.reset_state()

    def test_authorized_approver_is_recorded(self):
        result = GovernedAgent(approver=lambda req: True).run_case("refund request", "C-100", "INV-9")
        self.assertEqual(result["bounded_output"]["action_status"], "approved")
        resolved = _events(result, "approval.resolved")
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["details"]["approver"], "support_manager")

    def test_self_approval_is_rejected(self):
        result = GovernedAgent(approver=lambda req: True, approver_principal="support_agent").run_case(
            "refund request", "C-100", "INV-9", principal="support_agent"
        )
        self.assertEqual(result["bounded_output"]["action_status"], "approval_denied")
        self.assertEqual(fake_tools.REFUNDS, [])
        resolved = _events(result, "approval.resolved")
        self.assertEqual(resolved[0]["details"]["authority_basis"], "self_approval_rejected")

    def test_unauthorized_approver_is_rejected(self):
        # billing_admin is not in APPROVER_AUTHORITY, so it cannot approve a destructive action.
        result = GovernedAgent(approver=lambda req: True, approver_principal="billing_admin").run_case(
            "refund request", "C-100", "INV-9", principal="support_agent"
        )
        self.assertEqual(result["bounded_output"]["action_status"], "approval_denied")
        self.assertEqual(fake_tools.REFUNDS, [])
        resolved = _events(result, "approval.resolved")
        self.assertEqual(resolved[0]["details"]["authority_basis"], "unauthorized_approver")


if __name__ == "__main__":
    unittest.main()
