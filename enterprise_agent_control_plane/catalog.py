from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ChoiceCard:
    capability: str
    risk: str
    description: str


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
