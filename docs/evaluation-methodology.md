# Evaluation methodology

How candidate routers and policies are scored offline, before any change is enabled — the
dependency-free stand-in for `skdr-eval`.

## Two offline lanes

Both lanes run with no model, no network, and no API keys. They live in
`enterprise_agent_control_plane/evals.py` and read committed datasets from `evals/`.

### Router lane (`evals/sample_routing_logs.csv`)

Each candidate router (`route_v1`, `route_v2`) is replayed over a small golden set of
queries and scored on how often its routed sequence matches the expected one. The two
routers agree on the refund and escalation paths and diverge only on the email path, where
the safer expectation is to *draft* the reply rather than *send* it — the change `route_v2`
made and `route_v1` did not. So `route_v2` scores 100% and `route_v1` misses the email case.

The dataset is **generated from the real routers** (`python -m
enterprise_agent_control_plane.evals --generate`), so it cannot drift away from the code it
describes; a test asserts the committed file still matches the routers.

### Policy lane (`evals/sample_policy_decisions.csv`)

A golden set of `principal, capability, amount → expected_decision` cases is replayed through
`AgentFencePolicy`. The lane reports per-decision accuracy and highlights **unsafe drift** —
a case the golden set expected to be `deny`/`ask` that a candidate policy would `allow`
(for example, widening a refund threshold so a large refund auto-approves).

## Regression gate

`make eval` (or `python -m enterprise_agent_control_plane.evals`) prints both comparisons and
exits non-zero when a router falls below its committed accuracy floor or any golden policy
decision flips. The `evals` CI workflow runs it on every push and pull request, so routing and
policy changes cannot merge an unevaluated regression.

## Future `skdr-eval` integration

`skdr-eval` formalises this pattern (candidate scoring, richer metrics, trace replay). The
integration point is `evals.py`: the committed datasets and the `evaluate_routers` /
`evaluate_policy` entry points map onto its offline-scoring API. This remains a reference
pattern, not a production evaluation harness.
