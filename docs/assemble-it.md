# Portfolio role: ASSEMBLE IT

The Enterprise Agent Control Plane has one portfolio job: **ASSEMBLE IT**.

It is a reference architecture for showing that independently useful governance components can compose on the same realistic synthetic workflow. It should not be the first repository used to convince someone that the individual components are valuable.

## Sequence in the portfolio

1. `mcp-agent-security-dojo` — **BREAK IT**: reproduce security failures and compare mitigations.
2. `agent-routing-eval-lab` — **MEASURE IT**: evaluate routing-policy changes from logged evidence.
3. this repo — **ASSEMBLE IT**: compose controls that have already earned their place.

The Control Plane may remain partially deferred until the upstream components have meaningful native/external evidence. An impressive architecture diagram is not a substitute for downstream pull.

## Core experiment

Implement the same Customer Operations scenario twice:

- **plain** — competent in-house governance with no dgenio runtime dependencies;
- **with ecosystem** — the same domain, tools, fixtures and expected invariants, delegating relevant responsibilities to actual OSS components.

The plain implementation is not a strawman. A competent team should be able to look at it and say, "yes, we could reasonably build and maintain this ourselves."

## Minimal initial ecosystem surface

Use only components the scenario genuinely needs and whose standalone value has evidence upstream:

- `contextweaver` — bounded context / capability shortlist;
- `chainweaver` — deterministic known-path execution;
- `weaver-kernel` / agent-kernel — scoped authorization;
- AgentFence — real Go/sidecar policy boundary over tool calls;
- `weaver-spec` only when a shared contract is actually required.

Do not make `skdr-eval`, `lessonweaver`, VibeGuard, or every sibling project mandatory simply to make the architecture look complete.

## Fair comparison standard

Run both implementations against identical synthetic inputs and compare **behavioral invariants**:

- can an unauthorized principal execute a money-moving write?
- can untrusted tool output steer a forbidden action?
- can sensitive raw values reach model-visible context?
- are risky writes authorization/policy checked and evidenced?
- do legitimate authorized actions still succeed?
- do known business processes execute deterministically and fail closed when prerequisites fail?
- what happens when a tool schema, policy or dependency changes?
- which responsibilities remain local maintenance and which are delegated to a component?

Lines of code, dependency counts, package size and similar statistics may be supplementary. Because this repo controls both implementations, they are too easy to game to serve as headline proof.

## Real-mode integrity

A real ecosystem run must record component version or commit provenance and must actually execute the component or AgentFence boundary. If an integration is unavailable, report it as unavailable. Never silently fall back to local code and label the result as real.

## Scope guardrails

Until the core comparison has external pull, do not prioritize:

- new domains or scenario galleries;
- multi-tenancy or multi-agent workflow products;
- real-model/provider integrations;
- hosted control-plane services;
- workshop/content/discoverability programs;
- Pages sites or packaging the reference architecture as a product;
- standards/compliance mappings as evidence;
- framework adapters or policy-language expansion;
- integrations whose primary value belongs in another lab.

Reliability work that strengthens the existing reference—fail-closed behavior, redaction completeness, policy/audit correctness, deterministic fixtures, schema parity and property tests—remains valuable.

## Decision rule

Broaden the architecture only when a real integration or external adopter exposes a repeated composition need. If the upstream components never develop external pull, leaving this as a smaller, honest reference is preferable to building a self-referential platform.
