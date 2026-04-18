from __future__ import annotations

import json

from .base import BaseAgent


class CompleteCodeGenerator(BaseAgent):
    name = "complete_code_generator"
    prompt_file = "complete_code_generator.txt"

    def run(self, compiled_json: dict, geometry_code: str) -> str:
        prompt = (
            f"{self.prompt_template}\n\n"
            f"Compiled JSON:\n{json.dumps(compiled_json, ensure_ascii=False, indent=2)}\n\n"
            f"Geometry Code:\n{geometry_code}\n"
        )
        return self.llm_client.run_text(self.name, prompt, self.model_config)
