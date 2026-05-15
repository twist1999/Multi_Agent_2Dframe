from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str]


# Canonical top-level contract names shared by all agents.
AGENT_OUTPUT_KEYS: dict[str, str] = {
    "problem_analysis": "problem_analysis",
    "construction_planning": "construction_plan",
    "node_agent": "node_output",
    "element_agent": "element_output",
    "load_assignment": "load_output",
    "geometry_code_translator": "geometry_code",
    "complete_code_generator": "complete_code",
    "python_check_agent": "python_check_output",
}


StepType = Literal["erect_column", "install_beam", "apply_load"]
ElementType = Literal["column", "beam", "brace", "wall", "truss", "other"]
ConstraintType = Literal["free", "fixed", "pinned", "roller", "custom"]
LoadTargetType = Literal["element", "node"]
LoadType = Literal["uniform", "point", "nodal", "moment", "temperature", "other"]
ExecutionErrorType = Literal[
    "missing_dependency",
    "syntax_error",
    "import_error",
    "runtime_api_error",
    "invalid_model_topology",
    "data_contract_error",
    "timeout",
    "unknown",
]


class GeometrySpec(TypedDict, total=False):
    system_type: str
    dimensionality: Literal["2D", "3D"]
    coordinate_system: str
    story_count: int
    bay_count: int
    bay_widths: list[float]
    story_heights: list[float]
    units: dict[str, str]
    description: str


class SupportSpec(TypedDict, total=False):
    support_id: str
    level: str
    location: str
    constraint_type: ConstraintType
    constrained_dofs: list[str]
    description: str


class MaterialSpec(TypedDict, total=False):
    material_id: str
    model: str
    parameters: dict[str, float | int | str]
    description: str


class SectionSpec(TypedDict, total=False):
    section_id: str
    element_type: ElementType
    shape: str
    parameters: dict[str, float | int | str]
    description: str


class LoadCaseSpec(TypedDict, total=False):
    load_case_id: str
    load_type: LoadType
    direction: str
    target: str
    magnitude: float
    distribution: str
    description: str


class ModelingIntent(TypedDict, total=False):
    target_platform: str
    visualization: list[str]
    output_language: str
    analysis_type: str


class ProblemAnalysisOutput(TypedDict, total=False):
    schema_version: str
    project_name: str
    problem_statement: str
    assumptions: list[str]
    geometry: GeometrySpec
    supports: list[SupportSpec]
    materials: list[MaterialSpec]
    sections: list[SectionSpec]
    load_cases: list[LoadCaseSpec]
    modeling_intent: ModelingIntent


class ConstructionStep(TypedDict, total=False):
    step_number: int
    step_type: StepType
    story_number: int
    bay_number: int | None
    node_ids: list[int]
    element_ids: list[int]
    depends_on: list[int]
    description: str


class ConstructionPlanOutput(TypedDict, total=False):
    schema_version: str
    total_steps: int
    construction_steps: list[ConstructionStep]
    sequencing_notes: list[str]


class NodeRecord(TypedDict, total=False):
    id: int
    x: float
    y: float
    z: float
    story_number: int
    bay_position: int
    label: str
    description: str


class BoundaryConditionRecord(TypedDict, total=False):
    node_id: int
    step_number: int
    constraint_type: ConstraintType
    constrained_dofs: list[str]
    description: str


class NodeStepRecord(TypedDict, total=False):
    step_number: int
    nodes: list[NodeRecord]
    boundary_conditions: list[BoundaryConditionRecord]


class NodeOutput(TypedDict, total=False):
    schema_version: str
    node_count: int
    construction_steps: list[NodeStepRecord]


class ElementRecord(TypedDict, total=False):
    id: int
    type: ElementType
    node_i: int
    node_j: int
    section_id: str
    material_id: str
    orientation: str
    story_number: int
    bay_number: int
    description: str


class ElementStepRecord(TypedDict, total=False):
    step_number: int
    elements: list[ElementRecord]


