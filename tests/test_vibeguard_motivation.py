"""VibeGuard-motivation evidence (issues #35, #10, #105).

The risky fixture (``demos/risky_ai_change.diff``) widens the unsafe baseline's hardcoded
*fallback* refund amount (149.0 -> 100000.0). This test proves the existing suite would
**not** catch that change class -- it is evidence of the missing pre-merge gate, not the
gate itself. It never applies the diff and never changes the real default; the actual
gate lives in ``scripts/vibeguard_gate.py`` and is covered by ``test_vibeguard_gate.py``.
"""

import unittest
from pathlib import Path

from enterprise_agent_control_plane import fake_tools

_ROOT = Path(__file__).resolve().parents[1]
_BASELINE_SRC = _ROOT / "enterprise_agent_control_plane" / "baseline_agent.py"
_CHARACTERIZATION_SRC = _ROOT / "tests" / "test_baseline_characterization.py"
_FALLBACK_AMOUNT = "149.0"
_WIDENED_AMOUNT = 100000.0


class TestVibeGuardMotivation(unittest.TestCase):
    def test_real_fallback_amount_present_and_diff_not_applied(self):
        # The bound the fixture targets exists, and the illustrative diff is never applied.
        src = _BASELINE_SRC.read_text(encoding="utf-8")
        self.assertIn(_FALLBACK_AMOUNT, src)
        self.assertNotIn("100000", src)

    def test_no_characterization_test_pins_the_fallback_amount(self):
        # The characterization suite asserts only the PRESENCE of gaps (e.g. that an issued
        # refund's status is "issued"); none of them reference the fallback amount, so
        # widening it trips no assertion -- the gap a VibeGuard gate (#10) closes.
        char = _CHARACTERIZATION_SRC.read_text(encoding="utf-8")
        self.assertIn('"issued"', char)  # it does assert on the refund...
        self.assertNotIn("149", char)  # ...but never on the amount.

    def test_widened_fallback_still_passes_the_characterization_assertion(self):
        # Re-run the only assertion the baseline makes about an issued refund, at the
        # widened amount, WITHOUT touching baseline_agent.py: status is amount-blind, so the
        # widened value stays green exactly as the fixture claims.
        fake_tools.reset_state()
        refund = fake_tools.billing_issue_refund("INV-404", _WIDENED_AMOUNT, "customer requested")
        self.assertEqual(refund["status"], "issued")


if __name__ == "__main__":
    unittest.main()
