import unittest
from datetime import UTC, datetime, timedelta

from enterprise_agent_control_plane.policies import (
    AgentFencePolicy,
    CapabilityToken,
    holds_capability,
    issue_case_tokens,
    issue_tokens,
)


class TestPolicy(unittest.TestCase):
    def setUp(self):
        self.policy = AgentFencePolicy()

    def test_read_action_allowed(self):
        self.assertEqual(self.policy.evaluate("crm.search_customer", "support_agent").decision, "allow")

    def test_write_action_requires_approval(self):
        self.assertEqual(self.policy.evaluate("email.send_reply", "support_agent").decision, "ask")

    def test_refund_thresholds(self):
        self.assertEqual(self.policy.evaluate("billing.issue_refund", "support_agent", {"amount": 20.0}).decision, "allow")
        self.assertEqual(self.policy.evaluate("billing.issue_refund", "support_agent", {"amount": 149.0}).decision, "ask")
        self.assertEqual(self.policy.evaluate("billing.issue_refund", "support_agent", {"amount": 9999.0}).decision, "deny")

    def test_refund_without_amount_requires_approval(self):
        self.assertEqual(self.policy.evaluate("billing.issue_refund", "support_agent").decision, "ask")

    def test_export_case_restricted_to_managers(self):
        self.assertEqual(self.policy.evaluate("audit.export_case", "support_agent").decision, "deny")
        self.assertEqual(self.policy.evaluate("audit.export_case", "support_manager").decision, "allow")

    def test_unknown_capability_denied_by_default(self):
        self.assertEqual(self.policy.evaluate("billing.delete_everything", "support_manager").decision, "deny")


class TestCapabilityTokens(unittest.TestCase):
    def test_role_grants_issued_as_tokens(self):
        tokens = issue_tokens("support_agent")
        self.assertTrue(holds_capability(tokens, "billing.issue_refund"))
        self.assertFalse(holds_capability(tokens, "audit.export_case"))

    def test_unknown_principal_holds_nothing(self):
        self.assertEqual(issue_tokens("intern"), [])
        self.assertFalse(holds_capability(issue_tokens("intern"), "crm.search_customer"))

    def test_expired_token_is_invalid(self):
        past = datetime.now(UTC) - timedelta(hours=1)
        future = datetime.now(UTC) + timedelta(hours=1)
        expired = CapabilityToken("support_agent", "billing.issue_refund", expires=past)
        valid = CapabilityToken("support_agent", "billing.issue_refund", expires=future)
        self.assertFalse(expired.is_valid("billing.issue_refund"))
        self.assertTrue(valid.is_valid("billing.issue_refund"))


class TestCaseScopedTokens(unittest.TestCase):
    # --- just-in-time, case-scoped issuance (issue #63) -----------------------
    def test_only_requested_and_role_granted_capabilities_are_minted(self):
        # support_agent's role grants email.send_reply, but a refund case that never requests
        # it must not mint it -- least privilege, just-in-time rather than a standing grant.
        needed = {"crm.search_customer", "billing.get_invoice", "billing.issue_refund"}
        tokens = issue_case_tokens("support_agent", needed, scope="trace-1")
        self.assertEqual(
            sorted(t.capability for t in tokens),
            ["billing.get_invoice", "billing.issue_refund", "crm.search_customer"],
        )
        # The standing role grant would include email.send_reply; the case grant does not.
        self.assertTrue(holds_capability(issue_tokens("support_agent"), "email.send_reply"))
        self.assertFalse(holds_capability(tokens, "email.send_reply"))

    def test_requesting_a_capability_outside_the_role_grants_nothing(self):
        # The role still bounds what can be minted (least privilege twice): audit.export_case is
        # not in support_agent's grant, so requesting it for a case mints no token for it.
        tokens = issue_case_tokens("support_agent", {"audit.export_case"}, scope="trace-2")
        self.assertEqual(tokens, [])

    def test_tokens_carry_the_case_scope_and_expire(self):
        tokens = issue_case_tokens("support_agent", {"billing.issue_refund"}, scope="trace-3")
        self.assertEqual({t.scope for t in tokens}, {"trace-3"})

        # A short TTL means the grant does not outlive the case.
        expired = issue_case_tokens(
            "support_agent", {"billing.issue_refund"}, scope="trace-3",
            expires=datetime.now(UTC) - timedelta(seconds=1),
        )
        self.assertFalse(holds_capability(expired, "billing.issue_refund"))
        future = issue_case_tokens(
            "support_agent", {"billing.issue_refund"}, scope="trace-3",
            expires=datetime.now(UTC) + timedelta(seconds=60),
        )
        self.assertTrue(holds_capability(future, "billing.issue_refund"))


if __name__ == "__main__":
    unittest.main()
