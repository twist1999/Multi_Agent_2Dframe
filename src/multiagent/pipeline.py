from __future__ import annotations

import ast

from .agents.complete_code_generator import CompleteCodeGenerator
from .agents.construction_planning import ConstructionPlanningAgent
from .agents.element_agent import ElementAgent
from .agents.geometry_code_translator import GeometryCodeTranslator
from .agents.load_assignment import LoadAssignmentAgent
from .agents.node_agent import NodeAgent
from .agents.problem_analysis import ProblemAnalysisAgent
from .config import PipelineConfig
import time

from .functions.connectivity_mapping import map_connectivity
from .functions.json_compiler import compile_json
from .llm.client import LLMClient
from .rag_context import RAGContextProvider
from .rl.repair import build_repair_hint
from .state import PipelineState
from .utils import dump_json, dump_text
from .validators.checkpoints import validate_analysis_planning, validate_geometry


class StructuralModelingPipeline:
    def __init__(self, config: PipelineConfig, llm_client: LLMClient | None = None) -> None:
        self.config = config
        self.llm_client = llm_client or LLMClient()
        self.rag_context = RAGContextProvider(config.rag)
        self.problem_analysis_agent = ProblemAnalysisAgent(self.llm_client, config.problem_analysis)
        self.construction_planning_agent = ConstructionPlanningAgent(self.llm_client, config.construction_planning)
        self.node_agent = NodeAgent(self.llm_client, config.node_agent)
        self.element_agent = ElementAgent(self.llm_client, config.element_agent)
        self.load_assignment_agent = LoadAssignmentAgent(self.llm_client, config.load_assignment)
        self.geometry_code_translator = GeometryCodeTranslator(
            self.llm_client,
            config.geometry_code_translator,
            rag_context=self.rag_context,
        )
        self.complete_code_generator = CompleteCodeGenerator(
            self.llm_client,
            config.complete_code_generator,
            rag_context=self.rag_context,
        )

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
        repair_hint: str | None = None
        for attempt in range(1, self.config.max_retries_analysis_planning + 1):
            state.log(f"Analysis/planning attempt {attempt}.")
            try:
                problem_analysis = self.problem_analysis_agent.run(state.user_input, repair_hint=repair_hint)
                construction_plan = self.construction_planning_agent.run(problem_analysis, repair_hint=repair_hint)
            except Exception as exc:
                state.log(f"Analysis/planning API call failed: {exc}")
                if attempt < self.config.max_retries_analysis_planning:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"Analysis/planning API call failed after {attempt} retries.") from exc
            result = validate_analysis_planning(problem_analysis, construction_plan)
            if result.ok:
                state.problem_analysis = problem_analysis
                state.construction_plan = construction_plan
                return
            state.log("Analysis/planning checkpoint failed: " + "; ".join(result.errors))
            repair_hint = build_repair_hint("analysis_planning", result.errors, attempt)
            if self.config.write_outputs:
                dump_json(self.config.output_dir / "debug_problem_analysis.json", problem_analysis)
                dump_json(self.config.output_dir / "debug_construction_plan.json", construction_plan)
                dump_text(self.config.output_dir / "pipeline.log", "\n".join(state.logs))
        raise RuntimeError("Analysis and planning checkpoint failed after maximum retries.")

    def _run_geometry_assembly(self, state: PipelineState) -> None:
        assert state.problem_analysis is not None
        assert state.construction_plan is not None
        repair_hint: str | None = None
        for attempt in range(1, self.config.max_retries_geometry + 1):
            state.log(f"Geometry assembly attempt {attempt}.")
            try:
                node_output = self.node_agent.run(state.problem_analysis, state.construction_plan, repair_hint=repair_hint)
                element_output = self.element_agent.run(state.problem_analysis, state.construction_plan, repair_hint=repair_hint)
            except Exception as exc:
                state.log(f"Geometry assembly API call failed: {exc}")
                if attempt < self.config.max_retries_geometry:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"Geometry assembly API call failed after {attempt} retries.") from exc
            result = validate_geometry(node_output, element_output)
            if result.ok:
                state.node_output = node_output
                state.element_output = element_output
                state.mapped_geometry = map_connectivity(node_output, element_output)
                return
            state.log("Geometry checkpoint failed: " + "; ".join(result.errors))
            repair_hint = build_repair_hint("geometry_assembly", result.errors, attempt)
            if self.config.write_outputs:
                dump_json(self.config.output_dir / "debug_node_output.json", node_output)
                dump_json(self.config.output_dir / "debug_element_output.json", element_output)
                dump_text(self.config.output_dir / "pipeline.log", "\n".join(state.logs))
        raise RuntimeError("Geometry checkpoint failed after maximum retries.")

    def _run_load_integration(self, state: PipelineState) -> None:
        assert state.problem_analysis is not None
        assert state.mapped_geometry is not None
        state.load_output = self.load_assignment_agent.run(state.problem_analysis, state.mapped_geometry)
        state.compiled_json = compile_json(state.problem_analysis, state.mapped_geometry, state.load_output)

    def _run_code_translation(self, state: PipelineState) -> None:
        assert state.compiled_json is not None
        last_error: str | None = None
        repair_hint: str | None = None
        for attempt in range(1, self.config.max_retries_code_translation + 1):
            state.log(f"Code translation attempt {attempt}.")
            try:
                geometry_code = self.geometry_code_translator.run(state.compiled_json, repair_hint=repair_hint)
                complete_code = self.complete_code_generator.run(state.compiled_json, geometry_code, repair_hint=repair_hint)
            except Exception as exc:
                state.log(f"Code translation API call failed: {exc}")
                last_error = str(exc)
                if attempt < self.config.max_retries_code_translation:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"Code translation API call failed after {attempt} retries.") from exc

            syntax_error = self._validate_python_code(complete_code)
            if syntax_error is None:
                state.geometry_code = geometry_code
                state.complete_code = complete_code
                return

            last_error = syntax_error
            state.log("Code translation syntax check failed: " + syntax_error)
            repair_hint = build_repair_hint("code_translation", [syntax_error], attempt)

        raise RuntimeError(
            "Code translation failed after maximum retries."
            + (f" Last syntax error: {last_error}" if last_error else "")
        )

    def _validate_python_code(self, code: str) -> str | None:
        try:
            ast.parse(code)
        except SyntaxError as exc:
            return f"{exc.msg} at line {exc.lineno}"
        return None

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
