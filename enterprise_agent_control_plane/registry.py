"""Single capability registry — declare each capability once (issue #65).

The nine Customer Operations capabilities (plus the control-plane ``frame.expand``
capability, issue #114) used to be described in four places that had to agree by hand:
``catalog.build_catalog`` / ``catalog.build_tool_definitions`` (risk + description +
args schema), ``policies.ACTION_CLASSES`` (read/write/destructive), and each agent's
``self.tools`` callable map. A missed edit failed silently (deny-by-default) or unsafely
(``KeyError``).

This module makes a capability's metadata one authoritative :class:`CapabilitySpec`.
Everything else is *derived* from :data:`CAPABILITY_REGISTRY`:

* ``catalog.build_catalog`` / ``catalog.build_tool_definitions`` (model-visible card +
  full tool definition) — issue #65, #24.
* ``policies.ACTION_CLASSES`` (action-class classification) — issue #65.
* :func:`build_tool_map` (capability -> callable) for both agents — issue #65.
* ``frames.FrameStore`` reads :attr:`CapabilitySpec.sensitive_fields` to decide which
  fields a bounded Frame redacts — issue #22.

Adding a capability is a single edit here; ``tests/test_registry.py`` asserts the
derived views stay in parity.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from typing import Any

from pydantic import ValidationError, create_model

from . import fake_tools
from .errors import ErrorCode, error

ActionClass = str  # "read" | "write" | "destructive" -- mirrors policies.ActionClass

# args_schema type-string -> Python type, for schema-based validation (issues #4/#162).
_TYPE_MAP: dict[str, type] = {"str": str, "float": float, "int": int, "bool": bool}


@dataclass(frozen=True)
class CapabilitySpec:
    """The single, authoritative declaration of one capability (issue #65)."""

    capability: str
    risk: str  # "low" | "medium" | "high" -- model-visible ChoiceCard risk
    description: str
    action_class: ActionClass
    args_schema: dict[str, str] = field(default_factory=dict)
    # Constant values a deterministic flow step supplies for args the case payload does not
    # carry (issue #149). e.g. the refund flow searches the "refund" policy and drafts a
    # "refund review" topic -- these are step invocation defaults, not case inputs, so an
    # arg named here is NOT a required payload field for validation (issues #4/#162).
    step_defaults: dict[str, Any] = field(default_factory=dict)
    # The bound tool callable, or ``None`` for a control-plane-only capability that has no
    # enterprise tool behind it (e.g. ``frame.expand``, which the agent mediates directly).
    tool: Callable[..., Any] | None = None
    # Output field names a bounded Frame treats as sensitive and redacts (issue #22). Only
    # meaningful for capabilities that return such fields; empty for the rest.
    sensitive_fields: frozenset[str] = frozenset()
    # Whether this capability is part of the model-facing tool catalog (the customer-ops tool
    # surface). Control-plane capabilities like ``frame.expand`` are governed and audited but
    # never offered to the model as a pickable tool, so they stay out of the catalog/shortlist.
    in_tool_catalog: bool = True


# One declaration per capability. Order matters: the catalog/tool-definition views preserve
# this order, and the baseline's full-catalog context-size figure (issue #15) is computed from
# it -- keep the nine tool capabilities first and in their established order.
CAPABILITY_REGISTRY: dict[str, CapabilitySpec] = {
    "crm.search_customer": CapabilitySpec(
        capability="crm.search_customer",
        risk="low",
        description="Find customer profile and account status.",
        action_class="read",
        args_schema={"customer_id": "str"},
        tool=fake_tools.crm_search_customer,
        sensitive_fields=frozenset(
            {"email", "phone", "internal_notes", "risk_flags", "payment_method", "account_history"}
        ),
    ),
    "billing.get_invoice": CapabilitySpec(
        capability="billing.get_invoice",
        risk="low",
        description="Read invoice details.",
        action_class="read",
        args_schema={"invoice_id": "str"},
        tool=fake_tools.billing_get_invoice,
        sensitive_fields=frozenset(
            {"payment_method", "billing_address", "internal_margin", "fraud_score"}
        ),
    ),
    "billing.issue_refund": CapabilitySpec(
        capability="billing.issue_refund",
        risk="high",
        description="Issue a monetary refund to a customer.",
        action_class="destructive",
        args_schema={"invoice_id": "str", "amount": "float", "reason": "str"},
        tool=fake_tools.billing_issue_refund,
    ),
    "support.search_tickets": CapabilitySpec(
        capability="support.search_tickets",
        risk="low",
        description="Find support history.",
        action_class="read",
        args_schema={"customer_id": "str"},
        tool=fake_tools.support_search_tickets,
        # Ticket free-text is untrusted data that may carry injected directives (issue #37);
        # the bounded Frame redacts it so it cannot be read back as an instruction.
        sensitive_fields=frozenset({"agent_comments", "internal_priority"}),
    ),
    "support.create_task": CapabilitySpec(
        capability="support.create_task",
        risk="medium",
        description="Create follow-up tasks for operations.",
        action_class="write",
        args_schema={"customer_id": "str", "note": "str"},
        tool=fake_tools.support_create_task,
    ),
    "email.draft_reply": CapabilitySpec(
        capability="email.draft_reply",
        risk="low",
        description="Draft customer-facing response text.",
        action_class="read",  # composes text only; no external side effect
        args_schema={"customer_name": "str", "topic": "str"},
        step_defaults={"topic": "refund review"},
        tool=fake_tools.email_draft_reply,
    ),
    "email.send_reply": CapabilitySpec(
        capability="email.send_reply",
        risk="high",
        description="Send customer-facing response.",
        action_class="write",
        args_schema={"to": "str", "subject": "str", "body": "str"},
        tool=fake_tools.email_send_reply,
    ),
    "docs.search_policy": CapabilitySpec(
        capability="docs.search_policy",
        risk="low",
        description="Find internal policy references.",
        action_class="read",
        args_schema={"query": "str"},
        step_defaults={"query": "refund"},
        tool=fake_tools.docs_search_policy,
    ),
    "audit.export_case": CapabilitySpec(
        capability="audit.export_case",
        risk="medium",
        description="Export case evidence for review.",
        action_class="read",  # read/export only, but principal-restricted in policies
        args_schema={"case_id": "str"},
        tool=fake_tools.audit_export_case,
    ),
    # Control-plane capability: revealing a Frame's redacted raw detail is itself a gated,
    # audited action (issue #114). It has no enterprise tool and is never offered to the model
    # as a pickable catalog entry, so ``in_tool_catalog=False``.
    "frame.expand": CapabilitySpec(
        capability="frame.expand",
        risk="high",
        description="Reveal a Frame's redacted raw detail (principal-restricted, audited).",
        action_class="read",
        args_schema={"handle": "str"},
        tool=None,
        in_tool_catalog=False,
    ),
}


def tool_capabilities() -> list[CapabilitySpec]:
    """The model-facing tool capabilities, in registry order (issue #65)."""
    return [spec for spec in CAPABILITY_REGISTRY.values() if spec.in_tool_catalog]


def build_tool_map() -> dict[str, Callable[..., Any]]:
    """Capability -> bound callable, derived from the registry (issue #65).

    The single map both agents use, so no agent hand-maintains its own tool dict. Only
    capabilities with a bound tool are included (``frame.expand`` is mediated by the agent).
    """
    return {
        spec.capability: spec.tool for spec in CAPABILITY_REGISTRY.values() if spec.tool is not None
    }


def sensitive_fields(capability: str) -> frozenset[str]:
    """The fields a bounded Frame redacts for ``capability`` (issue #22), or empty."""
    spec = CAPABILITY_REGISTRY.get(capability)
    return spec.sensitive_fields if spec is not None else frozenset()


def risk_of(capability: str) -> str:
    """The declared risk band for ``capability`` (defaults to ``unknown``)."""
    spec = CAPABILITY_REGISTRY.get(capability)
    return spec.risk if spec is not None else "unknown"


# --- Registry-driven step invocation and validation (issues #149, #4/#162) ----
# A single binder derives a flow step's call from the registry, replacing the hand-maintained
# per-capability ``if/elif`` dispatcher the executor used to carry (and its unreachable
# ``support.create_task`` branch, issue #165). Both the binder and the validator read the same
# ``args_schema`` / ``step_defaults``, so the invocation contract lives in one place.


def required_step_inputs(capability: str) -> list[str]:
    """The payload fields a flow step needs the case to supply (issues #4/#162).

    Every ``args_schema`` field except those the step fills from ``step_defaults`` -- i.e. the
    case inputs a caller must provide, in schema order.
    """
    spec = CAPABILITY_REGISTRY[capability]
    return [name for name in spec.args_schema if name not in spec.step_defaults]


@cache
def _step_input_model(capability: str) -> type:
    """A pydantic model over a step's required, typed inputs (issues #4/#162, cached)."""
    spec = CAPABILITY_REGISTRY[capability]
    fields: dict[str, Any] = {
        name: (_TYPE_MAP.get(spec.args_schema[name], object), ...)
        for name in required_step_inputs(capability)
    }
    model_name = capability.replace(".", "_") + "_StepInput"
    return create_model(model_name, **fields)


def validate_step_input(capability: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Validate a step's inputs before it runs; ``None`` if valid, else a structured error.

    Replaces the executor's bare ``payload["customer_id"]`` access (which raised an unhandled
    ``KeyError`` on bad input) with a declared, typed contract derived from the registry
    (issues #4/#162). A missing or wrong-typed required field yields an ``invalid_input``
    error (issue #174) the executor fails closed on, rather than an opaque exception.
    """
    model = _step_input_model(capability)
    required = required_step_inputs(capability)
    subset = {name: payload[name] for name in required if name in payload}
    try:
        model(**subset)
    except ValidationError as exc:
        fields = sorted({str(err["loc"][0]) for err in exc.errors() if err.get("loc")})
        return error(
            ErrorCode.INVALID_INPUT,
            capability=capability,
            detail=f"invalid or missing inputs for {capability}: {fields}",
            fields=fields,
        )
    return None


def bind_step_args(capability: str, payload: dict[str, Any]) -> list[Any]:
    """Build a flow step's positional tool arguments from the registry (issue #149).

    Each ``args_schema`` field is taken from the payload, or from ``step_defaults`` when the
    payload does not carry it. Call :func:`validate_step_input` first: it guarantees every
    required field is present, so this never raises the ``KeyError`` the old dispatcher could.
    """
    spec = CAPABILITY_REGISTRY[capability]
    return [
        payload[name] if name in payload else spec.step_defaults[name] for name in spec.args_schema
    ]
