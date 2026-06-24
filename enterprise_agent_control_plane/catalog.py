import json
from collections.abc import Iterable
from dataclasses import dataclass

from pydantic import BaseModel

from .registry import tool_capabilities


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
    bloat measurable (issue #15) and comparable to the governed shortlist (issue #24).
    """

    capability: str
    risk: str
    description: str
    args_schema: dict[str, str]


def build_catalog() -> list[ChoiceCard]:
    """Model-visible ChoiceCards (capability + risk + description only), from the registry.

    Derived from :data:`registry.CAPABILITY_REGISTRY` (issue #65) so the card text and the
    full tool definition can never drift. ChoiceCards deliberately omit the argument schema:
    that heavyweight detail stays in :func:`build_tool_definitions` / the registry and never
    enters model-visible context (issue #24).
    """
    return [
        ChoiceCard(spec.capability, spec.risk, spec.description) for spec in tool_capabilities()
    ]


def build_tool_definitions() -> list[ToolDefinition]:
    """Full tool definitions (incl. argument schemas) for the model-facing tools (issue #65)."""
    return [
        ToolDefinition(
            capability=spec.capability,
            risk=spec.risk,
            description=spec.description,
            args_schema=dict(spec.args_schema),
        )
        for spec in tool_capabilities()
    ]


def serialize_tool_catalog(tool_definitions: Iterable[ToolDefinition]) -> str:
    """Serialize full tool definitions as the JSON blob a naive agent puts in context."""
    return "[" + ",".join(td.model_dump_json() for td in tool_definitions) + "]"


def serialize_choice_cards(cards: Iterable[ChoiceCard]) -> str:
    """Serialize the model-visible ChoiceCards (capability + risk + description only).

    This is the governed path's bounded, model-visible context for the tool surface — the
    counterpart to :func:`serialize_tool_catalog`, used to make the contextweaver reduction
    measurable in the same units (issue #24).
    """
    return json.dumps(
        [{"capability": c.capability, "risk": c.risk, "description": c.description} for c in cards],
        separators=(",", ":"),
    )


def context_size(serialized: str) -> dict[str, int]:
    """Dependency-free context-size metric: characters plus a rough token estimate.

    A character count is an honest, reproducible stand-in for token cost (no tokenizer
    download / network). ``approx_tokens`` uses the common ~4-chars-per-token heuristic
    and is explicitly an estimate, not a tokenizer result.
    """
    chars = len(serialized)
    return {"chars": chars, "approx_tokens": chars // 4}


def shortlist_capabilities(
    query: str, catalog: Iterable[ChoiceCard], limit: int = 4
) -> list[ChoiceCard]:
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


def context_reduction(
    shortlist: Iterable[ChoiceCard],
    tool_definitions: Iterable[ToolDefinition],
) -> dict[str, int]:
    """Measure the model-visible context reduction of the governed shortlist (issue #24).

    Compares the governed model-visible context (bounded ChoiceCards) against the baseline's
    full tool catalog (verbose definitions with argument schemas) in the same units as the
    baseline metric (issue #15): character count, with a rough ~4-chars-per-token estimate.
    The reduction is the contextweaver story made measurable rather than asserted.
    """
    shortlist_chars = len(serialize_choice_cards(shortlist))
    full_chars = len(serialize_tool_catalog(tool_definitions))
    reduction = full_chars - shortlist_chars
    reduction_pct = round(100 * reduction / full_chars) if full_chars else 0
    return {
        "full_catalog_chars": full_chars,
        "shortlist_chars": shortlist_chars,
        "reduction_chars": reduction,
        "reduction_pct": reduction_pct,
        "full_catalog_approx_tokens": full_chars // 4,
        "shortlist_approx_tokens": shortlist_chars // 4,
    }
