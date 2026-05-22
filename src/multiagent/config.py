from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(os.getenv("MULTIAGENT_ROOT", r"H:\codex\multiagent"))
PROMPTS_ROOT = PROJECT_ROOT / "src" / "multiagent" / "prompts"
OUTPUT_ROOT = PROJECT_ROOT / "outputs"
PRESETS_ROOT = PROJECT_ROOT / "presets"
RAG_OS_ROOT = Path(os.getenv("RAG_OS_ROOT", r"H:\codex\RAG_OS"))


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class AgentModelConfig:
    provider: str = "deepseek"
    model_name: str = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
    api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))
    base_url: str = field(default_factory=lambda: os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    temperature: float = 0.0


@dataclass
class RagConfig:
    enabled: bool = field(default_factory=lambda: _env_flag("MULTIAGENT_RAG_ENABLED", True))
    project_root: Path = field(default_factory=lambda: Path(os.getenv("RAG_OS_ROOT", str(RAG_OS_ROOT))))
    top_k: int = field(default_factory=lambda: int(os.getenv("MULTIAGENT_RAG_TOP_K", "3")))
    max_chars: int = field(default_factory=lambda: int(os.getenv("MULTIAGENT_RAG_MAX_CHARS", "6000")))


@dataclass
class RLConfig:
    enabled: bool = field(default_factory=lambda: _env_flag("MULTIAGENT_RL_ENABLED", True))
    epsilon: float = field(default_factory=lambda: float(os.getenv("MULTIAGENT_RL_EPSILON", "0.05")))
    alpha: float = field(default_factory=lambda: float(os.getenv("MULTIAGENT_RL_ALPHA", "0.1")))
    buffer_size: int = field(default_factory=lambda: int(os.getenv("MULTIAGENT_RL_BUFFER_SIZE", "200")))
    use_bandit: bool = field(default_factory=lambda: _env_flag("MULTIAGENT_RL_BANDIT", True))
    use_few_shot: bool = field(default_factory=lambda: _env_flag("MULTIAGENT_RL_FEWSHOT", False))
    use_presets: bool = field(default_factory=lambda: _env_flag("MULTIAGENT_RL_PRESETS", True))
    presets_path: Path = field(default_factory=lambda: Path(os.getenv(
        "MULTIAGENT_RL_PRESETS_PATH",
        str(PRESETS_ROOT / "q_values.json"),
    )))
    few_shot_presets_path: Path = field(default_factory=lambda: Path(os.getenv(
        "MULTIAGENT_RL_FEWSHOT_PATH",
        str(PRESETS_ROOT / "few_shot_examples.json"),
    )))


@dataclass
class PipelineConfig:
    max_retries_analysis_planning: int = 5
    max_retries_geometry: int = 5
    max_retries_code_translation: int = 3
    write_outputs: bool = True
    output_dir: Path = OUTPUT_ROOT
    problem_analysis: AgentModelConfig = field(default_factory=AgentModelConfig)
    construction_planning: AgentModelConfig = field(default_factory=AgentModelConfig)
    node_agent: AgentModelConfig = field(default_factory=AgentModelConfig)
    element_agent: AgentModelConfig = field(default_factory=AgentModelConfig)
    load_assignment: AgentModelConfig = field(default_factory=AgentModelConfig)
    geometry_code_translator: AgentModelConfig = field(default_factory=AgentModelConfig)
    complete_code_generator: AgentModelConfig = field(default_factory=AgentModelConfig)
    python_check_agent: AgentModelConfig = field(default_factory=AgentModelConfig)
    rag: RagConfig = field(default_factory=RagConfig)
    rl: RLConfig = field(default_factory=RLConfig)


def ensure_directories() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    PRESETS_ROOT.mkdir(parents=True, exist_ok=True)
