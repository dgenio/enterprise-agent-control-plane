# FAQ

Direct answers to common questions about agent governance and what this
repository demonstrates. Answers stay within honest scope: this is a reference
architecture, not production software. See the [glossary](glossary.md) for term
definitions and the [docs index](README.md) for the full map.

## What is an agent control plane?

A governed layer between an operator's request and the enterprise tools an
agent can call. Instead of handing the model every tool and trusting it, the
control plane shortlists only relevant capabilities, runs known paths as
deterministic flows, gates risky actions through an allow/deny/ask policy with
capability tokens, and records a structured audit trace. In this repo that
layer is `GovernedAgent` in `enterprise_agent_control_plane/governed_agent.py`.

## How do I govern MCP tools?

The pattern shown here applies directly to MCP tools: classify each tool by
risk (`read` / `write` / `destructive`), expose a bounded shortlist rather than
the full catalog, and require a policy decision plus a scoped capability token
before any write/destructive call executes. See `policies.py` (`AgentFencePolicy`,
`ACTION_CLASSES`, capability tokens) and `catalog.py` (`shortlist_capabilities`).

## How do I audit tool-using agents?

Record a structured, ordered trace of every governed step — request, shortlist,
flow selection, policy decisions, approvals, and the bounded output frame —
rather than flat free-text logs. This repo's `AuditTrace`
(`enterprise_agent_control_plane/audit.py`) emits such a trace to `traces/`; the
unsafe baseline deliberately emits only flat logs to show the contrast.

## How do I reduce agent context bloat?

Stop re-sending the full tool catalog and stop forwarding raw tool outputs into
the model loop. Surface a bounded shortlist of capabilities and return a bounded
output frame instead of raw payloads. The demo quantifies the difference:
the baseline's model-visible context grows every step, while the governed
shortlist keeps it flat (see `catalog.py` and `baseline_agent.py`).

## How do I evaluate agent routing before deployment?

Score candidate routers (and policies) offline against labeled logs/scenarios
with expected decisions, and refuse changes that regress. This repo sketches
that lane in `evals.py` over `evals/sample_routing_logs.csv` — the `skdr-eval`
pattern applied locally and offline.

## What's the difference between the unsafe baseline and the governed path here?

The baseline offers the full tool catalog every step, forwards raw outputs into
context, executes writes with no gate, and emits flat logs. The governed path
shortlists capabilities, runs a deterministic flow, gates the risky action
through policy + capability tokens (allow/deny/ask), returns a bounded output
frame, and writes a structured audit trace. `make demo` runs both on the same
case and prints the side-by-side contrast.

## Is this production-ready?

No. It is a runnable **reference architecture and learning repository**. The
tools and data are synthetic, the model is replaced by a deterministic offline
router, and there are no security guarantees. See [`SECURITY.md`](../SECURITY.md)
and the "What this is / is not" section of the [README](../README.md).
