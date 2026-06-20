import json
import unittest
from pathlib import Path

from enterprise_agent_control_plane import fake_tools
from enterprise_agent_control_plane.baseline_agent import BaselineAgent
from enterprise_agent_control_plane.governed_agent import GovernedAgent


class TestBaselineVsGoverned(unittest.TestCase):
    def setUp(self):
        fake_tools.reset_state()

    def test_baseline_exposes_full_catalog_and_attempts_risky_action(self):
        result = BaselineAgent().run_case("refund request", "C-100", "INV-9")
        self.assertEqual(result["mode"], "unsafe")
        self.assertEqual(result["tools_offered_each_step"], 9)
        self.assertEqual(result["raw_outputs"]["billing.issue_refund"]["status"], "issued")

    def test_governed_path_bounds_tools_and_writes_audit_trace(self):
        result = GovernedAgent().run_case(
            "refund request", "C-100", "INV-9", principal="support_agent"
        )
        self.assertEqual(result["mode"], "governed")
        self.assertLess(len(result["visible_tools"]), 9)
        # The $149 refund is within the manager limit, so it is held for approval rather
        # than executed; with no approver configured it stays pending.
        self.assertEqual(result["bounded_output"]["action_status"], "approval_required")

        trace = json.loads(Path(result["audit_trace_path"]).read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(trace["events"]), 3)


if __name__ == "__main__":
    unittest.main()
