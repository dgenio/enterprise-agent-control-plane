# Governed-vs-baseline comparison scorecard

Same case run both ways: `refund request` for C-100 / INV-9.
_live baseline and governed runs (numbers derived, not hardcoded)._

| Dimension | Baseline | Governed |
|---|---|---|
| tools exposed to the model | 9 | 5 |
| approx model-visible context (chars) | 1290 | 108 |
| raw sensitive fields in model context | 14 | 0 |
| ungated write/destructive actions | 1 | 0 |
| policy decisions recorded | 0 | 1 |
| structured audit trace | none | yes |

Gated action: `billing.issue_refund` -> **approval_required**.

> Reference comparison only -- not a security benchmark or a production guarantee.
