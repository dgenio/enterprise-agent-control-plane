"""lessonweaver-style reviewed-lesson staging (issues #6, #68).

A failed or corrected run can produce a *candidate lesson*: a short summary plus, optionally,
a proposed change to policy. The whole point of the lane is the review gate -- a candidate
only changes future agent behavior **after a human reviews it**; unreviewed candidates stay
inert. This module models that lifecycle as plain, offline data so the demo and tests can
exercise it without any external service.

The contrast it demonstrates:

* :meth:`LessonWeaverStub.reviewed_lessons` returns only reviewed candidates (issue #6).
* :meth:`LessonWeaverStub.candidate_policy` applies the proposed change of *reviewed* lessons
  to a base :class:`~enterprise_agent_control_plane.policies.AgentFencePolicy`, while an
  unreviewed lesson leaves the policy unchanged (issue #68).
"""

from dataclasses import dataclass, replace
from typing import Any, Optional

from .policies import AgentFencePolicy

# Policy threshold fields a lesson may propose tightening. Kept explicit so a malformed or
# unknown field on a candidate cannot silently reshape an unrelated part of the policy.
_TUNABLE_THRESHOLDS = ("refund_auto_limit", "refund_manager_limit")


@dataclass(frozen=True)
class PolicyChange:
    """A proposed, reviewable change to one policy threshold, derived from a failure.

    ``field`` names the :class:`AgentFencePolicy` threshold to change (one of
    ``refund_auto_limit`` / ``refund_manager_limit``); ``new_value`` is the proposed value;
    ``rationale`` records why the correction suggests it.
    """

    field: str
    new_value: float
    rationale: str

    def as_dict(self) -> dict[str, Any]:
        return {"field": self.field, "new_value": self.new_value, "rationale": self.rationale}


@dataclass(frozen=True)
class LessonCandidate:
    """One candidate lesson mined from a failed/corrected run (issues #6, #68)."""

    failure_id: str
    summary: str
    reviewed: bool = False
    proposed_change: Optional[PolicyChange] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "failure_id": self.failure_id,
            "summary": self.summary,
            "reviewed": self.reviewed,
            "proposed_change": self.proposed_change.as_dict() if self.proposed_change else None,
        }


class LessonWeaverStub:
    """lessonweaver-style reviewed lesson staging."""

    def __init__(self):
        self._candidates: list[LessonCandidate] = []

    def add_failure(
        self,
        failure_id: str,
        summary: str,
        proposed_change: Optional[PolicyChange] = None,
    ) -> None:
        self._candidates.append(
            LessonCandidate(
                failure_id=failure_id,
                summary=summary,
                reviewed=False,
                proposed_change=proposed_change,
            )
        )

    def mark_reviewed(self, failure_id: str) -> None:
        for i, item in enumerate(self._candidates):
            if item.failure_id == failure_id:
                self._candidates[i] = replace(item, reviewed=True)

    def candidates(self) -> list[LessonCandidate]:
        """All staged candidates, reviewed or not."""
        return list(self._candidates)

    def reviewed_lessons(self) -> list[LessonCandidate]:
        return [x for x in self._candidates if x.reviewed]

    def candidate_policy(self, base: AgentFencePolicy) -> AgentFencePolicy:
        """Apply *reviewed* lessons' proposed changes to ``base``, returning a new policy (#68).

        Only reviewed candidates with a proposed change take effect; an unreviewed candidate
        is inert and the returned policy equals ``base``. When several reviewed lessons touch
        the same threshold, the later one wins (last review applied). The base policy is never
        mutated -- a fresh :class:`AgentFencePolicy` is returned so the change is a *candidate*
        the caller can compare against the current policy.
        """
        overrides: dict[str, float] = {}
        for lesson in self.reviewed_lessons():
            change = lesson.proposed_change
            if change is not None and change.field in _TUNABLE_THRESHOLDS:
                overrides[change.field] = change.new_value
        if not overrides:
            return base
        return AgentFencePolicy(
            refund_auto_limit=overrides.get("refund_auto_limit", base.refund_auto_limit),
            refund_manager_limit=overrides.get("refund_manager_limit", base.refund_manager_limit),
        )
