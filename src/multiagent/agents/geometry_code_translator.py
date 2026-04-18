from __future__ import annotations

import json

from .base import BaseAgent


class GeometryCodeTranslator(BaseAgent):
    name = "geometry_code_translator"
    prompt_file = "geometry_code_translator.txt"

    def run(self, compiled_json: dict) -> str:
        prompt = f"{self.prompt_template}\n\nCompiled JSON:\n{json.dumps(compiled_json, ensure_ascii=False, indent=2)}\n"
        return self.llm_client.run_text(self.name, prompt, self.model_config)
