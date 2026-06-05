import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable, Literal, Optional

Decision = Literal["allow", "deny", "ask"]
ActionClass = Literal["read", "write", "destructive"]


# --- Action classes (issue #2) ------------------------------------------------
# Every governed capability is classified by the kind of side effect it can have.
# Anything not listed here is unknown and denied by default (deny-by-default).
ACTION_CLASSES: dict[str, ActionClass] = {
    "crm.search_customer": "read",
    "billing.get_invoice": "read",
    "support.search_tickets": "read",
    "docs.search_policy": "read",
    "email.draft_reply": "read",   # composes text only; no external side effect
    "audit.export_case": "read",   # read/export only, but principal-restricted below
    "support.create_task": "write",
    "email.send_reply": "write",
    "billing.issue_refund": "destructive",
}

# Capabilities only specific principals may ever invoke, regardless of action class.
# audit.export_case exposes case evidence, so it is restricted to managers.
PRINCIPAL_RESTRICTED: dict[str, set[str]] = {
    "audit.export_case": {"support_manager", "supervisor"},
}

# Parameter-aware thresholds for destructive money movement (issue #36). An amount at
# or below the auto limit is allowed outright; at or below the manager limit it requires
# approval; anything larger is denied. Mirrored in policies/agentfence.policy.yaml;
# unifying YAML as the single runtime source is tracked in issue #3.
REFUND_AUTO_LIMIT = 50.0
REFUND_MANAGER_LIMIT = 500.0


@dataclass(frozen=True)
class PolicyDecision:
    decision: Decision
    reason: str
    action_class: Optional[ActionClass] = None


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
        args: Optional[dict[str, Any]] = None,
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

        if action_class == "read":
            return PolicyDecision("allow", f"{capability} is a read action; allowed.", action_class)

        if action_class == "write":
            return PolicyDecision("ask", f"{capability} is a write action; requires approval.", action_class)

        # destructive: parameter-aware thresholds (issue #36)
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
    expires: Optional[datetime] = None

    def is_valid(self, capability: str, now: Optional[datetime] = None) -> bool:
        if self.capability != capability:
            return False
        if self.expires is None:
            return True
        now = now or datetime.now(UTC)
        return now < self.expires


# Role -> capabilities each principal is granted scoped tokens for (issue #23).
# Mirrored in policies/capability_policy.yaml; runtime unification tracked in issue #3.
ROLE_GRANTS: dict[str, set[str]] = {
    "support_agent": {
        "crm.search_customer",
        "billing.get_invoice",
        "support.search_tickets",
        "docs.search_policy",
        "email.draft_reply",
        "email.send_reply",
        "support.create_task",
        "billing.issue_refund",
    },
    "support_manager": {
        "crm.search_customer",
        "billing.get_invoice",
        "support.search_tickets",
        "docs.search_policy",
        "email.draft_reply",
        "email.send_reply",
        "support.create_task",
        "billing.issue_refund",
        "audit.export_case",
    },
    "billing_admin": {
        "crm.search_customer",
        "billing.get_invoice",
        "billing.issue_refund",
    },
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


def may_approve(approver_principal: str, action_class: Optional[ActionClass]) -> bool:
    """True if ``approver_principal`` is authorized to approve the given action class (#64)."""
    if action_class is None:
        return False
    return action_class in APPROVER_AUTHORITY.get(approver_principal, set())


def issue_tokens(principal: str, expires: Optional[datetime] = None) -> list[CapabilityToken]:
    """Mint the scoped capability tokens a principal's role grants (issue #23)."""
    grants = ROLE_GRANTS.get(principal, set())
    return [CapabilityToken(principal=principal, capability=cap, expires=expires) for cap in sorted(grants)]


def holds_capability(
    tokens: Iterable[CapabilityToken],
    capability: str,
    now: Optional[datetime] = None,
) -> bool:
    """True if the principal holds a valid, unexpired token for the capability."""
    return any(token.is_valid(capability, now) for token in tokens)
