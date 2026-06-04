# Recommended adoption path

How to layer this architecture incrementally, starting from a naive agent and
adding one governance control at a time. Each step states the problem it solves,
what changes, and the module/library it maps to. This expands the
[consultant playbook](consultant-playbook.md) and follows the same
baseline-to-governed progression the `make demo` contrast already exhibits.

> Following this path does **not** yield production-grade security. It is a
> reference sequence for understanding and demonstrating the controls.

## Step 0 — Start from the unsafe baseline

- **Problem:** A first-pass agent gets the full tool catalog, forwards raw
  outputs into context, and executes writes on a model decision alone.
- **Change:** None yet — this is the "before". Run it to see the gaps.
- **Maps to:** `BaselineAgent` (`enterprise_agent_control_plane/baseline_agent.py`).

## Step 1 — Add bounded routing

- **Problem:** Over-permissioned tool surface and growing model-visible context.
- **Change:** Surface a bounded shortlist of capabilities instead of the full
  catalog; keep heavyweight tool detail out of the model loop.
- **Maps to:** `catalog.py` (`shortlist_capabilities`, `ChoiceCard`) — `contextweaver`.

## Step 2 — Add a policy + capability boundary

- **Problem:** Risky writes execute with no gate and no notion of who may act.
- **Change:** Classify capabilities by risk, require a scoped capability token,
  and gate write/destructive actions through an allow/deny/ask policy.
- **Maps to:** `policies.py` (`AgentFencePolicy`, `ACTION_CLASSES`, capability
  tokens) — `AgentFence` + `agent-kernel`.

## Step 3 — Add deterministic flows

- **Problem:** Known, fixed business paths are re-decided by the model each step.
- **Change:** Compile predictable paths into deterministic flows; keep the risky
  write out of the flow steps and gate it separately.
- **Maps to:** `flows.py` (`ChainWeaverExecutor`, `FLOW_REGISTRY`, `select_flow`) — `ChainWeaver`.

## Step 4 — Add audit

- **Problem:** Flat logs cannot answer who did what, with which arguments, and
  whether anything was blocked.
- **Change:** Emit a structured, ordered audit trace for every governed run.
- **Maps to:** `audit.py` (`AuditTrace`) — `agent-kernel`.

## Step 5 — Add offline evaluation

- **Problem:** Routing/policy changes ship on intuition with no regression check.
- **Change:** Score candidate routers and policies offline against labeled
  data before enabling them.
- **Maps to:** `evals.py` + `evals/` — `skdr-eval`.

## Step 6 — Add lesson capture

- **Problem:** Operator corrections are lost; the same mistake recurs.
- **Change:** Turn a failed/corrected trace into a human-reviewed lesson that
  only changes behavior once approved.
- **Maps to:** `lessons.py` (`LessonWeaverStub`) — `lessonweaver`.

## Step 7 — Add CI safety gates

- **Problem:** AI-generated changes can quietly weaken the safety posture.
- **Change:** Add a pre-merge gate that inspects diffs for safety regressions.
- **Maps to:** `.github/workflows/vibeguard.yml` — `VibeGuard`.

## Related reading

- [Glossary](glossary.md) — term definitions for each control.
- [Comparison](comparison.md) — how this sequence compares to alternatives.
- [Docs index](README.md).
