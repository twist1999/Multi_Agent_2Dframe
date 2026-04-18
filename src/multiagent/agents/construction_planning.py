from __future__ import annotations

import json

from .base import BaseAgent


class ConstructionPlanningAgent(BaseAgent):
    name = "construction_planning"
    prompt_file = "construction_planning.txt"

    def run(self, problem_analysis: dict) -> dict:
        prompt = f"{self.prompt_template}\n\nProblem Analysis JSON:\n{json.dumps(problem_analysis, ensure_ascii=False, indent=2)}\n"
        return self.llm_client.run_structured(self.name, prompt, self.model_config)
