from __future__ import annotations

from typing import Any


class RewardScorer:
    """Rule-based reward layer for API-driven LLM orchestration.

    This is intentionally not model fine-tuning. It turns observable artifacts
    into a stable technical reward signal that can guide retries and prompts.
    """

    def score(
        self,
        *,
        outputs: dict[str, Any],
        run_state: dict[str, Any],
        execution_state: dict[str, Any],
        section_diagram_state: dict[str, Any],
        feedback: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        components: list[dict[str, Any]] = []
        self._add_status_component(components, "pipeline_completed", run_state, 0.6, -0.6)
        self._add_presence_component(components, "analysis_outputs", outputs, ["problem_analysis", "construction_plan"], 0.25)
        self._add_presence_component(components, "geometry_outputs", outputs, ["node_output", "element_output"], 0.35)
        self._add_presence_component(components, "compiled_model", outputs, ["mapped_geometry", "load_output", "compiled_model"], 0.35)
        self._add_presence_component(components, "code_generated", outputs, ["geometry_code", "complete_code"], 0.35)
        self._add_status_component(components, "generated_code_execution", execution_state, 0.8, -0.8)
        self._add_status_component(components, "section_force_diagrams", section_diagram_state, 0.4, -0.25)

        python_check = outputs.get("python_check_output") or {}
        if python_check:
            components.append(
                {
                    "name": "python_check_diagnosis",
                    "value": -0.2 if python_check.get("should_retry") else -0.05,
                    "reason": str(python_check.get("root_cause") or "Python Check Agent produced a diagnosis."),
                }
            )

        if feedback:
            verdict = str(feedback.get("verdict", "")).lower()
            if verdict == "correct":
                components.append(
                    {"name": "human_feedback", "value": 1.0, "reason": "Human marked the current result as correct."}
                )
            elif verdict == "incorrect":
                components.append(
                    {"name": "human_feedback", "value": -1.0, "reason": "Human marked the current result as incorrect."}
                )

        total = round(sum(float(item["value"]) for item in components), 4)
        error_type = self._infer_error_type(run_state, execution_state, section_diagram_state, python_check, feedback)
        return {
            "schema_version": "1.0",
            "total_reward": total,
            "success": error_type == "none" and total >= 1.5,
            "error_type": error_type,
            "components": components,
        }

    def _add_presence_component(
        self,
        components: list[dict[str, Any]],
        name: str,
        outputs: dict[str, Any],
        keys: list[str],
        value: float,
    ) -> None:
        present = [key for key in keys if self._has_value(outputs.get(key))]
        missing = [key for key in keys if key not in present]
        partial = len(present) / max(len(keys), 1)
        components.append(
            {
                "name": name,
                "value": round(value * partial, 4),
                "reason": f"Present: {', '.join(present) or 'none'}; missing: {', '.join(missing) or 'none'}.",
            }
        )

    def _add_status_component(
        self,
        components: list[dict[str, Any]],
        name: str,
        state: dict[str, Any],
        success_value: float,
        failure_value: float,
    ) -> None:
        status = state.get("status", "idle")
        if status == "succeeded":
            value = success_value
        elif status == "failed":
            value = failure_value
        else:
            value = 0.0
        components.append(
            {
                "name": name,
                "value": value,
                "reason": str(state.get("message") or f"Status is {status}."),
            }
        )

    def _infer_error_type(
        self,
        run_state: dict[str, Any],
        execution_state: dict[str, Any],
        section_diagram_state: dict[str, Any],
        python_check: dict[str, Any],
        feedback: dict[str, Any] | None,
    ) -> str:
        if feedback and str(feedback.get("verdict", "")).lower() == "incorrect":
            return "human_rejected_output"
        if python_check.get("error_type"):
            return str(python_check["error_type"])
        if execution_state.get("status") == "failed":
            return "generated_code_execution_failed"
        if section_diagram_state.get("status") == "failed":
            return "visualization_failed"
        if run_state.get("status") == "failed":
            return "pipeline_failed"
        return "none"

    def _has_value(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (dict, list, tuple, set)):
            return bool(value)
        return True
