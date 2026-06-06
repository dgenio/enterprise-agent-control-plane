# Audit trace

How the governed path records what it did, in a form a reviewer or downstream tool can
check — a schema-validated, per-step, tamper-evident record. Implemented in
[`enterprise_agent_control_plane/audit.py`](../enterprise_agent_control_plane/audit.py).

> Reference architecture and learning repository — **not** production security software.
> The integrity pattern below is illustrative, not cryptographic non-repudiation.

## Event schema

Every event's `action` is drawn from an enumerated vocabulary
(`audit.ACTION_VOCABULARY`), and each action declares the `details` fields it must carry.
`validate_trace` reports any unknown action, any missing required field, and — when asked
— any mandatory event a completed run failed to emit, so an incomplete or malformed trace
is *detectable* rather than silently accepted.

| Action | Required `details` |
| --- | --- |
| `request.received` | `request`, `intent`, `principal` |
| `shortlist` | `capabilities`, `reason` |
| `flow.select` | `intent`, `reason` |
| `flow.execute` | `flow_id`, `steps` |
| `flow.step` | `step`, `capability`, `token_valid`, `result_ref` |
| `policy.decision` | `capability`, `principal`, `decision`, `outcome`, `reason`, `token_valid`, `policy_version`, `policy_thresholds` |
| `approval.request` | `capability`, `reason` |
| `approval.resolved` | `capability` |
| `output.frame` | `request`, `intent`, `flow`, `status` |

A completed, flow-matched run must emit `request.received`, `shortlist`, `flow.select`,
`flow.execute`, `policy.decision`, and `output.frame` (`audit.REQUIRED_GOVERNED_ACTIONS`).
A request that matches no flow emits the smaller no-match set instead.

## Per-step events

The deterministic flow records each step as its own `flow.step` event with the step name,
capability, whether the principal held a valid capability token, and a `result_ref` (a
content digest of the step output, not the raw payload). The principal's token is verified
**before** each step runs: a step whose capability the principal does not hold fails closed
— the tool is never invoked and the event is marked `token_valid=false` — so read steps are
held to the same least-privilege check as the gated write.

## Decision provenance

Each `policy.decision` event is stamped with the deciding policy's `policy_version` and the
`policy_thresholds` in effect (`AgentFencePolicy.provenance`). The version is a content
hash of the ruleset and thresholds, so changing a threshold changes the recorded version —
two traces are comparable, and a trace can be replayed against a named policy version. This
is reference provenance, not signing.

## Tamper-evident hash chain

Each event carries a SHA-256 `hash` over its own content plus the previous event's `hash`
(the all-zero genesis hash for the first event), forming an append-only chain.
`AuditTrace.verify()` — and `verify_event_chain` over a reloaded trace — recompute the
chain and return pass/fail; a single edited, removed, or reordered event breaks
verification.

**This is a tamper-evident *reference pattern*, not production-grade tamper-proofing.** It
uses a plain hash chain with no signatures, key management, or external timestamping, and
makes no claim of cryptographic non-repudiation. It demonstrates the shape of a trustworthy
audit trace; a production system would layer real signing and storage controls on top.

## Related

- [Governance model](governance-model.md) — the decisions recorded in the trace.
- [Architecture](architecture.md) — where audit sits in the data flow.
- [Baseline incident post-mortem](baseline-incident-postmortem.md) — what audit-light logs can't answer.
- [Glossary](glossary.md) — definitions.
- [Docs index](README.md) — the full documentation map.
