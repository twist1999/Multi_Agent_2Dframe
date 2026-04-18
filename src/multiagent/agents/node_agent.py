from __future__ import annotations

import json

from .base import BaseAgent


class NodeAgent(BaseAgent):
    name = "node_agent"
    prompt_file = "node_agent.txt"

    def run(self, problem_analysis: dict, construction_plan: dict) -> dict:
        prompt = (
            f"{self.prompt_template}\n\n"
            f"Problem Analysis JSON:\n{json.dumps(problem_analysis, ensure_ascii=False, indent=2)}\n\n"
            f"Construction Plan JSON:\n{json.dumps(construction_plan, ensure_ascii=False, indent=2)}\n"
        )
        return self.llm_client.run_structured(self.name, prompt, self.model_config)
