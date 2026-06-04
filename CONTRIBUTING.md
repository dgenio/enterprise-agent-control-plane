# Contributing

Thanks for your interest in **enterprise-agent-control-plane**. This is a
runnable **reference architecture and learning repository**, not production
security software — contributions should keep it honest, offline, and easy to
read. See the [docs index](docs/README.md) and the
[recommended adoption path](docs/adoption-path.md) for orientation.

## Setup

The only dependency is `pydantic`. Everything runs offline with no API keys.

```bash
make setup   # pip install -e .
make demo    # run the baseline-vs-governed demo
make test    # run the unit test suite
```

## Running the demo and tests

- `make demo` runs `apps/demo_cli/main.py`: the unsafe baseline across a
  realistic multi-case workload, then the governed control plane, then a
  side-by-side contrast.
- `make test` runs `python -m unittest discover -s tests -p "test_*.py"`. All
  tests are offline and deterministic; add new tests with the same `unittest`
  style as the existing files under `tests/`.

## Conventions

- **Commits & PR titles:** Conventional Commits with a scope, matching history,
  e.g. `feat(governed): ...`, `fix(baseline): ...`, `docs(readme): ...`,
  `test(policy): ...`.
- **Code style:** match the surrounding code — type hints, absolute imports
  from `enterprise_agent_control_plane`, small focused functions, and
  comments that point at the issue a behavior demonstrates.
- **Keep it offline:** no network calls, API keys, or real PII. Synthetic data
  only.
- **Be honest about scope:** do not add production-readiness or security
  guarantees. Keep the reference-architecture framing intact.

## Scope of contributions

Good fits include: new governance scenarios, clearer demonstrations of a
baseline gap or a governed control, documentation/discoverability improvements,
and bug fixes. Anything that would imply this is production-ready, or that adds
heavyweight dependencies, is out of scope — open an issue to discuss first.

## Filing issues

Please use the [issue templates](.github/ISSUE_TEMPLATE). They prompt for
context, the desired outcome, and acceptance criteria, which keeps issues
aligned with the project's direction.
