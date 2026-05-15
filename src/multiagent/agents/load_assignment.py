from __future__ import annotations

import json

from .base import BaseAgent


class LoadAssignmentAgent(BaseAgent):
    name = "load_assignment"
    prompt_file = "load_assignment.txt"

    def run(self, problem_analysis: dict, mapped_geometry: dict, repair_hint: str | None = None) -> dict:
        prompt = (
            f"{self.prompt_template}\n\n"
            f"Problem Analysis JSON:\n{json.dumps(problem_analysis, ensure_ascii=False, indent=2)}\n\n"
            f"Mapped Geometry JSON:\n{json.dumps(mapped_geometry, ensure_ascii=False, indent=2)}\n"
        )
        if repair_hint:
            prompt += f"\n{repair_hint}\n"
        return self.llm_client.run_structured(self.name, prompt, self.model_config)
