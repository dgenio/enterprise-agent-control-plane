"""Parity guard: the YAML config is the single source of truth and stays anchored to the
registry (issues #148, #3).

Since #3 makes the YAML authoritative at runtime, this is the guard #148 asked for in its
end-state form (its body scoped itself "until #3 lands"): it fails if a ``flows/*.flow.yaml``
or ``policies/*.yaml`` file drifts from the authoritative capability registry, and it proves a
change made *only* in YAML is what the runtime actually uses.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from enterprise_agent_control_plane import config, flows
from enterprise_agent_control_plane.flows import FLOW_REGISTRY
from enterprise_agent_control_plane.policies import (
    ACTION_CLASSES,
    PRINCIPAL_RESTRICTED,
    REFUND_AUTO_LIMIT,
    REFUND_MANAGER_LIMIT,
    ROLE_GRANTS,
)
from enterprise_agent_control_plane.registry import CAPABILITY_REGISTRY


class TestFlowYamlParity(unittest.TestCase):
    def test_flow_registry_matches_the_yaml_files(self):
        # The in-memory registry is exactly what the YAML declares -- proving the YAML, not a
        # Python mirror, built it.
        yaml_flows = config.load_flow_definitions()
        self.assertEqual(set(FLOW_REGISTRY), set(yaml_flows))
        for flow_id, spec in yaml_flows.items():
            flow = FLOW_REGISTRY[flow_id]
            self.assertEqual([(s.name, s.capability) for s in flow.steps], spec["steps"])
            self.assertEqual(flow.gated_capabilities, spec["gated_capabilities"])

    def test_every_flow_capability_is_a_registry_capability(self):
        for flow in FLOW_REGISTRY.values():
            for step in flow.steps:
                self.assertIn(step.capability, CAPABILITY_REGISTRY, f"{flow.flow_id}:{step.name}")
            for cap in flow.gated_capabilities:
                self.assertIn(cap, CAPABILITY_REGISTRY, f"{flow.flow_id} gated {cap}")


class TestPolicyYamlParity(unittest.TestCase):
    def test_policy_capability_map_mirrors_the_registry_action_classes(self):
        # The registry is authoritative for capability -> action class (issue #65); the policy
        # YAML carries a mirror for documentation, and this guard fails if it drifts (Q1 design
        # decision recorded in AGENTS.md).
        yaml_caps = config.load_agentfence_policy()["capabilities"]
        self.assertEqual(set(yaml_caps), set(ACTION_CLASSES))
        for cap, action_class in yaml_caps.items():
            self.assertEqual(action_class, ACTION_CLASSES[cap], cap)

    def test_restricted_and_thresholds_match_the_yaml(self):
        policy = config.load_agentfence_policy()
        yaml_restricted = {cap: set(p) for cap, p in policy["restricted"].items()}
        self.assertEqual(PRINCIPAL_RESTRICTED, yaml_restricted)
        for cap in yaml_restricted:
            self.assertIn(cap, CAPABILITY_REGISTRY, cap)
        thresholds = policy["thresholds"]["billing.issue_refund"]
        self.assertEqual(REFUND_AUTO_LIMIT, float(thresholds["refund_auto_limit"]))
        self.assertEqual(REFUND_MANAGER_LIMIT, float(thresholds["refund_manager_limit"]))

    def test_role_grants_match_the_yaml_and_name_real_capabilities(self):
        principals = config.load_capability_policy()["principals"]
        yaml_grants = {name: set(cfg["grants"]) for name, cfg in principals.items()}
        self.assertEqual(ROLE_GRANTS, yaml_grants)
        for role, grants in yaml_grants.items():
            for cap in grants:
                self.assertIn(cap, CAPABILITY_REGISTRY, f"{role} grants unknown {cap}")


class TestYamlIsTheRuntimeSourceOfTruth(unittest.TestCase):
    def test_a_flow_change_made_only_in_yaml_is_reflected_at_runtime(self):
        # Issue #3 acceptance criterion: edit only the YAML, and the runtime registry changes.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            (tmp_dir / "probe.flow.yaml").write_text(
                "flow_id: probe\n"
                "steps:\n"
                "  - name: lookup_customer\n"
                "    capability: crm.search_customer\n"
                "gated_capabilities:\n"
                "  - billing.issue_refund\n",
                encoding="utf-8",
            )
            with mock.patch.object(config, "FLOWS_DIR", tmp_dir):
                rebuilt = flows._build_flow_registry()
        self.assertEqual(set(rebuilt), {"probe"})
        self.assertEqual([s.capability for s in rebuilt["probe"].steps], ["crm.search_customer"])
        self.assertEqual(rebuilt["probe"].gated_capabilities, ("billing.issue_refund",))


if __name__ == "__main__":
    unittest.main()
