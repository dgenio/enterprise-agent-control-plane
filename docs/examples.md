# Examples gallery

The full [`make demo`](../README.md#demo-walkthrough) exercises every control at
once. These small, isolated, copy-paste examples each demonstrate **one** governed
capability so you can understand a building block on its own. Every example reuses
the in-memory fake tools and synthetic fixtures and runs offline with no API keys.

> Reference architecture and learning repository — **not** production security
> software. These snippets demonstrate patterns; they add no security guarantee.

The runnable scripts live under [`examples/`](../examples/). Run any of them from
the repository root after `make setup`.

## Bounded capability shortlist — contextweaver

Surfaces only a small, relevant set of capabilities instead of the full tool
catalog, and measures the model-visible context reduction.

- Maps to: [`catalog.py`](../enterprise_agent_control_plane/catalog.py)
  (`shortlist_capabilities`, `context_reduction`).
- Adoption path: [Step 1 — bounded routing](adoption-path.md#step-1--add-bounded-routing).

```bash
python examples/bounded_shortlist.py
```

## Policy decision: allow / deny / ask — AgentFence

Classifies a capability and returns `allow`, `deny`, or `ask` before a risky
action runs, with a deny-by-default posture.

- Maps to: [`policies.py`](../enterprise_agent_control_plane/policies.py)
  (`AgentFencePolicy.evaluate`, `ACTION_CLASSES`).
- Adoption path: [Step 2 — policy + capability boundary](adoption-path.md#step-2--add-a-policy--capability-boundary).

```bash
python examples/policy_decisions.py
```

## Deterministic flow execution — ChainWeaver

Runs a known business path (refund review) as a compiled, deterministic flow with
no model round-trip between steps; the risky write stays out of the flow.

- Maps to: [`flows.py`](../enterprise_agent_control_plane/flows.py)
  (`select_flow`, `ChainWeaverExecutor`, `FLOW_REGISTRY`).
- Adoption path: [Step 3 — deterministic flows](adoption-path.md#step-3--add-deterministic-flows).

```bash
python examples/deterministic_flow.py
```

## Structured, tamper-evident audit trace — agent-kernel

Records a schema-validated, hash-chained audit trace and verifies it, instead of
emitting flat free-text logs.

- Maps to: [`audit.py`](../enterprise_agent_control_plane/audit.py)
  (`AuditTrace`, `validate_trace`, `verify_event_chain`); schema in the
  [audit trace doc](audit-trace.md).
- Adoption path: [Step 4 — audit](adoption-path.md#step-4--add-audit).

```bash
python examples/audit_trace.py
```

## Related

- [Examples directory README](../examples/README.md) — the same gallery as a table.
- [Recommended adoption path](adoption-path.md) — how the controls layer together.
- [Glossary](glossary.md) — definitions for each term above.
- [Docs index](README.md).
