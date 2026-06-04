# Evaluation lane

Offline evaluation inputs used to score routing and policy candidates before deployment —
the dependency-free stand-in for `skdr-eval`. See `docs/evaluation-methodology.md` for the
full methodology.

## Datasets

- `sample_routing_logs.csv` — golden routing expectations per candidate router
  (`route_v1` / `route_v2`). **Generated** from the real routers, so it never drifts from
  the code. Regenerate with `python -m enterprise_agent_control_plane.evals --generate`.
- `sample_policy_decisions.csv` — golden `principal, capability, amount → expected_decision`
  cases replayed through `AgentFencePolicy`.

## Running

```bash
make eval
```

Prints router accuracy and policy-decision accuracy, flags any unsafe drift (expected
`deny`/`ask` but `allow`), and exits non-zero on a regression. The `evals` CI workflow runs
this on every push and pull request as a regression gate.
