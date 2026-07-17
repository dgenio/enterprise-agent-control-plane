"""Load flow and policy definitions from YAML as the single runtime source of truth (#3).

The repo ships ``flows/*.flow.yaml`` and ``policies/*.yaml`` that used to be inert -- the
runtime hardcoded equivalent Python dicts and the YAML only documented them, so the two
could (and did) drift. This module makes the YAML authoritative: :mod:`flows` builds its
``FLOW_REGISTRY`` from :func:`load_flow_definitions`, and :mod:`policies` reads its thresholds,
principal restrictions, and role grants from :func:`load_agentfence_policy` /
:func:`load_capability_policy`.

Scope, per the design decision recorded in ``AGENTS.md``: the YAML owns the *policy rules and
flow structure*; the capability -> action-class assignment stays authoritative in
:mod:`registry` (issue #65) and the policy YAML merely mirrors it under a CI parity guard
(``tests/test_yaml_parity.py``, issue #148). This deliberately does not introduce an evaluated
rule language -- that is the separate big-swing issue #182.

Path resolution: the YAML lives at the repository root (``flows/``, ``policies/``), one level
above this package, not inside it -- so it is resolved relative to the repo root and is
available under the editable install the project uses everywhere (``make setup``,
CONTRIBUTING.md). A missing or malformed file raises loudly rather than silently falling back
to a stale default, since a silent fallback would recreate exactly the drift issue #3 removes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def repo_root() -> Path:
    """The repository root -- one level above this package (mirrors scripts/vibeguard_gate.py)."""
    return Path(__file__).resolve().parents[1]


FLOWS_DIR = repo_root() / "flows"
POLICIES_DIR = repo_root() / "policies"


def _load_yaml(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(
            f"required config file {path} is missing; the YAML files are the single source of "
            f"truth (issue #3) and must be present (they ship at the repo root, resolved under "
            f"the editable install)."
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        raise ValueError(f"config file {path} is empty or not valid YAML")
    return data


def load_flow_definitions() -> dict[str, dict[str, Any]]:
    """Parse every ``flows/*.flow.yaml`` into ``{flow_id: {steps, gated_capabilities}}`` (#3).

    Keyed and returned in ``flow_id`` order so the registry is deterministic regardless of
    filesystem enumeration order.
    """
    flows: dict[str, dict[str, Any]] = {}
    for path in sorted(FLOWS_DIR.glob("*.flow.yaml")):
        data = _load_yaml(path)
        flow_id = data.get("flow_id")
        if not flow_id:
            raise ValueError(f"{path} is missing a 'flow_id'")
        if flow_id in flows:
            raise ValueError(f"duplicate flow_id {flow_id!r} (also defined in another file)")
        steps = data.get("steps") or []
        for step in steps:
            if "name" not in step or "capability" not in step:
                raise ValueError(f"{path}: every step needs a 'name' and a 'capability'")
        flows[flow_id] = {
            "steps": [(s["name"], s["capability"]) for s in steps],
            "gated_capabilities": tuple(data.get("gated_capabilities") or ()),
        }
    return dict(sorted(flows.items()))


def load_agentfence_policy() -> dict[str, Any]:
    """The AgentFence policy rules: action-class decisions, thresholds, restrictions (#3)."""
    return _load_yaml(POLICIES_DIR / "agentfence.policy.yaml")


def load_capability_policy() -> dict[str, Any]:
    """The per-principal capability grants (issue #3)."""
    return _load_yaml(POLICIES_DIR / "capability_policy.yaml")
