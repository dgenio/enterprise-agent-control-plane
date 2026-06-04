# The lesson-capture gap (baseline "before") — issue #34

Prototype agents repeat the same mistake: an operator corrects the agent, the correction
is applied ad hoc in the moment, and nothing durable captures it — so the next run makes
the identical error. The unsafe baseline in this repo has no learning loop, and that
absence is the motivation for `lessonweaver`.

## What the demo shows

The `make demo` "lost operator correction" section runs the same flawed case twice:

1. **Run 1** — the baseline issues the policy-blind refund (no gate, no approval).
2. **Operator correction** — a human notes the correction out loud:
   *"this refund should have required approval."*
3. **Run 2** — the identical case reproduces the **identical** unsafe outcome. The
   correction was never captured anywhere, so nothing changed. Because the fake refund
   tool has no idempotency guard (issue #32), the second run also appends a **second**
   refund.

The baseline only emits flat free-text logs (issue #19) and no structured failure record,
so there is no artifact a correction could attach to and no place it could persist.

## Failure mode

**No learning loop.** Repeated human corrections are discarded; the agent cannot
accumulate operational lessons, so identical failures recur run after run with no
institutional memory.

## How `lessonweaver` is the fix

`lessonweaver` turns a recurring failure into a **reviewed lesson**: a failed trace →
a lesson candidate → a reviewed lesson that becomes a durable guardrail. The forward
lesson-capture lane (issue #6) builds that path on top of `LessonWeaverStub`
(`enterprise_agent_control_plane/lessons.py`), reusing this same policy-blind refund as
its first reviewed lesson.

A related class of lost-correction risk — an AI-generated change that quietly erodes
safety with no pre-merge gate — is demonstrated separately in
[`demos/README.md`](../demos/README.md) (issue #35).
