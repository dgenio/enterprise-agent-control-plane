"""Tests for the VibeGuard diff safety gate (issues #10, #91, #125).

The gate must (a) flag the committed risky fixture -- the demonstrable run #91 calls for --
and (b) actually detect each documented change class while staying quiet on benign diffs.
Without the negative tests a refactor could turn the gate into a no-op that still passes
the fixture check.
"""

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from scripts.vibeguard_gate import main, repo_root, scan_diff

# A minimal unified diff that widens a fallback refund amount (the fixture's change class).
_WIDENED = """\
@@ -249,1 +249,1 @@ class BaselineAgent:
-            amount = invoice.get("amount", 149.0) if isinstance(invoice, dict) else 149.0
+            amount = invoice.get("amount", 100000.0) if isinstance(invoice, dict) else 100000.0
"""

# The same line narrowed -- only widening is a finding, so this must stay clean.
_NARROWED = """\
@@ -249,1 +249,1 @@ class BaselineAgent:
-            amount = invoice.get("amount", 149.0) if isinstance(invoice, dict) else 149.0
+            amount = invoice.get("amount", 49.0) if isinstance(invoice, dict) else 49.0
"""

# A benign comment-only change.
_CLEAN = """\
@@ -10,1 +10,1 @@
-# old comment
+# new, clearer comment
"""


class TestVibeGuardGate(unittest.TestCase):
    def test_committed_fixture_is_flagged(self):
        fixture = (repo_root() / "demos" / "risky_ai_change.diff").read_text(encoding="utf-8")
        findings = scan_diff(fixture)
        self.assertTrue(findings, "the gate must flag the committed risky fixture")
        self.assertTrue(any("widened money-movement/fallback bound" in f for f in findings))
        # The widened value (149 -> 100000) must be visible in the human-readable finding.
        self.assertTrue(any("100000" in f and "149" in f for f in findings))

    def test_widened_amount_is_flagged(self):
        self.assertEqual(len(scan_diff(_WIDENED)), 1)

    def test_narrowed_amount_is_not_flagged(self):
        self.assertEqual(scan_diff(_NARROWED), [])

    def test_clean_diff_is_not_flagged(self):
        self.assertEqual(scan_diff(_CLEAN), [])

    def test_empty_diff_is_not_flagged(self):
        self.assertEqual(scan_diff(""), [])

    def test_removing_a_write_capability_is_flagged(self):
        diff = (
            "@@ -12,1 +12,1 @@\n"
            '-WRITE_OR_DESTRUCTIVE = {"billing.issue_refund", "email.send_reply", "support.create_task"}\n'
            '+WRITE_OR_DESTRUCTIVE = {"email.send_reply", "support.create_task"}\n'
        )
        findings = scan_diff(diff)
        self.assertTrue(
            any('"billing.issue_refund"' in f and "WRITE_OR_DESTRUCTIVE" in f for f in findings),
            f"expected a hidden-write finding, got: {findings}",
        )

    def test_introducing_a_network_call_is_flagged(self):
        diff = (
            "@@ -1,0 +1,1 @@\n"
            '+    response = requests.get("http://example.com/refund")\n'
        )
        findings = scan_diff(diff)
        self.assertTrue(
            any("outbound network call" in f for f in findings),
            f"expected an outbound-call finding, got: {findings}",
        )

    def test_runtime_source_change_is_scanned(self):
        # The same widening, attributed to a runtime source file, IS flagged.
        diff = (
            "+++ b/enterprise_agent_control_plane/baseline_agent.py\n"
            "@@ -249,1 +249,1 @@\n"
            '-            amount = invoice.get("amount", 149.0)\n'
            '+            amount = invoice.get("amount", 100000.0)\n'
        )
        self.assertEqual(len(scan_diff(diff)), 1)

    def test_changes_under_ignored_paths_are_skipped(self):
        # Tests, docs, demo fixtures, and these scripts are not the agent's runtime; a
        # widening or a network reference there must not trip the gate (otherwise the PR
        # that introduces the gate, and every test snippet, would be blocked).
        for path in (
            "tests/test_example.py",
            "docs/vibeguard.md",
            "demos/risky_ai_change.diff",
            "scripts/vibeguard_gate.py",
        ):
            diff = (
                f"+++ b/{path}\n"
                "@@ -1,1 +1,1 @@\n"
                '-            amount = invoice.get("amount", 149.0)\n'
                '+            amount = invoice.get("amount", 100000.0)\n'
                "+    import urllib.request\n"
            )
            self.assertEqual(scan_diff(diff), [], f"{path} should be skipped")


class TestVibeGuardGateCli(unittest.TestCase):
    def _run(self, argv: list[str]) -> int:
        with redirect_stdout(io.StringIO()):
            return main(argv)

    def test_self_check_exits_zero(self):
        # The gate flags the fixture, so the self-check passes.
        self.assertEqual(self._run(["--self-check"]), 0)

    def test_gate_blocks_a_risky_diff(self):
        with tempfile.NamedTemporaryFile("w", suffix=".diff", delete=False) as handle:
            handle.write(_WIDENED)
            path = handle.name
        self.addCleanup(lambda: Path(path).unlink(missing_ok=True))
        self.assertEqual(self._run(["--diff", path]), 1)

    def test_gate_passes_a_clean_diff(self):
        with tempfile.NamedTemporaryFile("w", suffix=".diff", delete=False) as handle:
            handle.write(_CLEAN)
            path = handle.name
        self.addCleanup(lambda: Path(path).unlink(missing_ok=True))
        self.assertEqual(self._run(["--diff", path]), 0)


if __name__ == "__main__":
    unittest.main()
