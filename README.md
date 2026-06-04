# enterprise-agent-control-plane

[![tests](https://github.com/dgenio/enterprise-agent-control-plane/actions/workflows/tests.yml/badge.svg)](https://github.com/dgenio/enterprise-agent-control-plane/actions/workflows/tests.yml)
[![license: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![python: >=3.10](https://img.shields.io/badge/python-%3E%3D3.10-3776AB.svg?logo=python&logoColor=white)](pyproject.toml)
[![status: reference architecture](https://img.shields.io/badge/status-reference%20architecture-6f42c1.svg)](README.md#disclaimer)

Runnable reference architecture for governed enterprise tool-using agents, contrasting an unsafe baseline against a bounded, policy-gated, auditable control-plane path.

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

## Quickstart

```bash
make setup
make demo
make test
```

## Demo walkthrough

`make demo` prints two paths:

1. **Unsafe baseline**
   - exposes full catalog,
   - emits raw tool output,
   - attempts risky refund action directly.
2. **Governed path**
   - shortlists relevant capabilities,
   - runs deterministic refund-review flow,
   - blocks/reroutes risky action via policy decision,
   - returns bounded output frame,
   - emits audit trace in `traces/governed_run.json`.

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
