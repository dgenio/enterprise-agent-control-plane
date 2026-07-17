"""Schema-based input validation for deterministic flows (issues #4/#162).

Before this, the executor read ``payload["customer_id"]`` directly and a missing field raised
an unhandled ``KeyError``. Now each step validates its inputs against the capability's declared
schema first and fails *closed* with a structured ``invalid_input`` error instead. These tests
assert the failure is clean (not a raw exception), that it halts the flow before any later
step, and that the happy path still conforms to the declared output shape.
"""

import unittest

from enterprise_agent_control_plane import fake_tools
from enterprise_agent_control_plane.errors import ErrorCode
from enterprise_agent_control_plane.flows import ChainWeaverExecutor
from enterprise_agent_control_plane.registry import build_tool_map, validate_step_input


class TestStepInputValidation(unittest.TestCase):
    def test_missing_required_field_reports_it(self):
        result = validate_step_input("crm.search_customer", {})
        self.assertIsNotNone(result)
        self.assertEqual(result["error"], ErrorCode.INVALID_INPUT.value)
        self.assertEqual(result["fields"], ["customer_id"])

    def test_wrong_typed_field_is_rejected(self):
        result = validate_step_input("crm.search_customer", {"customer_id": ["not", "a", "str"]})
        self.assertIsNotNone(result)
        self.assertEqual(result["error"], ErrorCode.INVALID_INPUT.value)
        self.assertIn("customer_id", result["fields"])

    def test_valid_input_passes(self):
        self.assertIsNone(validate_step_input("crm.search_customer", {"customer_id": "C-100"}))

    def test_defaulted_arg_is_not_a_required_input(self):
        # docs.search_policy's ``query`` is supplied by a step default, so an empty payload is
        # still valid input for that step.
        self.assertIsNone(validate_step_input("docs.search_policy", {}))


class TestExecutorFailsClosedOnBadInput(unittest.TestCase):
    def setUp(self):
        fake_tools.reset_state()
        self.runner = ChainWeaverExecutor(build_tool_map())

    def test_missing_input_fails_closed_without_keyerror(self):
        # The refund flow's first step needs customer_id; omitting it must NOT raise -- it must
        # produce a structured invalid_input failure and halt before any later step.
        result = self.runner.run("refund_review", {"invoice_id": "INV-9"})
        self.assertEqual(result[0]["status"], "failed")
        self.assertEqual(result[0]["output"]["error"], ErrorCode.INVALID_INPUT.value)
        # Fail closed: the flow halted at the first step, so no downstream step ran and no
        # refund/draft was reached.
        self.assertEqual(len(result), 1)

    def test_happy_path_outputs_conform_to_declared_shape(self):
        result = self.runner.run(
            "refund_review",
            {"customer_id": "C-100", "invoice_id": "INV-9", "customer_name": "Ari Carter"},
        )
        self.assertEqual(
            [s["step"] for s in result],
            ["lookup_customer", "lookup_invoice", "check_policy", "draft_reply"],
        )
        for step in result:
            self.assertEqual(step["status"], "ok")
            # Each step returns a structured (dict or list) output, never a raw scalar or None.
            self.assertIsInstance(step["output"], (dict, list))


if __name__ == "__main__":
    unittest.main()
