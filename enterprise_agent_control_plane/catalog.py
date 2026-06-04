from dataclasses import dataclass
from typing import Iterable

from pydantic import BaseModel


@dataclass(frozen=True)
class ChoiceCard:
    capability: str
    risk: str
    description: str


class ToolDefinition(BaseModel):
    """Full, serializable tool definition (name + description + argument schema).

    This is the heavyweight tool detail a naive agent pastes into model context for
    *every* tool on *every* turn. The governed shortlist (contextweaver) keeps this
    out of model-visible context; the baseline does not. Used to make tool-context
    bloat measurable (issue #15) and comparable to a future governed shortlist.
    """

    capability: str
    risk: str
    description: str
    args_schema: dict[str, str]


def build_catalog() -> list[ChoiceCard]:
    return [
        ChoiceCard("crm.search_customer", "low", "Find customer profile and account status."),
        ChoiceCard("billing.get_invoice", "low", "Read invoice details."),
        ChoiceCard("billing.issue_refund", "high", "Issue a monetary refund to a customer."),
        ChoiceCard("support.search_tickets", "low", "Find support history."),
        ChoiceCard("support.create_task", "medium", "Create follow-up tasks for operations."),
        ChoiceCard("email.draft_reply", "low", "Draft customer-facing response text."),
        ChoiceCard("email.send_reply", "high", "Send customer-facing response."),
        ChoiceCard("docs.search_policy", "low", "Find internal policy references."),
        ChoiceCard("audit.export_case", "medium", "Export case evidence for review."),
    ]


def build_tool_definitions() -> list[ToolDefinition]:
    """Full tool definitions, including argument schemas, for all nine capabilities."""
    return [
        ToolDefinition(
            capability="crm.search_customer",
            risk="low",
            description="Find customer profile and account status.",
            args_schema={"customer_id": "str"},
        ),
        ToolDefinition(
            capability="billing.get_invoice",
            risk="low",
            description="Read invoice details.",
            args_schema={"invoice_id": "str"},
        ),
        ToolDefinition(
            capability="billing.issue_refund",
            risk="high",
            description="Issue a monetary refund to a customer.",
            args_schema={"invoice_id": "str", "amount": "float", "reason": "str"},
        ),
        ToolDefinition(
            capability="support.search_tickets",
            risk="low",
            description="Find support history.",
            args_schema={"customer_id": "str"},
        ),
        ToolDefinition(
            capability="support.create_task",
            risk="medium",
            description="Create follow-up tasks for operations.",
            args_schema={"customer_id": "str", "note": "str"},
        ),
        ToolDefinition(
            capability="email.draft_reply",
            risk="low",
            description="Draft customer-facing response text.",
            args_schema={"customer_name": "str", "topic": "str"},
        ),
        ToolDefinition(
            capability="email.send_reply",
            risk="high",
            description="Send customer-facing response.",
            args_schema={"to": "str", "subject": "str", "body": "str"},
        ),
        ToolDefinition(
            capability="docs.search_policy",
            risk="low",
            description="Find internal policy references.",
            args_schema={"query": "str"},
        ),
        ToolDefinition(
            capability="audit.export_case",
            risk="medium",
            description="Export case evidence for review.",
            args_schema={"case_id": "str"},
        ),
    ]


def serialize_tool_catalog(tool_definitions: Iterable[ToolDefinition]) -> str:
    """Serialize full tool definitions as the JSON blob a naive agent puts in context."""
    return "[" + ",".join(td.model_dump_json() for td in tool_definitions) + "]"


def context_size(serialized: str) -> dict[str, int]:
    """Dependency-free context-size metric: characters plus a rough token estimate.

    A character count is an honest, reproducible stand-in for token cost (no tokenizer
    download / network). ``approx_tokens`` uses the common ~4-chars-per-token heuristic
    and is explicitly an estimate, not a tokenizer result.
    """
    chars = len(serialized)
    return {"chars": chars, "approx_tokens": chars // 4}


def shortlist_capabilities(query: str, catalog: Iterable[ChoiceCard], limit: int = 4) -> list[ChoiceCard]:
    """contextweaver-style bounded shortlist adapter."""
    query_l = query.lower()
    scored: list[tuple[int, ChoiceCard]] = []
    for card in catalog:
        score = 0
        for token in card.capability.split(".") + card.description.lower().split():
            if token in query_l:
                score += 1
        if "refund" in query_l and "refund" in card.capability:
            score += 3
        if "reply" in query_l and "email" in card.capability:
            score += 2
        scored.append((score, card))
    scored.sort(key=lambda x: (x[0], -len(x[1].capability)), reverse=True)
    return [card for score, card in scored if score > 0][:limit] or list(catalog)[:limit]
