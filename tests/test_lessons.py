import unittest

from enterprise_agent_control_plane.lessons import LessonWeaverStub


class TestLessonLifecycle(unittest.TestCase):
    # --- lesson capture lifecycle (issue #9) ----------------------------------
    def test_add_review_then_only_reviewed_returned(self):
        weaver = LessonWeaverStub()
        weaver.add_failure("F-1", "refund fired on a not-found invoice")
        weaver.add_failure("F-2", "reply sent without approval")

        # Before review, nothing is promoted: unreviewed candidates stay inert.
        self.assertEqual(weaver.reviewed_lessons(), [])

        weaver.mark_reviewed("F-1")
        reviewed = weaver.reviewed_lessons()
        self.assertEqual([lesson.failure_id for lesson in reviewed], ["F-1"])
        self.assertTrue(reviewed[0].reviewed)
        self.assertEqual(reviewed[0].summary, "refund fired on a not-found invoice")

    def test_mark_reviewed_unknown_failure_is_a_no_op(self):
        weaver = LessonWeaverStub()
        weaver.add_failure("F-1", "a failure")
        weaver.mark_reviewed("does-not-exist")
        self.assertEqual(weaver.reviewed_lessons(), [])


if __name__ == "__main__":
    unittest.main()
