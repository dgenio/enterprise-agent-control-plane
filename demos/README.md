# Demo fixtures

Inert, clearly-labeled artifacts used to make a risk concrete. Nothing here is
applied to the live code paths.

## `risky_ai_change.diff` — a risky AI-generated change with no pre-merge gate (issue #35)

`VibeGuard` exists because AI-assisted changes can quietly weaken an agent's safety
posture, and without a pre-merge gate they merge unnoticed. This repo's CI does not yet
catch that class of change:

- `.github/workflows/tests.yml` runs the unit tests, but the baseline characterization
  tests (`tests/test_baseline_characterization.py`) assert only the **presence** of the
  baseline's gaps (for example, that an issued refund's `status` is `"issued"`). None of
  them pin the fallback refund **amount**, so a diff that quietly widens it stays green.
- `.github/workflows/vibeguard.yml` only echoes a placeholder line — no check inspects a
  diff for a safety regression before merge.

`risky_ai_change.diff` is a plausible example of such a change: it widens the unsafe
baseline's hardcoded fallback refund amount from `$149` to `$100,000`, so a refund issued
on a missing or garbage invoice (see issue #32) would move three orders of magnitude more
money. The diff is **illustrative only** and is never applied.

### What a VibeGuard gate would add

A pre-merge VibeGuard check (tracked in issue #10) would flag edits in this class —
for example, a diff that:

- widens a hardcoded money-movement amount or fallback bound (this fixture),
- removes a capability from the baseline's `WRITE_OR_DESTRUCTIVE` set (hiding a write),
- weakens a governed policy mapping (e.g. raising `REFUND_AUTO_LIMIT`), or
- introduces an unexpected outbound call.

This is a stand-in for the official VibeGuard action, not production protection.
