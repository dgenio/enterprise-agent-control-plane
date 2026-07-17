"""Structured error taxonomy for governed failures (issue #174).

Before this module, a governed failure was a bare ``{"error": "..."}`` string literal
repeated across :mod:`flows`, :mod:`governed_agent`, and :mod:`baseline_agent` (plus the
synthetic tools' ``not_found``). A typo produced a silent mismatch -- a consumer branching
on ``out.get("error") == "out_of_budget"`` would simply never fire -- and the set of
failures a step could emit was undiscoverable without grepping. This module names each one
once so producers and consumers share a single vocabulary.

The wire values are deliberately unchanged from the pre-taxonomy literals, so emitted audit
traces stay byte-for-byte comparable and any external reader keying on the old strings keeps
working. :class:`ErrorCode` subclasses ``str`` for the same reason: a member compares and
serialises exactly like its string value.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    """The ``{"error": <code>}`` values a governed step or synthetic tool can emit (#174).

    Subclassing ``str`` means ``ErrorCode.OUT_OF_BUDGET == "out_of_budget"`` and
    ``json.dumps`` renders the plain value, so nothing downstream has to know the enum
    exists to keep working.
    """

    # A step needs a capability outside the case capability budget; the flow fails closed
    # here rather than reaching beyond the bounded budget (issue #110).
    OUT_OF_BUDGET = "out_of_budget"
    # A tool raised; the executor converts any exception into a structured failure (issue #41).
    EXCEPTION = "exception"
    # The deterministic executor has no binding for the step's capability.
    UNKNOWN_STEP = "unknown_step"
    # The governed write invoker has no binding for the gated capability (issue #38).
    UNKNOWN_WRITE = "unknown_write"
    # The baseline dispatcher has no binding for the capability.
    UNKNOWN_CAPABILITY = "unknown_capability"
    # A synthetic enterprise tool has no record for the requested id.
    NOT_FOUND = "not_found"
    # A step's input failed schema validation before the tool ran (issues #4/#162).
    INVALID_INPUT = "invalid_input"


def error(code: ErrorCode, **detail: Any) -> dict[str, Any]:
    """Build a structured error payload ``{"error": <code>, **detail}`` (issue #174).

    The ``error`` value is stored as the plain wire string (``code.value``) so a serialized
    payload is identical to the literal it replaces.
    """
    return {"error": code.value, **detail}


def is_error(output: Any, code: ErrorCode | None = None) -> bool:
    """True if ``output`` is a structured error payload (optionally of a specific code).

    ``code=None`` matches any error -- the general "did this step fail?" check the executor
    uses; a specific code answers "did it fail *this* way?" (e.g. out-of-budget vs a tool
    error) without a bare string compare at the call site.
    """
    if not isinstance(output, dict) or "error" not in output:
        return False
    return code is None or output["error"] == code.value


class StepStatus(str, Enum):
    """The lifecycle status a flow-step record carries (issue #174).

    A distinct vocabulary from :class:`ErrorCode`: a status describes what happened to the
    *step* (ran, failed, was skipped for want of a token), independent of the specific error
    a failed step's output holds. Values are unchanged from the prior string literals.
    """

    OK = "ok"
    FAILED = "failed"
    BLOCKED_NO_TOKEN = "blocked_no_token"
