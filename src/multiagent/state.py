from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineState:
    user_input: str
    problem_analysis: dict[str, Any] | None = None
    construction_plan: dict[str, Any] | None = None
    node_output: dict[str, Any] | None = None
    element_output: dict[str, Any] | None = None
    mapped_geometry: dict[str, Any] | None = None
    load_output: dict[str, Any] | None = None
    compiled_json: dict[str, Any] | None = None
    geometry_code: str | None = None
    complete_code: str | None = None
    python_check_output: dict[str, Any] | None = None
    logs: list[str] = field(default_factory=list)

    def log(self, message: str) -> None:
        self.logs.append(message)
