# VibeGuard pre-merge diff safety gate

VibeGuard is the repository's **AI-coding safety lane**: a pre-merge check that inspects a
change's *diff* for edits that quietly weaken the agent's safety posture — the class of
regression that unit tests and review can miss because the code still "works". It is the
control that maps to the *"unsafe AI-generated changes merged unflagged"* row of the
[control traceability matrix](control-traceability.md).

> Reference architecture and learning repository — **not** production security software.
> This gate is an offline stand-in for the official VibeGuard action, not a guarantee.

## What it protects against

The gate ([`scripts/vibeguard_gate.py`](../scripts/vibeguard_gate.py)) flags the change
classes documented in [`demos/README.md`](../demos/README.md):

1. **Widened money-movement / fallback bound** — e.g. raising the unsafe baseline's
   hardcoded fallback refund amount, or raising `REFUND_AUTO_LIMIT`. This is the class the
   [`demos/risky_ai_change.diff`](../demos/risky_ai_change.diff) fixture demonstrates
   (it widens the fallback refund from `$149` to `$100,000`).
2. **A capability removed from `WRITE_OR_DESTRUCTIVE`** — hides a write so it is no longer
   treated as a policy-blind / gated action.
3. **An introduced outbound network call** — this repo is offline-only, so any added
   `requests`/`urllib`/`socket`/… call is suspect.

A finding blocks the pull request; an empty result means none of these classes were
detected. The gate reads a unified diff only — it never applies the fixture and never
mutates source.

## Running it locally

```bash
make vibeguard                                   # self-check: prove the gate flags the fixture
git diff origin/main...HEAD | python scripts/vibeguard_gate.py --diff -   # gate your branch
python scripts/vibeguard_gate.py --diff some.patch                        # gate a diff file
```

## In CI

[`.github/workflows/vibeguard.yml`](../.github/workflows/vibeguard.yml) runs on every pull
request with least-privilege (`contents: read`). It first runs `--self-check` (so a broken
gate fails loudly rather than waving changes through), then diffs the PR against its base
branch and pipes the result through the gate.

## Future integration point

The official public **VibeGuard** action plugs in at the same workflow step: replace the
"Gate the pull request diff" step with the published action (or `vibeguard gate` once
available) while keeping the self-check and the offline fixture as a regression anchor. The
detectors here intentionally mirror the documented change classes so the contract stays
stable across that swap.
