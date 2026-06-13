# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims
to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This is a runnable **reference architecture and learning repository**, not
production security software. Entries describe what the demo and tests actually
exercise — they make no production-readiness or security claims.

## [Unreleased]

### Added

- **Examples gallery** (`examples/`, `docs/examples.md`): runnable, copy-paste
  snippets demonstrating the bounded shortlist, allow/deny/ask policy decisions,
  deterministic flow execution, and audit-trace export in isolation (issue #62).
- **Integration maturity matrix** (`docs/maturity-matrix.md`): which controls are
  local reference implementations, which use a real package, and which are
  planned, linked to code and tracking issues (issue #143).
- **Claims & receipts** (`CLAIMS.md`): every before/after contrast number tied to
  the command that produces it and the generated artifact (issue #142).
- **Daily Driver / workshop guide** (`docs/workshop-guide.md`): setup, demo
  script, talking points, expected outputs, objections, and follow-ups (issue #141).
- **Demo & sharing assets** (`docs/assets/`): Mermaid architecture source, a
  captured annotated demo-output snippet, and a social-card plan (issue #53).
- **Traceability-matrix guardrail** (`scripts/check_traceability.py`,
  `tests/test_traceability.py`, `make traceability`, docs-health CI step):
  validates the control traceability matrix's statuses, library names, code
  links, and issue references (issue #133).

### Changed

- README ecosystem links no longer carry the "placeholder" framing; the library
  list is an accurate table with canonical names, aliases, and `weaver-spec`
  (issue #144).

## [0.1.0] - 2026-06-06

Initial public reference point. The repository runs a fully offline
baseline-vs-governed contrast for a Customer Operations agent.

### Added

- **Unsafe baseline** (`BaselineAgent`) demonstrating the "before" gaps over a
  realistic multi-case workload: full tool catalog every step, raw-output
  leakage, cumulative context growth, poor tool selection, indirect prompt
  injection, missing execution contract, sensitive-data exfiltration,
  durable-log leakage, no aggregate budget, policy-blind writes, audit-light
  logging, and a lost operator correction.
- **Governed control plane** (`GovernedAgent`): bounded capability shortlist
  (context firewall), deterministic flow registry/runner, allow/deny/ask policy
  gate with action classes and a deny-by-default posture, scoped capability
  tokens, separation-of-duties approval handling, bounded output frames, gated
  Frame expansion, and a schema-validated, per-step, tamper-evident audit trace.
- **Offline evaluation lane** (`evals.py`, `evals/`) scoring candidate routers
  and policies against committed golden datasets, wired as a CI regression gate.
- **Lesson-capture stub** (`lessons.py`) staging reviewed lessons.
- Runnable entry points: `make setup`, `make demo`, `make baseline`,
  `make test`, `make eval`.
- Documentation set under `docs/` (architecture, governance model, threat model,
  audit trace, evaluation methodology, adoption path, comparison, glossary, FAQ,
  consultant playbook, roadmap, baseline write-ups) plus `README.md`,
  `PROJECT_SUMMARY.md`, `llms.txt`, and `METADATA.md`.
- Repository health files: `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`,
  `CODE_OF_CONDUCT.md`, `AGENTS.md`, issue templates, and a pull-request template.
- CI workflows: unit tests, the offline evaluation gate, a docs-health check,
  and a VibeGuard placeholder.

### Notes

- The dgenio ecosystem libraries (contextweaver, ChainWeaver, agent-kernel,
  AgentFence, skdr-eval, lessonweaver, VibeGuard) are demonstrated as local
  patterns, not consumed as live dependencies. The only runtime dependency is
  `pydantic`.

<!--
Release process (requires repository admin; not performed automatically):
  git tag -a v0.1.0 -m "v0.1.0"
  git push origin v0.1.0
Then publish a GitHub Release for v0.1.0 whose notes reuse the canonical
description and link the README, the demo, and the docs index.
-->

[Unreleased]: https://github.com/dgenio/enterprise-agent-control-plane/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/dgenio/enterprise-agent-control-plane/releases/tag/v0.1.0
