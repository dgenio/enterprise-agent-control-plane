"""Example: deterministic flow execution (ChainWeaver-style) — issue #62.

What this shows
---------------
A known business path (refund review) is compiled into a deterministic flow whose
read-only prep steps run with no model round-trip between them. The risky write
(``billing.issue_refund``) is deliberately *not* a flow step — it is gated
separately — so running the flow performs only safe preparation.

Maps to
-------
* Module: ``enterprise_agent_control_plane/flows.py``
  (``select_flow``, ``ChainWeaverExecutor``, ``FLOW_REGISTRY``).
* dgenio library: ``ChainWeaver`` (deterministic tool flows).

Run it
------
    python examples/deterministic_flow.py

See ``docs/examples.md`` for the gallery, ``docs/adoption-path.md`` (Step 3) for
where this fits, and ``docs/glossary.md`` for "deterministic flow".
"""

from enterprise_agent_control_plane import fake_tools
from enterprise_agent_control_plane.flows import ChainWeaverExecutor, select_flow
from enterprise_agent_control_plane.registry import build_tool_map


def main() -> None:
    request = "refund request"
    intent, flow_id = select_flow(request)
    print(f"request: {request!r} -> intent={intent}, flow={flow_id}")

    fake_tools.reset_state()
    executor = ChainWeaverExecutor(tools=build_tool_map())
    payload = {"customer_id": "C-100", "invoice_id": "INV-9", "customer_name": "Ari Carter"}

    results = executor.run(flow_id, payload)
    for record in results:
        print(f"  step {record['step']:<16} ({record['capability']}) -> {record['status']}")

    print(f"gated write (not a flow step): {len(fake_tools.REFUNDS)} refund(s) issued by the flow")


if __name__ == "__main__":
    main()
