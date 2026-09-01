"""Tests for the structured error taxonomy (issue #174).

The taxonomy's whole value is that producers and consumers share one vocabulary and the wire
values never silently drift. These tests lock the wire strings (so an emitted trace stays
comparable), prove the ``error``/``is_error`` helpers behave, and assert the codes are unique.
"""

import unittest

from enterprise_agent_control_plane.errors import ErrorCode, StepStatus, error, is_error


class TestErrorTaxonomy(unittest.TestCase):
    def test_wire_values_are_stable(self):
        # These strings appear in emitted audit traces and are matched by external readers, so
        # they must not change silently. Locking them is the point of the taxonomy.
        self.assertEqual(ErrorCode.OUT_OF_BUDGET.value, "out_of_budget")
        self.assertEqual(ErrorCode.EXCEPTION.value, "exception")
        self.assertEqual(ErrorCode.UNKNOWN_STEP.value, "unknown_step")
        self.assertEqual(ErrorCode.UNKNOWN_WRITE.value, "unknown_write")
        self.assertEqual(ErrorCode.UNKNOWN_CAPABILITY.value, "unknown_capability")
        self.assertEqual(ErrorCode.NOT_FOUND.value, "not_found")
        self.assertEqual(ErrorCode.INVALID_INPUT.value, "invalid_input")

    def test_codes_are_unique(self):
        values = [c.value for c in ErrorCode]
        self.assertEqual(len(values), len(set(values)))

    def test_str_enum_compares_to_wire_string(self):
        # A str-Enum member equals its wire string, so consumers may compare either way.
        self.assertEqual(ErrorCode.OUT_OF_BUDGET, "out_of_budget")

    def test_error_builds_payload_with_plain_string_code(self):
        payload = error(ErrorCode.INVALID_INPUT, capability="crm.search_customer", fields=["x"])
        # The stored ``error`` value is the plain wire string, byte-identical to the literal it
        # replaced -- not the enum object.
        self.assertEqual(payload["error"], "invalid_input")
        self.assertIsInstance(payload["error"], str)
        self.assertEqual(payload["capability"], "crm.search_customer")
        self.assertEqual(payload["fields"], ["x"])

    def test_is_error_detects_any_and_specific_code(self):
        payload = error(ErrorCode.OUT_OF_BUDGET, detail="over budget")
        self.assertTrue(is_error(payload))
        self.assertTrue(is_error(payload, ErrorCode.OUT_OF_BUDGET))
        self.assertFalse(is_error(payload, ErrorCode.NOT_FOUND))
        # Non-error payloads and non-dicts are not errors.
        self.assertFalse(is_error({"ok": True}))
        self.assertFalse(is_error(None))
        self.assertFalse(is_error("nope"))

    def test_step_status_values_are_stable(self):
        self.assertEqual(StepStatus.OK.value, "ok")
        self.assertEqual(StepStatus.FAILED.value, "failed")
        self.assertEqual(StepStatus.BLOCKED_NO_TOKEN.value, "blocked_no_token")


if __name__ == "__main__":
    unittest.main()
