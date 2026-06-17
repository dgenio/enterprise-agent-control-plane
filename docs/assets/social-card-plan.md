# Social preview card — plan

The plan for the GitHub social-preview card (issue #53). This documents the
intended card so it can be produced consistently; the image itself is tracked
separately. Until the image exists, the default README/Open Graph preview is
acceptable (consistent with [`METADATA.md`](../../METADATA.md)).

## Dimensions

- **1280 × 640 px** (2:1), the size GitHub renders for social previews.
- Keep critical content within a ~1200 × 600 safe area for cropping.

## Content

- **Title:** `enterprise-agent-control-plane`.
- **Subtitle (canonical tagline):** "Build the same Customer Operations agent two
  ways — an unsafe baseline vs a bounded, policy-gated, auditable control plane —
  and run the contrast offline."
- **Before/after motif:** a compact "unsafe baseline → governed control plane"
  arrow, optionally with the scorecard contrast (9 → 5 tools, 1290 → 108 chars).
- **Honest footer:** "Reference architecture — not production security software."

## Producing it

When the card is generated, save it as `social-card.png` in this directory and set
it as the repository's social preview (Settings → General → Social preview). Keep
the wording identical to the canonical tagline in [`METADATA.md`](../../METADATA.md)
so the card cannot drift from the other surfaces.
