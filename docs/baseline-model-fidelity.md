# Baseline model-stand-in fidelity (is the "before" a strawman?) — issue #74

The unsafe baseline uses a **deterministic, offline router** (`baseline_router.py`) as a
stand-in for an LLM. That choice is deliberate: it keeps `make demo` reproducible, key-free,
and runnable in CI with no network. A fair reviewer will ask whether the gaps the baseline
demonstrates are artifacts of a *rigged* stand-in rather than properties a real model would
actually exhibit. This page states the fidelity assumptions honestly so the "before" half of
the contrast is credible rather than a strawman.

> Reference architecture and learning repository — **not** production security software.
> No claim is made that the deterministic stand-in equals a real model.

## What the stand-in is

`route_v1` / `route_v2` / `route_greedy` / `route_injection_naive` / `route_injection_exfil`
each take the request, the tools already called, and the *accumulated raw tool output*, and
return the next capability (or `None`). The baseline loop re-invokes the router every step
over the **whole** catalog, with no bounded shortlist — exactly how a naive first-pass agent
would let a model pick the next tool from everything on every turn.

## Which gaps are architectural (model-independent)

These hold for **any** decision-maker, because they are properties of the *architecture* the
baseline is wired into, not of the router:

| Gap | Why it is architectural | Code |
|---|---|---|
| Tool overload / unbounded context | The full 9-tool catalog is serialized into context every step regardless of who picks. | `baseline_agent.py` (`serialize_tool_catalog`) |
| Raw-output leakage | Tool outputs are forwarded verbatim; nothing projects task-relevant fields. | `leaked_fields`, `raw_outputs` |
| Sensitive fields in durable logs (#106) | A first-pass logger dumps raw payloads to logs/artifacts with no redaction. | `[debug]` log lines |
| Policy-blind writes | No principal, token, or policy decision stands between intent and a write. | `policy_blind_writes` |
| No execution contract (#32/#73) | No precondition ties an action to the success of the reads it depends on. | `precondition_gaps`, `silent_failures` |
| No egress boundary (#103) | The send recipient/body are derived from in-context data with no allow-list or gate. | `email.send_reply` path |
| No aggregate budget (#109) | Nothing caps the count of writes or total money moved across a session. | `aggregate_session_side_effects` |
| Audit-light execution | Only flat free-text logs exist; there is no structured, queryable trace. | `structured_audit_trace: None` |
| Per-step model round-trips (#72) | A fixed path is re-decided every step instead of being compiled into a flow. | `model_decisions` |

## Which behaviors are simplified for the demo

These are conveniences of the stand-in, not load-bearing claims:

- **Determinism.** The router always picks the same path for a given request. A real model
  would vary run to run; we fix it so the contrast is reproducible.
- **Curated mis-selection / injection.** `route_greedy` and the injection routers trigger on
  obvious, clearly-`[FAKE]` planted text. A real model's mis-selection and prompt-injection
  susceptibility would be broader and less predictable, not narrower.

## How a real model would change the picture

A real, nondeterministic LLM would add risk **on top of** the gaps above, never remove them:

- **Nondeterminism** — the same request could take different paths across runs, so the
  policy-blind writes and leakage become intermittent and harder to characterize.
- **Mis-selection at scale** — a larger, verbose tool catalog widens the surface for picking
  the wrong (or a high-blast-radius) tool.
- **Prompt-injection** — untrusted tool/ticket text is far more likely to steer a real model
  than the narrow planted directives shown here.

In other words, the deterministic stand-in is a **conservative** "before": it understates,
rather than overstates, how a real model would behave in this architecture.

## Related

- [Threat model](threat-model.md) — the baseline risks each governed control addresses.
- [The lesson-capture gap](lesson-capture-gap.md) — a worked baseline "before".
- [Baseline incident post-mortem](baseline-incident-postmortem.md) — the gaps combined into
  one realistic, un-investigable incident.
