from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import PROMPTS_ROOT
from ..utils import load_text


@dataclass
class PromptVariant:
    variant_id: str          # e.g. "node_agent-v1"
    agent_name: str
    prompt_path: Path | None = None
    prompt_text: str = ""    # cached prompt content
    q_value: float = 0.0     # exponential moving average of reward
    count: int = 0           # times selected

    def load(self) -> str:
        if self.prompt_text:
            return self.prompt_text
        if self.prompt_path and self.prompt_path.exists():
            self.prompt_text = load_text(self.prompt_path)
            return self.prompt_text
        return ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "agent_name": self.agent_name,
            "q_value": self.q_value,
            "count": self.count,
        }


class PerAgentBanditOptimizer:
    """ε-greedy multi-armed bandit for per-agent prompt variant selection.

    Each agent has multiple PromptVariant instances. The optimizer tracks
    Q-values via exponential moving average and selects variants with
    ε-greedy exploration.
    """

    def __init__(
        self,
        agent_name: str,
        variants: list[PromptVariant] | None = None,
        epsilon: float = 0.1,
        alpha: float = 0.1,
    ) -> None:
        self.agent_name = agent_name
        self.variants: dict[str, PromptVariant] = {}
        self.epsilon = epsilon
        self.alpha = alpha
        if variants:
            for v in variants:
                self.variants[v.variant_id] = v
        self._default_variant: PromptVariant | None = None

    def register_variant(self, variant: PromptVariant) -> None:
        self.variants[variant.variant_id] = variant

    @property
    def default_variant(self) -> PromptVariant:
        if self._default_variant:
            return self._default_variant
        # Fallback: use the current default prompt file
        fallback_path = PROMPTS_ROOT / f"{self.agent_name}.txt"
        self._default_variant = PromptVariant(
            variant_id=f"{self.agent_name}-default",
            agent_name=self.agent_name,
            prompt_path=fallback_path,
            q_value=0.5,
        )
        return self._default_variant

    def select_variant(self) -> PromptVariant:
        """ε-greedy selection: exploit best Q-value, explore randomly.

        Returns the selected PromptVariant.
        """
        if not self.variants:
            return self.default_variant

        # Exploration
        if random.random() < self.epsilon:
            return random.choice(list(self.variants.values()))

        # Exploitation: pick highest Q-value
        best = max(self.variants.values(), key=lambda v: v.q_value)
        if best.q_value <= 0 and self.default_variant.q_value >= best.q_value:
            return self.default_variant
        return best

    def update(self, variant_id: str, reward: float) -> None:
        """Update Q-value using exponential moving average.

        Q_new = (1 - alpha) * Q_old + alpha * reward
        """
        variant = self.variants.get(variant_id)
        if variant is None:
            return
        variant.count += 1
        if variant.count == 1:
            variant.q_value = reward
        else:
            variant.q_value = round(
                (1 - self.alpha) * variant.q_value + self.alpha * reward,
                4,
            )

    def best_variant(self) -> PromptVariant:
        if not self.variants:
            return self.default_variant
        return max(self.variants.values(), key=lambda v: v.q_value)

    def summary(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "epsilon": self.epsilon,
            "alpha": self.alpha,
            "best_variant": self.best_variant().variant_id,
            "best_q_value": self.best_variant().q_value,
            "variants": [v.to_dict() for v in self.variants.values()],
        }

    @classmethod
    def from_variant_dir(
        cls,
        agent_name: str,
        variant_dir: Path | None = None,
        epsilon: float = 0.1,
        alpha: float = 0.1,
    ) -> PerAgentBanditOptimizer:
        """Create an optimizer by loading all variants from a directory.

        Expected structure: variant_dir/{v1}.txt, {v2}.txt, ...
        If variant_dir doesn't exist or is empty, falls back to default prompt.
        """
        optimizer = cls(agent_name=agent_name, epsilon=epsilon, alpha=alpha)
        if variant_dir is None:
            variant_dir = PROMPTS_ROOT / "variants" / agent_name

        if variant_dir.exists():
            for txt_file in sorted(variant_dir.glob("*.txt")):
                if txt_file.stem.startswith("v"):
                    variant_id = f"{agent_name}-{txt_file.stem}"
                    optimizer.register_variant(PromptVariant(
                        variant_id=variant_id,
                        agent_name=agent_name,
                        prompt_path=txt_file,
                    ))

        if not optimizer.variants:
            # Register default prompt as the only variant
            default_path = PROMPTS_ROOT / f"{agent_name}.txt"
            if default_path.exists():
                optimizer.register_variant(PromptVariant(
                    variant_id=f"{agent_name}-v1",
                    agent_name=agent_name,
                    prompt_path=default_path,
                    q_value=0.5,
                ))

        return optimizer


class MultiAgentOptimizer:
    """Manages a PerAgentBanditOptimizer for each agent in the pipeline."""

    CORE_AGENTS = [
        "problem_analysis",
        "construction_planning",
        "node_agent",
        "element_agent",
        "load_assignment",
        "geometry_code_translator",
        "complete_code_generator",
    ]

    def __init__(self, epsilon: float = 0.1, alpha: float = 0.1) -> None:
        self.epsilon = epsilon
        self.alpha = alpha
        self.optimizers: dict[str, PerAgentBanditOptimizer] = {}
        self._init_all()

    def _init_all(self) -> None:
        for agent_name in self.CORE_AGENTS:
            self.optimizers[agent_name] = PerAgentBanditOptimizer.from_variant_dir(
                agent_name=agent_name,
                epsilon=self.epsilon,
                alpha=self.alpha,
            )

    def get(self, agent_name: str) -> PerAgentBanditOptimizer:
        if agent_name not in self.optimizers:
            self.optimizers[agent_name] = PerAgentBanditOptimizer.from_variant_dir(
                agent_name=agent_name,
                epsilon=self.epsilon,
                alpha=self.alpha,
            )
        return self.optimizers[agent_name]

    def select(self, agent_name: str) -> PromptVariant:
        return self.get(agent_name).select_variant()

    def update(self, agent_name: str, variant_id: str, reward: float) -> None:
        self.get(agent_name).update(variant_id, reward)

    def summary(self) -> dict[str, Any]:
        return {
            "epsilon": self.epsilon,
            "alpha": self.alpha,
            "agents": {
                name: opt.summary()
                for name, opt in self.optimizers.items()
            },
        }
