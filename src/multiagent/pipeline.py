from __future__ import annotations

from .agents.complete_code_generator import CompleteCodeGenerator
from .agents.construction_planning import ConstructionPlanningAgent
from .agents.element_agent import ElementAgent
from .agents.geometry_code_translator import GeometryCodeTranslator
from .agents.load_assignment import LoadAssignmentAgent
from .agents.node_agent import NodeAgent
from .agents.problem_analysis import ProblemAnalysisAgent
from .config import PipelineConfig
from .functions.connectivity_mapping import map_connectivity
from .functions.json_compiler import compile_json
from .llm.client import LLMClient
from .state import PipelineState
from .utils import dump_json, dump_text
from .validators.checkpoints import validate_analysis_planning, validate_geometry


class StructuralModelingPipeline:
    def __init__(self, config: PipelineConfig, llm_client: LLMClient | None = None) -> None:
        self.config = config
        self.llm_client = llm_client or LLMClient()
        self.problem_analysis_agent = ProblemAnalysisAgent(self.llm_client, config.problem_analysis)
        self.construction_planning_agent = ConstructionPlanningAgent(self.llm_client, config.construction_planning)
        self.node_agent = NodeAgent(self.llm_client, config.node_agent)
        self.element_agent = ElementAgent(self.llm_client, config.element_agent)
        self.load_assignment_agent = LoadAssignmentAgent(self.llm_client, config.load_assignment)
        self.geometry_code_translator = GeometryCodeTranslator(self.llm_client, config.geometry_code_translator)
        self.complete_code_generator = CompleteCodeGenerator(self.llm_client, config.complete_code_generator)

    def run(self, user_input: str) -> PipelineState:
        state = PipelineState(user_input=user_input)
        state.log("Starting analysis and planning module.")
        self._run_analysis_and_planning(state)
        state.log("Starting geometry assembly module.")
        self._run_geometry_assembly(state)
        state.log("Starting load integration module.")
        self._run_load_integration(state)
        state.log("Starting code translation module.")
        self._run_code_translation(state)
        self._persist_outputs(state)
        return state

    def _run_analysis_and_planning(self, state: PipelineState) -> None:
        for attempt in range(1, self.config.max_retries_analysis_planning + 1):
            state.log(f"Analysis/planning attempt {attempt}.")
            problem_analysis = self.problem_analysis_agent.run(state.user_input)
            construction_plan = self.construction_planning_agent.run(problem_analysis)
            result = validate_analysis_planning(problem_analysis, construction_plan)
            if result.ok:
                state.problem_analysis = problem_analysis
                state.construction_plan = construction_plan
                return
            state.log("Analysis/planning checkpoint failed: " + "; ".join(result.errors))
        raise RuntimeError("Analysis and planning checkpoint failed after maximum retries.")

    def _run_geometry_assembly(self, state: PipelineState) -> None:
        assert state.problem_analysis is not None
        assert state.construction_plan is not None
        for attempt in range(1, self.config.max_retries_geometry + 1):
            state.log(f"Geometry assembly attempt {attempt}.")
            node_output = self.node_agent.run(state.problem_analysis, state.construction_plan)
            element_output = self.element_agent.run(state.problem_analysis, state.construction_plan)
            result = validate_geometry(node_output, element_output)
            if result.ok:
                state.node_output = node_output
                state.element_output = element_output
                state.mapped_geometry = map_connectivity(node_output, element_output)
                return
            state.log("Geometry checkpoint failed: " + "; ".join(result.errors))
        raise RuntimeError("Geometry checkpoint failed after maximum retries.")

    def _run_load_integration(self, state: PipelineState) -> None:
        assert state.problem_analysis is not None
        assert state.mapped_geometry is not None
        state.load_output = self.load_assignment_agent.run(state.problem_analysis, state.mapped_geometry)
        state.compiled_json = compile_json(state.problem_analysis, state.mapped_geometry, state.load_output)

    def _run_code_translation(self, state: PipelineState) -> None:
        assert state.compiled_json is not None
        state.geometry_code = self.geometry_code_translator.run(state.compiled_json)
        state.complete_code = self.complete_code_generator.run(state.compiled_json, state.geometry_code)

    def _persist_outputs(self, state: PipelineState) -> None:
        if not self.config.write_outputs:
            return
        out_dir = self.config.output_dir
        dump_json(out_dir / "state_problem_analysis.json", state.problem_analysis or {})
        dump_json(out_dir / "state_construction_plan.json", state.construction_plan or {})
        dump_json(out_dir / "state_node_output.json", state.node_output or {})
        dump_json(out_dir / "state_element_output.json", state.element_output or {})
        dump_json(out_dir / "state_mapped_geometry.json", state.mapped_geometry or {})
        dump_json(out_dir / "state_load_output.json", state.load_output or {})
        dump_json(out_dir / "state_compiled.json", state.compiled_json or {})
        dump_text(out_dir / "geometry_code.py", state.geometry_code or "")
        dump_text(out_dir / "complete_code.py", state.complete_code or "")
        dump_text(out_dir / "pipeline.log", "\n".join(state.logs))
