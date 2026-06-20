# Security policy

## Scope: this is a reference architecture, not production security software

**enterprise-agent-control-plane** is a runnable **reference architecture and
learning repository**. It demonstrates governance *patterns* for tool-using
agents — bounded context, deterministic flows, policy gates, capability tokens,
and audit traces — using **synthetic, in-memory tools and data**.

It is **not**:

- production security software or a hardened gateway,
- a security hardening guide,
- a source of any security guarantee.

There is intentionally unsafe code in this repository (the "baseline" agent) so
the contrast with the governed path is concrete. The fake tools and data
(`enterprise_agent_control_plane/fake_tools.py`, fixtures, sample logs) are
illustrative only and contain no real credentials, PII, or live endpoints.

See the "What this repo is / is not" section of the [README](README.md) and the
[FAQ](docs/faq.md) for the full framing.

## Supply-chain hygiene

A governance reference is judged partly on its own supply-chain posture, so the
repository models the hygiene it advocates (issue #152):

- **Pinned GitHub Actions.** Every workflow pins each `uses:` action to a full
  commit SHA (with a version comment), not a floating tag.
- **Dependabot.** [`.github/dependabot.yml`](.github/dependabot.yml) keeps the
  `github-actions` and `pip` ecosystems current weekly, including bumping the
  SHA-pinned actions.
- **CodeQL.** [`.github/workflows/codeql.yml`](.github/workflows/codeql.yml)
  runs code scanning on pushes, pull requests, and a weekly schedule.

This is defensive hygiene for example code, not a production-hardening claim.

## Reporting a problem in the example code

This project does not run a formal vulnerability-disclosure program and offers
no response SLA. If you spot a bug, an inaccuracy, or a way the example code
could mislead a reader:

- **Open a GitHub issue:** https://github.com/dgenio/enterprise-agent-control-plane/issues

Please keep reports focused on the example code and documentation. Because all
tools and data here are synthetic and the project is not deployed anywhere,
there is no production system to compromise.
