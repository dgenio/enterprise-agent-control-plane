"""Safe Frame / context firewall for governed tool outputs (issues #22, #37).

Raw tool outputs (customer PII, invoice amounts, ticket free-text) must not flow straight
back into model-visible context. Instead each output is wrapped in a bounded :class:`Frame`
that carries a short summary, an opaque handle, the list of redacted sensitive fields, and a
risk band — while the raw payload is stored behind the handle in a :class:`FrameStore`.
Retrieving raw detail requires an explicit, gated :meth:`FrameStore.expand` call (governed in
``governed_agent.expand_frame``, issue #114).

Two properties:

* **Bounded exposure (issue #22).** A Frame inlines *no* raw values — only a value-free
  summary plus a handle. Sensitive fields named in the capability registry
  (``registry.sensitive_fields``) are listed as ``redacted_fields`` so an auditor sees what
  was withheld without seeing it.
* **Untrusted-by-default (issue #37).** Every Frame is marked ``untrusted=True``: tool output
  is data, never instructions. The marker travels with the output so a downstream reader can
  never mistake a planted directive in (e.g.) ticket text for a command.

This is an illustrative context firewall, not real PII protection — no encryption,
tokenization, or production redaction is claimed.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Frame:
    """A bounded view of one tool/flow output: summary + opaque handle, no raw values."""

    capability: str
    summary: str
    handle: str
    redacted_fields: list[str]
    risk: str
    # Tool output is data, not instructions (issue #37). Always True for tool-derived frames.
    untrusted: bool = True

    def as_dict(self) -> dict[str, Any]:
        """JSON-native, model-visible projection (carries no raw payload)."""
        return {
            "capability": self.capability,
            "summary": self.summary,
            "handle": self.handle,
            "redacted_fields": list(self.redacted_fields),
            "risk": self.risk,
            "untrusted": self.untrusted,
        }


def field_names(output: Any) -> list[str]:
    """Top-level field names of a dict output, or the union of keys across a list of dicts."""
    if isinstance(output, dict):
        return list(output.keys())
    if isinstance(output, list):
        keys: list[str] = []
        for item in output:
            if isinstance(item, dict):
                for key in item:
                    if key not in keys:
                        keys.append(key)
        return keys
    return []


class FrameStore:
    """In-memory handle -> raw payload store: raw detail lives here, never inline (issue #22)."""

    def __init__(self) -> None:
        self._raw: dict[str, Any] = {}

    def wrap(
        self,
        capability: str,
        output: Any,
        *,
        risk: str,
        sensitive_fields: "frozenset[str] | set[str]",
        untrusted: bool = True,
    ) -> Frame:
        """Wrap ``output`` as a bounded Frame, stashing the raw payload behind a handle.

        ``redacted_fields`` are the top-level fields present in ``output`` whose names are in
        ``sensitive_fields``. The summary names only the non-sensitive field names and counts;
        it never echoes a raw value, so nothing sensitive reaches model-visible context.
        """
        keys = field_names(output)
        redacted = [k for k in keys if k in sensitive_fields]
        # An opaque handle, unique per wrap. The store size is folded into the digest so two
        # steps that return identical payloads still get distinct handles -- this is
        # deliberately NOT a pure content address, so callers must not assume handle stability
        # across identical payloads (see test_identical_payloads_get_distinct_handles).
        seed = json.dumps({"capability": capability, "output": output, "n": len(self._raw)}, sort_keys=True, default=str)
        handle = "frame-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
        self._raw[handle] = output
        summary = self._summarize(capability, output, keys, redacted)
        return Frame(
            capability=capability,
            summary=summary,
            handle=handle,
            redacted_fields=sorted(redacted),
            risk=risk,
            untrusted=untrusted,
        )

    @staticmethod
    def _summarize(capability: str, output: Any, keys: list[str], redacted: list[str]) -> str:
        """A value-free, model-visible summary of an output (issue #22)."""
        visible = [k for k in keys if k not in redacted]
        if isinstance(output, list):
            shape = f"{len(output)} record(s)"
        elif isinstance(output, dict):
            shape = f"{len(keys)} field(s)"
        else:
            shape = "scalar value"
        detail = f"; visible fields: {visible}" if visible else ""
        redaction = f"; {len(redacted)} sensitive field(s) redacted ({sorted(redacted)})" if redacted else ""
        return f"{capability} returned {shape}{detail}{redaction}; raw detail behind handle."

    def has(self, handle: str) -> bool:
        return handle in self._raw

    def expand(self, handle: str) -> Any:
        """Return the raw payload behind ``handle``.

        This is the only path to raw detail. It is deliberately unguarded at this layer — the
        *governance* of expansion (principal check, policy decision, audit event) lives in
        ``governed_agent.expand_frame`` (issue #114), so this store stays a simple, inspectable
        handle map. Raises ``KeyError`` for an unknown handle.
        """
        return self._raw[handle]
