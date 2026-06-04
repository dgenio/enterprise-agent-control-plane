# Repository metadata (canonical source)

This file is the single source of truth for the repository's public-facing
metadata: the tagline, the GitHub **About** description, the topics, the
homepage URL, and the social-preview plan. Other surfaces — `README.md`,
`pyproject.toml`, `llms.txt`, `docs/listing-snippets.md`, and the GitHub repo
settings — should reuse these values verbatim so they cannot drift.

> This is a runnable **reference architecture and learning repository**, not
> production security software. Keep all metadata honest about that scope.

## Canonical tagline

> Build the same Customer Operations agent two ways — an unsafe baseline vs a
> bounded, policy-gated, auditable control plane — and run the contrast offline.

## GitHub About description (≤120 characters)

Use this verbatim in the repository **About** box:

> Runnable reference architecture for governed enterprise tool-using agents: bounded context, policy gates, audit traces.

## Repository topics (for an admin to apply in repo settings)

Apply these in **Settings → General → Topics** (GitHub allows up to 20; these
are accurate to what the repo actually demonstrates — do not add aspirational
topics):

`ai-agents`, `agent-governance`, `mcp`, `tool-using-agents`,
`agent-control-plane`, `ai-safety`, `deterministic-workflows`, `audit-trail`,
`policy-enforcement`, `reference-architecture`, `llm`, `agent-security`,
`offline-evaluation`

## Homepage URL

Until GitHub Pages is configured (tracked in issue #61), use the repository URL
as the **About → Website** value:

> https://github.com/dgenio/enterprise-agent-control-plane

The in-repo documentation landing page is [`docs/README.md`](docs/README.md);
once Pages publishes it, switch the homepage to the published Pages URL and
update `pyproject.toml`'s `Documentation` URL to match.

## Social preview plan

GitHub social-preview cards render at **1280×640 px** (2:1). The intended card
content (image generation tracked separately under demo assets, issue #53):

- Title: the repository name.
- Subtitle: the canonical tagline above.
- A compact before/after motif: "unsafe baseline → governed control plane".
- Honest footer: "Reference architecture — not production security software."

Until the image exists, the default README/Open Graph preview is acceptable.
