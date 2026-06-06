import unittest

from scripts.check_docs_health import (
    canonical_description,
    check_canonical_description,
    check_links,
    collect_errors,
    repo_root,
)


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


if __name__ == "__main__":
    unittest.main()
