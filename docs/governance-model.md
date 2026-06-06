# Governance model — action classes, decisions, tokens, and approval

How the control plane decides whether a tool call may run: classify the
capability, require a scoped token, apply an allow/deny/ask policy, and record
the decision in the audit trace.

All of the mechanisms below live in
[`policies.py`](../enterprise_agent_control_plane/policies.py) and are exercised
by [`governed_agent.py`](../enterprise_agent_control_plane/governed_agent.py).

## Action classes

Every capability is classified by the side effect it can have, derived from the
single [capability registry](../enterprise_agent_control_plane/registry.py):

- **`read`** — no side effect (lookups, drafting text). Allowed outright.
- **`write`** — an external, non-monetary side effect (send an email, create a
  task). Gated to `ask` (approval required).
- **`destructive`** — money movement or irreversible action (issue a refund).
  Decided by parameter-aware thresholds.

A capability the policy does not recognise is **denied by default** — the
posture is deny-by-default, not allow-by-default.

## Decisions: allow / deny / ask

`AgentFencePolicy.evaluate(capability, principal, args)` returns a
`PolicyDecision` of `allow`, `deny`, or `ask`, each with a human-readable
reason:

- **read** → `allow`.
- **write** → `ask`.
- **destructive** (refund) → amount at/under the auto limit `allow`; at/under the
  manager limit `ask`; above it `deny`.
- **principal-restricted** capabilities (e.g. `audit.export_case`,
  `frame.expand`) → `deny` for principals not on the allow-list, regardless of
  action class.

## Capability tokens (least privilege)

Before policy evaluation, the principal must hold a valid `CapabilityToken` for
the capability (`issue_tokens`, `holds_capability`, `ROLE_GRANTS`). A capability
the role does not grant is rejected at the token layer even before the policy
runs. Tokens carry scope, issuer, and optional expiry. (Just-in-time,
case-scoped issuance is tracked as a follow-up in issue #63.)

## Approval and separation of duties

An `ask` decision is resolved by an injected approver. `APPROVER_AUTHORITY`
records which principals may approve which action classes, and `may_approve`
enforces that the approver is **not** the requester — a `support_agent` cannot
approve their own refund.

## Provenance and audit

Each decision is stamped with the policy `version` (a content hash of the
ruleset and thresholds) and the thresholds in effect, then recorded as a
`policy.decision` event in the [audit trace](audit-trace.md). Two traces are
therefore comparable, and a trace can be replayed against a named policy
version. This is reference provenance, not cryptographic signing.

## Related

- [Architecture](architecture.md) — where the policy gate sits in the data flow.
- [Audit trace](audit-trace.md) — how decisions and provenance are recorded.
- [Threat model](threat-model.md) — the baseline risks these controls address.
- [Glossary](glossary.md) — definitions of every term above.
- [Docs index](README.md) — the full documentation map.
