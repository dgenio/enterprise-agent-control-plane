# Threat model — baseline risks and the controls that address them

The concrete risks the unsafe baseline exhibits, and the governed control that
mitigates each one. Scope: the patterns this reference architecture
demonstrates — not a production security assessment.

> Reference architecture and learning repository — **not** production security
> software. The mitigations below are illustrative patterns, not guarantees.

Each risk below is demonstrated, not asserted: `make demo` runs the baseline
behavior, and the [control traceability matrix](control-traceability.md) maps
every risk to the code and library that closes it.

## Threats and mitigations

| # | Threat | How the baseline exhibits it | Governed mitigation |
|---|---|---|---|
| 1 | **Over-permissioned tool surface** | The full tool catalog is offered to the model on every step. | Bounded shortlist surfaces only relevant capabilities (`catalog.py`). |
| 2 | **Unbounded / growing context** | The catalog is re-sent and raw outputs are retained each step. | Bounded Frames + shortlist keep model-visible context flat (`frames.py`, `catalog.py`). |
| 3 | **Raw-output / sensitive-field leakage** | Tool payloads are forwarded verbatim, including sensitive-looking fields. | Frames project only task-relevant fields; raw detail stays out of the loop (`frames.py`). |
| 4 | **Indirect prompt injection** | Untrusted ticket text is read as an instruction. | Tool output is treated as untrusted data behind a Frame boundary. |
| 5 | **Policy-blind writes** | Writes execute with no gate, principal, or token. | allow/deny/ask policy + capability tokens before any write (`policies.py`). |
| 6 | **No separation of duties** | Nothing prevents self-approval of a risky action. | `APPROVER_AUTHORITY` / `may_approve` require a different authorized approver. |
| 7 | **Missing execution contract** | A refund fires on a not-found invoice; read failures are absorbed silently. | Flows fail closed; a failed dependency halts the flow before any write (`flows.py`). |
| 8 | **Data exfiltration / no egress boundary** | An injected directive redirects an outbound email to an external address. | The send is a gated write decided before execution (`policies.py`). |
| 9 | **No aggregate budget** | Nothing caps write count or total money moved across a session. | A case capability budget bounds what the flow may invoke. |
| 10 | **Audit-light logging** | Only flat free-text logs exist; an incident cannot be reconstructed. | Structured, per-step, tamper-evident trace (`audit.py`). |
| 11 | **Unevaluated routing/policy changes** | A router change ships on intuition. | Offline evaluation gate scores changes before they merge (`evals.py`). |
| 12 | **Lost operator corrections** | The same mistake recurs; nothing captures the correction. | Reviewed lessons turn a correction into a durable guardrail (`lessons.py`). |

For a worked, end-to-end version of several of these combining into one
un-investigable incident, see the
[baseline incident post-mortem](baseline-incident-postmortem.md).

## Out of scope

This model covers the example code's demonstrated risks. It does **not** cover
deployment, hosting, network, secret-management, or supply-chain threats of a
real system — there is no production system here to assess.

## Related

- [Control traceability matrix](control-traceability.md) — risk → control → library → code.
- [Governance model](governance-model.md) — how the mitigations decide each call.
- [Baseline model-stand-in fidelity](baseline-model-fidelity.md) — why these gaps are architectural.
- [Glossary](glossary.md) — definitions.
- [Docs index](README.md) — the full documentation map.
