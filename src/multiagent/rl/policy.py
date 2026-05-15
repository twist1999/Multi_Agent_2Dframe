from __future__ import annotations

from typing import Any


class RulePolicy:
    """Policy optimization layer for choosing the next orchestration action."""

    def choose(
        self,
        *,
        reward_report: dict[str, Any],
        outputs: dict[str, Any],
        run_state: dict[str, Any],
        execution_state: dict[str, Any],
        section_diagram_state: dict[str, Any],
        feedback: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        error_type = reward_report.get("error_type", "none")
        python_check = outputs.get("python_check_output") or {}

        if feedback and str(feedback.get("verdict", "")).lower() == "incorrect":
            return {
                "action_type": "targeted_reanalysis",
                "target_agent": self._target_from_feedback(feedback),
                "reason": "Human feedback rejected the current output; retry the clicked agent with a focused repair prompt.",
                "params": {"feedback_notes": feedback.get("notes", "")},
            }

        if execution_state.get("status") == "failed" and python_check.get("should_retry"):
            return {
                "action_type": "repair_and_retry",
                "target_agent": python_check.get("suggested_target_agent") or "CompleteCodeGenerator",
                "reason": python_check.get("repair_action") or "Generated code failed and Python Check Agent recommends retry.",
                "params": {"error_type": python_check.get("error_type"), "confidence": python_check.get("confidence")},
            }

        if execution_state.get("status") == "failed":
            return {
                "action_type": "retry_code_generation",
                "target_agent": "CompleteCodeGenerator",
                "reason": "Generated code execution failed; regenerate complete code with stricter OpenSeesPy syntax constraints.",
                "params": {"increase_rag_top_k": True, "include_stderr": True},
            }

        if section_diagram_state.get("status") == "failed":
            return {
                "action_type": "repair_visualization",
                "target_agent": "CompleteCodeGenerator",
                "reason": "Opsvis section-force rendering failed; keep model generation but adjust analysis/visualization code.",
                "params": {"include_section_diagram_stderr": True},
            }

        if run_state.get("status") == "failed":
            return {
                "action_type": "retry_pipeline",
                "target_agent": "orchestrator",
                "reason": "Pipeline failed before a complete artifact set was produced.",
                "params": {"use_schema_guardrails": True},
            }

        if reward_report.get("success"):
            return {
                "action_type": "accept",
                "target_agent": "none",
                "reason": "Current artifacts passed the rule-based reward threshold.",
                "params": {},
            }

        return {
            "action_type": "observe_more",
            "target_agent": "orchestrator",
            "reason": "No hard failure is visible yet; collect execution result or human feedback before retrying.",
            "params": {"error_type": error_type},
        }

    def _target_from_feedback(self, feedback: dict[str, Any]) -> str:
        selected = feedback.get("selected_object") or {}
        kind = str(selected.get("kind", "")).lower()
        if kind == "node":
            return "NodeAgent"
        if kind == "element":
            return "ElementAgent"
        return "orchestrator"
