"""Parity tests for the single capability registry (issue #65).

The catalog, full tool definitions, action-class map, and each agent's tool map are all
derived from :data:`registry.CAPABILITY_REGISTRY`. These tests assert the derived views
describe exactly the same capability set with consistent metadata, so adding or renaming a
capability is a single edit that cannot leave one view out of sync.
"""

import unittest

from enterprise_agent_control_plane.catalog import build_catalog, build_tool_definitions
from enterprise_agent_control_plane.policies import ACTION_CLASSES
from enterprise_agent_control_plane.registry import (
    CAPABILITY_REGISTRY,
    build_tool_map,
    tool_capabilities,
)


class TestRegistryParity(unittest.TestCase):
    def test_catalog_views_cover_the_same_tool_capabilities(self):
        tool_caps = {spec.capability for spec in tool_capabilities()}
        self.assertEqual({c.capability for c in build_catalog()}, tool_caps)
        self.assertEqual({t.capability for t in build_tool_definitions()}, tool_caps)
        self.assertEqual(set(build_tool_map()), tool_caps)
        # The model-facing tool surface is the nine Customer Operations capabilities.
        self.assertEqual(len(tool_caps), 9)

    def test_card_and_tool_definition_metadata_match_the_registry(self):
        definitions = {t.capability: t for t in build_tool_definitions()}
        for card in build_catalog():
            spec = CAPABILITY_REGISTRY[card.capability]
            self.assertEqual(card.risk, spec.risk)
            self.assertEqual(card.description, spec.description)
            self.assertEqual(definitions[card.capability].args_schema, dict(spec.args_schema))

    def test_action_classes_are_derived_for_every_registry_capability(self):
        # ACTION_CLASSES covers every capability in the registry, including the control-plane
        # frame.expand capability (issue #114), and agrees with each spec.
        self.assertEqual(set(ACTION_CLASSES), set(CAPABILITY_REGISTRY))
        for cap, spec in CAPABILITY_REGISTRY.items():
            self.assertEqual(ACTION_CLASSES[cap], spec.action_class)

    def test_tool_map_binds_only_capabilities_with_a_callable(self):
        tool_map = build_tool_map()
        for callable_ in tool_map.values():
            self.assertTrue(callable(callable_))
        # frame.expand is control-plane only: it has an action class but no tool callable and
        # is never offered to the model as a pickable catalog entry.
        self.assertIn("frame.expand", ACTION_CLASSES)
        self.assertNotIn("frame.expand", tool_map)
        self.assertNotIn("frame.expand", {c.capability for c in build_catalog()})


if __name__ == "__main__":
    unittest.main()
