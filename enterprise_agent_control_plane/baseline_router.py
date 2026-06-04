"""Deterministic, offline routing stand-in for the unsafe baseline agent.

A real first-pass agent would let an LLM pick the next tool from the full catalog on
every turn. To keep the demo reproducible and key-free, these functions stand in for
that model: given the request, the set of tools already called, and the *accumulated
raw tool output so far*, each returns the next capability to invoke (or ``None`` when
the loop should stop). The baseline loop re-invokes the router every step over the
*whole* catalog -- there is no bounded shortlist (issue #14).

The router receives the accumulated tool output on purpose: the unsafe baseline has no
provenance boundary between operator instructions and tool/customer data, so a naive
router can read fetched text as if it were a command (issue #31).

Several variants exist on purpose:

* ``route_v1`` / ``route_v2`` -- a heuristic tweak a team might "ship" without offline
  evaluation (issue #20): they differ only on the email path (send vs draft). The
  differing case lines up with ``evals/sample_routing_logs.csv`` so the eval lane
  (issue #7) can later score the change that was shipped blind.
* ``route_greedy`` -- an over-eager router that demonstrates poor tool selection under
  an undifferentiated nine-tool catalog (issue #30).
* ``route_injection_naive`` -- a router with no trust boundary that lets an injected
  directive in fetched tool data steer a write (issue #31).
"""

from typing import Any, Callable, Mapping, Sequence

# A router sees the request, the capabilities already called, and the accumulated raw
# tool output keyed by capability. ``context`` defaults to empty so simple variants and
# direct callers can ignore it.
Router = Callable[[str, Sequence[str], Mapping[str, Any]], "str | None"]


def route_v1(request: str, called: Sequence[str], context: "Mapping[str, Any] | None" = None) -> "str | None":
    """Baseline router v1: on the email path it sends a reply directly."""
    return _route(request, called, email_capability="email.send_reply")


def route_v2(request: str, called: Sequence[str], context: "Mapping[str, Any] | None" = None) -> "str | None":
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


def route_greedy(request: str, called: Sequence[str], context: "Mapping[str, Any] | None" = None) -> "str | None":
    """Over-eager baseline router demonstrating poor tool selection (issue #30).

    With no bounded shortlist, every one of the nine tools is equally present in
    context, so a plausible over-eager heuristic treats *any* billing-related request
    as a refund and reaches the high-risk ``billing.issue_refund`` even when the request
    only warranted a lookup. The cost of that mis-selection grows with catalog size; a
    bounded ChoiceCard shortlist (issue #24) would have excluded the wrong candidate.
    """
    text = request.lower()
    done = set(called)

    if "billing" in text or "invoice" in text or "charge" in text:
        if "crm.search_customer" not in done:
            return "crm.search_customer"
        if "billing.get_invoice" not in done:
            return "billing.get_invoice"
        # Over-reach: the request only asked to look into billing, but the undifferentiated
        # catalog lets the router escalate straight to the destructive refund.
        if "billing.issue_refund" not in done:
            return "billing.issue_refund"
        return None

    # Anything non-billing falls back to the ordinary v1 behaviour.
    return _route(text, called, email_capability="email.send_reply")


def _looks_like_refund_directive(context: "Mapping[str, Any]") -> bool:
    """Scan accumulated tool output for injected text that reads like a refund command.

    This is deliberately naive: it treats untrusted tool/customer data as if it could
    carry instructions, which is exactly the missing provenance boundary issue #31
    demonstrates. It only ever matches the obviously-``[FAKE]`` planted directive.
    """
    blob = repr(context).lower()
    return "issue a full refund" in blob or "issue a refund" in blob


def route_injection_naive(
    request: str, called: Sequence[str], context: "Mapping[str, Any] | None" = None
) -> "str | None":
    """Baseline router with no trust boundary between data and instructions (issue #31).

    For a benign read request (e.g. "review this customer's latest ticket"), it looks
    up the customer and their tickets -- then, because tool output and operator intent
    share one undifferentiated context, an injected ``[FAKE]`` directive planted in the
    fetched ticket data steers it into a ``billing.issue_refund`` the request never
    authorized. A safe Frame / context firewall (issue #22) would have quarantined the
    ticket text as data.
    """
    context = context or {}
    done = set(called)

    if "crm.search_customer" not in done:
        return "crm.search_customer"
    if "support.search_tickets" not in done:
        return "support.search_tickets"
    # No provenance boundary: act on instruction-like text found in fetched tool data.
    if _looks_like_refund_directive(context) and "billing.issue_refund" not in done:
        return "billing.issue_refund"
    return None
