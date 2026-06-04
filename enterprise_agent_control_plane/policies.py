from dataclasses import dataclass
from typing import Literal

Decision = Literal["allow", "deny", "ask"]


@dataclass(frozen=True)
class PolicyDecision:
    decision: Decision
    reason: str


class AgentFencePolicy:
    """AgentFence-style local policy gate adapter."""

    def evaluate(self, capability: str, principal: str) -> PolicyDecision:
        if capability in {"billing.issue_refund", "email.send_reply"}:
            return PolicyDecision("ask", f"{capability} requires explicit approval for principal {principal}.")
        if capability == "audit.export_case" and principal != "supervisor":
            return PolicyDecision("deny", "Only supervisor can export cases.")
        return PolicyDecision("allow", "Allowed by local policy.")


@dataclass(frozen=True)
class CapabilityToken:
    principal: str
    capability: str


def check_capability(token: CapabilityToken, capability: str) -> bool:
    return token.capability == capability
