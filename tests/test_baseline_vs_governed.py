import json
import unittest
from pathlib import Path

from enterprise_agent_control_plane.baseline_agent import BaselineAgent
from enterprise_agent_control_plane.governed_agent import GovernedAgent


class TestBaselineVsGoverned(unittest.TestCase):
    def test_baseline_exposes_full_catalog_and_attempts_risky_action(self):
        result = BaselineAgent().run_case("C-100", "INV-9")
        self.assertEqual(result["mode"], "unsafe")
        self.assertEqual(len(result["visible_tools"]), 9)
        self.assertEqual(result["raw_outputs"]["refund_attempt"]["status"], "issued")

    def test_governed_path_bounds_tools_and_writes_audit_trace(self):
        result = GovernedAgent().run_case("C-100", "INV-9")
        self.assertEqual(result["mode"], "governed")
        self.assertLess(len(result["visible_tools"]), 9)
        self.assertEqual(result["bounded_output"]["refund_action"], "blocked")

        trace = json.loads(Path(result["audit_trace_path"]).read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(trace["events"]), 3)


if __name__ == "__main__":
    unittest.main()
