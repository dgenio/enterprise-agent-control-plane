# Roadmap — what is planned next

The intended direction for this reference architecture, grouped by theme. This
is a learning/portfolio reference, so the roadmap favors clearer demonstrations
and honest framing over production hardening.

> This remains a reference architecture and learning repository — **not**
> production security software. Roadmap items add demonstration value, not
> security guarantees.

## Ecosystem integration

- Restructure into two runnable implementations — a `plain` build with no dgenio
  dependencies and a `with_ecosystem` build that consumes the Weaver Stack
  libraries (contextweaver, ChainWeaver, agent-kernel, AgentFence, skdr-eval,
  lessonweaver, VibeGuard) as real dependencies, so the contrast is "the
  governance code you delete when you adopt the stack".
- Replace the in-repo stubs with direct integrations behind an MCP boundary.

## Governance depth

- Just-in-time, case-scoped capability tokens with expiry, rather than standing
  role grants.
- Role-differentiated decisions demonstrated across all principals.

Shipped: flow and policy definitions now load from the `flows/` and `policies/` YAML as the
single runtime source of truth (issue #3), and deterministic flow steps validate their inputs
against a declared schema before running (issues #4/#162). See the
[Changelog](../CHANGELOG.md).

## Evaluation & lessons

- Expand the evaluation datasets and add a trace-replay harness.
- Demonstrate a human-reviewed lesson changing a candidate policy while
  unreviewed lessons stay inert.

## Demo, docs & CI

- A generated baseline-vs-governed comparison scorecard artifact.
- A real VibeGuard pre-merge gate replacing the placeholder workflow.
- Shareable demo assets and a published docs homepage.

Items are tracked as individual GitHub issues; see the
[issues list](https://github.com/dgenio/enterprise-agent-control-plane/issues)
for current status and priorities.

## Related

- [Architecture](architecture.md) — the current module and data-flow map.
- [Recommended adoption path](adoption-path.md) — how the controls layer today.
- [Changelog](../CHANGELOG.md) — what has shipped so far.
- [Docs index](README.md) — the full documentation map.
