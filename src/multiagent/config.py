from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(r"H:\codex\multiagent")
PROMPTS_ROOT = PROJECT_ROOT / "src" / "multiagent" / "prompts"
OUTPUT_ROOT = PROJECT_ROOT / "outputs"


@dataclass
class AgentModelConfig:
    provider: str = "deepseek"
    model_name: str = "deepseek-chat"
    api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))
    base_url: str = field(default_factory=lambda: os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    temperature: float = 0.0


@dataclass
class PipelineConfig:
    max_retries_analysis_planning: int = 5
    max_retries_geometry: int = 5
    write_outputs: bool = True
    output_dir: Path = OUTPUT_ROOT
    problem_analysis: AgentModelConfig = field(default_factory=AgentModelConfig)
    construction_planning: AgentModelConfig = field(default_factory=AgentModelConfig)
    node_agent: AgentModelConfig = field(default_factory=AgentModelConfig)
    element_agent: AgentModelConfig = field(default_factory=AgentModelConfig)
    load_assignment: AgentModelConfig = field(default_factory=AgentModelConfig)
    geometry_code_translator: AgentModelConfig = field(default_factory=AgentModelConfig)
    complete_code_generator: AgentModelConfig = field(default_factory=AgentModelConfig)


def ensure_directories() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
