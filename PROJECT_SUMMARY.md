# Project summary

A structured, human- and machine-readable overview of this repository. For the
machine-optimized version see [`llms.txt`](llms.txt); for definitions see the
[glossary](docs/glossary.md).

## Purpose

Runnable reference architecture for governed enterprise tool-using agents.
Build the same Customer Operations agent two ways — an **unsafe baseline** vs a
bounded, policy-gated, auditable **control plane** — and run the contrast
offline, so the value of each governance control is concrete and measurable.

## Audience

Platform/engineering teams, security teams, AI/data leaders, and consultants
evaluating governance patterns for tool-using agents.

## Architecture in brief

| Dimension | Unsafe baseline | Governed control plane |
|---|---|---|
| Tool exposure | Full catalog every step | Bounded shortlist |
| Tool output | Raw payloads forwarded into context | Bounded output frame |
| Risky actions | Executed with no gate | allow / deny / ask policy gate + capability tokens |
| Execution | Re-decided per step | Deterministic flow |
| Audit | Flat free-text logs | Structured audit trace |

## dgenio ecosystem mapping

| Library | Role | Demonstrated in |
|---|---|---|
| contextweaver | Bounded shortlist / context firewall | `catalog.py` |
| ChainWeaver | Deterministic flow executor | `flows.py` |
| agent-kernel | Capability tokens / authorization | `policies.py`, governed path |
| AgentFence | allow/deny/ask policy gate | `policies.py` |
| skdr-eval | Offline evaluation lane | `evals.py`, `evals/` |
| lessonweaver | Reviewed lessons | `lessons.py` |
| VibeGuard | CI guardrails for AI-generated changes | `.github/workflows/vibeguard.yml` |

## Commands

```bash
make setup   # install (only dependency: pydantic)
make demo    # run the baseline-vs-governed demo, offline
make test    # run the unit test suite
```

## Key paths

- `enterprise_agent_control_plane/` — the package.
- `apps/demo_cli/main.py` — demo entry point.
- `flows/`, `policies/`, `evals/`, `traces/`, `demos/`, `docs/`.

## Limitations

Reference architecture and learning repository, **not** production security
software. No security guarantees; all tools and data are synthetic; the model
is replaced by a deterministic offline router for reproducibility.
