"""Governed audit trace: a schema-validated, tamper-evident record of a run.

The audit trace is the governed path's primary evidence artifact. Three properties make
it usable as evidence rather than a free-text log:

* **Schema (issue #112).** Events draw their ``action`` from an enumerated
  :data:`ACTION_VOCABULARY`, and each action declares the ``details`` fields it must
  carry. :func:`validate_trace` confirms every event is well-formed and that a completed
  governed run emitted the mandatory events, so an incomplete or malformed trace is
  *detectable* instead of silently accepted.
* **Tamper-evidence (issue #39).** Each event carries a SHA-256 hash over its own content
  plus the previous event's hash, forming an append-only chain. :func:`verify_event_chain`
  (and :meth:`AuditTrace.verify`) recompute the chain and report whether a saved trace was
  altered after the fact. This is a *reference pattern*, not production-grade tamper-proofing
  -- no signatures, key management, or non-repudiation are claimed.
* **Provenance (issue #70).** The governed path stamps each ``policy.decision`` event with
  the deciding policy's version and thresholds; see ``policies.AgentFencePolicy.provenance``.
"""

import copy
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Optional

# Genesis seed for the hash chain: the first event links to this fixed, all-zero hash so
# the chain has an explicit, recomputable starting point (issue #39).
GENESIS_HASH = "0" * 64

# Enumerated governed action vocabulary and the ``details`` keys each action must carry
# (issue #112). Anything outside this map is an unknown action; anything missing its keys
# is malformed -- both are reported by :func:`validate_trace`.
ACTION_VOCABULARY: dict[str, set[str]] = {
    "request.received": {"request", "intent", "principal"},
    "shortlist": {"capabilities", "reason"},
    "flow.select": {"intent", "reason"},
    "flow.execute": {"flow_id", "steps"},
    "flow.step": {"step", "capability", "token_valid", "result_ref"},
    # A flow that halts fail-closed on a failed step (issue #41).
    "flow.halt": {"step", "capability", "reason"},
    "policy.decision": {
        "capability",
        "principal",
        "decision",
        "outcome",
        "reason",
        "token_valid",
        "policy_version",
        "policy_thresholds",
    },
    "approval.request": {"capability", "reason"},
    # The resolution records who approved/rejected and the basis for their authority so the
    # trace answers separation-of-duties questions (issue #64).
    "approval.resolved": {"capability", "approver"},
    # A gated write's side-effect outcome: committed, withheld as a dry-run, or recognized as
    # an idempotent replay (issues #38 / #113).
    "action.commit": {"capability", "mode"},
    # A bounded Frame wrapping one flow step's output: summary + opaque handle, with raw detail
    # redacted behind the handle (issues #22 / #37). The handle and redacted-field list make
    # the context-firewall boundary auditable without recording the raw payload.
    "flow.frame": {"capability", "handle", "redacted_fields"},
    # A governed, audited expansion of a Frame's redacted raw detail (issue #114): records the
    # handle and the principal-checked outcome so the trace answers "who revealed what, when".
    "frame.expand": {"handle", "outcome"},
    "output.frame": {"request", "intent", "flow", "status"},
}

# The events a completed, flow-matched governed run must emit, in no particular order
# (issue #112). A run that does not match a flow emits the smaller no-match set instead, so
# completeness is only asserted when the caller knows a flow ran.
REQUIRED_GOVERNED_ACTIONS: tuple[str, ...] = (
    "request.received",
    "shortlist",
    "flow.select",
    "flow.execute",
    "policy.decision",
    "output.frame",
)


@dataclass
class AuditEvent:
    ts: str
    actor: str
    action: str
    outcome: str
    details: dict[str, Any]
    # Hash-chain fields (issue #39); ``record`` always populates them.
    prev_hash: str = GENESIS_HASH
    hash: str = ""


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)


