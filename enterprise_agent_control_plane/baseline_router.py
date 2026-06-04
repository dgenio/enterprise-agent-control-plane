"""Deterministic, offline routing stand-in for the unsafe baseline agent.

A real first-pass agent would let an LLM pick the next tool from the full catalog on
every turn. To keep the demo reproducible and key-free, these functions stand in for
that model: given the request and the set of tools already called, each returns the
next capability to invoke (or ``None`` when the loop should stop). The baseline loop
re-invokes the router every step over the *whole* catalog -- there is no bounded
shortlist (issue #14).

Two variants exist on purpose. ``route_v2`` is a heuristic tweak a team might "ship"
without any offline evaluation (issue #20): it differs from ``route_v1`` only on the
email path -- drafting a reply instead of sending one directly. The differing case
lines up with ``evals/sample_routing_logs.csv`` so the eval lane (issue #7) can later
score the change that was shipped blind.
"""

from typing import Callable, Sequence

Router = Callable[[str, Sequence[str]], "str | None"]


def route_v1(request: str, called: Sequence[str]) -> "str | None":
    """Baseline router v1: on the email path it sends a reply directly."""
    return _route(request, called, email_capability="email.send_reply")


def route_v2(request: str, called: Sequence[str]) -> "str | None":
    """Baseline router v2: same as v1 but drafts the email instead of sending it.

    Shipped on intuition with no offline comparison against v1 (issue #20).
    """
    return _route(request, called, email_capability="email.draft_reply")


def _route(request: str, called: Sequence[str], *, email_capability: str) -> "str | None":
    text = request.lower()
    done = set(called)

    if "refund" in text:
        if "crm.search_customer" not in done:
            return "crm.search_customer"
        if "billing.get_invoice" not in done:
            return "billing.get_invoice"
        if "billing.issue_refund" not in done:
            return "billing.issue_refund"
        return None

    if "escalate" in text or "ticket" in text:
        if "support.search_tickets" not in done:
            return "support.search_tickets"
        if "support.create_task" not in done:
            return "support.create_task"
        return None

    if "email" in text or "reply" in text or "send" in text:
        if "crm.search_customer" not in done:
            return "crm.search_customer"
        if email_capability not in done:
            return email_capability
        return None

    return None
