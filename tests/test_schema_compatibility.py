from __future__ import annotations

import unittest

from multiagent.functions.connectivity_mapping import map_connectivity
from multiagent.functions.schema_normalizer import normalize_elements, normalize_nodes
from multiagent.validators.checkpoints import validate_analysis_planning, validate_geometry


class SchemaCompatibilityTests(unittest.TestCase):
    def test_analysis_planning_accepts_lowercase_bay_story_schema(self) -> None:
        problem_analysis = {
            "geometry": {
                "bays": [
                    {"bay_number": 1, "stories": [{"height": 4.0}, {"height": 5.0}]},
                    {"bay_number": 2, "story_heights_m": [4.0]},
                ]
            }
        }
        construction_plan = {
            "construction_steps": [
                {"step_number": 1, "bay_number": 1, "story_number": 1, "step_type": "column"},
                {"step_number": 2, "bay_number": 1, "story_number": 2, "step_type": "girder"},
                {"step_number": 3, "bay_number": 2, "story_number": 1, "step_type": "column"},
            ]
        }

        result = validate_analysis_planning(problem_analysis, construction_plan)

        self.assertTrue(result.ok, result.errors)

    def test_normalizes_node_generation_variants(self) -> None:
        node_output = {
            "steps": [
                {
                    "added_nodes": [{"id": "N1", "x": 0, "y": 0}],
                    "added_boundary_conditions": [{"node_id": "N1", "type": "fixed"}],
                },
                {
                    "created_nodes": [{"node_id": 2, "x_m": 0, "y_m": 4}],
                    "applied_boundary_conditions": [],
                },
                {
                    "nodes": {"3": [4, 0]},
                    "created": [{"type": "node", "id": 4, "x": 4, "y": 4}],
                },
            ]
        }

        nodes, boundary_conditions = normalize_nodes(node_output)

        self.assertEqual({node["id"] for node in nodes}, {1, 2, 3, 4})
        self.assertEqual(boundary_conditions[0]["node_id"], 1)

    def test_geometry_accepts_element_variants_and_maps_connectivity(self) -> None:
        node_output = {
            "nodes": [
                {"id": 1, "x": 0, "y": 0},
                {"id": 2, "x": 0, "y": 4},
                {"id": 3, "x": 4, "y": 4},
            ]
        }
        element_output = {
            "construction_sequence": [
                {"Element": {"id": "E1", "type": "column", "nodes": [1, 2]}},
                {
                    "created": [
                        {"type": "beam", "id": "G1", "node1": 2, "node2": 3},
                    ]
                },
            ]
        }

        result = validate_geometry(node_output, element_output)
        mapped = map_connectivity(node_output, element_output)

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(len(mapped["elements"]), 2)

    def test_rejects_elements_without_connectivity(self) -> None:
        elements = normalize_elements(
            {
                "element_definitions": [
                    {"element_id": 1, "type": "column", "bay": 1, "story": 1, "length_m": 4.0}
                ]
            }
        )

        self.assertEqual(elements, [])


if __name__ == "__main__":
    unittest.main()
