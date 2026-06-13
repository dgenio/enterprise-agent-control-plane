"""Tests for the traceability-matrix guardrail (issue #133).

Positive tests assert the committed matrix is clean. Detection tests build a tiny matrix
in a temp repo and inject one defect each, so the checker is proven to actually catch the
problems it exists to catch (without them, a refactor could turn it into a no-op while the
positive tests still pass).
"""

import tempfile
import unittest
from pathlib import Path

from scripts.check_traceability import check_matrix, collect_errors, matrix_rows, repo_root

# A minimal, well-formed matrix used as the positive control for the detection harness. The
# "Where it lives" link points at a file the temp repo actually creates.
_HEADER = (
    "| Baseline risk | Governed control | dgenio library | Where it lives | Status |\n"
    "|---|---|---|---|---|\n"
)


class TestTraceabilityMatrix(unittest.TestCase):
    def test_committed_matrix_is_clean(self):
        errors = collect_errors(repo_root())
        self.assertEqual(errors, [], f"traceability matrix errors: {errors}")

    def test_matrix_rows_are_parsed(self):
        rows = matrix_rows(repo_root())
        # The real matrix has many rows; each parsed row carries the five declared columns.
        self.assertGreater(len(rows), 5)
        self.assertTrue(all(len(r) == 5 for r in rows), "every row must have five columns")


class TestTraceabilityDetection(unittest.TestCase):
    def _tmp_root(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "docs").mkdir()
        (root / "code.py").write_text("# referenced by the matrix\n", encoding="utf-8")
        return root

    def _write_matrix(self, root: Path, row: str) -> None:
        (root / "docs" / "control-traceability.md").write_text(
            _HEADER + row + "\n", encoding="utf-8"
        )

    def test_clean_temp_matrix_passes(self):
        # Positive control: a well-formed row produces no errors, so the negatives below are
        # attributable to the injected defect, not the scaffolding.
        root = self._tmp_root()
        self._write_matrix(root, "| risk | control | contextweaver | [`code.py`](../code.py) | Implemented |")
        self.assertEqual(check_matrix(root), [])

    def test_unconstrained_status_is_flagged(self):
        root = self._tmp_root()
        self._write_matrix(root, "| risk | control | contextweaver | [`code.py`](../code.py) | Shipped |")
        errors = check_matrix(root)
        self.assertTrue(any("not one of the allowed values" in e for e in errors), errors)

    def test_unknown_library_is_flagged(self):
        root = self._tmp_root()
        self._write_matrix(root, "| risk | control | madeuplib | [`code.py`](../code.py) | Implemented |")
        errors = check_matrix(root)
        self.assertTrue(any("no known Weaver Stack library" in e for e in errors), errors)

    def test_broken_code_link_is_flagged(self):
        root = self._tmp_root()
        self._write_matrix(root, "| risk | control | contextweaver | [`gone.py`](../gone.py) | Implemented |")
        errors = check_matrix(root)
        self.assertTrue(any("broken code/doc link" in e for e in errors), errors)

    def test_partial_row_without_issue_is_flagged(self):
        root = self._tmp_root()
        self._write_matrix(root, "| risk | control | lessonweaver | [`code.py`](../code.py) | Partial |")
        errors = check_matrix(root)
        self.assertTrue(any("links no tracking issue" in e for e in errors), errors)

    def test_partial_row_with_issue_passes(self):
        root = self._tmp_root()
        self._write_matrix(
            root, "| risk | control | lessonweaver | [`code.py`](../code.py) | Partial (planned, issue #68) |"
        )
        self.assertEqual(check_matrix(root), [])


if __name__ == "__main__":
    unittest.main()
