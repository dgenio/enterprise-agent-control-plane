import unittest

from enterprise_agent_control_plane.lessons import LessonWeaverStub, PolicyChange
from enterprise_agent_control_plane.policies import AgentFencePolicy


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


class TestReviewedLessonChangesPolicy(unittest.TestCase):
    # --- reviewed lesson changes a candidate policy; unreviewed stays inert (issue #68) ---
    def _weaver_with_tightening_lesson(self) -> LessonWeaverStub:
        weaver = LessonWeaverStub()
        weaver.add_failure(
            "F-refund-autoapprove",
            "a small refund auto-approved that an operator said should have required review",
            proposed_change=PolicyChange(
                "refund_auto_limit", 25.0, "the auto-approve limit was set too high"
            ),
        )
        return weaver

    def test_unreviewed_lesson_leaves_policy_inert(self):
        base = AgentFencePolicy()
        candidate = self._weaver_with_tightening_lesson().candidate_policy(base)
        # Inert until review: the candidate equals the base, so a $40 refund is still auto-allowed.
        self.assertEqual(candidate.refund_auto_limit, base.refund_auto_limit)
        self.assertEqual(
            candidate.evaluate("billing.issue_refund", "support_agent", {"amount": 40.0}).decision,
            "allow",
        )

    def test_reviewed_lesson_changes_candidate_policy(self):
        base = AgentFencePolicy()
        weaver = self._weaver_with_tightening_lesson()
        weaver.mark_reviewed("F-refund-autoapprove")
        candidate = weaver.candidate_policy(base)
        # The reviewed lesson tightens the auto-approve limit, so the same $40 refund now needs
        # approval -- and the base policy is never mutated (the change is a candidate).
        self.assertEqual(candidate.refund_auto_limit, 25.0)
        self.assertEqual(
            candidate.evaluate("billing.issue_refund", "support_agent", {"amount": 40.0}).decision,
            "ask",
        )
        self.assertEqual(base.refund_auto_limit, 50.0)

    def test_reviewed_lesson_without_a_proposed_change_does_not_alter_policy(self):
        base = AgentFencePolicy()
        weaver = LessonWeaverStub()
        weaver.add_failure("F-note-only", "a correction with no concrete policy change yet")
        weaver.mark_reviewed("F-note-only")
        self.assertIs(weaver.candidate_policy(base), base)

    def test_candidate_serializes_for_an_artifact(self):
        weaver = self._weaver_with_tightening_lesson()
        weaver.mark_reviewed("F-refund-autoapprove")
        as_dict = weaver.reviewed_lessons()[0].as_dict()
        self.assertTrue(as_dict["reviewed"])
        self.assertEqual(as_dict["proposed_change"]["field"], "refund_auto_limit")
        self.assertEqual(as_dict["proposed_change"]["new_value"], 25.0)


if __name__ == "__main__":
    unittest.main()
