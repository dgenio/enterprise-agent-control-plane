import unittest

from enterprise_agent_control_plane import fake_tools
from enterprise_agent_control_plane.governed_agent import GovernedAgent


class TestRoleDifferentiatedDecisions(unittest.TestCase):
    """Same capability, different decision per principal -- exercises billing_admin (issue #108)."""

    def setUp(self):
        fake_tools.reset_state()
        self.agent = GovernedAgent()

    def _decide_outcome(self, capability: str, principal: str, args=None) -> str:
        return self.agent.decide(capability, principal, args).outcome

    def test_frame_expand_differs_by_role(self):
        # frame.expand reveals a Frame's redacted raw detail (issue #114): only principals
        # authorized to view sensitive material hold the token for it.
        self.assertEqual(self._decide_outcome("frame.expand", "support_agent"), "denied")
        self.assertEqual(self._decide_outcome("frame.expand", "support_manager"), "allowed")
        self.assertEqual(self._decide_outcome("frame.expand", "billing_admin"), "allowed")

    def test_billing_admin_is_exercised_and_role_scoped(self):
        # support.create_task is in the agent/manager grant (write -> ask) but NOT
        # billing_admin's, so billing_admin is rejected at the token layer -- the previously
        # unused principal now produces a distinct decision (issue #108).
        self.assertEqual(
            self._decide_outcome("support.create_task", "support_agent"), "approval_required"
        )
        self.assertEqual(
            self._decide_outcome("support.create_task", "support_manager"), "approval_required"
        )
        self.assertEqual(self._decide_outcome("support.create_task", "billing_admin"), "denied")

    def test_audit_export_is_restricted_to_managers(self):
        self.assertEqual(self._decide_outcome("audit.export_case", "support_manager"), "allowed")
        self.assertEqual(self._decide_outcome("audit.export_case", "support_agent"), "denied")
        self.assertEqual(self._decide_outcome("audit.export_case", "billing_admin"), "denied")

    def test_token_validity_distinguishes_no_grant_from_policy_denial(self):
        # The decision's token_valid flag separates a token-layer rejection (role holds no
        # grant) from a policy decision reached because the grant *is* held.
        no_grant = self.agent.decide("support.create_task", "billing_admin")
        self.assertFalse(no_grant.token_valid)
        held = self.agent.decide("frame.expand", "billing_admin")
        self.assertTrue(held.token_valid)


if __name__ == "__main__":
    unittest.main()
