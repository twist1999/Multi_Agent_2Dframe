from __future__ import annotations

from typing import TYPE_CHECKING

from ..config import AgentModelConfig, PROMPTS_ROOT
from ..llm.client import LLMClient
from ..utils import load_text

if TYPE_CHECKING:
    from ..rl.prompt_optimizer import PromptVariant


class BaseAgent:
    name: str = ""
    prompt_file: str = ""

    def __init__(self, llm_client: LLMClient, model_config: AgentModelConfig) -> None:
        self.llm_client = llm_client
        self.model_config = model_config

    @property
    def prompt_template(self) -> str:
        return load_text(PROMPTS_ROOT / self.prompt_file)

    def resolve_prompt(self, variant: PromptVariant | None = None) -> str:
        """Return the prompt text, optionally from a bandit-selected variant."""
        if variant is not None:
            loaded = variant.load()
            if loaded:
                return loaded
        return self.prompt_template
