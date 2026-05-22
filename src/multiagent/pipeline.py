from __future__ import annotations

import ast
import time
from typing import Any

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
from .rag_context import RAGContextProvider
from .rl.agent_reward import AgentRewardDecomposer, classify_checkpoint_errors
from .rl.repair import build_repair_hint
from .state import PipelineState
from .utils import dump_json, dump_text
from .validators.checkpoints import (
    _error_is_element_fault,
    _error_is_node_fault,
    validate_analysis_planning,
    validate_geometry,
    validate_geometry_consistency,
)


class StructuralModelingPipeline:
    def __init__(self, config: PipelineConfig, llm_client: LLMClient | None = None,
                 optimizer: Any = None) -> None:
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

        # RL components
        self._optimizer: Any = optimizer
        self._experience_buffer: Any = None
        self._reward_decomposer: Any = None
        self._checkpoint_errors: dict[str, list[str]] = {}
        self._variant_tracker: dict[str, str] = {}  # agent_name -> variant_id
        self._consistency_details: dict[str, Any] | None = None

    @property
    def optimizer(self):
        if self._optimizer is None:
            from .rl.prompt_optimizer import MultiAgentOptimizer
            if self.config.rl.use_presets:
                self._optimizer = MultiAgentOptimizer.from_presets(
                    epsilon=self.config.rl.epsilon,
                    alpha=self.config.rl.alpha,
                    presets_path=self.config.rl.presets_path,
                )
            else:
                self._optimizer = MultiAgentOptimizer(
                    epsilon=self.config.rl.epsilon,
                    alpha=self.config.rl.alpha,
                )
        return self._optimizer

    @property
    def experience_buffer(self):
        if self._experience_buffer is None:
            from .rl.experience_buffer import ExperienceBuffer
            self._experience_buffer = ExperienceBuffer(max_records_per_agent=self.config.rl.buffer_size)
        return self._experience_buffer

    @property
    def reward_decomposer(self):
        if self._reward_decomposer is None:
            self._reward_decomposer = AgentRewardDecomposer()
        return self._reward_decomposer

    def _select_variant(self, agent_name: str) -> Any | None:
        """Select a prompt variant for the given agent if RL bandit is enabled."""
        if not self.config.rl.enabled or not self.config.rl.use_bandit:
            return None
        variant = self.optimizer.select(agent_name)
        self._variant_tracker[agent_name] = variant.variant_id
        return variant

    def _record_agent_experience(
        self,
        agent_name: str,
        run_id: str,
        agent_reward: Any,
        success: bool,
        llm_input: str = "",
        llm_output: str = "",
    ) -> None:
        """Store per-agent experience to the buffer."""
        if not self.config.rl.enabled:
            return
        from .rl.experience_buffer import hash_prompt
        self.experience_buffer.insert(
            agent_name=agent_name,
            run_id=run_id,
            prompt_hash=hash_prompt(llm_input),
            prompt_variant=self._variant_tracker.get(agent_name, "default"),
            input_signature=agent_reward.details.get("input_signature", ""),
            reward=agent_reward.total,
            base_success=agent_reward.base_success,
            validation_pass=agent_reward.validation_pass,
            downstream_feedback=agent_reward.downstream_feedback,
            error_categories=agent_reward.error_categories,
            success=success,
            llm_input=llm_input,
            llm_output=llm_output,
        )
        # Update bandit Q-value if using bandit
        if self.config.rl.use_bandit and agent_name in self._variant_tracker:
            self.optimizer.update(agent_name, self._variant_tracker[agent_name], agent_reward.total)

    def decompose_and_record(self, outputs: dict, run_id: str, execution_state: dict, feedback: dict | None = None) -> dict:
        """Decompose pipeline reward into per-agent rewards and record experiences."""
        if not self.config.rl.enabled:
            return {}
        checkpoint_errors = classify_checkpoint_errors(
            analysis_errors=self._checkpoint_errors.get("analysis_planning"),
            geometry_errors=self._checkpoint_errors.get("geometry"),
            code_errors=self._checkpoint_errors.get("code_translation"),
            consistency_errors=self._checkpoint_errors.get("geometry_consistency"),
        )
        agent_rewards = self.reward_decomposer.decompose(
            outputs=outputs,
            checkpoint_errors=checkpoint_errors,
            execution_state=execution_state,
            feedback=feedback,
        )
        for agent_name, reward in agent_rewards.items():
            self._record_agent_experience(
                agent_name=agent_name,
                run_id=run_id,
                agent_reward=reward,
                success=reward.total >= 0.5,
            )
        return agent_rewards

    def run(self, user_input: str) -> PipelineState:
        self._checkpoint_errors = {}
        self._variant_tracker = {}
        self._consistency_details = None
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
        all_errors: list[str] = []
        pa_variant = self._select_variant("problem_analysis")
        cp_variant = self._select_variant("construction_planning")
        for attempt in range(1, self.config.max_retries_analysis_planning + 1):
            state.log(f"Analysis/planning attempt {attempt}.")
            try:
                problem_analysis = self.problem_analysis_agent.run(
                    state.user_input, repair_hint=repair_hint,
                    prompt_override=pa_variant.load() if pa_variant else None,
                )
                construction_plan = self.construction_planning_agent.run(
                    problem_analysis, repair_hint=repair_hint,
                    prompt_override=cp_variant.load() if cp_variant else None,
                )
            except Exception as exc:
                state.log(f"Analysis/planning API call failed: {exc}")
                all_errors.append(str(exc))
                if attempt < self.config.max_retries_analysis_planning:
                    time.sleep(2 ** attempt)
                    continue
                self._checkpoint_errors["analysis_planning"] = all_errors
                raise RuntimeError(f"Analysis/planning API call failed after {attempt} retries.") from exc
            result = validate_analysis_planning(problem_analysis, construction_plan)
            if result.ok:
                state.problem_analysis = problem_analysis
                state.construction_plan = construction_plan
                self._checkpoint_errors["analysis_planning"] = all_errors
                return
            state.log("Analysis/planning checkpoint failed: " + "; ".join(result.errors))
            all_errors.extend(result.errors)
            repair_hint = build_repair_hint("analysis_planning", result.errors, attempt)
            if self.config.write_outputs:
                dump_json(self.config.output_dir / "debug_problem_analysis.json", problem_analysis)
                dump_json(self.config.output_dir / "debug_construction_plan.json", construction_plan)
                dump_text(self.config.output_dir / "pipeline.log", "\n".join(state.logs))
        self._checkpoint_errors["analysis_planning"] = all_errors
        raise RuntimeError("Analysis and planning checkpoint failed after maximum retries.")

    def _run_geometry_assembly(self, state: PipelineState) -> None:
        assert state.problem_analysis is not None
        assert state.construction_plan is not None
        repair_hint: str | None = None
        node_repair_hint: str | None = None
        elem_repair_hint: str | None = None
        all_errors: list[str] = []
        all_consistency_errors: list[str] = []
        n_variant = self._select_variant("node_agent")
        e_variant = self._select_variant("element_agent")
        for attempt in range(1, self.config.max_retries_geometry + 1):
            state.log(f"Geometry assembly attempt {attempt}.")
            try:
                # Allow per-agent targeted repair hints
                node_hint = node_repair_hint or repair_hint
                elem_hint = elem_repair_hint or repair_hint
                node_output = self.node_agent.run(
                    state.problem_analysis, state.construction_plan, repair_hint=node_hint,
                    prompt_override=n_variant.load() if n_variant else None,
                )
                element_output = self.element_agent.run(
                    state.problem_analysis, state.construction_plan, repair_hint=elem_hint,
                    prompt_override=e_variant.load() if e_variant else None,
                )
            except Exception as exc:
                state.log(f"Geometry assembly API call failed: {exc}")
                all_errors.append(str(exc))
                if attempt < self.config.max_retries_geometry:
                    time.sleep(2 ** attempt)
                    continue
                self._checkpoint_errors["geometry"] = all_errors
                raise RuntimeError(f"Geometry assembly API call failed after {attempt} retries.") from exc

            # Phase 1: Basic schema validation
            result = validate_geometry(node_output, element_output)
            if not result.ok:
                state.log("Geometry checkpoint failed: " + "; ".join(result.errors))
                all_errors.extend(result.errors)
                repair_hint = build_repair_hint("geometry_assembly", result.errors, attempt)
                node_repair_hint = None
                elem_repair_hint = None
                if self.config.write_outputs:
                    dump_json(self.config.output_dir / "debug_node_output.json", node_output)
                    dump_json(self.config.output_dir / "debug_element_output.json", element_output)
                    dump_text(self.config.output_dir / "pipeline.log", "\n".join(state.logs))
                continue

            # Phase 2: Structural consistency check (new)
            consistency = validate_geometry_consistency(
                node_output, element_output,
                problem_analysis=state.problem_analysis,
                construction_plan=state.construction_plan,
            )
            state.log(
                f"Geometry consistency: errors={consistency.details.get('summary', {}).get('total_errors', 0)}, "
                f"warnings={consistency.details.get('summary', {}).get('total_warnings', 0)}"
            )

            if not consistency.ok:
                state.log("Geometry consistency check failed: " + "; ".join(consistency.errors))
                all_consistency_errors.extend(consistency.errors)
                all_errors.extend(consistency.errors)

                # Classify errors by agent for targeted retry
                node_errs = [e for e in consistency.errors if _error_is_node_fault(e)]
                elem_errs = [e for e in consistency.errors if _error_is_element_fault(e)]

                if node_errs and not elem_errs:
                    node_repair_hint = build_repair_hint("geometry_assembly", node_errs, attempt)
                    elem_repair_hint = None
                    state.log("Targeting Node Agent for repair (node-specific errors only).")
                elif elem_errs and not node_errs:
                    elem_repair_hint = build_repair_hint("geometry_assembly", elem_errs, attempt)
                    node_repair_hint = None
                    state.log("Targeting Element Agent for repair (element-specific errors only).")
                else:
                    node_repair_hint = build_repair_hint("geometry_assembly", node_errs, attempt) if node_errs else None
                    elem_repair_hint = build_repair_hint("geometry_assembly", elem_errs, attempt) if elem_errs else None
                    repair_hint = build_repair_hint("geometry_assembly", consistency.errors, attempt)

                if self.config.write_outputs:
                    dump_json(self.config.output_dir / "debug_node_output.json", node_output)
                    dump_json(self.config.output_dir / "debug_element_output.json", element_output)
                    dump_json(self.config.output_dir / "debug_geometry_consistency.json", consistency.details)
                    dump_text(self.config.output_dir / "pipeline.log", "\n".join(state.logs))
                continue

            # Both validations passed
            state.node_output = node_output
            state.element_output = element_output
            state.mapped_geometry = map_connectivity(node_output, element_output)
            self._checkpoint_errors["geometry"] = all_errors
            self._checkpoint_errors["geometry_consistency"] = all_consistency_errors
            # Persist consistency details for UI
            if consistency.details:
                self._consistency_details = consistency.details
            return

        self._checkpoint_errors["geometry"] = all_errors
        self._checkpoint_errors["geometry_consistency"] = all_consistency_errors
        raise RuntimeError("Geometry checkpoint failed after maximum retries.")

    def _run_load_integration(self, state: PipelineState) -> None:
        assert state.problem_analysis is not None
        assert state.mapped_geometry is not None
        la_variant = self._select_variant("load_assignment")
        state.load_output = self.load_assignment_agent.run(
            state.problem_analysis, state.mapped_geometry,
            prompt_override=la_variant.load() if la_variant else None,
        )
        state.compiled_json = compile_json(state.problem_analysis, state.mapped_geometry, state.load_output)

    def _run_code_translation(self, state: PipelineState) -> None:
        assert state.compiled_json is not None
        last_error: str | None = None
        repair_hint: str | None = None
        all_errors: list[str] = []
        gc_variant = self._select_variant("geometry_code_translator")
        cc_variant = self._select_variant("complete_code_generator")
        for attempt in range(1, self.config.max_retries_code_translation + 1):
            state.log(f"Code translation attempt {attempt}.")
            try:
                geometry_code = self.geometry_code_translator.run(
                    state.compiled_json, repair_hint=repair_hint,
                    prompt_override=gc_variant.load() if gc_variant else None,
                )
                complete_code = self.complete_code_generator.run(
                    state.compiled_json, geometry_code, repair_hint=repair_hint,
                    prompt_override=cc_variant.load() if cc_variant else None,
                )
            except Exception as exc:
                state.log(f"Code translation API call failed: {exc}")
                last_error = str(exc)
                all_errors.append(last_error)
                if attempt < self.config.max_retries_code_translation:
                    time.sleep(2 ** attempt)
                    continue
                self._checkpoint_errors["code_translation"] = all_errors
                raise RuntimeError(f"Code translation API call failed after {attempt} retries.") from exc

            syntax_error = self._validate_python_code(complete_code)
            if syntax_error is None:
                state.geometry_code = geometry_code
                state.complete_code = complete_code
                self._checkpoint_errors["code_translation"] = all_errors
                return

            last_error = syntax_error
            all_errors.append(syntax_error)
            state.log("Code translation syntax check failed: " + syntax_error)
            repair_hint = build_repair_hint("code_translation", [syntax_error], attempt)

        self._checkpoint_errors["code_translation"] = all_errors
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
        if self._consistency_details:
            dump_json(out_dir / "geometry_consistency.json", self._consistency_details)
