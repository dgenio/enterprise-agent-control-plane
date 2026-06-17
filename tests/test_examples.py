"""Smoke tests for the runnable examples gallery (issue #62).

The ``examples/*.py`` scripts are documentation: each demonstrates one capability against
the real modules. Nothing in ``make test`` executed them, so an API change in a demonstrated
module (``catalog``, ``policies``, ``flows``, ``audit``) could silently break an example while
the rest of the suite stayed green. These tests run each example end-to-end in a subprocess
and assert it exits cleanly and prints something, so a broken example fails CI.
"""

import subprocess
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_EXAMPLES_DIR = _REPO_ROOT / "examples"

# Every runnable example in the gallery (the demonstration scripts, not examples/README.md).
_EXAMPLES = sorted(p.name for p in _EXAMPLES_DIR.glob("*.py"))


class TestExamplesRun(unittest.TestCase):
    def test_gallery_is_discovered(self):
        # Guard against the glob silently matching nothing (which would make the run-tests
        # below vacuously pass); the gallery ships four examples.
        self.assertEqual(
            len(_EXAMPLES), 4, f"expected 4 runnable examples, found {_EXAMPLES}"
        )

    def test_each_example_runs_cleanly(self):
        for name in _EXAMPLES:
            with self.subTest(example=name):
                result = subprocess.run(
                    [sys.executable, str(_EXAMPLES_DIR / name)],
                    cwd=_REPO_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    f"{name} exited {result.returncode}\nstdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}",
                )
                self.assertTrue(
                    result.stdout.strip(), f"{name} produced no output"
                )


if __name__ == "__main__":
    unittest.main()
