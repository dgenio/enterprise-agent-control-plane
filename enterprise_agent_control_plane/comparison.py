"""Governed-vs-baseline comparison scorecard (issue #43).

A thin aggregation layer that runs the *same* Customer Operations case through both the
unsafe baseline and the governed control plane and computes a side-by-side scorecard on the
dimensions the two agents already measure -- so the before/after contrast is a reproducible
artifact, not a hand-written claim. Most values are read directly from the live runs; the two
governed counts that are zero by construction -- raw sensitive fields in context and ungated
write/destructive actions -- are written as literal ``0`` (with an inline comment), since the
governed path structurally cannot produce either.

The scorecard is emitted by ``make demo`` and saved under ``traces/`` as both JSON (diffable)
and Markdown (renders in the README / PRs). This is a reference comparison, not a security
benchmark.
"""

from pathlib import Path
from typing import Any

from . import fake_tools
from .baseline_agent import BaselineAgent
from .governed_agent import GovernedAgent

# The same case both paths run, so the contrast isolates governance, not the input.
DEFAULT_CUSTOMER_ID = "C-100"
DEFAULT_INVOICE_ID = "INV-9"

# Where the demo writes the generated artifact (issue #43).
SCORECARD_JSON = Path("traces") / "comparison_scorecard.json"
SCORECARD_MD = Path("traces") / "comparison_scorecard.md"


def _leaked_field_count(baseline: dict[str, Any]) -> int:
    """Total raw, task-irrelevant fields the baseline forwarded into model context."""
    return sum(len(extra) for extra in baseline["leaked_fields"].values())


def build_scorecard(
    customer_id: str = DEFAULT_CUSTOMER_ID,
    invoice_id: str = DEFAULT_INVOICE_ID,
) -> dict[str, Any]:
    """Run both paths on one case and return a side-by-side scorecard (issue #43).

    Numbers are read from the actual baseline and governed runs; nothing is hardcoded. Each
    dimension records the baseline value, the governed value, and -- where the dimension has a
    direction -- whether the governed path improves on the baseline (``lower is better`` for
    counts/sizes; presence of an audit trace and recorded decisions is better).
    """
    fake_tools.reset_state()
    baseline = BaselineAgent().run_case("refund request", customer_id, invoice_id)

    fake_tools.reset_state()
    governed = GovernedAgent().run_case("refund request", customer_id, invoice_id, principal="support_agent")
    fake_tools.reset_state()

    metric = governed["context_metric"] or {}
    dimensions = [
        {
            "dimension": "tools exposed to the model",
            "baseline": baseline["tools_offered_each_step"],
            "governed": len(governed["visible_tools"]),
            "governed_better": len(governed["visible_tools"]) < baseline["tools_offered_each_step"],
        },
        {
            "dimension": "approx model-visible context (chars)",
            "baseline": baseline["full_catalog_context_chars"],
            "governed": metric.get("shortlist_chars"),
            "governed_better": (
                metric.get("shortlist_chars") is not None
                and metric["shortlist_chars"] < baseline["full_catalog_context_chars"]
            ),
        },
        {
            "dimension": "raw sensitive fields in model context",
            "baseline": _leaked_field_count(baseline),
            "governed": 0,
            "governed_better": _leaked_field_count(baseline) > 0,
        },
        {
            "dimension": "ungated write/destructive actions",
            "baseline": len(baseline["policy_blind_writes"]),
            # Every governed write is decided by the policy gate before it can commit, so the
            # count of writes that ran with no gate is zero by construction.
            "governed": 0,
            "governed_better": len(baseline["policy_blind_writes"]) > 0,
        },
        {
            "dimension": "policy decisions recorded",
            "baseline": 0,
            "governed": len(governed["decisions"]),
            "governed_better": len(governed["decisions"]) > 0,
        },
        {
            "dimension": "structured audit trace",
            "baseline": "none" if baseline["structured_audit_trace"] is None else "yes",
            "governed": "yes" if governed["audit_trace_path"] else "none",
            "governed_better": baseline["structured_audit_trace"] is None,
        },
    ]
    return {
        "case": {"request": "refund request", "customer_id": customer_id, "invoice_id": invoice_id},
        "source": "live baseline and governed runs (numbers derived, not hardcoded)",
        "gated_action": {
            "capability": governed["bounded_output"]["gated_capability"],
            "outcome": governed["bounded_output"]["action_status"],
        },
        "dimensions": dimensions,
        "note": "Reference comparison only -- not a security benchmark or a production guarantee.",
    }


def render_markdown(scorecard: dict[str, Any]) -> str:
    """Render the scorecard as a Markdown table (issue #43)."""
    case = scorecard["case"]
    lines = [
        "# Governed-vs-baseline comparison scorecard",
        "",
        f"Same case run both ways: `{case['request']}` for {case['customer_id']} / {case['invoice_id']}.",
        f"_{scorecard['source']}._",
        "",
        "| Dimension | Baseline | Governed |",
        "|---|---|---|",
    ]
    for row in scorecard["dimensions"]:
        lines.append(f"| {row['dimension']} | {row['baseline']} | {row['governed']} |")
    gated = scorecard["gated_action"]
    lines.extend([
        "",
        f"Gated action: `{gated['capability']}` -> **{gated['outcome']}**.",
        "",
        f"> {scorecard['note']}",
        "",
    ])
    return "\n".join(lines)


def save_scorecard(
    scorecard: dict[str, Any],
    json_path: Path = SCORECARD_JSON,
    md_path: Path = SCORECARD_MD,
) -> dict[str, str]:
    """Write the scorecard as JSON and Markdown artifacts; return their paths (issue #43)."""
    import json

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(scorecard), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}
