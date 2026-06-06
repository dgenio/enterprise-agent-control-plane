# Consultant playbook — applying the pattern in an engagement

How to use this reference architecture in a client or internal engagement:
connect each governance control to the business risk it reduces, and sequence
adoption so value lands early.

This playbook is the engagement-facing companion to the
[recommended adoption path](adoption-path.md) (which is the technical, step-by-step
sequence). Use them together.

## Why this matters to the business

Teams adopt tool-using agents quickly, then discover the governance gaps the
[threat model](threat-model.md) lists: over-broad tool access, unaudited
actions, money moved without a gate, and changes shipped without evaluation.
The cost is not hypothetical — the
[baseline incident post-mortem](baseline-incident-postmortem.md) shows several
minor gaps combining into one un-investigable data-exfiltration incident.

## The four moves

1. **Bounded capability discovery.** Inventory the tools an agent can reach and
   classify each by risk (`read` / `write` / `destructive`). Replace "all tools,
   every step" with a bounded shortlist. *Business value:* smaller blast radius
   and lower context cost. *Maps to:* `catalog.py`.
2. **Encode known high-value paths as deterministic flows.** The predictable
   business workflows (refund review, customer reply, escalation) should run the
   same way every time, with the risky write held out of the steps. *Business
   value:* repeatability and fewer model round-trips. *Maps to:* `flows.py`.
3. **Add explicit policy gates and auditable outcomes.** Put an allow/deny/ask
   decision and a capability-token check in front of every write, and record a
   structured trace. *Business value:* enforceable controls and a record you can
   investigate. *Maps to:* `policies.py`, `audit.py`.
4. **Evaluate candidate changes offline before rollout.** Score routing and
   policy changes against labeled data and refuse regressions. *Business value:*
   change safety without a live blast radius. *Maps to:* `evals.py`.

## How to run a session

- **Show the contrast first.** Run `make demo` so stakeholders see the baseline
  gaps and the governed path on the same case before any slideware.
- **Anchor on the [traceability matrix](control-traceability.md).** It is the
  one artifact that maps each risk to the control, the library, and the code —
  ideal to screenshot into a proposal.
- **Sequence with the [adoption path](adoption-path.md).** Land bounded context
  and the policy gate first; they deliver the most risk reduction per unit of
  effort.
- **Stay honest about scope.** This is a reference architecture, not a product.
  Position it as the pattern a team adopts or evaluates, not a drop-in guarantee.

## Related

- [Recommended adoption path](adoption-path.md) — the technical step-by-step sequence.
- [Control traceability matrix](control-traceability.md) — risk → control → library.
- [Comparison](comparison.md) — how this relates to neighboring approaches.
- [Docs index](README.md) — the full documentation map.
