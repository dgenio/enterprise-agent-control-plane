# Documentation

**enterprise-agent-control-plane** is a runnable reference architecture for
governed enterprise tool-using agents. Build the same Customer Operations agent
two ways — an unsafe baseline vs a bounded, policy-gated, auditable control
plane — and run the contrast offline. This page is the entry point to the
documentation; start here, then follow the links below.

> Reference architecture and learning repository — **not** production security
> software. See [`SECURITY.md`](../SECURITY.md).

## Start here

- [Project summary](../PROJECT_SUMMARY.md) — one-page overview of purpose,
  architecture, and commands.
- [Glossary](glossary.md) — canonical definitions of the core vocabulary,
  linked to where each term lives in the code.
- [FAQ](faq.md) — direct answers to common agent-governance questions.

## Architecture & governance

- [Architecture](architecture.md) — the module/data-flow map: catalog →
  shortlist → flow → policy → audit.
- [Governance model](governance-model.md) — action classes, allow/deny/ask
  decisions, capability tokens, and audit.
- [Threat model](threat-model.md) — the baseline risks each control addresses.
- [Evaluation methodology](evaluation-methodology.md) — offline scoring of
  candidate routers and policies.

## Adopting & comparing

- [Recommended adoption path](adoption-path.md) — how to layer the architecture
  one control at a time.
- [Comparison](comparison.md) — how this reference architecture relates to plain
  agent loops, workflow engines, hosted gateways, and ad hoc MCP setups.
- [Consultant playbook](consultant-playbook.md) — applying the pattern in an
  engagement.

## Project direction & reuse

- [Roadmap](roadmap.md) — what is planned next.
- [The lesson-capture gap](lesson-capture-gap.md) — a worked baseline "before".
- [Listing snippets](listing-snippets.md) — ready-to-copy descriptions for
  external listings.

## Running it

From the repository root:

```bash
make setup   # install (only dependency: pydantic)
make demo    # run the baseline-vs-governed demo, offline
make test    # run the unit test suite
```
