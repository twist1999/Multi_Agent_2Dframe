from __future__ import annotations

from typing import Any

STAGE_GUIDANCE: dict[str, str] = {
    "analysis_planning": (
        "The Problem Analysis or Construction Plan JSON failed validation. "
        "Review the error messages below and fix the JSON structure accordingly. "
        "Ensure bay/story geometry is present, construction steps cover every bay-story pair, "
        "and step numbers are unique."
    ),
    "geometry_assembly": (
        "The Node or Element output failed geometry validation. "
        "Ensure every node ID is unique, every element ID is unique, "
        "and every element references existing node IDs. "
        "Check that coordinate values are numeric and element connectivity is correct."
    ),
    "code_translation": (
        "The generated Python code has syntax errors. "
        "Fix the syntax errors and regenerate valid OpenSeesPy code. "
        "Check for missing parentheses, incorrect indentation, or invalid variable names."
    ),
}


def build_repair_hint(
    stage: str,
    errors: list[str],
    attempt: int,
) -> str:
    """Build a compact repair hint from validation errors for pipeline retries.

    This is a lightweight version that works without the full RL reward stack.
    It can be used directly in pipeline.py retry loops.
    """
    if not errors:
        return ""

    error_text = "\n".join(f"  - {err}" for err in errors)
    guidance = STAGE_GUIDANCE.get(stage, "Fix the validation errors listed below.")

    return "\n".join([
        "",
        "REPAIR CONTEXT (previous attempt failed validation):",
        f"Attempt {attempt} failed. {guidance}",
        "Validation errors:",
        error_text,
        "",
        "Please fix these issues and regenerate the output with the correct structure.",
    ])


def build_repair_prompt(
    base_prompt: str,
    policy_action: dict[str, Any],
    reward_report: dict[str, Any],
) -> str:
    """Build a full RL-informed repair prompt for the next LLM retry.

    This is the webapp / RL-stack version that uses the complete reward report
    and policy decision to provide richer repair context.
    """
    failed_components = [
        component
        for component in reward_report.get("components", [])
        if float(component.get("value", 0.0)) < 0
    ]
    component_text = "\n".join(
        f"- {item.get('name')}: {item.get('reason')}" for item in failed_components
    ) or "- No negative reward component was found."

    return "\n".join(
        [
            base_prompt.strip(),
            "",
            "RL-style repair context:",
            f"Recommended action: {policy_action.get('action_type')} -> {policy_action.get('target_agent')}",
            f"Reason: {policy_action.get('reason')}",
            f"Reward total: {reward_report.get('total_reward')}",
            "Negative reward components:",
            component_text,
            "",
            "Repair only the failing part, preserve validated artifacts where possible, and return the expected schema.",
        ]
    )
