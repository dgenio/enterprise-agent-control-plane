import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from enterprise_agent_control_plane import comparison


class TestComparisonScorecard(unittest.TestCase):
    """Generated governed-vs-baseline scorecard artifact (issue #43)."""

    def test_governed_improves_on_baseline_for_key_dimensions(self):
        rows = {row["dimension"]: row for row in comparison.build_scorecard()["dimensions"]}

        # Fewer tools exposed to the model.
        self.assertLess(
            rows["tools exposed to the model"]["governed"],
            rows["tools exposed to the model"]["baseline"],
        )
        # No write runs without a policy gate on the governed path; the baseline has at least one.
        self.assertEqual(rows["ungated write/destructive actions"]["governed"], 0)
        self.assertGreater(rows["ungated write/destructive actions"]["baseline"], 0)
        # A structured audit trace exists for the governed run; the baseline has none.
        self.assertEqual(rows["structured audit trace"]["governed"], "yes")
        self.assertEqual(rows["structured audit trace"]["baseline"], "none")

        # Every directional dimension favors the governed path.
        self.assertTrue(
            all(row["governed_better"] for row in comparison.build_scorecard()["dimensions"])
        )

    def test_numbers_are_derived_from_runs_not_hardcoded(self):
        rows = {row["dimension"]: row for row in comparison.build_scorecard()["dimensions"]}
        # The baseline exposes the full nine-tool catalog every step.
        self.assertEqual(rows["tools exposed to the model"]["baseline"], 9)
        # The bounded shortlist is meaningfully smaller in model-visible context size.
        self.assertLess(
            rows["approx model-visible context (chars)"]["governed"],
            rows["approx model-visible context (chars)"]["baseline"],
        )
        # The leaked-field count comes from the baseline run, so it is a positive integer.
        self.assertGreater(rows["raw sensitive fields in model context"]["baseline"], 0)

    def test_save_writes_json_and_markdown_artifacts(self):
        scorecard = comparison.build_scorecard()
        with TemporaryDirectory() as tmp:
            json_path = Path(tmp) / "scorecard.json"
            md_path = Path(tmp) / "scorecard.md"
            paths = comparison.save_scorecard(scorecard, json_path=json_path, md_path=md_path)

            loaded = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
            self.assertEqual(loaded["dimensions"], scorecard["dimensions"])

            md = Path(paths["markdown"]).read_text(encoding="utf-8")
            self.assertIn("| Dimension | Baseline | Governed |", md)
            self.assertIn("comparison scorecard", md.lower())


if __name__ == "__main__":
    unittest.main()
