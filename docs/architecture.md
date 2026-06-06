# Architecture — module and data-flow map

How a request flows through the governed control plane, and where each control
lives in the code: catalog → shortlist → flow → policy → audit.

This repository builds the same Customer Operations agent two ways. The
[unsafe baseline](baseline-model-fidelity.md) is the "before"; the governed
control plane below is the "after". Both run offline over the same synthetic
tools so the only meaningful difference is the governance plumbing.

## Module map

| Module | Responsibility |
|---|---|
| [`registry.py`](../enterprise_agent_control_plane/registry.py) | The single capability registry. Each capability is declared once (risk, description, action class, argument schema, sensitive fields, bound tool); every other view derives from it so they cannot drift. |
| [`catalog.py`](../enterprise_agent_control_plane/catalog.py) | Bounded shortlist / context firewall — turns the registry into model-visible `ChoiceCard`s and a budget-aware shortlist, and measures the context reduction vs the full catalog. |
| [`flows.py`](../enterprise_agent_control_plane/flows.py) | Deterministic flow registry and runner. Intent → flow selection, then fixed steps run with no per-step model routing; risky writes stay out of the steps and are gated separately. |
| [`policies.py`](../enterprise_agent_control_plane/policies.py) | The allow/deny/ask policy gate, action classes, capability tokens, principal restrictions, and approver authority. |
| [`governed_agent.py`](../enterprise_agent_control_plane/governed_agent.py) | The control plane that orchestrates the above and returns a bounded output frame. |
| [`audit.py`](../enterprise_agent_control_plane/audit.py) | The structured, per-step, tamper-evident audit trace. |
| [`frames.py`](../enterprise_agent_control_plane/frames.py) | Bounded Frames that project task-relevant fields and keep raw, sensitive output out of the model loop. |
| [`evals.py`](../enterprise_agent_control_plane/evals.py) | Offline evaluation of candidate routers/policies against committed datasets. |
| [`lessons.py`](../enterprise_agent_control_plane/lessons.py) | Reviewed-lesson staging — a failure becomes a durable guardrail only after human review. |

## Data flow (governed path)

1. **Request received** — an operator request arrives under a named *principal*.
2. **Shortlist** — `catalog.shortlist_capabilities` surfaces a small, relevant
   set of capabilities instead of the full tool catalog (bounded context).
3. **Flow selection** — `flows.select_flow` maps the request to one deterministic
   flow, or returns "no matching flow" rather than defaulting silently.
4. **Deterministic execution** — `ChainWeaverExecutor` runs the flow's read-only
   steps; each step is checked against a capability token and the case budget,
   and fails closed if a dependency fails.
5. **Policy gate** — each write/destructive action is classified and decided
   `allow` / `deny` / `ask` by `AgentFencePolicy`; `ask` requires an authorized
   approver who is not the requester (separation of duties).
6. **Bounded output frame** — the run returns a structured summary (intent, flow,
   gated capability, decision, reason), not raw tool payloads.
7. **Audit trace** — every step and decision is recorded as a hash-chained event
   under `traces/`.

For the full risk-by-risk mapping of which control closes which baseline gap,
see the [control traceability matrix](control-traceability.md).

## Related

- [Governance model](governance-model.md) — action classes, decisions, tokens, approval.
- [Audit trace](audit-trace.md) — the event schema and tamper-evident chain.
- [Control traceability matrix](control-traceability.md) — risk → control → library.
- [Glossary](glossary.md) — definitions for every term above.
- [Docs index](README.md) — the full documentation map.
