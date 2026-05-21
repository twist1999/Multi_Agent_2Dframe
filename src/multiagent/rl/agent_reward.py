from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentReward:
    agent_name: str
    base_success: float = 0.0
    validation_pass: float = 0.0
    downstream_feedback: float = 0.0
    total: float = 0.0
    error_categories: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


def _compute_input_signature(agent_name: str, agent_inputs: dict[str, Any]) -> str:
    """Compact summary of agent input dimensions for similarity matching."""
    if agent_name == "problem_analysis":
        return "user_input"
    if agent_name == "construction_planning":
        return "construction_planning"
    if agent_name in ("node_agent", "element_agent"):
        bay_count = 0
        story_count = 0
        pa = agent_inputs.get("problem_analysis", {})
        geometry = pa.get("geometry", pa.get("Geometry", {}))
        if isinstance(geometry, dict):
            bays = geometry.get("Bay_data", geometry.get("bays", []))
            if isinstance(bays, list):
                bay_count = len(bays)
                for bay in bays:
                    if isinstance(bay, dict):
                        sc = bay.get("Story_count", bay.get("story_count", 0))
                        if sc:
                            story_count = max(story_count, int(sc))
            if not bay_count:
                bay_count = int(geometry.get("Total_bays", geometry.get("bay_count", 0)))
            if not story_count:
                story_count = int(geometry.get("Total_stories", geometry.get("story_count", 0)))
        return f"bays:{bay_count}_stories:{story_count}"
    if agent_name == "load_assignment":
        return "load_assignment"
    if agent_name == "geometry_code_translator":
        return "geometry_code"
    if agent_name == "complete_code_generator":
        return "complete_code"
    return "unknown"


def _error_blames_agent(agent_name: str, error_text: str) -> bool:
    """Check if a validation error text implicates a specific agent."""
    node_keywords = ["node", "duplicate node", "node id", "node output", "nodes"]
    element_keywords = ["element", "duplicate element", "element id", "element output", "elements"]
    analysis_keywords = ["bay/story geometry", "problem analysis", "bay_data", "geometry"]
    plan_keywords = ["construction plan", "construction step", "step number", "step", "missing bay", "story"]

    text_lower = error_text.lower()

    if agent_name == "problem_analysis":
        return any(kw in text_lower for kw in analysis_keywords) and not any(
            kw in text_lower for kw in plan_keywords
        )
    if agent_name == "construction_planning":
        return any(kw in text_lower for kw in plan_keywords)
    if agent_name == "node_agent":
        return any(kw in text_lower for kw in node_keywords)
    if agent_name == "element_agent":
        return any(kw in text_lower for kw in element_keywords)
    if agent_name in ("geometry_code_translator", "complete_code_generator"):
        return "syntax" in text_lower or "code" in text_lower
    return False


def _python_check_agent_target(python_check: dict[str, Any]) -> str | None:
    """Extract the agent targeted by PythonCheckAgent diagnosis."""
    if not python_check:
        return None
    target = python_check.get("suggested_target_agent") or python_check.get("responsible_stage") or ""
    target = str(target).lower().replace(" ", "_")
    # Map PythonCheckAgent output names to internal agent names
    mapping: dict[str, str] = {
        "nodeagent": "node_agent",
        "node_agent": "node_agent",
        "elementagent": "element_agent",
        "element_agent": "element_agent",
        "problemanalysis": "problem_analysis",
        "problem_analysis": "problem_analysis",
        "constructionplanning": "construction_planning",
        "construction_planning": "construction_planning",
        "loadassignment": "load_assignment",
        "load_assignment": "load_assignment",
        "geometrycodetranslator": "geometry_code_translator",
        "geometry_code_translator": "geometry_code_translator",
        "completecodegenerator": "complete_code_generator",
        "complete_code_generator": "complete_code_generator",
    }
    return mapping.get(target)


def _human_feedback_target(feedback: dict[str, Any] | None) -> str | None:
    """Extract the agent targeted by human feedback."""
    if not feedback:
        return None
    verdict = str(feedback.get("verdict", "")).lower()
    if verdict != "incorrect":
        return None
    selected = feedback.get("selected_object") or {}
    kind = str(selected.get("kind", "")).lower()
    if kind == "node":
        return "node_agent"
    if kind == "element":
        return "element_agent"
    return None


CORE_AGENTS = [
    "problem_analysis",
    "construction_planning",
    "node_agent",
    "element_agent",
    "load_assignment",
    "geometry_code_translator",
    "complete_code_generator",
]


