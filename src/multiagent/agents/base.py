from __future__ import annotations

from pathlib import Path

from ..config import AgentModelConfig, PROMPTS_ROOT
from ..llm.client import LLMClient
from ..utils import load_text


class BaseAgent:
    name: str = ""
    prompt_file: str = ""

    def __init__(self, llm_client: LLMClient, model_config: AgentModelConfig) -> None:
        self.llm_client = llm_client
        self.model_config = model_config

    @property
    def prompt_template(self) -> str:
        return load_text(PROMPTS_ROOT / self.prompt_file)
