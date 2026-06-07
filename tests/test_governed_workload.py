import unittest

from enterprise_agent_control_plane import fake_tools
from enterprise_agent_control_plane.governed_agent import GovernedAgent
from enterprise_agent_control_plane.scenarios import WORKLOAD


class TestGovernedWorkload(unittest.TestCase):
    """The governed path over the full multi-case workload (issue #107)."""

    def setUp(self):
        fake_tools.reset_state()

    def _run_all(self) -> dict[str, dict]:
        outcomes = {}
        for scenario in WORKLOAD:
            fake_tools.reset_state()
            result = GovernedAgent().run_case(
                scenario.request, scenario.customer_id, scenario.invoice_id, principal="support_agent"
            )
            outcomes[scenario.name] = result["bounded_output"]
        return outcomes

    def test_governed_path_handles_every_workload_case(self):
        # The governed path must run the same multi-case workload the baseline does, so the
        # before/after contrast is case-for-case rather than five-vs-one (issue #107).
        outcomes = self._run_all()
        self.assertEqual({s.name for s in WORKLOAD}, set(outcomes))

        # refund / escalation / email each select a deterministic flow and hold their gated
        # write for approval (no approver configured) instead of executing it.
        for name, gated in (
            ("refund", "billing.issue_refund"),
            ("escalation", "support.create_task"),
            ("email_reply", "email.send_reply"),
        ):
            self.assertEqual(outcomes[name]["status"], "ok")
            self.assertEqual(outcomes[name]["gated_capability"], gated)
            self.assertEqual(outcomes[name]["action_status"], "approval_required")

        # The ambiguous request matches no governed flow -- an explicit no-match, not a silent
        # default (the baseline's unbounded router stalls here).
        self.assertEqual(outcomes["ambiguous"]["status"], "no_matching_flow")

        # The not-found invoice halts the flow fail-closed before any write (the baseline
        # refunds it anyway).
        self.assertEqual(outcomes["not_found"]["status"], "halted")

    def test_no_side_effect_commits_without_approval(self):
        # Across the whole workload, with no approver, the governed path commits nothing: every
        # risky write is held, in contrast to the baseline's policy-blind writes (issue #107).
        self._run_all()
        self.assertEqual(fake_tools.REFUNDS, [])
        self.assertEqual(fake_tools.TASKS, [])
        self.assertEqual(fake_tools.SENT_EMAILS, [])


if __name__ == "__main__":
    unittest.main()
