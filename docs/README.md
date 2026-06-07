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
- [Audit trace](audit-trace.md) — the event schema, per-step events, decision
  provenance, and the tamper-evident (hash-chained) reference pattern.
- [Threat model](threat-model.md) — the baseline risks each control addresses.
- [Control traceability matrix](control-traceability.md) — each baseline risk
  mapped to the governed control, the dgenio library, and the code.
- [VibeGuard gate](vibeguard.md) — the pre-merge diff safety gate that flags
  AI-generated changes which quietly weaken the agent's safety posture.
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

- [Changelog](../CHANGELOG.md) — what has shipped, by version.
- [Roadmap](roadmap.md) — what is planned next.
- [The lesson-capture gap](lesson-capture-gap.md) — a worked baseline "before".
- [Baseline model-stand-in fidelity](baseline-model-fidelity.md) — why the "before"
  gaps are architectural, not artifacts of the deterministic offline stand-in.
- [Baseline incident post-mortem](baseline-incident-postmortem.md) — the baseline gaps
  combined into one realistic, un-investigable incident.
- [Listing snippets](listing-snippets.md) — ready-to-copy descriptions for
  external listings.

## Running it

From the repository root:

```bash
make setup   # install (only dependency: pydantic)
make demo    # run the baseline-vs-governed demo, offline
make test    # run the unit test suite
```