def _event_hash(ts: str, actor: str, action: str, outcome: str, details: dict[str, Any], prev_hash: str) -> str:
    """SHA-256 over a canonical JSON of the event content plus the previous hash.

    ``sort_keys`` makes the digest independent of dict ordering, so an event hashes the
    same when recorded and when recomputed from a reloaded trace. ``default=str`` is a
    safety net for any non-JSON-native value; trace details are normally JSON-native.
    """
    canonical = json.dumps(
        {
            "ts": ts,
            "actor": actor,
            "action": action,
            "outcome": outcome,
            "details": details,
            "prev_hash": prev_hash,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AuditTrace:
    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self.events: list[AuditEvent] = []

    def record(self, actor: str, action: str, outcome: str, details: dict[str, Any]) -> None:
        # ``details`` must be JSON-native (str/int/float/bool/None/list/dict): the hash chain
        # and :meth:`save` both serialize it with :func:`json.dumps`, so a non-JSON-native
        # value would either hash via its ``str()`` fallback or fail to save -- keep the
        # recorded evidence and what is persisted/verified identical.
        prev_hash = self.events[-1].hash if self.events else GENESIS_HASH
        ts = datetime.now(UTC).isoformat()
        # Store an independent copy so later mutation of the caller's dict -- e.g. the
        # ``output.frame`` details, which run_case also returns as ``bounded_output`` --
        # cannot silently alter recorded evidence or invalidate the hash chain.
        details = copy.deepcopy(details)
        self.events.append(
            AuditEvent(
                ts=ts,
                actor=actor,
                action=action,
                outcome=outcome,
                details=details,
                prev_hash=prev_hash,
                hash=_event_hash(ts, actor, action, outcome, details, prev_hash),
            )
        )

    def as_dict(self) -> dict[str, Any]:
        return {"trace_id": self.trace_id, "events": [asdict(e) for e in self.events]}

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.as_dict(), indent=2), encoding="utf-8")

    def verify(self) -> bool:
        """True if this trace's hash chain is internally consistent (issue #39)."""
        return verify_event_chain(self.as_dict()["events"])

    def validate(self, require_complete: bool = False) -> ValidationResult:
        """Validate this trace against the event schema (issue #112)."""
        required = REQUIRED_GOVERNED_ACTIONS if require_complete else None
        return validate_trace(self.as_dict()["events"], required_actions=required)


def verify_event_chain(events: Iterable[dict[str, Any]]) -> bool:
    """Recompute the hash chain over serialized events and report pass/fail (issue #39).

    Each event must link to the previous event's hash (the genesis hash for the first) and
    its stored hash must match a recomputation over its content. A single edited, removed,
    or reordered event breaks the chain. A malformed event (missing fields) fails
    verification rather than raising, so a corrupted trace is reported, not crashed on.
    """
    prev_hash = GENESIS_HASH
    for event in events:
        if event.get("prev_hash") != prev_hash:
            return False
        expected = _event_hash(
            event.get("ts"),
            event.get("actor"),
            event.get("action"),
            event.get("outcome"),
            event.get("details"),
            prev_hash,
        )
        if event.get("hash") != expected:
            return False
        prev_hash = event.get("hash")
    return True


def validate_trace(
    events: Iterable[dict[str, Any]],
    required_actions: Optional[Iterable[str]] = None,
) -> ValidationResult:
    """Validate serialized events against the schema (issue #112).

    Reports an unknown ``action``, any missing required ``details`` field, and -- when
    ``required_actions`` is given -- any mandatory event a completed run failed to emit.
    Dependency-free and offline.
    """
    errors: list[str] = []
    seen: set[str] = set()
    for index, event in enumerate(events):
        action = event.get("action")
        seen.add(action)
        required_fields = ACTION_VOCABULARY.get(action)
        if required_fields is None:
            errors.append(f"event[{index}]: unknown action {action!r}")
            continue
        details = event.get("details")
        if not isinstance(details, dict):
            errors.append(f"event[{index}] ({action}): details must be an object")
            continue
        missing = sorted(required_fields - details.keys())
        if missing:
            errors.append(f"event[{index}] ({action}): missing required detail(s) {missing}")
    if required_actions is not None:
        for action in required_actions:
            if action not in seen:
                errors.append(f"trace is incomplete: missing mandatory event {action!r}")
    return ValidationResult(ok=not errors, errors=errors)
