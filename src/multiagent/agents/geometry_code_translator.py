from __future__ import annotations

import json

from .base import BaseAgent
from ..rag_context import RAGContextProvider


class GeometryCodeTranslator(BaseAgent):
    name = "geometry_code_translator"
    prompt_file = "geometry_code_translator.txt"

    def __init__(self, *args, rag_context: RAGContextProvider | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.rag_context = rag_context

    def run(self, compiled_json: dict, repair_hint: str | None = None, prompt_override: str | None = None) -> str:
        docs_context = self.rag_context.geometry_context(compiled_json) if self.rag_context else ""
        base = prompt_override if prompt_override else self.prompt_template
        prompt = (
            f"{base}\n\n"
            f"{docs_context}\n"
            f"Compiled JSON:\n{json.dumps(compiled_json, ensure_ascii=False, indent=2)}\n"
        )
        if repair_hint:
            prompt += f"\n{repair_hint}\n"
        return self.llm_client.run_text(self.name, prompt, self.model_config)
