# Glossary

Canonical definitions for the vocabulary used across this repository. Other
docs and the README link here instead of re-defining terms, so the wording
stays consistent. Each term notes where it lives in the code.

| Term | Definition | Where it lives |
|---|---|---|
| **Control plane** | The governed layer that sits between an operator request and the enterprise tools: it shortlists capabilities, runs a deterministic flow, gates risky actions through policy, and records an audit trace. | `GovernedAgent` in `enterprise_agent_control_plane/governed_agent.py` |
| **Bounded context / shortlist** | Surfacing only a small, relevant set of capabilities to the model instead of the full tool catalog, keeping model-visible context narrow. | `shortlist_capabilities`, `ChoiceCard` in `enterprise_agent_control_plane/catalog.py` |
| **Deterministic flow** | A fixed, predictable multi-step business path compiled out of the model loop, so known paths run the same way every time. | `ChainWeaverExecutor`, `FlowDefinition`, `FLOW_REGISTRY`, `select_flow` in `enterprise_agent_control_plane/flows.py` |
| **Policy gate (allow / deny / ask)** | The decision point that classifies a capability and returns `allow`, `deny`, or `ask` (approval required) before a risky action can run. | `AgentFencePolicy.evaluate`, `PolicyDecision` in `enterprise_agent_control_plane/policies.py` |
| **Action class** | The risk classification (`read` / `write` / `destructive`) attached to each capability, used by the policy gate to decide posture. | `ACTION_CLASSES` in `enterprise_agent_control_plane/policies.py` |
| **Capability token** | A scoped grant that a principal must hold to invoke a capability; checked at the token layer before policy evaluation. | `CapabilityToken`, `issue_tokens`, `holds_capability`, `ROLE_GRANTS` in `enterprise_agent_control_plane/policies.py` |
| **Principal** | The identity on whose behalf a request runs (e.g. `support_agent`, `support_manager`); determines which capabilities are granted and which actions may be approved. | `PRINCIPAL_RESTRICTED`, `ROLE_GRANTS` in `enterprise_agent_control_plane/policies.py` |
| **Bounded output frame** | The structured, model-visible result of a governed run — intent, flow, gated capability, decision, and reason — instead of raw tool payloads. | `bounded_output` frame in `enterprise_agent_control_plane/governed_agent.py` |
| **Context firewall** | The principle of keeping raw, sensitive-looking tool output (and any untrusted text it contains) out of the model loop, exposing only a bounded summary. | governed path in `governed_agent.py`; contrasted with the baseline's raw-output leakage in `baseline_agent.py` |
| **Audit trace** | An ordered, structured record of what happened in a governed run — request, shortlist, flow, policy decisions, approvals, output frame. | `AuditTrace`, `AuditEvent` in `enterprise_agent_control_plane/audit.py` |
| **Offline evaluation** | Scoring candidate routers or policies against labeled logs/scenarios before any change is enabled — no live model or network. | `compare_router_candidates` in `enterprise_agent_control_plane/evals.py`; data in `evals/` |
| **Reviewed lesson** | A failure turned into a human-reviewed, durable guardrail; unreviewed lessons stay inert until a human approves them. | `LessonWeaverStub`, `LessonCandidate` in `enterprise_agent_control_plane/lessons.py` |
| **Unsafe baseline** | The intentionally naive "before" agent — full tool catalog, raw outputs forwarded, writes with no gate, flat logs — used as the contrast for the governed path. | `BaselineAgent` in `enterprise_agent_control_plane/baseline_agent.py` |

## Related reading

- [Architecture](architecture.md) — how these pieces fit together.
- [Governance model](governance-model.md) — action classes, decisions, tokens, audit.
- [Docs index](README.md) — the full documentation map.
