from __future__ import annotations

import json

from .base import BaseAgent


class ProblemAnalysisAgent(BaseAgent):
    name = "problem_analysis"
    prompt_file = "problem_analysis.txt"

    def run(self, user_input: str, repair_hint: str | None = None, prompt_override: str | None = None) -> dict:
        base = prompt_override if prompt_override else self.prompt_template
        prompt = f"{base}\n\nUser Input:\n{user_input}\n"
        if repair_hint:
            prompt += f"\n{repair_hint}\n"
        return self.llm_client.run_structured(self.name, prompt, self.model_config)
