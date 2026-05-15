from __future__ import annotations

import json

from .base import BaseAgent


class ConstructionPlanningAgent(BaseAgent):
    name = "construction_planning"
    prompt_file = "construction_planning.txt"

    def run(self, problem_analysis: dict, repair_hint: str | None = None) -> dict:
        prompt = f"{self.prompt_template}\n\nProblem Analysis JSON:\n{json.dumps(problem_analysis, ensure_ascii=False, indent=2)}\n"
        if repair_hint:
            prompt += f"\n{repair_hint}\n"
        result = self.llm_client.run_structured(self.name, prompt, self.model_config)
        if isinstance(result, list):
            return {"Construction_steps": [self._normalize_step(step) for step in result]}
        if isinstance(result, dict) and "Construction_steps" not in result:
            for key in ("construction_steps", "steps", "plan"):
                value = result.get(key)
                if isinstance(value, list):
                    return {"Construction_steps": [self._normalize_step(step) for step in value]}
        if isinstance(result, dict) and isinstance(result.get("Construction_steps"), list):
            return {
                **result,
                "Construction_steps": [
                    self._normalize_step(step) for step in result["Construction_steps"]
                ],
            }
        return result

    def _normalize_step(self, step: dict) -> dict:
        if not isinstance(step, dict):
            return {}
        return {
            **step,
            "Step_number": step.get("Step_number", step.get("step_number")),
            "Bay_number": step.get("Bay_number", step.get("bay_number")),
            "Story_number": step.get("Story_number", step.get("story_number")),
            "Step_type": step.get("Step_type", step.get("step_type")),
        }
