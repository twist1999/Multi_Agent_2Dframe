from __future__ import annotations

import time

from multiagent.config import PipelineConfig
from multiagent.pipeline import StructuralModelingPipeline
from multiagent.state import PipelineState


class SlowNodeAgent:
    def run(self, *args, **kwargs) -> dict:
        time.sleep(0.35)
        return {
            "nodes": [
                {"id": 1, "x": 0.0, "y": 0.0},
                {"id": 2, "x": 5.0, "y": 0.0},
                {"id": 3, "x": 0.0, "y": 3.0},
                {"id": 4, "x": 5.0, "y": 3.0},
            ],
            "boundary_conditions": [
                {"node_id": 1, "constraints": "fixed"},
                {"node_id": 2, "constraints": "fixed"},
            ],
        }


class SlowElementAgent:
    def run(self, *args, **kwargs) -> dict:
        time.sleep(0.35)
        return {
            "elements": [
                {"id": 1, "node_i": 1, "node_j": 3, "type": "column"},
                {"id": 2, "node_i": 2, "node_j": 4, "type": "column"},
                {"id": 3, "node_i": 1, "node_j": 2, "type": "beam"},
                {"id": 4, "node_i": 3, "node_j": 4, "type": "beam"},
            ]
        }


def test_geometry_agents_run_in_parallel_before_mapping():
    config = PipelineConfig(write_outputs=False)
    config.rl.enabled = False
    pipeline = StructuralModelingPipeline(config)
    pipeline.node_agent = SlowNodeAgent()
    pipeline.element_agent = SlowElementAgent()

    state = PipelineState(user_input="one-bay one-story frame")
    state.problem_analysis = {
        "geometry": {
            "Total_bays": 1,
            "Total_stories": 1,
            "bay_widths": [5.0],
            "story_heights": [3.0],
        }
    }
    state.construction_plan = {
        "Construction_steps": [
            {"Step_number": 1, "Bay_number": 1, "Story_number": 1, "Step_type": "frame"}
        ]
    }

    started = time.perf_counter()
    pipeline._run_geometry_assembly(state)
    elapsed = time.perf_counter() - started

    assert elapsed < 0.6
    assert state.node_output is not None
    assert state.element_output is not None
    assert state.mapped_geometry is not None
    assert len(state.mapped_geometry["nodes"]) == 4
    assert len(state.mapped_geometry["elements"]) == 4
