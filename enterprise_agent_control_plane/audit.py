import json
from dataclasses import dataclass, asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class AuditEvent:
    ts: str
    actor: str
    action: str
    outcome: str
    details: dict[str, Any]


class AuditTrace:
    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self.events: list[AuditEvent] = []

    def record(self, actor: str, action: str, outcome: str, details: dict[str, Any]) -> None:
        self.events.append(
            AuditEvent(
                ts=datetime.now(UTC).isoformat(),
                actor=actor,
                action=action,
                outcome=outcome,
                details=details,
            )
        )

    def as_dict(self) -> dict[str, Any]:
        return {"trace_id": self.trace_id, "events": [asdict(e) for e in self.events]}

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.as_dict(), indent=2), encoding="utf-8")
