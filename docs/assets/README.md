# Demo & sharing assets

Shareable, externally-referenceable assets for the before/after story (issue #53).
These live in one predictable place so the README and external listings can point
at them.

> Reference architecture and learning repository — **not** production security
> software.

## Contents

- [`architecture.mmd`](architecture.mmd) — Mermaid source for the baseline-vs-governed
  architecture diagram. Render to SVG/PNG with the Mermaid CLI
  (`mmdc -i architecture.mmd -o architecture.svg`) for non-GitHub embeds.
- [`demo-output.txt`](demo-output.txt) — a captured, annotated excerpt of `make demo`,
  suitable for embedding in slides or posts. Numbers are from real offline runs.
- [`social-card-plan.md`](social-card-plan.md) — dimensions and intended content for the
  GitHub social-preview card (image tracked separately).

## Notes

- Diagrams are kept as Mermaid source so they stay reviewable in-repo; export an image
  only when an external embed needs one.
- Do not fabricate demo output — recapture `demo-output.txt` from a real `make demo` run
  if the demo changes.

See the [docs index](../README.md) and [CLAIMS.md](../../CLAIMS.md) for where these
assets are referenced.