class AgentRewardDecomposer:
    """Decompose pipeline-level reward signals into per-agent rewards.

    Uses three signal sources weighted equally:
    1. base_success (0.3) — agent output is parseable / present
    2. validation_pass (0.3) — agent passed its checkpoints
    3. downstream_feedback (0.4) — downstream agents or human flagged this agent
    """

    def decompose(
        self,
        *,
        outputs: dict[str, Any],
        checkpoint_errors: dict[str, list[str]] | None = None,
        python_check: dict[str, Any] | None = None,
        execution_state: dict[str, Any] | None = None,
        feedback: dict[str, Any] | None = None,
        agent_inputs: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, AgentReward]:
        checkpoint_errors = checkpoint_errors or {}
        execution_state = execution_state or {}
        agent_inputs = agent_inputs or {}
        rewards: dict[str, AgentReward] = {}

        for agent_name in CORE_AGENTS:
            base = self._compute_base_success(agent_name, outputs)
            vpass = self._compute_validation_pass(agent_name, checkpoint_errors)
            down = self._compute_downstream_feedback(
                agent_name,
                checkpoint_errors,
                python_check,
                execution_state,
                feedback,
            )
            total = round(base + vpass + down, 4)
            errors = self._collect_error_categories(
                agent_name, checkpoint_errors, python_check, execution_state, feedback
            )
            signature = _compute_input_signature(agent_name, agent_inputs.get(agent_name, {}))
            rewards[agent_name] = AgentReward(
                agent_name=agent_name,
                base_success=base,
                validation_pass=vpass,
                downstream_feedback=down,
                total=total,
                error_categories=errors,
                details={
                    "input_signature": signature,
                    "checkpoint_errors": checkpoint_errors.get(agent_name, []),
                },
            )

        return rewards

    def _compute_base_success(self, agent_name: str, outputs: dict[str, Any]) -> float:
        """+0.3 if agent produced parseable output, 0 otherwise."""
        output_keys: dict[str, str] = {
            "problem_analysis": "problem_analysis",
            "construction_planning": "construction_plan",
            "node_agent": "node_output",
            "element_agent": "element_output",
            "load_assignment": "load_output",
            "geometry_code_translator": "geometry_code",
            "complete_code_generator": "complete_code",
        }
        key = output_keys.get(agent_name)
        if not key:
            return 0.0
        value = outputs.get(key)
        if value is None:
            return 0.0
        if isinstance(value, str):
            return 0.3 if value.strip() else 0.0
        if isinstance(value, (dict, list)):
            return 0.3 if value else 0.0
        return 0.0

    def _compute_validation_pass(self, agent_name: str, checkpoint_errors: dict[str, list[str]]) -> float:
        """+0.3 if no checkpoint errors blame this agent, 0 otherwise."""
        agent_errors = checkpoint_errors.get(agent_name, [])
        if not agent_errors:
            return 0.3
        # Proportional reduction based on error count
        penalty = min(0.3, 0.1 * len(agent_errors))
        return round(0.3 - penalty, 4)

    def _compute_downstream_feedback(
        self,
        agent_name: str,
        checkpoint_errors: dict[str, list[str]],
        python_check: dict[str, Any] | None,
        execution_state: dict[str, Any] | None,
        feedback: dict[str, Any] | None,
    ) -> float:
        """+0.4 if no downstream signals blame this agent. Penalties for blame."""
        score = 0.4
        execution_state = execution_state or {}

        # PythonCheckAgent blamed this agent
        target = _python_check_agent_target(python_check or {})
        if target == agent_name:
            confidence = float(python_check.get("confidence", 0.5)) if python_check else 0.5
            score -= 0.2 * confidence

        # Human feedback blamed this agent
        human_target = _human_feedback_target(feedback)
        if human_target == agent_name:
            score -= 0.3

        # Code execution failed + no specific blame → small penalty for code agents
        if execution_state.get("status") == "failed":
            if agent_name in ("geometry_code_translator", "complete_code_generator"):
                if target is None:
                    score -= 0.1

        return max(-0.4, round(score, 4))

    def _collect_error_categories(
        self,
        agent_name: str,
        checkpoint_errors: dict[str, list[str]],
        python_check: dict[str, Any] | None,
        execution_state: dict[str, Any] | None,
        feedback: dict[str, Any] | None,
    ) -> list[str]:
        categories: list[str] = []
        execution_state = execution_state or {}

        agent_errors = checkpoint_errors.get(agent_name, [])
        if agent_errors:
            categories.append("validation_failed")

        target = _python_check_agent_target(python_check or {})
        if target == agent_name:
            categories.append("python_check_blamed")

        human_target = _human_feedback_target(feedback)
        if human_target == agent_name:
            categories.append("human_rejected")

        if execution_state.get("status") == "failed":
            if agent_name in ("geometry_code_translator", "complete_code_generator"):
                categories.append("execution_failed")

        return categories


def classify_checkpoint_errors(
    analysis_errors: list[str] | None,
    geometry_errors: list[str] | None,
    code_errors: list[str] | None,
) -> dict[str, list[str]]:
    """Classify raw checkpoint error lists into per-agent error buckets.

    Returns dict keyed by agent_name.
    """
    result: dict[str, list[str]] = {agent: [] for agent in CORE_AGENTS}

    if analysis_errors:
        for err in analysis_errors:
            if _error_blames_agent("problem_analysis", err):
                result["problem_analysis"].append(err)
            if _error_blames_agent("construction_planning", err):
                result["construction_planning"].append(err)
            # If no clear blame, assign to both
            if not result["problem_analysis"] and not result["construction_planning"]:
                result["problem_analysis"].append(err)
                result["construction_planning"].append(err)

    if geometry_errors:
        for err in geometry_errors:
            if _error_blames_agent("node_agent", err):
                result["node_agent"].append(err)
            if _error_blames_agent("element_agent", err):
                result["element_agent"].append(err)
            if not _error_blames_agent("node_agent", err) and not _error_blames_agent("element_agent", err):
                result["node_agent"].append(err)
                result["element_agent"].append(err)

    if code_errors:
        for err in code_errors:
            result["geometry_code_translator"].append(err)
            result["complete_code_generator"].append(err)

    return result
