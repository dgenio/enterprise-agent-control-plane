# Control traceability matrix — baseline risk → governed control → library

One table that answers, for each unsafe-baseline risk: which governed control
closes it, which dgenio library the control maps to, and where it lives in the
code. This is the qualitative companion to the (planned) quantitative
comparison scorecard.

> Reference architecture and learning repository — **not** production security
> software. "Status" describes what the example code demonstrates, not a
> security guarantee.

Each row pairs a demonstrated baseline gap (run it via `make demo`) with the
specific governed mechanism that mitigates it. For the threats themselves see
the [threat model](threat-model.md); for how each decision is made see the
[governance model](governance-model.md).

| Baseline risk | Governed control | dgenio library | Where it lives | Status |
|---|---|---|---|---|
| Over-permissioned tool surface (full catalog every step) | Bounded capability shortlist | contextweaver | [`catalog.py`](../enterprise_agent_control_plane/catalog.py) (`shortlist_capabilities`, `ChoiceCard`) | Implemented |
| Unbounded / growing model-visible context | Bounded Frames + shortlist; context-size metric | contextweaver | [`frames.py`](../enterprise_agent_control_plane/frames.py), [`catalog.py`](../enterprise_agent_control_plane/catalog.py) (`context_reduction`) | Implemented |
| Raw-output / sensitive-field leakage | Frame projects only task-relevant fields | agent-kernel (Frames) | [`frames.py`](../enterprise_agent_control_plane/frames.py); `sensitive_fields` in [`registry.py`](../enterprise_agent_control_plane/registry.py) | Implemented |
| Indirect prompt injection via tool output | Tool output treated as untrusted data behind a Frame | agent-kernel (Frames) | [`frames.py`](../enterprise_agent_control_plane/frames.py), [`governed_agent.py`](../enterprise_agent_control_plane/governed_agent.py) | Implemented |
| Policy-blind write / destructive actions | allow/deny/ask policy gate + action classes | AgentFence | [`policies.py`](../enterprise_agent_control_plane/policies.py) (`AgentFencePolicy`, `ACTION_CLASSES`) | Implemented |
| No least privilege / no notion of "who may act" | Scoped capability tokens, principal restrictions | agent-kernel | [`policies.py`](../enterprise_agent_control_plane/policies.py) (`CapabilityToken`, `ROLE_GRANTS`, `holds_capability`) | Implemented |
| No separation of duties (self-approval) | Authorized approver who is not the requester | AgentFence / agent-kernel | [`policies.py`](../enterprise_agent_control_plane/policies.py) (`APPROVER_AUTHORITY`, `may_approve`) | Implemented |
| Per-step model round-trips on a fixed path | Deterministic compiled flow | ChainWeaver | [`flows.py`](../enterprise_agent_control_plane/flows.py) (`ChainWeaverExecutor`, `FLOW_REGISTRY`) | Implemented |
| Missing execution contract (acts on failed reads) | Fail-closed flow steps; halt before any write | ChainWeaver / agent-kernel | [`flows.py`](../enterprise_agent_control_plane/flows.py) (`run` fail-closed paths) | Implemented |
| Data exfiltration / no egress boundary | Outbound send is a gated write decided first | AgentFence | [`policies.py`](../enterprise_agent_control_plane/policies.py), [`governed_agent.py`](../enterprise_agent_control_plane/governed_agent.py) | Implemented |
| No aggregate budget across a session | Case capability budget bounds invocable tools | AgentFence / agent-kernel | [`flows.py`](../enterprise_agent_control_plane/flows.py) (`budget` argument), [`governed_agent.py`](../enterprise_agent_control_plane/governed_agent.py) | Implemented |
| Audit-light, un-investigable logs | Structured, per-step, tamper-evident trace | agent-kernel (audit) | [`audit.py`](../enterprise_agent_control_plane/audit.py) (`AuditTrace`, `AuditEvent`) | Implemented |
| Unevaluated routing/policy changes | Offline evaluation gate before merge | skdr-eval | [`evals.py`](../enterprise_agent_control_plane/evals.py), [`evals/`](../evals/) | Implemented (local stand-in) |
| Lost operator corrections | Reviewed lesson becomes a durable guardrail | lessonweaver | [`lessons.py`](../enterprise_agent_control_plane/lessons.py) (`LessonWeaverStub`) | Partial (staging; review-to-behavior loop planned, issue #68) |
| Unsafe AI-generated changes merged unflagged | Pre-merge diff safety gate | VibeGuard | [`.github/workflows/vibeguard.yml`](../.github/workflows/vibeguard.yml) | Planned (placeholder, issues #10/#91) |

## How to read the status column

- **Implemented** — the control runs in the governed path and is covered by a test.
- **Local stand-in** — the pattern is demonstrated offline without the real library.
- **Partial / Planned** — the artifact or the full loop is not finished; the linked
  issue tracks the remaining work. Nothing here is a production security guarantee.

## Related

- [Threat model](threat-model.md) — the risks in the left column, explained.
- [Governance model](governance-model.md) — how each control decides a call.
- [Architecture](architecture.md) — where each control sits in the data flow.
- [Baseline incident post-mortem](baseline-incident-postmortem.md) — several risks combined.
- [Docs index](README.md) — the full documentation map.
