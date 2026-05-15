from __future__ import annotations

import json

from .base import BaseAgent
from ..rag_context import RAGContextProvider


class CompleteCodeGenerator(BaseAgent):
    name = "complete_code_generator"
    prompt_file = "complete_code_generator.txt"

    def __init__(self, *args, rag_context: RAGContextProvider | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.rag_context = rag_context

    def run(self, compiled_json: dict, geometry_code: str, repair_hint: str | None = None) -> str:
        docs_context = self.rag_context.complete_code_context(compiled_json, geometry_code) if self.rag_context else ""
        prompt = (
            f"{self.prompt_template}\n\n"
            f"{docs_context}\n"
            f"Compiled JSON:\n{json.dumps(compiled_json, ensure_ascii=False, indent=2)}\n\n"
            f"Geometry Code:\n{geometry_code}\n"
        )
        if repair_hint:
            prompt += f"\n{repair_hint}\n"
        return self.llm_client.run_text(self.name, prompt, self.model_config)
