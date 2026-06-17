"""Example: bounded capability shortlist (contextweaver-style) — issue #62.

What this shows
---------------
A naive agent pastes the *full* tool catalog into model context on every step.
The governed path surfaces only a small, relevant shortlist of capabilities, so
model-visible context stays narrow. This example runs the shortlist over the
catalog for a refund request and prints the measured context reduction.

Maps to
-------
* Module: ``enterprise_agent_control_plane/catalog.py``
  (``build_catalog``, ``shortlist_capabilities``, ``context_reduction``).
* dgenio library: ``contextweaver`` (budget-aware context firewall / bounded shortlist).

Run it
------
    python examples/bounded_shortlist.py

See ``docs/examples.md`` for the gallery, ``docs/adoption-path.md`` (Step 1) for
where this fits, and ``docs/glossary.md`` for the term "bounded context / shortlist".
"""

from enterprise_agent_control_plane.catalog import (
    build_catalog,
    build_tool_definitions,
    context_reduction,
    shortlist_capabilities,
)


def main() -> None:
    request = "refund request for a paid invoice"
    catalog = build_catalog()
    shortlist = shortlist_capabilities(request, catalog, limit=4)

    print(f"request: {request!r}")
    print(f"full catalog: {len(catalog)} capabilities")
    print(f"shortlist:    {len(shortlist)} capabilities -> {[c.capability for c in shortlist]}")

    reduction = context_reduction(shortlist, build_tool_definitions())
    print(
        "model-visible context: "
        f"{reduction['full_catalog_chars']} chars (full catalog) -> "
        f"{reduction['shortlist_chars']} chars (shortlist) "
        f"= {reduction['reduction_pct']}% smaller"
    )


if __name__ == "__main__":
    main()
