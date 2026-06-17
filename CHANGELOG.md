# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims
to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This is a runnable **reference architecture and learning repository**, not
production security software. Entries describe what the demo and tests actually
exercise — they make no production-readiness or security claims.

## [Unreleased]

## [0.2.0] - 2026-06-17

### Added

- **VibeGuard diff gate** — replaced the placeholder CI workflow with a real
  offline gate that scans for risky AI-generated changes (two-layer: official
  hygiene patterns + domain-specific rules). Covered by tests and documented in
  [`docs/vibeguard.md`](docs/vibeguard.md).
- **Governed multi-case workload** — `GovernedAgent` now surfaces a full
  multi-case workload with a role matrix, JIT case-scoped capability tokens,
  and a reviewed-lesson loop. Tests and demo entry point updated.
- **Offline evaluation scorecard** — per-case scoring and aggregate scorecard
  output for the governed path.
- **Docs-health CI gate** — checks internal links and enforces the canonical
  description across docs. Negative tests and scoped triggers included.
- **Traceability matrix** — [`docs/control-traceability.md`](docs/control-traceability.md)
  maps each baseline risk to its governed control.
- **Community health files** — `CODE_OF_CONDUCT.md` and `AGENTS.md` operating
  guide for automated contributors.
- **CHANGELOG and CITATION.cff** — enriched metadata and release notes.

### Changed

- Expanded thin documentation pages with summaries and cross-links.

### Fixed

- Enforced case-token scope and unique per-case audit traces in the governed
  path.
- Kept gated actions inside the aggregate budget; clarified Frame-handling
  comments.
- Aligned VibeGuard domain-gate docstring and narrowed the network regex.
- Reworded a synthetic email subject to avoid a SQL false positive in scans.

<!--
Release process (requires repository admin; not performed automatically):
  git tag -a v0.2.0 -m "v0.2.0"
  git push origin v0.2.0
Then publish a GitHub Release for v0.2.0 whose notes reuse the canonical
description and link the README, the demo, and the docs index.
-->

[Unreleased]: https://github.com/dgenio/enterprise-agent-control-plane/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/dgenio/enterprise-agent-control-plane/releases/tag/v0.2.0
[0.1.0]: https://github.com/dgenio/enterprise-agent-control-plane/releases/tag/v0.1.0
