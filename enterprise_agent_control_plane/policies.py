import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, cast

from .config import load_agentfence_policy, load_capability_policy
from .registry import CAPABILITY_REGISTRY

Decision = Literal["allow", "deny", "ask"]
ActionClass = Literal["read", "write", "destructive"]


# The AgentFence policy rules are loaded from YAML as the single source of truth (issue #3).
_AF_POLICY = load_agentfence_policy()


# --- Action classes (issue #2) ------------------------------------------------
# Every governed capability is classified by the kind of side effect it can have. Derived from
# the single capability registry (issue #65) so the classification can never drift from the
# catalog or tool bindings -- the registry, NOT the policy YAML, is authoritative for this
# assignment (see AGENTS.md and tests/test_yaml_parity.py). Anything not in the registry is
# unknown and denied by default (deny-by-default) -- see ``AgentFencePolicy.evaluate``.
ACTION_CLASSES: dict[str, ActionClass] = {
    cap: cast(ActionClass, spec.action_class) for cap, spec in CAPABILITY_REGISTRY.items()
}

# How each action class is decided, from the policy YAML (issue #3): e.g. read -> allow,
# write -> ask, destructive -> threshold. The mapping is data; the threshold *logic* stays in
# ``evaluate`` (no evaluated rule language -- that is the separate big-swing issue #182).
ACTION_CLASS_DECISIONS: dict[str, str] = dict(_AF_POLICY["action_classes"])

# Capabilities only specific principals may ever invoke, regardless of action class, from the
# policy YAML (issue #3). audit.export_case exposes case evidence; frame.expand reveals a
# Frame's redacted raw detail (issue #114) -- both are restricted to principals authorized to
# see sensitive material.
PRINCIPAL_RESTRICTED: dict[str, set[str]] = {
    cap: set(principals) for cap, principals in (_AF_POLICY.get("restricted") or {}).items()
}

# Parameter-aware thresholds for destructive money movement (issue #36), from the policy YAML
# (issue #3). An amount at or below the auto limit is allowed outright; at or below the manager
# limit it requires approval; anything larger is denied.
_REFUND_THRESHOLDS = _AF_POLICY["thresholds"]["billing.issue_refund"]
REFUND_AUTO_LIMIT = float(_REFUND_THRESHOLDS["refund_auto_limit"])
REFUND_MANAGER_LIMIT = float(_REFUND_THRESHOLDS["refund_manager_limit"])


@dataclass(frozen=True)
class PolicyDecision:
    decision: Decision
    reason: str
    action_class: ActionClass | None = None


