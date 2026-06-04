import unittest

from enterprise_agent_control_plane.policies import AgentFencePolicy, CapabilityToken, check_capability


class TestPolicy(unittest.TestCase):
    def test_risky_actions_require_approval(self):
        policy = AgentFencePolicy()
        self.assertEqual(policy.evaluate("billing.issue_refund", "agent").decision, "ask")
        self.assertEqual(policy.evaluate("email.send_reply", "agent").decision, "ask")

    def test_export_case_denied_for_non_supervisor(self):
        policy = AgentFencePolicy()
        self.assertEqual(policy.evaluate("audit.export_case", "agent").decision, "deny")

    def test_capability_token_validation(self):
        token = CapabilityToken(principal="agent", capability="billing.issue_refund")
        self.assertTrue(check_capability(token, "billing.issue_refund"))
        self.assertFalse(check_capability(token, "email.send_reply"))


if __name__ == "__main__":
    unittest.main()
