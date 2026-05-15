from __future__ import annotations

import json

from .base import BaseAgent


class PythonCheckAgent(BaseAgent):
    name = "python_check_agent"
    prompt_file = "python_check_agent.txt"

    def run(
        self,
        user_input: str,
        compiled_model: dict,
        geometry_code: str,
        complete_code: str,
        execution_report: dict,
    ) -> dict:
        prompt = (
            f"{self.prompt_template}\n\n"
            f"User Input:\n{user_input}\n\n"
            f"Compiled Model JSON:\n{json.dumps(compiled_model, ensure_ascii=False, indent=2)}\n\n"
            f"Geometry Code:\n{geometry_code}\n\n"
            f"Complete Code:\n{complete_code}\n\n"
            f"Execution Report JSON:\n{json.dumps(execution_report, ensure_ascii=False, indent=2)}\n"
        )
        return self.llm_client.run_structured(self.name, prompt, self.model_config)
