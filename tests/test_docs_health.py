import tempfile
import unittest
from pathlib import Path

from scripts.check_docs_health import (
    canonical_description,
    check_canonical_description,
    check_links,
    collect_errors,
    repo_root,
)

_CANON = "A canonical one-line tagline for testing."


class TestDocsHealth(unittest.TestCase):
    def test_internal_links_resolve(self):
        errors = check_links(repo_root())
        self.assertEqual(errors, [], f"broken internal Markdown links: {errors}")

    def test_canonical_description_is_consistent(self):
        errors = check_canonical_description(repo_root())
        self.assertEqual(errors, [], f"canonical description drift: {errors}")

    def test_canonical_description_extracted_from_metadata(self):
        description = canonical_description(repo_root())
        # The description must be the honest, non-aspirational About string.
        self.assertIn("reference architecture", description)
        self.assertIn("tool-using agents", description)

    def test_collect_errors_is_clean(self):
        self.assertEqual(collect_errors(repo_root()), [])


class TestDocsHealthDetection(unittest.TestCase):
    """Negative tests: the guard must actually *detect* the problems it exists to catch.

    Without these, a refactor could quietly turn the checker into a no-op while the
    positive tests above still pass.
    """

    def _tmp_root(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def _write_metadata(self, root: Path) -> None:
        (root / "METADATA.md").write_text(
            f"## GitHub About description\n\n> {_CANON}\n", encoding="utf-8"
        )

    def test_broken_internal_link_is_flagged(self):
        root = self._tmp_root()
        (root / "docs").mkdir()
        (root / "README.md").write_text("[x](docs/missing.md)\n", encoding="utf-8")
        errors = check_links(root)
        self.assertTrue(
            any("broken internal link" in e for e in errors),
            f"expected a broken-link error, got: {errors}",
        )

    def test_link_escaping_repo_root_is_flagged(self):
        root = self._tmp_root()
        (root / "docs").mkdir()
        # Target resolves outside the repo root (and exists on the runner) -- must be
        # rejected rather than silently passing.
        (root / "README.md").write_text(
            "[x](../../../../../../etc/hosts)\n", encoding="utf-8"
        )
        errors = check_links(root)
        self.assertTrue(
            any("escapes repo root" in e for e in errors),
            f"expected an escapes-repo-root error, got: {errors}",
        )

    def test_canonical_description_drift_is_flagged(self):
        root = self._tmp_root()
        self._write_metadata(root)
        (root / "README.md").write_text(_CANON + "\n", encoding="utf-8")
        (root / "pyproject.toml").write_text(
            f'description = "{_CANON}"\n', encoding="utf-8"
        )
        # CITATION.cff drifts: it does not carry the canonical tagline verbatim.
        (root / "CITATION.cff").write_text(
            "abstract: A different tagline entirely.\n", encoding="utf-8"
        )
        errors = check_canonical_description(root)
        self.assertTrue(
            any("CITATION.cff" in e and "drift" in e for e in errors),
            f"expected a CITATION.cff drift error, got: {errors}",
        )

    def test_consistent_temp_repo_passes(self):
        # Positive control for the temp-repo harness so the negative tests above are
        # meaningful (the failures come from the injected defect, not the scaffolding).
        root = self._tmp_root()
        (root / "docs").mkdir()
        self._write_metadata(root)
        for name in ("README.md", "pyproject.toml", "CITATION.cff"):
            (root / name).write_text(_CANON + "\n", encoding="utf-8")
        self.assertEqual(collect_errors(root), [])


if __name__ == "__main__":
    unittest.main()