class AgentFencePolicy:
    """AgentFence-style local policy gate.

    Decisions derive from the capability's action class (issue #2) plus, for
    parameter-sensitive actions, the call arguments (issue #36), with a
    deny-by-default posture for any capability the policy does not recognise.
    """

    def __init__(
        self,
        refund_auto_limit: float = REFUND_AUTO_LIMIT,
        refund_manager_limit: float = REFUND_MANAGER_LIMIT,
    ):
        self.refund_auto_limit = refund_auto_limit
        self.refund_manager_limit = refund_manager_limit

    # --- Decision provenance (issue #70) --------------------------------------
    def thresholds(self) -> dict[str, float]:
        """The effective threshold values that shape parameter-aware decisions."""
        return {
            "refund_auto_limit": self.refund_auto_limit,
            "refund_manager_limit": self.refund_manager_limit,
        }

    @property
    def version(self) -> str:
        """A stable identifier derived from the ruleset and threshold content (issue #70).

        Hashing the static rules (action classes, principal restrictions) together with the
        instance thresholds means the version changes whenever the policy that produced a
        decision changes -- so two traces are comparable and a trace is replayable against a
        named policy version. This is reference provenance, not signing.
        """
        payload = json.dumps(
            {
                "action_classes": ACTION_CLASSES,
                "action_class_decisions": ACTION_CLASS_DECISIONS,
                "principal_restricted": {k: sorted(v) for k, v in PRINCIPAL_RESTRICTED.items()},
                "thresholds": self.thresholds(),
            },
            sort_keys=True,
        )
        return "af-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]

    def provenance(self) -> dict[str, Any]:
        """The provenance stamp recorded alongside each policy decision (issue #70)."""
        return {"policy_version": self.version, "thresholds": self.thresholds()}

    def evaluate(
        self,
        capability: str,
        principal: str,
        args: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        args = args or {}
        action_class = ACTION_CLASSES.get(capability)
        if action_class is None:
            # Deny-by-default: an unrecognised capability is never allowed (issue #2).
            return PolicyDecision("deny", f"Unknown capability {capability!r} denied by default.")

        allowed_principals = PRINCIPAL_RESTRICTED.get(capability)
        if allowed_principals is not None and principal not in allowed_principals:
            return PolicyDecision(
                "deny",
                f"{capability} is restricted to {sorted(allowed_principals)}; {principal} is not permitted.",
                action_class,
            )

        # The decision for this action class comes from the policy YAML (issue #3): read is
        # allowed, write asks for approval, destructive is threshold-evaluated below.
        rule = ACTION_CLASS_DECISIONS.get(action_class)
        if rule == "allow":
            return PolicyDecision(
                "allow", f"{capability} is a {action_class} action; allowed.", action_class
            )

        if rule == "ask":
            return PolicyDecision(
                "ask", f"{capability} is a {action_class} action; requires approval.", action_class
            )

        if rule != "threshold":
            # Deny-by-default: a known action class with no recognised decision rule is never
            # allowed (defends against a YAML that classifies an action class it cannot decide).
            return PolicyDecision(
                "deny",
                f"{capability} action class {action_class!r} has no decision rule; denied by default.",
                action_class,
            )

        # threshold: parameter-aware thresholds for destructive money movement (issue #36)
        amount = args.get("amount")
        if amount is None:
            return PolicyDecision(
                "ask",
                f"{capability} is destructive and no amount was supplied; requires approval.",
                action_class,
            )
        if amount <= self.refund_auto_limit:
            return PolicyDecision(
                "allow",
                f"{capability} amount {amount} is at or below the auto-approve limit "
                f"{self.refund_auto_limit}; allowed.",
                action_class,
            )
        if amount <= self.refund_manager_limit:
            return PolicyDecision(
                "ask",
                f"{capability} amount {amount} exceeds the auto-approve limit {self.refund_auto_limit} "
                f"but is within the manager limit {self.refund_manager_limit}; requires approval.",
                action_class,
            )
        return PolicyDecision(
            "deny",
            f"{capability} amount {amount} exceeds the manager limit {self.refund_manager_limit}; denied.",
            action_class,
        )


# --- Principals and scoped capability tokens (issue #23) ----------------------
@dataclass(frozen=True)
class CapabilityToken:
    """A scoped grant that a principal holds for a single capability.

    The token carries minimal governance metadata (scope, issuer, optional expiry)
    so that "who may do what" is explicit and auditable, rather than a bare string
    comparison. ``expires=None`` means non-expiring (the demo default).
    """

    principal: str
    capability: str
    scope: str = "customer-operations"
    issuer: str = "control-plane"
    expires: datetime | None = None

    def is_valid(
        self, capability: str, now: datetime | None = None, scope: str | None = None
    ) -> bool:
        if self.capability != capability:
            return False
        # When a scope is supplied, the token must have been minted for it (the case/trace id),
        # so a case-scoped token (issue #63) cannot be replayed in another context. ``scope=None``
        # skips the check, so non-expiring standing grants (issue #23) still validate.
        if scope is not None and self.scope != scope:
            return False
        if self.expires is None:
            return True
        now = now or datetime.now(timezone.utc)
        return now < self.expires


# Role -> capabilities each principal is granted scoped tokens for (issue #23), loaded from
# policies/capability_policy.yaml as the single source of truth (issue #3).
ROLE_GRANTS: dict[str, set[str]] = {
    principal: set(cfg.get("grants") or [])
    for principal, cfg in (load_capability_policy().get("principals") or {}).items()
}


# --- Approver authority for 'ask' decisions / separation of duties (issue #64) -----
# Which principals may approve which action classes. Approval of money movement or outbound
# messages must come from an authorized second party (not the requester), so the requesting
# support_agent cannot approve their own refund. Read actions are never gated to 'ask', so
# they never reach an approver.
APPROVER_AUTHORITY: dict[str, set[ActionClass]] = {
    "support_manager": {"write", "destructive"},
    "supervisor": {"write", "destructive"},
}


def may_approve(approver_principal: str, action_class: ActionClass | None) -> bool:
    """True if ``approver_principal`` is authorized to approve the given action class (#64)."""
    if action_class is None:
        return False
    return action_class in APPROVER_AUTHORITY.get(approver_principal, set())


def issue_tokens(principal: str, expires: datetime | None = None) -> list[CapabilityToken]:
    """Mint the *standing* capability tokens a principal's role grants (issue #23).

    Every capability the role allows, on every invocation, non-expiring by default. This is
    the "this role *could* do X" grant; :func:`issue_case_tokens` is the least-privilege,
    just-in-time contrast (issue #63).
    """
    grants = ROLE_GRANTS.get(principal, set())
    return [
        CapabilityToken(principal=principal, capability=cap, expires=expires)
        for cap in sorted(grants)
    ]


# --- Just-in-time, case-scoped token issuance (issue #63) ---------------------
# Standing role grants say "this principal *could* do X". A case-scoped grant says "this
# case was granted exactly the tokens its flow plus gated action need, valid for this trace,
# and they expire afterwards." Least privilege is applied twice: the role bounds what *can*
# be minted, and the case's needed-capability set bounds what *is* minted for this run.
CASE_TOKEN_TTL_SECONDS = 300


def issue_case_tokens(
    principal: str,
    capabilities: Iterable[str],
    scope: str,
    expires: datetime | None = None,
    ttl_seconds: int = CASE_TOKEN_TTL_SECONDS,
    now: datetime | None = None,
) -> list[CapabilityToken]:
    """Mint just-in-time, case-scoped tokens for a single run (issue #63).

    Only capabilities that the case actually needs *and* the principal's role grants are
    minted (role intersect needed), each carrying ``scope`` (the case/trace id) and a short
    expiry so the grant does not outlive the case. A capability the role grants but the case
    did not request is therefore never minted -- the contrast with :func:`issue_tokens`,
    which mints every standing role grant with no expiry.
    """
    granted = ROLE_GRANTS.get(principal, set())
    if expires is None:
        now = now or datetime.now(timezone.utc)
        expires = now + timedelta(seconds=ttl_seconds)
    needed = sorted(set(capabilities) & granted)
    return [
        CapabilityToken(principal=principal, capability=cap, scope=scope, expires=expires)
        for cap in needed
    ]


def holds_capability(
    tokens: Iterable[CapabilityToken],
    capability: str,
    now: datetime | None = None,
    scope: str | None = None,
) -> bool:
    """True if the principal holds a valid, unexpired token for the capability.

    When ``scope`` is given, a matching token must also have been minted for that scope (the
    case/trace id), so a case-scoped token (issue #63) cannot be replayed outside the case it
    was issued for. ``scope=None`` skips the scope check, so standing role grants (issue #23)
    still validate when used outside a case.
    """
    return any(token.is_valid(capability, now, scope) for token in tokens)
