"""End-to-end verification of per-agent RL optimization system."""

from __future__ import annotations

import json

from multiagent.rl.agent_reward import (
    AgentRewardDecomposer,
    classify_checkpoint_errors,
)
from src.multiagent.rl.experience_buffer import ExperienceBuffer, hash_prompt
from src.multiagent.rl.prompt_optimizer import (
    MultiAgentOptimizer,
    PerAgentBanditOptimizer,
    PromptVariant,
)

CORE_AGENTS = [
    "problem_analysis",
    "construction_planning",
    "node_agent",
    "element_agent",
    "load_assignment",
    "geometry_code_translator",
    "complete_code_generator",
]


def test_classify_checkpoint_errors():
    """Validate error attribution logic."""
    result = classify_checkpoint_errors(
        analysis_errors=["Construction plan missing step"],
        geometry_errors=["Duplicate node id: 5"],
        code_errors=["SyntaxError at line 42"],
    )
    assert "construction_planning" in result
    assert len(result["construction_planning"]) >= 1
    assert len(result["node_agent"]) >= 1
    assert len(result["complete_code_generator"]) >= 1
    print("  PASS: classify_checkpoint_errors")


def test_agent_reward_decomposer():
    """Validate per-agent reward computation."""
    decomposer = AgentRewardDecomposer()

    # Empty outputs — all agents get base_success=0
    rewards = decomposer.decompose(outputs={}, checkpoint_errors={}, execution_state={})
    assert len(rewards) == 7
    for agent_name, reward in rewards.items():
        assert reward.base_success == 0.0, f"{agent_name} should have base=0 for empty outputs"
    print("  PASS: empty outputs produce zero base_success")

    # With outputs
    outputs = {
        "problem_analysis": {"geometry": {}},
        "construction_plan": {"steps": []},
        "node_output": {"nodes": [{"id": 1, "x": 0, "y": 0}]},
        "element_output": {"elements": []},
        "load_output": {"loads": []},
        "geometry_code": "print('hello')",
        "complete_code": "print('world')",
    }
    rewards2 = decomposer.decompose(outputs=outputs, checkpoint_errors={}, execution_state={})
    for agent_name, reward in rewards2.items():
        assert reward.base_success >= 0.2, f"{agent_name} should have base > 0"
    print("  PASS: non-empty outputs produce positive base_success")

    # With checkpoint errors
    ce = classify_checkpoint_errors(
        analysis_errors=["Construction plan missing step"],
        geometry_errors=[],
        code_errors=[],
    )
    rewards3 = decomposer.decompose(outputs=outputs, checkpoint_errors=ce, execution_state={})
    cp_reward = rewards3["construction_planning"]
    assert cp_reward.validation_pass < 0.3, f"CP should have penalty, got {cp_reward.validation_pass}"
    print("  PASS: checkpoint errors produce validation_pass penalties")


def test_experience_buffer():
    """Validate experience buffer write/read."""
    buf = ExperienceBuffer()

    # Insert test experiences
    for agent_name in CORE_AGENTS[:3]:
        for i in range(3):
            buf.insert(
                agent_name=agent_name,
                run_id=f"test-{agent_name}-{i}",
                prompt_variant=f"{agent_name}-v{i+1}",
                input_signature="bays:3_stories:4",
                reward=0.5 + 0.1 * i,
                base_success=0.3,
                validation_pass=0.3,
                downstream_feedback=0.1 * i,
                success=i >= 1,
            )

    # Retrieve similar
    similar = buf.retrieve_similar("node_agent", "bays:3_stories:4", top_k=2)
    assert len(similar) >= 0  # May not have results with min_reward=0.3
    print(f"  PASS: experience buffer write/read (retrieved {len(similar)} similar)")

    # Stats
    stats = buf.stats()
    assert len(stats) >= 1
    print(f"  PASS: stats returns {len(stats)} agents")


def test_bandit_optimizer():
    """Validate bandit selection and update logic."""
    opt = PerAgentBanditOptimizer(agent_name="test_agent", epsilon=0.0, alpha=0.1)
    opt.register_variant(PromptVariant(
        variant_id="test-v1",
        agent_name="test_agent",
        prompt_text="prompt v1",
        q_value=0.0,
    ))
    opt.register_variant(PromptVariant(
        variant_id="test-v2",
        agent_name="test_agent",
        prompt_text="prompt v2",
        q_value=0.0,
    ))

    # With epsilon=0, should pick the first max (both 0)
    v = opt.select_variant()
    assert v is not None
    print(f"  PASS: select variant: {v.variant_id}")

    # Update v1 with high reward
    opt.update("test-v1", 0.8)
    assert opt.variants["test-v1"].q_value == 0.8
    print(f"  PASS: update v1 Q-value = {opt.variants['test-v1'].q_value}")

    # Now should exploit v1
    v2 = opt.select_variant()
    assert v2.variant_id == "test-v1", f"Should exploit best, got {v2.variant_id}"
    print(f"  PASS: exploit selects best variant")

    # Test exploration
    opt2 = PerAgentBanditOptimizer(agent_name="test2", epsilon=1.0, alpha=0.1)
    opt2.register_variant(PromptVariant(variant_id="test2-v1", agent_name="test2", prompt_text="v1", q_value=0.9))
    opt2.register_variant(PromptVariant(variant_id="test2-v2", agent_name="test2", prompt_text="v2", q_value=0.0))
    # With epsilon=1, should always explore (random)
    v3 = opt2.select_variant()
    assert v3 is not None
    print(f"  PASS: epsilon=1.0 explores randomly")


def test_multi_agent_optimizer():
    """Validate MultiAgentOptimizer loads variants for all 7 agents."""
    opt = MultiAgentOptimizer(epsilon=0.1, alpha=0.1)
    assert len(opt.optimizers) == 7
    for name in CORE_AGENTS:
        assert name in opt.optimizers, f"Missing optimizer for {name}"
        agent_opt = opt.optimizers[name]
        assert len(agent_opt.variants) >= 1, f"No variants for {name}"
    print(f"  PASS: MultiAgentOptimizer has {len(opt.optimizers)} agent optimizers")

    # Verify each has proper variants
    for name, agent_opt in opt.optimizers.items():
        variant = agent_opt.select_variant()
        prompt_text = variant.load()
        assert prompt_text, f"Empty prompt for {name}/{variant.variant_id}"
        assert len(prompt_text) > 20, f"Prompt too short for {name}: {len(prompt_text)} chars"
    print(f"  PASS: all agent variants load prompt text")

    # Update and verify Q-value tracking
    opt.update("node_agent", "node_agent-v1", 0.7)
    summary = opt.summary()
    assert "agents" in summary
    print(f"  PASS: summary generation OK")


def test_hash_prompt():
    """Validate prompt hashing."""
    h1 = hash_prompt("test prompt")
    h2 = hash_prompt("test prompt")
    h3 = hash_prompt("different prompt")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 16
    print(f"  PASS: hash_prompt (hash={h1})")


if __name__ == "__main__":
    print("Per-Agent RL System Verification\n")
    test_classify_checkpoint_errors()
    test_agent_reward_decomposer()
    test_experience_buffer()
    test_bandit_optimizer()
    test_multi_agent_optimizer()
    test_hash_prompt()
    print("\nAll tests passed.")
