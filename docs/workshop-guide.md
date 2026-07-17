# Daily Driver / workshop guide

A practical script for running this reference architecture in a workshop,
stakeholder demo, or internal brown-bag. It tells you what to run, what to say,
what the audience will see, and how to handle the questions that always come up.

> Reference architecture and learning repository — **not** production security
> software. Frame it that way to your audience: this demonstrates governance
> *patterns*; it is not a product or a security guarantee.

## Audience and goal

For platform/engineering leads, security teams, and AI/data decision-makers
evaluating how to let tool-using agents touch internal systems safely. By the
end, the audience can articulate the difference between an unsafe baseline agent
and a bounded, policy-gated, auditable control plane — and where each control
would live in their own stack.

## Setup (do this before the room is watching)

```bash
make setup   # runtime dependencies: pydantic, pyyaml; fully offline
make demo    # confirm it runs end-to-end and the scorecard prints
make test    # optional: confirm the suite is green
```

Everything is offline and deterministic, so there are no API keys, no network,
and the numbers are identical every run — safe to present live.

## The 15-minute script

1. **Frame the problem (2 min).** A first-pass agent gets the *full* tool catalog,
   forwards raw tool output into context, and executes writes on a model decision
   alone. Point at the [problem statement](../README.md#problem-statement).
2. **Run the baseline (4 min).** `make demo` section `[1]`. Walk the annotated
   gaps: over-permissioned context, raw-output leakage, a policy-blind refund, an
   injected ticket directive steering a write, a refund firing on a not-found
   invoice. Each line names the gap it surfaces.
3. **Run the governed path (4 min).** Same `make demo`, section `[2]`. Show the
   bounded shortlist (9 tools → 5), the deterministic flow, the policy gate holding
   the refund for approval, the bounded output frame, and the audit trace under
   `traces/`.
4. **Show the scorecard (3 min).** Section `[3]` /
   [`traces/comparison_scorecard.md`](../traces/comparison_scorecard.md): same case,
   both ways, on the same dimensions. This is the money slide.
5. **Close with adoption (2 min).** The controls layer one at a time — point at the
   [adoption path](adoption-path.md).

## Talking points

- **Bounded context is a cost and a safety lever.** Model-visible context drops
  from ~1290 to ~108 characters for the refund case; fewer tools in context means
  fewer ways to go wrong and a smaller bill.
- **Determinism removes a class of failure.** Known business paths are compiled
  into flows, so they cannot be re-decided (or prompt-injected) every step.
- **The gate is the point.** allow/deny/ask with capability tokens is what stands
  between intent and a money-moving action.
- **Auditability is non-negotiable.** A structured, hash-chained trace answers
  "who did what, with which arguments, and was anything blocked?"

## Expected outputs

- A printed baseline-vs-governed walkthrough and a side-by-side scorecard.
- Refreshed artifacts under `traces/` and `lessons/` (see [CLAIMS.md](../CLAIMS.md)
  for the receipts index).
- A green `make test` run (the behaviors are pinned by the suite).

## Common objections (and honest answers)

- *"Is the baseline a strawman?"* No — the gaps are architectural, not artifacts
  of the offline stand-in. See [baseline model-stand-in fidelity](baseline-model-fidelity.md).
- *"Does this make my agent secure?"* No. It is a reference architecture, not
  production security software, and claims no security guarantee.
- *"Are these the real libraries?"* Mostly local reference implementations today;
  one (VibeGuard) uses the real package. See the
  [integration maturity matrix](maturity-matrix.md).
- *"Can I see one control in isolation?"* Yes — the
  [examples gallery](examples.md) runs each capability on its own.

## Follow-up adoption paths

Point each interested team at the library that owns the control they care about
(see the [integration maturity matrix](maturity-matrix.md) for repos and status):
contextweaver (bounded context), ChainWeaver (deterministic flows), AgentFence +
agent-kernel (policy + capability tokens), skdr-eval (offline evaluation),
lessonweaver (reviewed lessons), and VibeGuard (pre-merge safety gate).

## Related

- [Recommended adoption path](adoption-path.md) — layer the controls one at a time.
- [Consultant playbook](consultant-playbook.md) — applying the pattern in an engagement.
- [Comparison](comparison.md) — how this relates to neighboring approaches.
- [Glossary](glossary.md) — definitions for every term above.
- [Docs index](README.md).
