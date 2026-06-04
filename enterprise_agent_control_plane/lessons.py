from dataclasses import dataclass, replace


@dataclass(frozen=True)
class LessonCandidate:
    failure_id: str
    summary: str
    reviewed: bool = False


class LessonWeaverStub:
    """lessonweaver-style reviewed lesson staging."""

    def __init__(self):
        self._candidates: list[LessonCandidate] = []

    def add_failure(self, failure_id: str, summary: str) -> None:
        self._candidates.append(LessonCandidate(failure_id=failure_id, summary=summary, reviewed=False))

    def mark_reviewed(self, failure_id: str) -> None:
        for i, item in enumerate(self._candidates):
            if item.failure_id == failure_id:
                self._candidates[i] = replace(item, reviewed=True)

    def reviewed_lessons(self) -> list[LessonCandidate]:
        return [x for x in self._candidates if x.reviewed]
