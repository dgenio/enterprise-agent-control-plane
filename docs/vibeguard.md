# VibeGuard pre-merge safety gate

VibeGuard is the repository's **AI-coding safety lane**: a pre-merge check that inspects a
change for edits that quietly weaken safety — the class of regression that unit tests and
review can miss because the code still "works". It maps to the *"unsafe AI-generated
changes merged unflagged"* row of the [control traceability matrix](control-traceability.md).

> Reference architecture and learning repository — **not** production security software.

The gate runs in two complementary layers, because they catch different things:

## 1. Official VibeGuard — artifact hygiene

The official [`vibeguard-gate`](https://pypi.org/project/vibeguard-gate/) package
(`dgenio/vibeguard`) is a deterministic, offline scanner for **artifact hygiene**: hardcoded
secrets, risky SQL, source-map leaks, packaging / supply-chain drift, and AI footprints. It
is version-pinned as a dev dependency and runs as the `vibeguard` CI job with a high
severity threshold.

```bash
pip install -e .[dev]          # installs vibeguard-gate==0.9.0
make vibeguard                 # == vibeguard gate --fail-on high
vibeguard scan --markdown      # full findings report (non-blocking)
```

The composite GitHub Action `dgenio/vibeguard` is an equivalent alternative to the pinned
CLI used in CI.

## 2. Domain gate — repo-specific safety regressions

The generic scanner does not model this agent's *domain* invariants, so a small companion
gate ([`scripts/vibeguard_gate.py`](../scripts/vibeguard_gate.py)) covers the change classes
documented in [`demos/README.md`](../demos/README.md):

1. **Widened money-movement / fallback bound** — e.g. raising the unsafe baseline's hardcoded
   fallback refund amount, or raising `REFUND_AUTO_LIMIT`. This is the class the
   [`demos/risky_ai_change.diff`](../demos/risky_ai_change.diff) fixture demonstrates (it
   widens the fallback refund from `$149` to `$100,000`).
2. **A capability removed from `WRITE_OR_DESTRUCTIVE`** — hides a write so it is no longer
   treated as a policy-blind / gated action.
3. **An introduced outbound network call** — this repo is offline-only.

Scanning is scoped to the agent's runtime source; `tests/`, `docs/`, `demos/`, `scripts/`,
and `*.md` are skipped so example diffs and the gate's own vocabulary do not self-trip.

```bash
make vibeguard-domain                                            # self-check against the fixture
git diff origin/main...HEAD | python scripts/vibeguard_gate.py --diff -   # gate your branch
```

## In CI

[`.github/workflows/vibeguard.yml`](../.github/workflows/vibeguard.yml) runs both layers on
every pull request with least-privilege (`contents: read`):

- the **`vibeguard`** job installs `vibeguard-gate==0.9.0` and runs `vibeguard gate --fail-on high`;
- the **`domain-gate`** job first `--self-check`s itself against the risky fixture (so a broken
  gate fails loudly), then diffs the PR against its base branch and pipes the result through
  the domain gate.
