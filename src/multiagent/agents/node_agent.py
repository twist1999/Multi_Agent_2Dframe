from __future__ import annotations

import json

from .base import BaseAgent
from ..functions.schema_normalizer import normalize_nodes


class NodeAgent(BaseAgent):
    name = "node_agent"
    prompt_file = "node_agent.txt"

    def run(self, problem_analysis: dict, construction_plan: dict, repair_hint: str | None = None, prompt_override: str | None = None) -> dict:
        base = prompt_override if prompt_override else self.prompt_template
        prompt = (
            f"{base}\n\n"
            f"Problem Analysis JSON:\n{json.dumps(problem_analysis, ensure_ascii=False, indent=2)}\n\n"
            f"Construction Plan JSON:\n{json.dumps(construction_plan, ensure_ascii=False, indent=2)}\n"
        )
        if repair_hint:
            prompt += f"\n{repair_hint}\n"
        result = self.llm_client.run_structured(self.name, prompt, self.model_config)
        if isinstance(result, dict):
            nodes, boundary_conditions = normalize_nodes(result)
            if nodes and "nodes" not in result:
                result = {**result, "nodes": nodes}
            if boundary_conditions and "boundary_conditions" not in result:
                result = {**result, "boundary_conditions": boundary_conditions}
        return result
