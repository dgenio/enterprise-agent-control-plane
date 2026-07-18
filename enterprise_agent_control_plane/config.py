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


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"required config file {path} is missing; the YAML files are the single source of "
            f"truth (issue #3) and must be present (they ship at the repo root, resolved under "
            f"the editable install)."
        )
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        # Surface the offending file with the parser error rather than a bare YAMLError; this
        # runs at import time, so the message must point at the file the reader has to fix.
        raise ValueError(f"config file {path} is not valid YAML: {exc}") from exc
    if data is None:
        raise ValueError(f"config file {path} is empty or not valid YAML")
    if not isinstance(data, dict):
        # Every config file in this repo is a top-level mapping; a list/scalar would otherwise
        # blow up later with an opaque AttributeError on ``.get``.
        raise ValueError(
            f"config file {path} must contain a top-level mapping, got {type(data).__name__}"
        )
    return data


def load_flow_definitions() -> dict[str, dict[str, Any]]:
    """Parse every ``flows/*.flow.yaml`` into ``{flow_id: {steps, gated_capabilities}}`` (#3).

    Keyed and returned in ``flow_id`` order so the registry is deterministic regardless of
    filesystem enumeration order.
    """
    flows: dict[str, dict[str, Any]] = {}
    for path in sorted(FLOWS_DIR.glob("*.flow.yaml")):
        data = _load_yaml(path)  # guaranteed a top-level mapping, or raises with the path
        # Fail loudly with the file and field named -- this runs at import time via
        # FLOW_REGISTRY, so a malformed file (steps as a mapping, a scalar step) must give a
        # diagnostic error, not a raw TypeError/AttributeError.
        flow_id = data.get("flow_id")
        if not flow_id:
            raise ValueError(f"{path} is missing a 'flow_id'")
        if flow_id in flows:
            raise ValueError(f"duplicate flow_id {flow_id!r} (also defined in another file)")
        steps = data.get("steps") or []
        if not isinstance(steps, list):
            raise ValueError(f"{path}: 'steps' must be a list, got {type(steps).__name__}")
        parsed_steps: list[tuple[str, str]] = []
        for index, step in enumerate(steps):
            if not isinstance(step, dict) or "name" not in step or "capability" not in step:
                raise ValueError(
                    f"{path}: step {index} must be a mapping with a 'name' and a 'capability'"
                )
            parsed_steps.append((step["name"], step["capability"]))
        gated = data.get("gated_capabilities") or []
        if not isinstance(gated, list):
            raise ValueError(
                f"{path}: 'gated_capabilities' must be a list, got {type(gated).__name__}"
            )
        flows[flow_id] = {"steps": parsed_steps, "gated_capabilities": tuple(gated)}
    return dict(sorted(flows.items()))


def load_agentfence_policy() -> dict[str, Any]:
    """The AgentFence policy rules: action-class decisions, thresholds, restrictions (#3)."""
    return _load_yaml(POLICIES_DIR / "agentfence.policy.yaml")


def load_capability_policy() -> dict[str, Any]:
    """The per-principal capability grants (issue #3)."""
    return _load_yaml(POLICIES_DIR / "capability_policy.yaml")
