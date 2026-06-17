# Examples gallery

Small, isolated, runnable snippets — one governed capability each — so you can
see a single building block without the full `make demo` walkthrough. Each
example reuses the in-memory fake tools and synthetic fixtures; everything runs
offline with no API keys.

> Reference architecture and learning repository — **not** production security
> software. These snippets demonstrate patterns; they add no security guarantee.

| Example | Shows | Maps to | dgenio library |
|---|---|---|---|
| [`bounded_shortlist.py`](bounded_shortlist.py) | Bounded capability shortlist + context reduction | `catalog.py` | contextweaver |
| [`policy_decisions.py`](policy_decisions.py) | allow / deny / ask policy decisions | `policies.py` | AgentFence |
| [`deterministic_flow.py`](deterministic_flow.py) | Deterministic flow execution (no per-step model loop) | `flows.py` | ChainWeaver |
| [`audit_trace.py`](audit_trace.py) | Structured, tamper-evident audit trace | `audit.py` | agent-kernel |

## Run them

From the repository root, after `make setup`:

```bash
python examples/bounded_shortlist.py
python examples/policy_decisions.py
python examples/deterministic_flow.py
python examples/audit_trace.py
```

See [`docs/examples.md`](../docs/examples.md) for the annotated gallery, the
[recommended adoption path](../docs/adoption-path.md) for where each control fits,
and the [glossary](../docs/glossary.md) for the vocabulary.
