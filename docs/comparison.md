# Comparison with neighboring approaches

Where this reference architecture fits relative to approaches you may already
be evaluating. The goal is accurate positioning, not selling against
alternatives — each approach is legitimate for its own purpose.

> This repository is a **reference architecture**, not a hosted product or a
> production gateway. Claims below describe what the code in this repo
> demonstrates.

| Capability | Plain agent loop (full tool access) | Workflow / orchestration engine | Hosted agent / MCP gateway | Ad hoc MCP server setup | **This reference architecture** |
|---|---|---|---|---|---|
| Bounded context / tool exposure | No — full catalog | Varies | Often yes | No | Yes — bounded shortlist (`catalog.py`) |
| Deterministic execution of known paths | No | Yes (its core) | Varies | No | Yes — flows (`flows.py`) |
| Policy gating (allow/deny/ask) | No | Rarely | Often yes | No | Yes — `policies.py` |
| Capability tokens / least privilege | No | Rarely | Varies | No | Yes — `policies.py` |
| Structured audit trace | No | Varies | Often yes | No | Yes — `audit.py` |
| Offline evaluation of routing/policy | No | No | Rarely | No | Sketched — `evals.py` |
| Hosting model | Library/script | Service | Hosted service | Self-hosted | None — runnable local reference |
| Production-ready | Depends | Depends | Yes (by design) | No | **No — reference/learning only** |

## How to read this

- **Plain agent loop:** the simplest starting point and the "before" this repo
  contrasts against. Fast to build, weak on governance.
- **Workflow/orchestration engine:** strong at deterministic execution, but not
  focused on agent tool-governance (policy, capability scoping, bounded context).
- **Hosted agent/MCP gateway:** can provide governance and audit as a managed
  service; this repo instead shows the *patterns* you would adopt or evaluate.
- **Ad hoc MCP server setup:** exposes tools without a governance layer; this
  repo demonstrates the layer that would sit in front of it.

This repository's niche is teaching and evaluating the governance patterns —
bounded context, deterministic flows, policy gates, capability tokens, audit,
and offline evaluation — as one coherent, runnable before/after example.

## Related reading

- [Adoption path](adoption-path.md) — how to layer these controls.
- [Glossary](glossary.md) — definitions.
- [Docs index](README.md).