class ElementOutput(TypedDict, total=False):
    schema_version: str
    element_count: int
    construction_steps: list[ElementStepRecord]


class GeometryOutput(TypedDict, total=False):
    schema_version: str
    nodes: list[NodeRecord]
    boundary_conditions: list[BoundaryConditionRecord]
    elements: list[ElementRecord]


class AssignedLoad(TypedDict, total=False):
    load_case_id: str
    target_type: LoadTargetType
    target_ids: list[int]
    load_type: LoadType
    direction: str
    magnitude: float
    coordinate_system: str
    application_step: int | None
    description: str


class LoadOutput(TypedDict, total=False):
    schema_version: str
    assigned_loads: list[AssignedLoad]


class CompiledModel(TypedDict, total=False):
    schema_version: str
    problem_analysis: ProblemAnalysisOutput
    construction_plan: ConstructionPlanOutput
    geometry: GeometryOutput
    loads: LoadOutput


class ExecutionReport(TypedDict, total=False):
    python_path: str
    returncode: int | None
    stdout: str
    stderr: str
    started_at: str
    finished_at: str


class PythonCheckOutput(TypedDict, total=False):
    schema_version: str
    error_type: ExecutionErrorType
    root_cause: str
    responsible_stage: str
    confidence: float
    repair_action: str
    should_retry: bool
    suggested_target_agent: str
    notes: list[str]


class AgentContract(TypedDict):
    input_keys: list[str]
    output_key: str
    output_description: str


AGENT_CONTRACTS: dict[str, AgentContract] = {
    "problem_analysis": {
        "input_keys": ["user_input"],
        "output_key": AGENT_OUTPUT_KEYS["problem_analysis"],
        "output_description": "Structured model intent extracted from natural language.",
    },
    "construction_planning": {
        "input_keys": [AGENT_OUTPUT_KEYS["problem_analysis"]],
        "output_key": AGENT_OUTPUT_KEYS["construction_planning"],
        "output_description": "Ordered construction and load application steps.",
    },
    "node_agent": {
        "input_keys": [
            AGENT_OUTPUT_KEYS["problem_analysis"],
            AGENT_OUTPUT_KEYS["construction_planning"],
        ],
        "output_key": AGENT_OUTPUT_KEYS["node_agent"],
        "output_description": "Step-indexed node and boundary-condition records.",
    },
    "element_agent": {
        "input_keys": [
            AGENT_OUTPUT_KEYS["problem_analysis"],
            AGENT_OUTPUT_KEYS["construction_planning"],
        ],
        "output_key": AGENT_OUTPUT_KEYS["element_agent"],
        "output_description": "Step-indexed element records using canonical node ids.",
    },
    "load_assignment": {
        "input_keys": [
            AGENT_OUTPUT_KEYS["problem_analysis"],
            "geometry",
        ],
        "output_key": AGENT_OUTPUT_KEYS["load_assignment"],
        "output_description": "Resolved load assignments against node/element ids.",
    },
    "geometry_code_translator": {
        "input_keys": ["compiled_model"],
        "output_key": AGENT_OUTPUT_KEYS["geometry_code_translator"],
        "output_description": "Geometry-only OpenSeesPy code.",
    },
    "complete_code_generator": {
        "input_keys": ["compiled_model", AGENT_OUTPUT_KEYS["geometry_code_translator"]],
        "output_key": AGENT_OUTPUT_KEYS["complete_code_generator"],
        "output_description": "Complete executable OpenSeesPy script.",
    },
    "python_check_agent": {
        "input_keys": [
            "user_input",
            "compiled_model",
            AGENT_OUTPUT_KEYS["geometry_code_translator"],
            AGENT_OUTPUT_KEYS["complete_code_generator"],
            "execution_report",
        ],
        "output_key": AGENT_OUTPUT_KEYS["python_check_agent"],
        "output_description": "Diagnosis of generated-code execution failures with repair guidance.",
    },
}
