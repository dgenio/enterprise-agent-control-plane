# Demo fixtures

Inert, clearly-labeled artifacts used to make a risk concrete. Nothing here is
applied to the live code paths.

## `risky_ai_change.diff` — the risky AI-generated change the VibeGuard gate catches (issue #35)

`VibeGuard` exists because AI-assisted changes can quietly weaken an agent's safety
posture, and without a pre-merge gate they merge unnoticed. The unit-test suite alone does
not catch that class of change:

- `.github/workflows/tests.yml` runs the unit tests, but the baseline characterization
  tests (`tests/test_baseline_characterization.py`) assert only the **presence** of the
  baseline's gaps (for example, that an issued refund's `status` is `"issued"`). None of
  them pin the fallback refund **amount**, so a diff that quietly widens it stays green.
  `tests/test_vibeguard_motivation.py` locks that gap in as evidence (issue #105).

`risky_ai_change.diff` is a plausible example of such a change: it widens the unsafe
baseline's hardcoded fallback refund amount from `$149` to `$100,000`, so a refund issued
on a missing or garbage invoice (see issue #32) would move three orders of magnitude more
money. The diff is **illustrative only** and is never applied.

### What the VibeGuard gate adds

CI runs two complementary layers (issues #10/#91/#125; see [`docs/vibeguard.md`](../docs/vibeguard.md)):

- the **official VibeGuard** (`vibeguard-gate`) for artifact hygiene — secrets, risky SQL,
  packaging / supply-chain drift, AI footprints; and
- a **domain gate** ([`scripts/vibeguard_gate.py`](../scripts/vibeguard_gate.py)) for the
  repo-specific regressions the generic tool does not model — a diff that widens a
  hardcoded money-movement amount or fallback bound (**this fixture**), removes a capability
  from the baseline's `WRITE_OR_DESTRUCTIVE` set (hiding a write), or introduces an
  unexpected outbound call.

Run `make vibeguard-domain` to watch the domain gate flag this fixture. These are
reference-architecture controls, not production protection.
