# Integration maturity matrix — stub vs real dgenio libraries

This repository demonstrates the [Weaver Stack](https://github.com/dgenio)
governance patterns. It is honest about *how* each pattern is currently realised:
most controls are **local reference implementations** (the pattern, hand-rolled
inline, with no dependency on the real package), one uses a **real package**, and
some shared contracts are **planned**.

> Reference architecture and learning repository — **not** production security
> software. "Maturity" describes how the example wires a library, not a security
> guarantee. The full restructure into a `plain` build and a `with_ecosystem` build
> that consumes the real libraries is tracked in [issue #80](https://github.com/dgenio/enterprise-agent-control-plane/issues/80).

## How to read the integration column

- **Local reference implementation** — the library's pattern is reproduced inline
  in this repo with no dependency on the real package. This is the teaching default.
- **Real package** — the published package is an actual dependency and runs here.
- **Planned** — not yet wired; the linked issue tracks the work.

## Matrix

| Library | Role in the control plane | Integration | Where it lives | Tracking |
|---|---|---|---|---|
| contextweaver | Bounded capability shortlist / context firewall | Local reference implementation | [`catalog.py`](../enterprise_agent_control_plane/catalog.py) (`shortlist_capabilities`, `context_reduction`) | [#85](https://github.com/dgenio/enterprise-agent-control-plane/issues/85), [#123](https://github.com/dgenio/enterprise-agent-control-plane/issues/123) |
| ChainWeaver | Deterministic flow executor | Local reference implementation | [`flows.py`](../enterprise_agent_control_plane/flows.py) (`ChainWeaverExecutor`, `FLOW_REGISTRY`) | [#86](https://github.com/dgenio/enterprise-agent-control-plane/issues/86), [#123](https://github.com/dgenio/enterprise-agent-control-plane/issues/123) |
| agent-kernel | Capability tokens, bounded Frames, audit trace primitives | Local reference implementation | [`policies.py`](../enterprise_agent_control_plane/policies.py) (`CapabilityToken`), [`frames.py`](../enterprise_agent_control_plane/frames.py), [`audit.py`](../enterprise_agent_control_plane/audit.py) | [#87](https://github.com/dgenio/enterprise-agent-control-plane/issues/87), [#123](https://github.com/dgenio/enterprise-agent-control-plane/issues/123) |
| AgentFence | allow/deny/ask policy gate | Local reference implementation | [`policies.py`](../enterprise_agent_control_plane/policies.py) (`AgentFencePolicy`, `ACTION_CLASSES`) | [#88](https://github.com/dgenio/enterprise-agent-control-plane/issues/88), [#123](https://github.com/dgenio/enterprise-agent-control-plane/issues/123) |
| skdr-eval | Offline evaluation lane | Local reference implementation | [`evals.py`](../enterprise_agent_control_plane/evals.py), [`evals/`](../evals/) | [#89](https://github.com/dgenio/enterprise-agent-control-plane/issues/89), [#123](https://github.com/dgenio/enterprise-agent-control-plane/issues/123) |
| lessonweaver | Reviewed-lesson capture (trace → guardrail) | Local reference implementation (staging stub) | [`lessons.py`](../enterprise_agent_control_plane/lessons.py) (`LessonWeaverStub`) | [#90](https://github.com/dgenio/enterprise-agent-control-plane/issues/90), [#68](https://github.com/dgenio/enterprise-agent-control-plane/issues/68) |
| VibeGuard | Pre-merge AI-change safety gate | Real package (`vibeguard-gate==0.9.0`, dev) + domain gate | [`.github/workflows/vibeguard.yml`](../.github/workflows/vibeguard.yml), [`scripts/vibeguard_gate.py`](../scripts/vibeguard_gate.py), [VibeGuard doc](vibeguard.md) | done ([#125](https://github.com/dgenio/enterprise-agent-control-plane/issues/125), [#91](https://github.com/dgenio/enterprise-agent-control-plane/issues/91)) |
| weaver-spec | Shared domain/type contracts both builds adopt | Planned | — (see [issue #83](https://github.com/dgenio/enterprise-agent-control-plane/issues/83)) | [#83](https://github.com/dgenio/enterprise-agent-control-plane/issues/83) |

## Related

- [Control traceability matrix](control-traceability.md) — each baseline risk mapped to
  the control, library, and code (validated in CI by `scripts/check_traceability.py`).
- [Roadmap](roadmap.md) — the ecosystem-integration direction.
- [Docs index](README.md) — the full documentation map.
