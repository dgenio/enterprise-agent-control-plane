# Listing snippets

Ready-to-copy, accurate descriptions of this repository at a few lengths, for
external listings (awesome lists, directories, blog/LinkedIn intros). All reuse
the canonical tagline from [`METADATA.md`](../METADATA.md) and preserve the
reference-architecture (non-production) framing. Keep these in sync with
`METADATA.md` if the tagline changes.

## One-liner (GitHub About / awesome-list entry)

> Runnable reference architecture for governed enterprise tool-using agents: bounded context, policy gates, audit traces.

## Short paragraph (blog / LinkedIn intro)

> enterprise-agent-control-plane is a runnable reference architecture for
> governed enterprise tool-using agents. Build the same Customer Operations
> agent two ways — an unsafe baseline vs a bounded, policy-gated, auditable
> control plane — and run the contrast offline. It demonstrates bounded context
> shortlisting, deterministic flows, capability tokens, an allow/deny/ask
> policy gate, and structured audit traces. It is a learning/reference project,
> not production security software.

## Longer summary (directory submission)

> **enterprise-agent-control-plane** — a runnable reference architecture for
> governing enterprise tool-using agents. It contrasts an intentionally unsafe
> baseline (full tool catalog every step, raw outputs forwarded into context,
> writes with no gate, flat logs) against a governed control plane that
> shortlists relevant capabilities, runs deterministic flows, gates risky
> actions through capability tokens and an allow/deny/ask policy, returns a
> bounded output frame, and emits a structured audit trace. The demo runs both
> on the same scenario offline and prints a side-by-side contrast. The
> governance patterns map to the dgenio ecosystem (contextweaver, ChainWeaver,
> agent-kernel, AgentFence, skdr-eval, lessonweaver, VibeGuard).
>
> Topics: ai-agents, agent-governance, mcp, tool-using-agents,
> agent-control-plane, ai-safety, deterministic-workflows, audit-trail,
> policy-enforcement, reference-architecture, llm, agent-security,
> offline-evaluation.
>
> This is a reference architecture and learning repository, not production
> security software and not a hardening guide.
