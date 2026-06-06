# AGENTS.md — operating guide for automated contributors

Operating instructions for AI coding agents and IDE assistants working in this
repository: how to set up, run, test, and modify it **without breaking what it
is meant to demonstrate**.

This file answers *"how do I work in this repo correctly?"*. For *"what is this
repo?"* see the project summary in [`PROJECT_SUMMARY.md`](PROJECT_SUMMARY.md)
and the machine-readable [`llms.txt`](llms.txt); for definitions see the
[glossary](docs/glossary.md). This guide links to those rather than duplicating
them.

## What this repository is

A runnable **reference architecture and learning repository** that builds the
same Customer Operations agent two ways — an unsafe baseline vs a governed
control plane — and runs the contrast offline. It is **not** production security
software. See [`README.md`](README.md) and [`SECURITY.md`](SECURITY.md).

## Setup, run, and test

Everything is offline and key-free. The only runtime dependency is `pydantic`.

```bash
make setup   # python -m pip install -e .
make demo    # run the baseline-vs-governed demo (apps/demo_cli)
make baseline# run the unsafe baseline alone; refresh traces/unsafe_run.json
make test    # python -m unittest discover -s tests -p "test_*.py"
make eval    # run the offline evaluation regression gate
```

Run `make test` (and, when touching routing/policy, `make eval`) before
proposing changes. CI runs the same `tests`, `evals`, and `docs-health`
workflows; keep them green.

## Key paths

- `enterprise_agent_control_plane/` — the package.
  - `baseline_agent.py`, `baseline_router.py`, `baseline_runner.py` — the unsafe "before".
  - `governed_agent.py` — the governed control plane.
  - `catalog.py` — bounded shortlist / context firewall (contextweaver pattern).
  - `flows.py` — deterministic flow registry/runner (ChainWeaver pattern).
  - `policies.py` — allow/deny/ask policy, action classes, capability tokens (AgentFence + agent-kernel patterns).
  - `registry.py` — the single capability registry everything else derives from.
  - `audit.py` — structured, tamper-evident audit trace.
  - `evals.py` — offline evaluation lane (skdr-eval pattern).
  - `lessons.py` — reviewed-lesson staging (lessonweaver pattern).
  - `frames.py`, `scenarios.py`, `fake_tools.py` — bounded frames, the shared workload, synthetic tools.
- `apps/` — runnable entry points (`demo_cli`, `baseline_cli`).
- `flows/`, `policies/` — YAML definitions mirrored by the package.
- `evals/` — committed golden datasets. `traces/` — emitted run artifacts.
- `demos/` — inert, illustrative fixtures (never applied to real source).
- `docs/` — documentation. `scripts/` — repo maintenance scripts.
- `tests/` — `unittest` suite.

## Conventions

- **Commits & PR titles:** Conventional Commits with a scope, e.g.
  `feat(governed): ...`, `fix(baseline): ...`, `docs(readme): ...`,
  `test(policy): ...`. See [`CONTRIBUTING.md`](CONTRIBUTING.md).
- **Code style:** type hints, absolute imports from
  `enterprise_agent_control_plane`, small focused functions, and comments that
  point at the issue a behavior demonstrates. Match the surrounding code; add a
  capability once in `registry.py` and let the other views derive from it.
- **Tests:** stdlib `unittest`, class-based, offline and deterministic. Follow
  the existing files under `tests/`.

## Guardrails (do not break the contrast)

- **Keep it offline.** No network calls, API keys, real PII, or live endpoints.
  All tools and data are synthetic.
- **Preserve the unsafe baseline.** The baseline's gaps (raw-output leakage,
  policy-blind writes, audit-light logs, etc.) are *deliberate* — they are the
  "before" the governed path is contrasted against. Do not "fix" the baseline;
  doing so destroys the demonstration.
- **Treat governed tool outputs as untrusted.** Tool/ticket text may carry
  injected directives; the governed path quarantines it behind bounded Frames.
  Keep raw, sensitive-looking output out of the model loop.
- **Do not apply the `demos/` fixtures.** They illustrate a risky change a
  pre-merge gate would catch; they must never be applied to committed source.
- **Stay honest about scope.** Do not add production-readiness or security
  guarantees, and do not introduce heavyweight dependencies without discussion.
- **Reuse the canonical wording.** Public-facing text reuses the canonical
  description and topics in [`METADATA.md`](METADATA.md) and the terms in the
  [glossary](docs/glossary.md). The `docs-health` check enforces this — see
  `scripts/check_docs_health.py` and `make docs-health`.
