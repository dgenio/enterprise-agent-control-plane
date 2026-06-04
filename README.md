# enterprise-agent-control-plane

[![tests](https://github.com/dgenio/enterprise-agent-control-plane/actions/workflows/tests.yml/badge.svg)](https://github.com/dgenio/enterprise-agent-control-plane/actions/workflows/tests.yml)
[![license: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![python: >=3.10](https://img.shields.io/badge/python-%3E%3D3.10-3776AB.svg?logo=python&logoColor=white)](pyproject.toml)
[![status: reference architecture](https://img.shields.io/badge/status-reference%20architecture-6f42c1.svg)](README.md#disclaimer)

Runnable reference architecture for governed enterprise tool-using agents: bounded context, policy gates, audit traces.

Build the same Customer Operations agent two ways — an unsafe baseline vs a bounded, policy-gated, auditable **control plane** — and run the contrast offline.

## Who this is for

Platform and engineering teams, security teams, AI/data leaders, and consultants evaluating **agent governance** patterns for **tool-using agents** and **MCP** tools — anyone who needs bounded context, policy enforcement, and auditability before letting agents touch internal tools.

## What you get

- **Bounded context** — a capability shortlist instead of the full tool catalog.
- **Deterministic flows** — known business paths compiled out of the model loop.
- **Policy gate** — allow/deny/ask decisions with capability tokens (least privilege).
- **Audit trace** — a structured, queryable record of every governed run.
- **Offline evaluation** — score routing/policy changes before enabling them.
- A runnable **before/after** demo that prints a side-by-side contrast.

## Quickstart

```bash
make setup
make demo
make test
```

## What this repo is / is not

**It is:**

- a runnable **reference architecture** for governed tool-using agents,
- a **before/after governance demo** (unsafe baseline vs governed control plane),
- a teaching, consulting, and portfolio artifact.

**It is not:**

- production security software or a hardened gateway,
- a hosted agent/MCP gateway or a drop-in library,
- a source of any security guarantee.

## When to use it / when not to

**Use it when** you are evaluating agent-governance patterns, running a workshop, building an internal reference, or explaining the value of bounded context, policy gates, and audit traces.

**Don't use it** to secure a live production agent as-is — the tools and data are synthetic, the model is a deterministic offline stand-in, and there are no security guarantees.

## Problem statement

Enterprise teams often start with broad tool access and unbounded prompts, then discover weak policy controls, poor auditability, and inconsistent execution. This repository demonstrates a practical "before vs after" architecture for a **Customer Operations Agent** with deterministic flows and governance controls.

## Architecture (reference)

```mermaid
flowchart LR
    U[Support Operator] --> B[Unsafe Baseline Agent]
    B --> T1[Full Tool Catalog]
    B --> R1[Raw Tool Outputs]

    U --> G[Governed Agent Control Plane]
    G --> CW[contextweaver shortlist]
    G --> CH[ChainWeaver deterministic flow]
    G --> AK[agent-kernel capabilities/tokens]
    G --> AF[AgentFence policy gate]
    G --> AU[Audit trace]
    G --> EV[skdr-eval offline comparison]
    G --> LW[lessonweaver reviewed lessons]
```

## Demo walkthrough

`make demo` runs the unsafe baseline across a realistic Customer Operations workload,
annotates each risk, then contrasts it with the governed path.

1. **Unsafe baseline** — a multi-case workload (refund, escalation, email reply,
   an ambiguous "just fix it" request, and a not-found case), each annotated with the
   gap it surfaces:
   - over-permissioned context (the full 9-tool catalog offered every step),
   - raw tool-output leakage (sensitive-looking fields forwarded verbatim),
   - **cumulative context growth** (catalog re-sent + raw outputs retained each step),
   - **poor tool selection** (an over-eager router reaches the destructive refund for a
     mere lookup),
   - **indirect prompt injection** (a planted `[FAKE]` ticket directive steers a write),
   - **no execution contract** (a refund fires on a not-found invoice, with no amount
     bound and no idempotency guard),
   - policy-blind writes, audit-light logging, and a **lost operator correction** that
     recurs because nothing captures it.
2. **Governed path**
   - shortlists relevant capabilities,
   - runs deterministic refund-review flow,
   - blocks/reroutes risky action via policy decision,
   - returns bounded output frame,
   - emits audit trace under `traces/`.
3. **Side-by-side contrast** — a generated scorecard putting both paths on the same
   dimensions (tools exposed, raw fields in context, ungated writes, policy decisions,
   audit trace).

Illustrative, inert fixtures live under [`demos/`](demos/) (a risky AI-generated change
no pre-merge gate would catch). The lesson-capture gap is written up in
[`docs/lesson-capture-gap.md`](docs/lesson-capture-gap.md).

## What this demonstrates

- bounded context routing over large tool catalogs,
- deterministic, schema-shaped business paths,
- capability and policy gates for risky actions,
- auditable execution traces,
- offline evaluation lane for safer changes.

## dgenio ecosystem fit

- `contextweaver`: shortlist adapter in `catalog.py`
- `ChainWeaver`: deterministic executor adapter in `flows.py`
- `agent-kernel`: capability-token pattern in `policies.py` + governed path
- `AgentFence`: local allow/deny/ask policy gate in `policies.py`
- `skdr-eval`: offline comparison stub in `evals.py` + `evals/`
- `lessonweaver`: reviewed lesson staging stub in `lessons.py`
- `VibeGuard`: CI workflow placeholder in `.github/workflows/vibeguard.yml`

## Implemented now vs planned

Implemented now:
- runnable local demo,
- fake in-memory enterprise tools,
- baseline vs governed behavior,
- deterministic flow registry and runner,
- policy + audit + tests + CI.

Planned:
- production-grade integrations for each dgenio library,
- richer policy language and approval orchestration,
- expanded replay/evaluation datasets.

## Documentation

Start at the [documentation index](docs/README.md). Highlights:

- [Glossary](docs/glossary.md) — canonical definitions, linked to the code.
- [FAQ](docs/faq.md) — common agent-governance questions answered directly.
- [Recommended adoption path](docs/adoption-path.md) — layer the controls one at a time.
- [Comparison](docs/comparison.md) — how this relates to neighboring approaches.

How to contribute: [`CONTRIBUTING.md`](CONTRIBUTING.md). Security scope and
reporting: [`SECURITY.md`](SECURITY.md).

## Disclaimer

This is a runnable **reference architecture and learning repository**, not production security software and not a production hardening guide.

## Library links (placeholders)

- contextweaver: https://github.com/dgenio/contextweaver
- ChainWeaver: https://github.com/dgenio/chainweaver
- agent-kernel: https://github.com/dgenio/agent-kernel
- AgentFence: https://github.com/dgenio/agentfence
- skdr-eval: https://github.com/dgenio/skdr-eval
- lessonweaver: https://github.com/dgenio/lessonweaver
- VibeGuard: https://github.com/dgenio/vibeguard
