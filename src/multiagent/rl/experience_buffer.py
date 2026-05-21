from __future__ import annotations

import hashlib
from typing import Any

from .logger import RLLogger


class ExperienceBuffer:
    """Per-agent experience store backed by SQLite via RLLogger.

    Provides:
    - insert(): store a new agent experience
    - retrieve_similar(): find successful cases with matching input_signature
    - stats(): per-agent success rates and average rewards
    """

    def __init__(self, logger: RLLogger | None = None, max_records_per_agent: int = 200) -> None:
        self.logger = logger or RLLogger()
        self.max_records = max_records_per_agent

    def insert(
        self,
        *,
        agent_name: str,
        run_id: str,
        prompt_hash: str = "",
        prompt_variant: str = "default",
        input_signature: str = "",
        reward: float = 0.0,
        base_success: float = 0.0,
        validation_pass: float = 0.0,
        downstream_feedback: float = 0.0,
        error_categories: list[str] | None = None,
        success: bool = False,
        llm_input: str | None = None,
        llm_output: str | None = None,
    ) -> None:
        self.logger.insert_agent_experience(
            agent_name=agent_name,
            run_id=run_id,
            prompt_hash=prompt_hash,
            prompt_variant=prompt_variant,
            input_signature=input_signature,
            reward=reward,
            base_success=base_success,
            validation_pass=validation_pass,
            downstream_feedback=downstream_feedback,
            error_categories=error_categories,
            success=success,
            llm_input=llm_input,
            llm_output=llm_output,
        )

    def retrieve_similar(
        self,
        agent_name: str,
        input_signature: str,
        top_k: int = 2,
        min_reward: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Retrieve top-k successful experiences with the same input_signature."""
        results = self.logger.agent_experiences(
            agent_name=agent_name,
            input_signature=input_signature,
            success_only=True,
            limit=top_k * 3,
        )
        filtered = [r for r in results if float(r.get("reward", 0)) >= min_reward]
        return filtered[:top_k]

    def retrieve_best_for_signature(
        self,
        agent_name: str,
        input_signature: str,
    ) -> dict[str, Any] | None:
        """Get the single best experience for a given input signature."""
        results = self.logger.agent_experiences(
            agent_name=agent_name,
            input_signature=input_signature,
            success_only=True,
            limit=1,
        )
        return results[0] if results else None

    def stats(self, agent_name: str | None = None) -> list[dict[str, Any]]:
        return self.logger.agent_reward_summary(agent_name)

    def variant_q_values(self, agent_name: str, input_signature: str) -> dict[str, float]:
        """Compute EMA Q-values for each prompt variant for a given agent + input signature."""
        results = self.logger.agent_experiences(
            agent_name=agent_name,
            input_signature=input_signature,
            success_only=False,
            limit=200,
        )
        variant_rewards: dict[str, list[float]] = {}
        for row in results:
            variant = str(row.get("prompt_variant", "default"))
            reward = float(row.get("reward", 0.0))
            variant_rewards.setdefault(variant, []).append(reward)

        q_values: dict[str, float] = {}
        for variant, rewards in variant_rewards.items():
            # Exponential moving average with α=0.1, most recent last
            ema = rewards[0] if rewards else 0.0
            for r in rewards[1:]:
                ema = 0.9 * ema + 0.1 * r
            q_values[variant] = round(ema, 4)
        return q_values


def hash_prompt(prompt_text: str) -> str:
    """SHA256 hash of a prompt string for deduplication."""
    return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:16]
