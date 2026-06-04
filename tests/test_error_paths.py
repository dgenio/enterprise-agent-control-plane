"""Tests for error-path behavior in fake tools and agents (F01)."""

import unittest

from enterprise_agent_control_plane import fake_tools
from enterprise_agent_control_plane.baseline_agent import BaselineAgent


class TestErrorPaths(unittest.TestCase):
    def setUp(self):
        fake_tools.reset_state()

    def test_crm_search_unknown_customer(self):
        result = fake_tools.crm_search_customer("UNKNOWN")
        self.assertEqual(result["error"], "not_found")
        self.assertEqual(result["customer_id"], "UNKNOWN")

    def test_billing_get_unknown_invoice(self):
        result = fake_tools.billing_get_invoice("BAD-ID")
        self.assertEqual(result["error"], "not_found")
        self.assertEqual(result["invoice_id"], "BAD-ID")

    def test_baseline_agent_with_unknown_ids(self):
        result = BaselineAgent().run_case("refund request", "UNKNOWN", "BAD-ID")
        self.assertEqual(result["raw_outputs"]["crm.search_customer"]["error"], "not_found")
        self.assertEqual(result["raw_outputs"]["billing.get_invoice"]["error"], "not_found")

    def test_support_search_no_tickets(self):
        result = fake_tools.support_search_tickets("UNKNOWN")
        self.assertEqual(result, [])

    def test_support_create_task_increments_task_id(self):
        fake_tools.support_create_task("C-100", "Note A")
        fake_tools.support_create_task("C-100", "Note B")
        self.assertEqual(len(fake_tools.TASKS), 2)
        self.assertEqual(fake_tools.TASKS[0]["task_id"], "TASK-1")
        self.assertEqual(fake_tools.TASKS[1]["task_id"], "TASK-2")


if __name__ == "__main__":
    unittest.main()
