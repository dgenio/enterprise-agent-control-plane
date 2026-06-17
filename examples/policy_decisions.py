"""Example: allow / deny / ask policy decisions (AgentFence-style) — issue #62.

What this shows
---------------
The policy gate classifies each capability and returns ``allow``, ``deny``, or
``ask`` (approval required) *before* a risky action can run, with a
deny-by-default posture for anything it does not recognise. This example evaluates
one capability per outcome so all three branches are visible side by side.

Maps to
-------
* Module: ``enterprise_agent_control_plane/policies.py``
  (``AgentFencePolicy.evaluate``, ``ACTION_CLASSES``, ``PolicyDecision``).
* dgenio library: ``AgentFence`` (policy firewall) with ``agent-kernel`` action classes.

Run it
------
    python examples/policy_decisions.py

See ``docs/examples.md`` for the gallery, ``docs/adoption-path.md`` (Step 2) for
where this fits, and ``docs/glossary.md`` for "policy gate (allow / deny / ask)".
"""

from enterprise_agent_control_plane.policies import AgentFencePolicy


def main() -> None:
    policy = AgentFencePolicy()

    # One call per outcome: a read is allowed; a refund above the manager limit is denied;
    # a refund within the manager band requires approval (ask).
    cases = [
        ("crm.search_customer", "support_agent", {}),
        ("billing.issue_refund", "support_agent", {"amount": 1000.0}),
        ("billing.issue_refund", "support_agent", {"amount": 149.0}),
    ]

    for capability, principal, args in cases:
        decision = policy.evaluate(capability, principal, args)
        print(f"{capability} (args={args or '{}'}) -> {decision.decision.upper()}")
        print(f"    reason: {decision.reason}")


if __name__ == "__main__":
    main()
