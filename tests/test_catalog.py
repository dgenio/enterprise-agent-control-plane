import unittest

from enterprise_agent_control_plane.catalog import build_catalog, shortlist_capabilities


class TestCatalog(unittest.TestCase):
    def test_catalog_contains_expected_tools(self):
        capabilities = {c.capability for c in build_catalog()}
        self.assertIn("billing.issue_refund", capabilities)
        self.assertEqual(len(capabilities), 9)

    def test_shortlist_is_bounded(self):
        shortlist = shortlist_capabilities("customer refund reply", build_catalog(), limit=3)
        self.assertLessEqual(len(shortlist), 3)
        self.assertTrue(any(c.capability == "billing.issue_refund" for c in shortlist))


if __name__ == "__main__":
    unittest.main()
