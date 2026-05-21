from __future__ import annotations

import json

from .base import BaseAgent
from ..functions.schema_normalizer import normalize_elements


class ElementAgent(BaseAgent):
    name = "element_agent"
    prompt_file = "element_agent.txt"

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
            elements = normalize_elements(result)
            if elements and "elements" not in result:
                result = {**result, "elements": elements}
        return result
