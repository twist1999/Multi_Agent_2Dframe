from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import traceback
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlparse

from .agents.python_check_agent import PythonCheckAgent
from .benchmark import BenchmarkCase, generate_benchmark_cases
from .config import OUTPUT_ROOT, PROJECT_ROOT, PipelineConfig, ensure_directories
from .functions.execution_diagnostics import build_execution_report
from .llm.client import LLMClient, reset_token_usage_callback, set_token_usage_callback
from .pipeline import StructuralModelingPipeline
from .rl.logger import RLLogger
from .rl.policy import RulePolicy
from .rl.reward import RewardScorer
from .rl.prompt_optimizer import MultiAgentOptimizer


WEB_ROOT = PROJECT_ROOT / "src" / "multiagent" / "web"
FEEDBACK_FILE = OUTPUT_ROOT / "feedback_history.jsonl"
RL_STATUS_FILE = OUTPUT_ROOT / "rl_status.json"
CURRENT_PROMPT_FILE = OUTPUT_ROOT / "current_prompt.json"
RUN_STATUS_FILE = OUTPUT_ROOT / "run_status.json"
EXECUTION_STATUS_FILE = OUTPUT_ROOT / "execution_status.json"
EXECUTION_STDOUT_FILE = OUTPUT_ROOT / "execution_stdout.txt"
EXECUTION_STDERR_FILE = OUTPUT_ROOT / "execution_stderr.txt"
GENERATED_CODE_FILE = OUTPUT_ROOT / "complete_code.py"
PYTHON_CHECK_OUTPUT_FILE = OUTPUT_ROOT / "python_check_output.json"
AXIAL_DIAGRAM_FILE = OUTPUT_ROOT / "axial_force_diagram.png"
SHEAR_DIAGRAM_FILE = OUTPUT_ROOT / "shear_force_diagram.png"
MOMENT_DIAGRAM_FILE = OUTPUT_ROOT / "moment_force_diagram.png"
SECTION_DIAGRAM_STATUS_FILE = OUTPUT_ROOT / "section_diagram_status.json"
SECTION_DIAGRAM_STDOUT_FILE = OUTPUT_ROOT / "section_diagram_stdout.txt"
SECTION_DIAGRAM_STDERR_FILE = OUTPUT_ROOT / "section_diagram_stderr.txt"
SECTION_DIAGRAM_DPI = int(os.getenv("SECTION_DIAGRAM_DPI", "450"))
BENCHMARK_STATUS_FILE = OUTPUT_ROOT / "benchmark_status.json"
AGENT_LLM_CONFIG_FILE = OUTPUT_ROOT / "agent_llm_config.json"
BENCHMARK_ARTIFACT_ROOT = OUTPUT_ROOT / "benchmark_artifacts"
MODEL_VISUALIZATION_FILE = OUTPUT_ROOT / "model_visualization.png"
NODE_VISUALIZATION_FILE = OUTPUT_ROOT / "node_visualization.png"
ELEMENT_VISUALIZATION_FILE = OUTPUT_ROOT / "element_visualization.png"
VISUALIZATION_STATUS_FILE = OUTPUT_ROOT / "visualization_status.json"
VISUALIZATION_STDOUT_FILE = OUTPUT_ROOT / "visualization_stdout.txt"
VISUALIZATION_STDERR_FILE = OUTPUT_ROOT / "visualization_stderr.txt"
GEOMETRY_CODE_FILE = OUTPUT_ROOT / "geometry_code.py"
PIPELINE_ARTIFACT_FILES = [
    OUTPUT_ROOT / "state_problem_analysis.json",
    OUTPUT_ROOT / "state_construction_plan.json",
    OUTPUT_ROOT / "state_node_output.json",
    OUTPUT_ROOT / "state_element_output.json",
    OUTPUT_ROOT / "state_mapped_geometry.json",
    OUTPUT_ROOT / "state_load_output.json",
    OUTPUT_ROOT / "state_compiled.json",
    OUTPUT_ROOT / "geometry_code.py",
    OUTPUT_ROOT / "complete_code.py",
    OUTPUT_ROOT / "pipeline.log",
    OUTPUT_ROOT / "debug_problem_analysis.json",
    OUTPUT_ROOT / "debug_construction_plan.json",
    OUTPUT_ROOT / "geometry_consistency.json",
]


RUN_STATE_LOCK = threading.Lock()
RUN_STATE: dict[str, str | None] = {
    "status": "idle",
    "message": "Ready to run.",
    "started_at": None,
    "finished_at": None,
    "error": None,
}

EXECUTION_STATE_LOCK = threading.Lock()
EXECUTION_STATE: dict[str, str | None | int] = {
    "status": "idle",
    "message": "Ready to execute generated code.",
    "started_at": None,
    "finished_at": None,
    "error": None,
    "returncode": None,
    "python_path": None,
}

VISUALIZATION_STATE_LOCK = threading.Lock()
VISUALIZATION_STATE: dict[str, str | None] = {
    "status": "idle",
    "message": "Ready to render model visualization.",
    "started_at": None,
    "finished_at": None,
    "error": None,
    "image_url": None,
}

SECTION_DIAGRAM_STATE_LOCK = threading.Lock()
SECTION_DIAGRAM_STATE: dict[str, str | None] = {
    "status": "idle",
    "message": "Run generated code to render opsvis section-force diagrams.",
    "started_at": None,
    "finished_at": None,
    "error": None,
    "python_path": None,
}

BENCHMARK_STATE_LOCK = threading.Lock()
BENCHMARK_STATE: dict[str, str | int | None] = {
    "status": "idle",
    "message": "Ready to run benchmark cases.",
    "batch_id": None,
    "total": 0,
    "completed": 0,
    "started_at": None,
    "finished_at": None,
    "error": None,
}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError):
        return None


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _has_llm_api_key() -> bool:
    return bool(os.getenv("DEEPSEEK_API_KEY", "").strip())


def _clear_pipeline_artifacts() -> None:
    for artifact in PIPELINE_ARTIFACT_FILES:
        if artifact.exists():
            artifact.unlink()


def _case_artifact_dir(case_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in case_id)
    return BENCHMARK_ARTIFACT_ROOT / safe


def _archive_benchmark_artifacts(case_id: str) -> Path:
    artifact_dir = _case_artifact_dir(case_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    for artifact in PIPELINE_ARTIFACT_FILES:
        if artifact.exists():
            shutil.copy2(artifact, artifact_dir / artifact.name)
    return artifact_dir


def _read_case_artifacts(case_id: str) -> dict:
    artifact_dir = _case_artifact_dir(case_id)
    if not artifact_dir.exists():
        return {
            "case_id": case_id,
            "available": False,
            "message": "No archived outputs are available for this case. Rerun the case to create review artifacts.",
            "outputs": {},
        }
    outputs = {
        "problem_analysis": _read_json(artifact_dir / "state_problem_analysis.json") or {},
        "construction_plan": _read_json(artifact_dir / "state_construction_plan.json") or {},
        "node_output": _read_json(artifact_dir / "state_node_output.json") or {},
        "element_output": _read_json(artifact_dir / "state_element_output.json") or {},
        "mapped_geometry": _read_json(artifact_dir / "state_mapped_geometry.json") or {},
        "load_output": _read_json(artifact_dir / "state_load_output.json") or {},
        "compiled_model": _read_json(artifact_dir / "state_compiled.json") or {},
        "debug_problem_analysis": _read_json(artifact_dir / "debug_problem_analysis.json") or {},
        "debug_construction_plan": _read_json(artifact_dir / "debug_construction_plan.json") or {},
        "geometry_code": _read_text(artifact_dir / "geometry_code.py") if (artifact_dir / "geometry_code.py").exists() else "",
        "complete_code": _read_text(artifact_dir / "complete_code.py") if (artifact_dir / "complete_code.py").exists() else "",
        "pipeline_log": _read_text(artifact_dir / "pipeline.log") if (artifact_dir / "pipeline.log").exists() else "",
    }
    return {
        "case_id": case_id,
        "available": True,
        "message": "Archived outputs loaded.",
        "artifact_dir": str(artifact_dir),
        "outputs": outputs,
    }


def _run_benchmark_case_code(case_id: str) -> dict:
    artifact_dir = _case_artifact_dir(case_id)
    code_path = artifact_dir / "complete_code.py"
    started_at = datetime.now(timezone.utc).isoformat()
    if not code_path.exists():
        return {
            "ok": False,
            "case_id": case_id,
            "status": "failed",
            "message": "No archived complete_code.py is available for this case.",
            "python_path": None,
            "returncode": None,
            "stdout": "",
            "stderr": f"Missing file: {code_path}",
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
    try:
        python_path = _resolve_ops_python()
    except Exception as exc:
        return {
            "ok": False,
            "case_id": case_id,
            "status": "failed",
            "message": "OPS Python could not be resolved.",
            "python_path": None,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
    try:
        completed = subprocess.run(
            [str(python_path), str(code_path)],
            cwd=str(artifact_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "case_id": case_id,
            "status": "failed",
            "message": "Archived case code timed out.",
            "python_path": str(python_path),
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": (exc.stderr or "") + "\nExecution timed out after 120 seconds.",
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "case_id": case_id,
            "status": "failed",
            "message": "Archived case code could not be executed.",
            "python_path": str(python_path),
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }

    succeeded = completed.returncode == 0
    return {
        "ok": succeeded,
        "case_id": case_id,
        "status": "succeeded" if succeeded else "failed",
        "message": "Archived case code executed successfully." if succeeded else "Archived case code exited with an error.",
        "python_path": str(python_path),
        "returncode": completed.returncode,
        "stdout": completed.stdout or "",
        "stderr": completed.stderr or "",
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }


def _update_run_state(**changes: str | None) -> dict[str, str | None]:
    with RUN_STATE_LOCK:
        RUN_STATE.update(changes)
        snapshot = dict(RUN_STATE)
    _write_json(RUN_STATUS_FILE, snapshot)
    return snapshot


def _snapshot_run_state() -> dict[str, str | None]:
    with RUN_STATE_LOCK:
        return dict(RUN_STATE)


def _update_execution_state(**changes: str | None | int) -> dict[str, str | None | int]:
    with EXECUTION_STATE_LOCK:
        EXECUTION_STATE.update(changes)
        snapshot = dict(EXECUTION_STATE)
    _write_json(EXECUTION_STATUS_FILE, snapshot)
    return snapshot


def _snapshot_execution_state() -> dict[str, str | None | int]:
    with EXECUTION_STATE_LOCK:
        return dict(EXECUTION_STATE)


def _update_visualization_state(**changes: str | None) -> dict[str, str | None]:
    with VISUALIZATION_STATE_LOCK:
        VISUALIZATION_STATE.update(changes)
        snapshot = dict(VISUALIZATION_STATE)
    _write_json(VISUALIZATION_STATUS_FILE, snapshot)
    return snapshot


def _snapshot_visualization_state() -> dict[str, str | None]:
    with VISUALIZATION_STATE_LOCK:
        return dict(VISUALIZATION_STATE)


def _update_section_diagram_state(**changes: str | None) -> dict[str, str | None]:
    with SECTION_DIAGRAM_STATE_LOCK:
        SECTION_DIAGRAM_STATE.update(changes)
        snapshot = dict(SECTION_DIAGRAM_STATE)
    _write_json(SECTION_DIAGRAM_STATUS_FILE, snapshot)
    return snapshot


def _snapshot_section_diagram_state() -> dict[str, str | None]:
    with SECTION_DIAGRAM_STATE_LOCK:
        return dict(SECTION_DIAGRAM_STATE)


def _update_benchmark_state(**changes: str | int | None) -> dict[str, str | int | None]:
    with BENCHMARK_STATE_LOCK:
        BENCHMARK_STATE.update(changes)
        snapshot = dict(BENCHMARK_STATE)
    _write_json(BENCHMARK_STATUS_FILE, snapshot)
    return snapshot


def _snapshot_benchmark_state() -> dict[str, str | int | None]:
    with BENCHMARK_STATE_LOCK:
        return dict(BENCHMARK_STATE)


def _resolve_ops_python() -> Path:
    candidates = [
        os.getenv("OPS_PYTHON"),
        r"D:\Anaconda\envs\ops_clean\python.exe",
        r"D:\Anaconda\envs\ops\python.exe",
        r"H:\ops\Scripts\python.exe",
        r"H:\codex\ops\Scripts\python.exe",
        r"H:\codex\.venv\Scripts\python.exe",
        r"H:\codex\multiagent\.venv\Scripts\python.exe",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return path
    raise FileNotFoundError(
        "Could not find the ops virtual environment Python. Set OPS_PYTHON to the venv's python.exe path."
    )


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped


def _artifact_url(route: str, path: Path) -> str | None:
    if not path.exists():
        return None
    return f"{route}?t={int(path.stat().st_mtime)}"


def _render_model_visualization_async() -> None:
    try:
        python_path = _resolve_ops_python()
        node_output = _read_json(OUTPUT_ROOT / "state_node_output.json") or {}
        element_output = _read_json(OUTPUT_ROOT / "state_element_output.json") or {}
        if not node_output:
            raise RuntimeError("state_node_output.json is empty. Run the pipeline first.")
        if not element_output:
            raise RuntimeError("state_element_output.json is empty. Run the pipeline first.")
    except Exception as exc:
        _update_visualization_state(
            status="failed",
            message="Visualization setup failed.",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error=str(exc),
            image_url=None,
        )
        return

    _update_visualization_state(
        status="running",
        message="Rendering Node / Element visualization with opsvis.",
        started_at=datetime.now(timezone.utc).isoformat(),
        finished_at=None,
        error=None,
        image_url=None,
    )
    script_path = OUTPUT_ROOT / "_render_model_plot.py"
    VISUALIZATION_STDOUT_FILE.write_text("", encoding="utf-8")
    VISUALIZATION_STDERR_FILE.write_text("", encoding="utf-8")
    script_path.write_text(
        "\n".join(
            [
                "import matplotlib",
                "matplotlib.use('Agg')",
                "import matplotlib.pyplot as plt",
                "import json",
                "",
                f"node_output = json.loads({json.dumps(json.dumps(node_output, ensure_ascii=False))})",
                f"element_output = json.loads({json.dumps(json.dumps(element_output, ensure_ascii=False))})",
                "",
                "nodes = []",
                "if 'nodes' in node_output:",
                "    for item in node_output.get('nodes', []):",
                "        node_id = int(item.get('id', item.get('node_id')))",
                "        x_val = float(item.get('x', item.get('x_m')))",
                "        y_val = float(item.get('y', item.get('y_m')))",
                "        nodes.append((node_id, x_val, y_val))",
                "else:",
                "    for step in node_output.get('construction_sequence', []):",
                "        for item in step.get('nodes_added', []):",
                "            node_id = int(item.get('id', item.get('node_id')))",
                "            x_val = float(item.get('x', item.get('x_m')))",
                "            y_val = float(item.get('y', item.get('y_m')))",
                "            nodes.append((node_id, x_val, y_val))",
                "unique_nodes = {}",
                "for node_id, x_val, y_val in nodes:",
                "    unique_nodes[node_id] = (x_val, y_val)",
                "nodes = [(node_id, *coords) for node_id, coords in sorted(unique_nodes.items())]",
                "",
                "plt.figure(figsize=(8, 6))",
                "if nodes:",
                "    xs = [x for _, x, _ in nodes]",
                "    ys = [y for _, _, y in nodes]",
                "    plt.scatter(xs, ys, s=55, c='#0f766e')",
                "    for node_id, x, y in nodes:",
                "        plt.text(x + 0.12, y + 0.12, str(node_id), fontsize=9, color='#16313a')",
                "plt.title('Node Agent Output')",
                "plt.xlabel('X')",
                "plt.ylabel('Y')",
                "plt.grid(True, alpha=0.25)",
                "plt.axis('equal')",
                "plt.tight_layout()",
                f"plt.savefig(r'{NODE_VISUALIZATION_FILE}', dpi=180, bbox_inches='tight')",
                "plt.close()",
                "",
                "plt.figure(figsize=(8, 6))",
                "elements = []",
                "if 'elements' in element_output:",
                "    elements = element_output.get('elements', [])",
                "elif 'element_definitions' in element_output:",
                "    elements = element_output.get('element_definitions', [])",
                "else:",
                "    for step in element_output.get('steps', []):",
                "        elements.extend(step.get('elements_added', []))",
                "node_lookup = {node_id: (x, y) for node_id, x, y in nodes}",
                "for item in elements:",
                "    pair = item.get('nodes')",
                "    if isinstance(pair, list) and len(pair) == 2:",
                "        node_i = int(pair[0])",
                "        node_j = int(pair[1])",
                "    else:",
                "        node_i_raw = str(item.get('node_i', '')).replace('N', '')",
                "        node_j_raw = str(item.get('node_j', '')).replace('N', '')",
                "        if not node_i_raw.isdigit() or not node_j_raw.isdigit():",
                "            continue",
                "        node_i = int(node_i_raw)",
                "        node_j = int(node_j_raw)",
                "    start = node_lookup.get(node_i)",
                "    end = node_lookup.get(node_j)",
                "    if start is None or end is None:",
                "        continue",
                "    x1, y1 = start",
                "    x2, y2 = end",
                "    plt.plot([x1, x2], [y1, y2], linewidth=2.4, color='#e58b2a')",
                "    mx = (x1 + x2) / 2",
                "    my = (y1 + y2) / 2",
                "    plt.text(mx, my, str(item.get('element_id', item.get('id', ''))), fontsize=8, color='#16313a')",
                "plt.title('Element Agent Output')",
                "plt.xlabel('X')",
                "plt.ylabel('Y')",
                "plt.grid(True, alpha=0.25)",
                "plt.axis('equal')",
                "plt.tight_layout()",
                f"plt.savefig(r'{ELEMENT_VISUALIZATION_FILE}', dpi=180, bbox_inches='tight')",
                "plt.close()",
                f"print(r'{NODE_VISUALIZATION_FILE}')",
                f"print(r'{ELEMENT_VISUALIZATION_FILE}')",
            ]
        ),
        encoding="utf-8",
    )
    try:
        completed = subprocess.run(
            [str(python_path), str(script_path)],
            cwd=str(OUTPUT_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        VISUALIZATION_STDOUT_FILE.write_text(completed.stdout or "", encoding="utf-8")
        VISUALIZATION_STDERR_FILE.write_text(completed.stderr or "", encoding="utf-8")
    except subprocess.TimeoutExpired:
        VISUALIZATION_STDERR_FILE.write_text("Visualization timed out after 120 seconds.", encoding="utf-8")
        _update_visualization_state(
            status="failed",
            message="Visualization rendering timed out.",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error="Visualization timed out after 120 seconds.",
            image_url=None,
        )
        return
    except Exception as exc:
        VISUALIZATION_STDERR_FILE.write_text(str(exc), encoding="utf-8")
        _update_visualization_state(
            status="failed",
            message="Visualization rendering failed.",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error=str(exc),
            image_url=None,
        )
        return
    finally:
        if script_path.exists():
            script_path.unlink()

    if completed.returncode != 0 or not NODE_VISUALIZATION_FILE.exists() or not ELEMENT_VISUALIZATION_FILE.exists():
        _update_visualization_state(
            status="failed",
            message="Visualization renderer did not produce the expected images.",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error=(completed.stderr or completed.stdout or f"Process exited with code {completed.returncode}.").strip(),
            image_url=None,
        )
        return

    _update_visualization_state(
        status="succeeded",
        message="Node and element visualizations rendered successfully.",
        finished_at=datetime.now(timezone.utc).isoformat(),
        error=None,
        image_url=f"/artifacts/node_visualization.png?t={int(datetime.now(timezone.utc).timestamp())}",
    )


def _collect_outputs() -> dict:
    return {
        "problem_analysis": _read_json(OUTPUT_ROOT / "state_problem_analysis.json") or {},
        "construction_plan": _read_json(OUTPUT_ROOT / "state_construction_plan.json") or {},
        "node_output": _read_json(OUTPUT_ROOT / "state_node_output.json") or {},
        "element_output": _read_json(OUTPUT_ROOT / "state_element_output.json") or {},
        "mapped_geometry": _read_json(OUTPUT_ROOT / "state_mapped_geometry.json") or {},
        "load_output": _read_json(OUTPUT_ROOT / "state_load_output.json") or {},
        "compiled_model": _read_json(OUTPUT_ROOT / "state_compiled.json") or {},
        "geometry_code": _read_text(OUTPUT_ROOT / "geometry_code.py") if (OUTPUT_ROOT / "geometry_code.py").exists() else "",
        "complete_code": _read_text(OUTPUT_ROOT / "complete_code.py") if (OUTPUT_ROOT / "complete_code.py").exists() else "",
        "pipeline_log": _read_text(OUTPUT_ROOT / "pipeline.log") if (OUTPUT_ROOT / "pipeline.log").exists() else "",
        "execution_stdout": _read_text(EXECUTION_STDOUT_FILE) if EXECUTION_STDOUT_FILE.exists() else "",
        "execution_stderr": _read_text(EXECUTION_STDERR_FILE) if EXECUTION_STDERR_FILE.exists() else "",
        "section_diagram_stdout": _read_text(SECTION_DIAGRAM_STDOUT_FILE) if SECTION_DIAGRAM_STDOUT_FILE.exists() else "",
        "section_diagram_stderr": _read_text(SECTION_DIAGRAM_STDERR_FILE) if SECTION_DIAGRAM_STDERR_FILE.exists() else "",
        "python_check_output": _read_json(PYTHON_CHECK_OUTPUT_FILE) or {},
    }


def _latest_feedback() -> dict | None:
    if not FEEDBACK_FILE.exists():
        return None
    lines = [line.strip() for line in FEEDBACK_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return None
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError:
        return None


def _current_run_id() -> str:
    run_state = _snapshot_run_state()
    current_prompt = _read_json(CURRENT_PROMPT_FILE) or {}
    return str(run_state.get("started_at") or current_prompt.get("saved_at") or datetime.now(timezone.utc).isoformat())


def _build_rl_snapshot(outputs: dict | None = None) -> dict:
    outputs = outputs or _collect_outputs()
    run_state = _snapshot_run_state()
    execution_state = _snapshot_execution_state()
    section_state = _snapshot_section_diagram_state()
    feedback = _latest_feedback()
    reward_report = RewardScorer().score(
        outputs=outputs,
        run_state=run_state,
        execution_state=execution_state,
        section_diagram_state=section_state,
        feedback=feedback,
    )
    policy_action = RulePolicy().choose(
        reward_report=reward_report,
        outputs=outputs,
        run_state=run_state,
        execution_state=execution_state,
        section_diagram_state=section_state,
        feedback=feedback,
    )
    status = _read_json(RL_STATUS_FILE) or {}
    return {
        "reward": reward_report,
        "policy_action": policy_action,
        "latest_feedback": feedback,
        "history": status.get("history", []),
        "prompt_history": RLLogger().prompt_history(),
        "database_path": str(RLLogger().db_path),
    }


def _build_agent_reward_summary() -> dict:
    try:
        summary = RLLogger().agent_reward_summary()
        return {
            "agents": summary,
            "total_experiences": sum(int(r.get("total_runs", 0)) for r in summary),
        }
    except Exception:
        return {"agents": [], "total_experiences": 0}


def _record_rl_event(event_name: str, metadata: dict | None = None) -> dict:
    current_prompt = _read_json(CURRENT_PROMPT_FILE) or {}
    prompt = str(current_prompt.get("prompt", ""))
    outputs = _collect_outputs()
    snapshot = _build_rl_snapshot(outputs)
    run_id = _current_run_id()
    RLLogger().upsert_run(
        run_id=run_id,
        prompt=prompt,
        status=str(_snapshot_run_state().get("status", "idle")),
        reward_report=snapshot["reward"],
        policy_action=snapshot["policy_action"],
        metadata={"event": event_name, **(metadata or {})},
    )
    snapshot["history"] = RLLogger().latest_runs()
    _write_json(RL_STATUS_FILE, snapshot)
    return snapshot


def _sum_token_usage(records: list[dict]) -> dict[str, int]:
    return {
        "prompt_tokens": sum(int(item.get("prompt_tokens") or 0) for item in records),
        "completion_tokens": sum(int(item.get("completion_tokens") or 0) for item in records),
        "total_tokens": sum(int(item.get("total_tokens") or 0) for item in records),
    }


def _optimized_pipeline_config() -> PipelineConfig:
    config = PipelineConfig()
    config.max_retries_analysis_planning = int(os.getenv("MULTIAGENT_REVIEW_RETRIES_ANALYSIS", "2"))
    config.max_retries_geometry = int(os.getenv("MULTIAGENT_REVIEW_RETRIES_GEOMETRY", "2"))
    config.max_retries_code_translation = int(os.getenv("MULTIAGENT_REVIEW_RETRIES_CODE", "2"))
    config.rag.top_k = int(os.getenv("MULTIAGENT_REVIEW_RAG_TOP_K", "1"))
    config.rag.max_chars = int(os.getenv("MULTIAGENT_REVIEW_RAG_MAX_CHARS", "2500"))
    return _apply_agent_llm_overrides(config)


def _run_benchmark_cases(
    cases: list[BenchmarkCase],
    *,
    message_prefix: str,
    config_factory: Callable[[], PipelineConfig] = _optimized_pipeline_config,
) -> None:
    if not cases:
        _update_benchmark_state(status="failed", message="No benchmark cases were selected.", error="empty case set")
        return
    batch_id = cases[0].batch_id
    _update_benchmark_state(
        status="running",
        message=f"{message_prefix} is running.",
        batch_id=batch_id,
        total=len(cases),
        completed=0,
        started_at=datetime.now(timezone.utc).isoformat(),
        finished_at=None,
        error=None,
    )
    logger = RLLogger()
    config = config_factory()
    rl_optimizer = MultiAgentOptimizer(
        epsilon=config.rl.epsilon,
        alpha=config.rl.alpha,
    ) if config.rl.enabled else None
    for index, case in enumerate(cases, start=1):
        started_at = datetime.now(timezone.utc).isoformat()
        retry_from_case_id = getattr(case, "retry_from_case_id", None)
        logger.insert_prompt(run_id=case.case_id, prompt=case.prompt, source="benchmark", note=batch_id)
        logger.upsert_benchmark_case(
            case_id=case.case_id,
            batch_id=batch_id,
            prompt=case.prompt,
            status="running",
            started_at=started_at,
            retry_from_case_id=retry_from_case_id,
        )
        _write_json(CURRENT_PROMPT_FILE, {"prompt": case.prompt, "saved_at": case.case_id})
        _update_run_state(
            status="running",
            message=f"{message_prefix} case {index}/{len(cases)} is running.",
            started_at=case.case_id,
            finished_at=None,
            error=None,
        )
        _clear_pipeline_artifacts()
        token_records: list[dict] = []
        token = set_token_usage_callback(token_records.append)
        try:
            try:
                pipeline = StructuralModelingPipeline(config_factory(), optimizer=rl_optimizer)
                pipeline.run(case.prompt)
            except Exception as exc:
                traceback_text = traceback.format_exc()
                reset_token_usage_callback(token)
                artifact_dir = _archive_benchmark_artifacts(case.case_id)
                _update_run_state(
                    status="failed",
                    message=f"{message_prefix} case {index}/{len(cases)} failed.",
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    error=str(exc),
                )
                logger.replace_benchmark_token_usage(case_id=case.case_id, records=token_records)
                snapshot = _record_rl_event(
                    "benchmark_case_failed",
                    {"case_id": case.case_id, "error": str(exc), "traceback": traceback_text},
                )
                if rl_optimizer and config.rl.enabled:
                    try:
                        pipeline.decompose_and_record(
                            outputs=_collect_outputs(),
                            run_id=case.case_id,
                            execution_state=_snapshot_execution_state(),
                        )
                    except Exception:
                        pass
                logger.upsert_benchmark_case(
                    case_id=case.case_id,
                    batch_id=batch_id,
                    prompt=case.prompt,
                    status="failed",
                    started_at=started_at,
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    error=f"{str(exc)}\n\n{traceback_text}",
                    token_usage=_sum_token_usage(token_records),
                    reward=float(snapshot["reward"].get("total_reward", 0.0)),
                    policy_action=str(snapshot["policy_action"].get("action_type", "")),
                    retry_from_case_id=retry_from_case_id,
                    artifact_dir=str(artifact_dir),
                )
            else:
                reset_token_usage_callback(token)
                logger.replace_benchmark_token_usage(case_id=case.case_id, records=token_records)
                artifact_dir = _archive_benchmark_artifacts(case.case_id)
                _update_run_state(
                    status="succeeded",
                    message=f"{message_prefix} case {index}/{len(cases)} completed.",
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    error=None,
                )
                snapshot = _record_rl_event("benchmark_case_succeeded", {"case_id": case.case_id})
                if rl_optimizer and config.rl.enabled:
                    try:
                        pipeline.decompose_and_record(
                            outputs=_collect_outputs(),
                            run_id=case.case_id,
                            execution_state=_snapshot_execution_state(),
                        )
                    except Exception:
                        pass
                logger.upsert_benchmark_case(
                    case_id=case.case_id,
                    batch_id=batch_id,
                    prompt=case.prompt,
                    status="succeeded",
                    started_at=started_at,
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    error=None,
                    token_usage=_sum_token_usage(token_records),
                    reward=float(snapshot["reward"].get("total_reward", 0.0)),
                    policy_action=str(snapshot["policy_action"].get("action_type", "")),
                    retry_from_case_id=retry_from_case_id,
                    artifact_dir=str(artifact_dir),
                )
        except Exception as post_exc:
            post_tb = traceback.format_exc()
            try:
                reset_token_usage_callback(token)
            except Exception:
                pass
            logger.replace_benchmark_token_usage(case_id=case.case_id, records=token_records)
            _update_run_state(
                status="failed",
                message=f"{message_prefix} case {index}/{len(cases)} failed during post-processing.",
                finished_at=datetime.now(timezone.utc).isoformat(),
                error=str(post_exc),
            )
            logger.upsert_benchmark_case(
                case_id=case.case_id,
                batch_id=batch_id,
                prompt=case.prompt,
                status="failed",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc).isoformat(),
                error=f"Post-processing error: {post_exc}\n\n{post_tb}",
                token_usage=_sum_token_usage(token_records),
                retry_from_case_id=retry_from_case_id,
            )
        _update_benchmark_state(completed=index)
    _update_benchmark_state(
        status="succeeded",
        message=f"{message_prefix} completed. Successful prompts from previous batches were preserved.",
        completed=len(cases),
        finished_at=datetime.now(timezone.utc).isoformat(),
        error=None,
    )


def _run_benchmark_async(count: int = 30, seed: int = 20260506, start_from: int = 1) -> None:
    if not _has_llm_api_key():
        _update_benchmark_state(
            status="failed",
            message="Benchmark cannot start because DEEPSEEK_API_KEY is not set.",
            error="Missing DEEPSEEK_API_KEY in the web server process.",
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        return
    cases = generate_benchmark_cases(count=count, seed=seed, start_from=start_from)
    _run_benchmark_cases(cases, message_prefix="Benchmark batch")


def _run_failed_benchmark_retry_async(batch_id: str | None = None) -> None:
    if not _has_llm_api_key():
        _update_benchmark_state(
            status="failed",
            message="Retry cannot start because DEEPSEEK_API_KEY is not set.",
            error="Missing DEEPSEEK_API_KEY in the web server process.",
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        return
    logger = RLLogger()
    source_batch_id = batch_id or logger.latest_batch_id()
    failed_cases = logger.failed_benchmark_cases(source_batch_id)
    retry_batch_id = datetime.now(timezone.utc).strftime("retry-%Y%m%d-%H%M%S")
    retry_cases: list[BenchmarkCase] = []
    for index, item in enumerate(failed_cases, start=1):
        retry_case = BenchmarkCase(
            case_id=f"{retry_batch_id}-case-{index:02d}",
            batch_id=retry_batch_id,
            prompt=str(item["prompt"]),
        )
        object.__setattr__(retry_case, "retry_from_case_id", item["case_id"])
        retry_cases.append(retry_case)
    _run_benchmark_cases(retry_cases, message_prefix=f"Retry batch for {source_batch_id}")


def _run_review_set_async(batch_id: str | None = None) -> None:
    if not _has_llm_api_key():
        _update_benchmark_state(
            status="failed",
            message="Review set cannot start because DEEPSEEK_API_KEY is not set.",
            error="Missing DEEPSEEK_API_KEY in the web server process.",
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        return
    logger = RLLogger()
    source_batch_id = batch_id or logger.latest_original_batch_id()
    source_cases = logger.final_successful_original_cases(source_batch_id)
    review_batch_id = datetime.now(timezone.utc).strftime("review-%Y%m%d-%H%M%S")
    review_cases: list[BenchmarkCase] = []
    for index, item in enumerate(source_cases, start=1):
        review_case = BenchmarkCase(
            case_id=f"{review_batch_id}-case-{index:02d}",
            batch_id=review_batch_id,
            prompt=str(item["prompt"]),
        )
        object.__setattr__(review_case, "retry_from_case_id", item["case_id"])
        review_cases.append(review_case)
    _run_benchmark_cases(
        review_cases,
        message_prefix=f"Review artifact batch for {source_batch_id}",
        config_factory=_optimized_pipeline_config,
    )


def _run_pipeline_async(prompt: str, run_id: str | None = None) -> None:
    try:
        config = _apply_agent_llm_overrides(PipelineConfig())
        pipeline = StructuralModelingPipeline(config)
        pipeline.run(prompt)
    except Exception as exc:
        if run_id:
            try:
                _archive_benchmark_artifacts(run_id)
            except Exception:
                pass
        _update_run_state(
            status="failed",
            message="Pipeline failed.",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error=str(exc),
        )
        _record_rl_event("pipeline_failed", {"error": str(exc)})
        return
    if run_id:
        try:
            _archive_benchmark_artifacts(run_id)
        except Exception:
            pass
    _update_run_state(
        status="succeeded",
        message="Pipeline completed successfully.",
        finished_at=datetime.now(timezone.utc).isoformat(),
        error=None,
    )
    _record_rl_event("pipeline_succeeded")


def _run_generated_code_async() -> None:
    try:
        python_path = _resolve_ops_python()
    except Exception as exc:
        _update_execution_state(
            status="failed",
            message="Execution failed before start.",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error=str(exc),
            python_path=None,
            returncode=None,
        )
        _update_section_diagram_state(
            status="failed",
            message="Opsvis diagrams skipped because execution could not start.",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error=str(exc),
            python_path=None,
        )
        _record_rl_event("execution_start_failed", {"error": str(exc)})
        return

    _update_execution_state(
        status="running",
        message="Executing generated code in ops environment.",
        started_at=datetime.now(timezone.utc).isoformat(),
        finished_at=None,
        error=None,
        python_path=str(python_path),
        returncode=None,
    )
    try:
        completed = subprocess.run(
            [str(python_path), str(GENERATED_CODE_FILE)],
            cwd=str(OUTPUT_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        EXECUTION_STDOUT_FILE.write_text(completed.stdout or "", encoding="utf-8")
        EXECUTION_STDERR_FILE.write_text(completed.stderr or "", encoding="utf-8")
    except subprocess.TimeoutExpired as exc:
        EXECUTION_STDOUT_FILE.write_text(exc.stdout or "", encoding="utf-8")
        EXECUTION_STDERR_FILE.write_text((exc.stderr or "") + "\nExecution timed out.", encoding="utf-8")
        _update_execution_state(
            status="failed",
            message="Generated code timed out.",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error="Execution timed out after 120 seconds.",
            python_path=str(python_path),
            returncode=None,
        )
        _run_python_check_agent(
            python_path=str(python_path),
            returncode=None,
            started_at=_snapshot_execution_state().get("started_at"),
            finished_at=_snapshot_execution_state().get("finished_at"),
        )
        _update_section_diagram_state(
            status="failed",
            message="Opsvis diagrams skipped because generated code timed out.",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error="Execution timed out before diagram rendering.",
            python_path=str(python_path),
        )
        _record_rl_event("execution_timeout", {"python_path": str(python_path)})
        return
    except Exception as exc:
        EXECUTION_STDERR_FILE.write_text(str(exc), encoding="utf-8")
        _update_execution_state(
            status="failed",
            message="Generated code execution failed.",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error=str(exc),
            python_path=str(python_path),
            returncode=None,
        )
        _run_python_check_agent(
            python_path=str(python_path),
            returncode=None,
            started_at=_snapshot_execution_state().get("started_at"),
            finished_at=_snapshot_execution_state().get("finished_at"),
        )
        _update_section_diagram_state(
            status="failed",
            message="Opsvis diagrams skipped because generated code failed.",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error=str(exc),
            python_path=str(python_path),
        )
        _record_rl_event("execution_exception", {"error": str(exc), "python_path": str(python_path)})
        return

    if completed.returncode == 0:
        if PYTHON_CHECK_OUTPUT_FILE.exists():
            PYTHON_CHECK_OUTPUT_FILE.unlink()
        _update_execution_state(
            status="succeeded",
            message="Generated code executed successfully.",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error=None,
            python_path=str(python_path),
            returncode=completed.returncode,
        )
        _run_section_diagrams_async(str(python_path))
    else:
        _update_execution_state(
            status="failed",
            message="Generated code exited with an error.",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error=f"Process exited with code {completed.returncode}.",
            python_path=str(python_path),
            returncode=completed.returncode,
        )
        _run_python_check_agent(
            python_path=str(python_path),
            returncode=completed.returncode,
            started_at=_snapshot_execution_state().get("started_at"),
            finished_at=_snapshot_execution_state().get("finished_at"),
        )
        _update_section_diagram_state(
            status="failed",
            message="Opsvis diagrams skipped because generated code failed.",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error=f"Generated code exited with code {completed.returncode}.",
            python_path=str(python_path),
        )
        _record_rl_event(
            "execution_failed",
            {"returncode": completed.returncode, "python_path": str(python_path)},
        )


def _run_section_diagrams_async(python_path: str) -> None:
    for artifact in (AXIAL_DIAGRAM_FILE, SHEAR_DIAGRAM_FILE, MOMENT_DIAGRAM_FILE):
        if artifact.exists():
            artifact.unlink()
    SECTION_DIAGRAM_STDOUT_FILE.write_text("", encoding="utf-8")
    SECTION_DIAGRAM_STDERR_FILE.write_text("", encoding="utf-8")
    _update_section_diagram_state(
        status="running",
        message="Rendering opsvis section-force diagrams.",
        started_at=datetime.now(timezone.utc).isoformat(),
        finished_at=None,
        error=None,
        python_path=python_path,
    )
    script_path = OUTPUT_ROOT / "_render_section_force_diagrams.py"
    script_path.write_text(
        "\n".join(
            [
                "import matplotlib",
                "matplotlib.use('Agg')",
                "import matplotlib.pyplot as plt",
                "import runpy",
                "import traceback",
                "",
                "try:",
                "    import opsvis",
                "    runpy.run_path(r'" + str(GENERATED_CODE_FILE) + "', run_name='__main__')",
                "    diagrams = [",
                "        ('N', r'" + str(AXIAL_DIAGRAM_FILE) + "', 'Axial Force Diagram', 5e-5, 'N'),",
                "        ('V', r'" + str(SHEAR_DIAGRAM_FILE) + "', 'Shear Force Diagram', 2e-4, 'N'),",
                "        ('M', r'" + str(MOMENT_DIAGRAM_FILE) + "', 'Bending Moment Diagram', 1e-4, 'N.m'),",
                "    ]",
                "    for sf_type, output_path, title, sfac, unit in diagrams:",
                "        plt.close('all')",
                "        fig, ax = plt.subplots(figsize=(28.0 / 2.54, 18.0 / 2.54))",
                "        fig.subplots_adjust(left=0.06, bottom=0.08, right=0.98, top=0.92)",
                "        opsvis.plot_model(",
                "            node_labels=0,",
                "            element_labels=0,",
                "            node_supports=False,",
                "            fmt_model={'color': '#6b7280', 'linestyle': '-', 'linewidth': 1.15, 'marker': '', 'markersize': 1},",
                "            ax=ax,",
                "        )",
                "        min_val, max_val, ax = opsvis.section_force_diagram_2d(",
                "            sf_type,",
                "            sfac=sfac,",
                "            ref_vert_lines=False,",
                "            end_max_values=False,",
                "            node_supports=False,",
                "            ax=ax,",
                "            alt_model_plot=0,",
                "        )",
                "        ax.set_title(title)",
                "        ax.margins(x=0.12, y=0.22)",
                "        ax.grid(True, alpha=0.22, linewidth=0.6)",
                "        ax.text(",
                "            0.02,",
                "            0.98,",
                "            f'min: {min_val:,.3g} {unit}\\nmax: {max_val:,.3g} {unit}',",
                "            transform=ax.transAxes,",
                "            va='top',",
                "            ha='left',",
                "            fontsize=9,",
                "            bbox={'boxstyle': 'round,pad=0.35', 'facecolor': 'white', 'edgecolor': '#9aa6aa', 'alpha': 0.88},",
                "        )",
                f"        ax.figure.savefig(output_path, dpi={SECTION_DIAGRAM_DPI}, bbox_inches='tight')",
                "        plt.close(ax.figure)",
                "except Exception:",
                "    traceback.print_exc()",
                "    raise",
            ]
        ),
        encoding="utf-8",
    )
    try:
        completed = subprocess.run(
            [python_path, str(script_path)],
            cwd=str(OUTPUT_ROOT),
            capture_output=True,
            text=True,
            timeout=180,
        )
        SECTION_DIAGRAM_STDOUT_FILE.write_text(completed.stdout or "", encoding="utf-8")
        SECTION_DIAGRAM_STDERR_FILE.write_text(completed.stderr or "", encoding="utf-8")
    except subprocess.TimeoutExpired:
        SECTION_DIAGRAM_STDERR_FILE.write_text("Opsvis diagram rendering timed out after 180 seconds.", encoding="utf-8")
        _update_section_diagram_state(
            status="failed",
            message="Opsvis diagram rendering timed out.",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error="Opsvis diagram rendering timed out after 180 seconds.",
            python_path=python_path,
        )
        _record_rl_event("section_diagrams_timeout", {"python_path": python_path})
        return
    except Exception as exc:
        SECTION_DIAGRAM_STDERR_FILE.write_text(str(exc), encoding="utf-8")
        _update_section_diagram_state(
            status="failed",
            message="Opsvis diagram rendering failed.",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error=str(exc),
            python_path=python_path,
        )
        _record_rl_event("section_diagrams_exception", {"error": str(exc), "python_path": python_path})
        return
    finally:
        if script_path.exists():
            script_path.unlink()

    missing = [path.name for path in (AXIAL_DIAGRAM_FILE, SHEAR_DIAGRAM_FILE, MOMENT_DIAGRAM_FILE) if not path.exists()]
    if completed.returncode != 0 or missing:
        error_text = (completed.stderr or completed.stdout or f"Process exited with code {completed.returncode}.").strip()
        if missing:
            error_text = f"{error_text} Missing artifacts: {', '.join(missing)}".strip()
        _update_section_diagram_state(
            status="failed",
            message="Opsvis did not produce the expected section-force diagrams.",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error=error_text,
            python_path=python_path,
        )
        _record_rl_event("section_diagrams_failed", {"error": error_text, "python_path": python_path})
        return

    _update_section_diagram_state(
        status="succeeded",
        message="Opsvis section-force diagrams rendered successfully.",
        finished_at=datetime.now(timezone.utc).isoformat(),
        error=None,
        python_path=python_path,
    )
    _record_rl_event("execution_and_section_diagrams_succeeded", {"python_path": python_path})


def _run_python_check_agent(
    *,
    python_path: str,
    returncode: int | None,
    started_at: str | None,
    finished_at: str | None,
) -> None:
    try:
        current_prompt = _read_json(CURRENT_PROMPT_FILE) or {}
        compiled_model = _read_json(OUTPUT_ROOT / "state_compiled.json") or {}
        geometry_code = _read_text(OUTPUT_ROOT / "geometry_code.py") if (OUTPUT_ROOT / "geometry_code.py").exists() else ""
        complete_code = _read_text(GENERATED_CODE_FILE) if GENERATED_CODE_FILE.exists() else ""
        execution_report = build_execution_report(
            python_path=python_path,
            returncode=returncode,
            stdout_path=EXECUTION_STDOUT_FILE,
            stderr_path=EXECUTION_STDERR_FILE,
            started_at=started_at,
            finished_at=finished_at,
        )
        config = PipelineConfig()
        agent = PythonCheckAgent(LLMClient(), config.python_check_agent)
        diagnosis = agent.run(
            user_input=str(current_prompt.get("prompt", "")),
            compiled_model=compiled_model,
            geometry_code=geometry_code,
            complete_code=complete_code,
            execution_report=execution_report,
        )
        _write_json(PYTHON_CHECK_OUTPUT_FILE, diagnosis)
    except Exception as exc:
        _write_json(
            PYTHON_CHECK_OUTPUT_FILE,
            {
                "schema_version": "1.0",
                "error_type": "unknown",
                "root_cause": "Python Check Agent failed while analyzing the execution error.",
                "responsible_stage": "python_check_agent",
                "confidence": 0.0,
                "repair_action": "Inspect stderr and the Python Check Agent invocation path.",
                "should_retry": False,
                "suggested_target_agent": "none",
                "notes": [str(exc)],
            },
        )


AGENT_TIERS = {
    "tier1": {
        "label": "Core Modeling",
        "agents": ["problem_analysis", "construction_planning", "node_agent", "element_agent"],
    },
    "tier2": {
        "label": "Code Generation",
        "agents": ["load_assignment", "geometry_code_translator", "complete_code_generator"],
    },
    "tier3": {
        "label": "Verification",
        "agents": ["python_check_agent"],
    },
}

_AGENT_TO_TIER: dict[str, str] = {}
for _tid, _tdef in AGENT_TIERS.items():
    for _aname in _tdef["agents"]:
        _AGENT_TO_TIER[_aname] = _tid


def _load_agent_llm_config() -> dict:
    """Load tiered LLM overrides from disk."""
    raw = _read_json(AGENT_LLM_CONFIG_FILE) or {}
    if "tiers" in raw:
        return raw
    if not raw:
        return {}
    # Migrate from legacy per-agent format to tiered format
    migrated: dict[str, dict] = {}
    for tid, tdef in AGENT_TIERS.items():
        migrated[tid] = {"label": tdef["label"], "model_name": "", "api_key": "", "base_url": ""}
    for agent_name, cfg in raw.items():
        tid = _AGENT_TO_TIER.get(agent_name)
        if tid and cfg:
            target = migrated[tid]
            if cfg.get("model_name") and not target["model_name"]:
                target["model_name"] = cfg["model_name"]
            if cfg.get("api_key") and not target["api_key"]:
                target["api_key"] = cfg["api_key"]
            if cfg.get("base_url") and not target["base_url"]:
                target["base_url"] = cfg["base_url"]
    result = {"tiers": migrated}
    _save_agent_llm_config(result)
    return result


def _save_agent_llm_config(config: dict) -> None:
    _write_json(AGENT_LLM_CONFIG_FILE, config)


def _apply_agent_llm_overrides(config: PipelineConfig) -> PipelineConfig:
    """Apply tiered LLM overrides to a PipelineConfig from saved file."""
    overrides = _load_agent_llm_config()
    tiers = overrides.get("tiers", {})
    if not tiers:
        return config

    agent_configs: dict[str, AgentModelConfig] = {
        "problem_analysis": config.problem_analysis,
        "construction_planning": config.construction_planning,
        "node_agent": config.node_agent,
        "element_agent": config.element_agent,
        "load_assignment": config.load_assignment,
        "geometry_code_translator": config.geometry_code_translator,
        "complete_code_generator": config.complete_code_generator,
        "python_check_agent": config.python_check_agent,
    }

    for tid, tdef in AGENT_TIERS.items():
        tier_cfg = tiers.get(tid, {})
        for agent_name in tdef["agents"]:
            cfg = agent_configs.get(agent_name)
            if cfg is None:
                continue
            if tier_cfg.get("api_key"):
                cfg.api_key = tier_cfg["api_key"]
            if tier_cfg.get("base_url"):
                cfg.base_url = tier_cfg["base_url"]
            if tier_cfg.get("model_name"):
                cfg.model_name = tier_cfg["model_name"]
    return config


def build_workspace_state() -> dict:
    example_input = _read_json(PROJECT_ROOT / "example_input.json") or {}
    current_prompt = _read_json(CURRENT_PROMPT_FILE) or {}
    outputs = _collect_outputs()
    prompt_text = current_prompt.get("prompt") or example_input.get("user_input") or ""
    return {
        "prompt": prompt_text,
        "prompt_source": "current_prompt" if current_prompt else "example_input",
        "run": _snapshot_run_state(),
        "execution": _snapshot_execution_state(),
        "visualization": _snapshot_visualization_state(),
        "section_diagrams": {
            **_snapshot_section_diagram_state(),
            "axial_image_url": _artifact_url("/artifacts/axial_force_diagram.png", AXIAL_DIAGRAM_FILE),
            "shear_image_url": _artifact_url("/artifacts/shear_force_diagram.png", SHEAR_DIAGRAM_FILE),
            "moment_image_url": _artifact_url("/artifacts/moment_force_diagram.png", MOMENT_DIAGRAM_FILE),
        },
        "outputs": outputs,
        "geometry_consistency": _read_json(OUTPUT_ROOT / "geometry_consistency.json"),
        "rl": _build_rl_snapshot(outputs),
        "agent_rewards": _build_agent_reward_summary(),
        "benchmark": {
            **_snapshot_benchmark_state(),
            "cases": RLLogger().benchmark_cases(),
        },
        "agent_llm_config": _load_agent_llm_config(),
        "stages": [
            {
                "id": "analysis",
                "title": "Analysis and Planning",
                "summary": "Problem analysis and construction planning outputs.",
                "status": "ready" if outputs["problem_analysis"] and outputs["construction_plan"] else "empty",
                "agents": [
                    {
                        "name": "Problem Analysis Agent",
                        "status": "ready" if outputs["problem_analysis"] else "empty",
                    },
                    {
                        "name": "Construction Planning Agent",
                        "status": "ready" if outputs["construction_plan"] else "empty",
                    },
                ],
            },
            {
                "id": "geometry",
                "title": "Geometry Assembly",
                "summary": "Node, element, and mapped geometry outputs.",
                "status": "ready" if outputs["node_output"] or outputs["element_output"] else "empty",
                "agents": [
                    {
                        "name": "Node Agent",
                        "status": "ready" if outputs["node_output"] else "empty",
                    },
                    {
                        "name": "Element Agent",
                        "status": "ready" if outputs["element_output"] else "empty",
                    },
                    {
                        "name": "Connectivity Mapping",
                        "status": "ready" if outputs["mapped_geometry"] else "empty",
                    },
                ],
            },
            {
                "id": "loads",
                "title": "Load Integration",
                "summary": "Mapped loads and compiled model bundle.",
                "status": "ready" if outputs["load_output"] else "empty",
                "agents": [
                    {
                        "name": "Load Assignment Agent",
                        "status": "ready" if outputs["load_output"] else "empty",
                    },
                    {
                        "name": "JSON File Compiler",
                        "status": "ready" if outputs["compiled_model"] else "empty",
                    },
                ],
            },
            {
                "id": "translation",
                "title": "Code Translation",
                "summary": "Generated geometry code and complete OpenSeesPy code.",
                "status": "ready" if outputs["geometry_code"] or outputs["complete_code"] else "empty",
                "agents": [
                    {
                        "name": "Geometry Code Translator",
                        "status": "ready" if outputs["geometry_code"] else "empty",
                    },
                    {
                        "name": "Complete Code Generator",
                        "status": "ready" if outputs["complete_code"] else "empty",
                    },
                ],
            },
        ],
    }


class MultiAgentWebHandler(BaseHTTPRequestHandler):
    server_version = "MultiAgentWeb/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        routes = {
            "/": ("text/html; charset=utf-8", WEB_ROOT / "index.html"),
            "/app.css": ("text/css; charset=utf-8", WEB_ROOT / "app.css"),
            "/app.js": ("application/javascript; charset=utf-8", WEB_ROOT / "app.js"),
        }
        if parsed.path == "/api/state":
            self._send_json(build_workspace_state())
            return
        if parsed.path == "/api/agent-rewards":
            try:
                query = parse_qs(parsed.query)
                agent_filter = str((query.get("agent") or [""])[0]).strip() or None
                summary = RLLogger().agent_reward_summary(agent_filter)
                experiences = RLLogger().agent_experiences(
                    agent_name=agent_filter,
                    success_only=False,
                    limit=100,
                )
                self._send_json({
                    "ok": True,
                    "summary": summary,
                    "recent_experiences": experiences,
                })
            except Exception as exc:
                self._send_json({"ok": False, "message": str(exc)})
            return
        if parsed.path == "/api/benchmark-case-artifacts":
            query = parse_qs(parsed.query)
            case_id = str((query.get("case_id") or [""])[0]).strip()
            if not case_id:
                self._send_json({"ok": False, "message": "case_id is required."})
                return
            self._send_json({"ok": True, **_read_case_artifacts(case_id)})
            return
        if parsed.path == "/artifacts/node_visualization.png":
            self._send_png(NODE_VISUALIZATION_FILE)
            return
        if parsed.path == "/artifacts/element_visualization.png":
            self._send_png(ELEMENT_VISUALIZATION_FILE)
            return
        if parsed.path == "/artifacts/axial_force_diagram.png":
            self._send_png(AXIAL_DIAGRAM_FILE)
            return
        if parsed.path == "/artifacts/shear_force_diagram.png":
            self._send_png(SHEAR_DIAGRAM_FILE)
            return
        if parsed.path == "/artifacts/moment_force_diagram.png":
            self._send_png(MOMENT_DIAGRAM_FILE)
            return
        route = routes.get(parsed.path)
        if route is None:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        content_type, file_path = route
        if not file_path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Static asset not found")
            return
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        payload = self._read_payload()
        if parsed.path == "/api/agent-llm-config":
            tiers_payload = payload.get("tiers", {})
            if not isinstance(tiers_payload, dict):
                self._send_json({"ok": False, "message": "Expected {tiers: {tier_id: {model_name, api_key, base_url}}}."})
                return
            sanitized_tiers: dict[str, dict[str, str]] = {}
            for tid, tdef in AGENT_TIERS.items():
                input_tier = tiers_payload.get(tid, {})
                sanitized_tiers[tid] = {
                    "label": tdef["label"],
                    "agents": tdef["agents"],
                    "model_name": str(input_tier.get("model_name", "")).strip() if isinstance(input_tier, dict) else "",
                    "api_key": str(input_tier.get("api_key", "")).strip() if isinstance(input_tier, dict) else "",
                    "base_url": str(input_tier.get("base_url", "")).strip() if isinstance(input_tier, dict) else "",
                }
            _save_agent_llm_config({"tiers": sanitized_tiers})
            configured = sum(1 for t in sanitized_tiers.values() if t["api_key"] or t["model_name"])
            self._send_json({
                "ok": True,
                "message": f"LLM config saved — {configured}/3 tiers configured.",
                "state": build_workspace_state(),
            })
            return
        if parsed.path == "/api/submit":
            prompt = str(payload.get("prompt", "")).strip()
            if not prompt:
                self._send_json({"ok": False, "message": "Prompt cannot be empty."})
                return
            has_env_key = _has_llm_api_key()
            agent_configs = _load_agent_llm_config()
            tiers = agent_configs.get("tiers", {})
            has_agent_key = any(cfg.get("api_key") for cfg in tiers.values())
            if not has_env_key and not has_agent_key:
                self._send_json(
                    {
                        "ok": False,
                        "message": "No API key configured. Set DEEPSEEK_API_KEY in environment or configure per-agent keys in LLM Settings.",
                        "state": build_workspace_state(),
                    }
                )
                return
            current_state = _snapshot_run_state()
            if current_state["status"] == "running":
                self._send_json(
                    {
                        "ok": False,
                        "message": "A pipeline run is already in progress.",
                        "state": build_workspace_state(),
                    }
                )
                return
            saved_at = datetime.now(timezone.utc).isoformat()
            _write_json(
                CURRENT_PROMPT_FILE,
                {
                    "prompt": prompt,
                    "saved_at": saved_at,
                },
            )
            RLLogger().insert_prompt(
                run_id=saved_at,
                prompt=prompt,
                source="web",
                note=str(payload.get("note", "")).strip(),
            )
            _clear_pipeline_artifacts()
            _update_run_state(
                status="running",
                message="Pipeline is running.",
                started_at=saved_at,
                finished_at=None,
                error=None,
            )
            worker = threading.Thread(target=_run_pipeline_async, args=(prompt, saved_at), daemon=True)
            worker.start()
            state = build_workspace_state()
            self._send_json(
                {
                    "ok": True,
                    "message": "Pipeline run started.",
                    "state": state,
                }
            )
            return
        if parsed.path == "/api/feedback":
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "prompt": str(payload.get("prompt", "")).strip(),
                "verdict": str(payload.get("verdict", "")).strip(),
                "notes": str(payload.get("notes", "")).strip(),
                "selected_object": payload.get("selected_object") or {},
            }
            with FEEDBACK_FILE.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            RLLogger().insert_feedback(
                run_id=_current_run_id(),
                verdict=record["verdict"],
                notes=record["notes"],
                selected_object=record["selected_object"],
            )
            _record_rl_event("human_feedback_saved", {"verdict": record["verdict"]})
            self._send_json(
                {
                    "ok": True,
                    "message": "Feedback saved and reward signal updated.",
                    "record": record,
                    "state": build_workspace_state(),
                }
            )
            return
        if parsed.path == "/api/run-generated-code":
            if not GENERATED_CODE_FILE.exists():
                self._send_json(
                    {
                        "ok": False,
                        "message": "Generated code file does not exist yet.",
                        "state": build_workspace_state(),
                    }
                )
                return
            current_execution = _snapshot_execution_state()
            if current_execution["status"] == "running":
                self._send_json(
                    {
                        "ok": False,
                        "message": "Generated code is already running.",
                        "state": build_workspace_state(),
                    }
                )
                return
            EXECUTION_STDOUT_FILE.write_text("", encoding="utf-8")
            EXECUTION_STDERR_FILE.write_text("", encoding="utf-8")
            worker = threading.Thread(target=_run_generated_code_async, daemon=True)
            worker.start()
            self._send_json(
                {
                    "ok": True,
                    "message": "Generated code execution started.",
                    "state": build_workspace_state(),
                }
            )
            return
        if parsed.path == "/api/run-benchmark":
            current_benchmark = _snapshot_benchmark_state()
            if current_benchmark["status"] == "running":
                self._send_json(
                    {
                        "ok": False,
                        "message": "A benchmark batch is already running.",
                        "state": build_workspace_state(),
                    }
                )
                return
            if not _has_llm_api_key():
                _update_benchmark_state(
                    status="failed",
                    message="Benchmark cannot start because DEEPSEEK_API_KEY is not set.",
                    error="Missing DEEPSEEK_API_KEY in the web server process.",
                    finished_at=datetime.now(timezone.utc).isoformat(),
                )
                self._send_json(
                    {
                        "ok": False,
                        "message": "DEEPSEEK_API_KEY is not set in the web server process. Set it, restart the UI, then run the benchmark again.",
                        "state": build_workspace_state(),
                    }
                )
                return
            count = int(payload.get("count") or 30)
            seed = int(payload.get("seed") or 20260506)
            start_from = int(payload.get("start_from") or 1)
            worker = threading.Thread(target=_run_benchmark_async, args=(count, seed, start_from), daemon=True)
            worker.start()
            self._send_json(
                {
                    "ok": True,
                    "message": "Benchmark batch started.",
                    "state": build_workspace_state(),
                }
            )
            return
        if parsed.path == "/api/retry-failed-benchmark":
            current_benchmark = _snapshot_benchmark_state()
            if current_benchmark["status"] == "running":
                self._send_json(
                    {
                        "ok": False,
                        "message": "A benchmark batch is already running.",
                        "state": build_workspace_state(),
                    }
                )
                return
            if not _has_llm_api_key():
                _update_benchmark_state(
                    status="failed",
                    message="Retry cannot start because DEEPSEEK_API_KEY is not set.",
                    error="Missing DEEPSEEK_API_KEY in the web server process.",
                    finished_at=datetime.now(timezone.utc).isoformat(),
                )
                self._send_json(
                    {
                        "ok": False,
                        "message": "DEEPSEEK_API_KEY is not set in the web server process. Set it, restart the UI, then retry failed cases.",
                        "state": build_workspace_state(),
                    }
                )
                return
            batch_id = str(payload.get("batch_id", "")).strip() or None
            failed_count = len(RLLogger().failed_benchmark_cases(batch_id))
            if failed_count == 0:
                self._send_json(
                    {
                        "ok": False,
                        "message": "No failed cases were found to retry. Successful prompts are already preserved.",
                        "state": build_workspace_state(),
                    }
                )
                return
            worker = threading.Thread(target=_run_failed_benchmark_retry_async, args=(batch_id,), daemon=True)
            worker.start()
            self._send_json(
                {
                    "ok": True,
                    "message": f"Retry batch started for {failed_count} failed cases. Existing successful prompts were preserved.",
                    "state": build_workspace_state(),
                }
            )
            return
        if parsed.path == "/api/run-review-set":
            current_benchmark = _snapshot_benchmark_state()
            if current_benchmark["status"] == "running":
                self._send_json(
                    {
                        "ok": False,
                        "message": "A benchmark or review batch is already running.",
                        "state": build_workspace_state(),
                    }
                )
                return
            if not _has_llm_api_key():
                _update_benchmark_state(
                    status="failed",
                    message="Review set cannot start because DEEPSEEK_API_KEY is not set.",
                    error="Missing DEEPSEEK_API_KEY in the web server process.",
                    finished_at=datetime.now(timezone.utc).isoformat(),
                )
                self._send_json(
                    {
                        "ok": False,
                        "message": "DEEPSEEK_API_KEY is not set in the web server process. Set it, restart the UI, then run the review set.",
                        "state": build_workspace_state(),
                    }
                )
                return
            batch_id = str(payload.get("batch_id", "")).strip() or None
            selected_count = len(RLLogger().final_successful_original_cases(batch_id))
            if selected_count == 0:
                self._send_json(
                    {
                        "ok": False,
                        "message": "No final-successful original cases were found for review.",
                        "state": build_workspace_state(),
                    }
                )
                return
            worker = threading.Thread(target=_run_review_set_async, args=(batch_id,), daemon=True)
            worker.start()
            self._send_json(
                {
                    "ok": True,
                    "message": f"Review set started for {selected_count} final-successful prompts. Outputs will be archived for human review.",
                    "state": build_workspace_state(),
                }
            )
            return
        if parsed.path == "/api/review-benchmark":
            case_id = str(payload.get("case_id", "")).strip()
            verdict = str(payload.get("verdict", "")).strip()
            notes = str(payload.get("notes", "")).strip()
            if not case_id or verdict not in {"correct", "incorrect"}:
                self._send_json({"ok": False, "message": "case_id and a valid verdict are required."})
                return
            RLLogger().review_benchmark_case(case_id=case_id, verdict=verdict, notes=notes)
            self._send_json(
                {
                    "ok": True,
                    "message": "Benchmark review saved.",
                    "state": build_workspace_state(),
                }
            )
            return
        if parsed.path == "/api/render-model-visualization":
            if not GEOMETRY_CODE_FILE.exists():
                self._send_json(
                    {
                        "ok": False,
                        "message": "geometry_code.py does not exist yet.",
                        "state": build_workspace_state(),
                    }
                )
                return
            current_visualization = _snapshot_visualization_state()
            if current_visualization["status"] == "running":
                self._send_json(
                    {
                        "ok": False,
                        "message": "Visualization is already rendering.",
                        "state": build_workspace_state(),
                    }
                )
                return
            worker = threading.Thread(target=_render_model_visualization_async, daemon=True)
            worker.start()
            self._send_json(
                {
                    "ok": True,
                    "message": "Visualization rendering started.",
                    "state": build_workspace_state(),
                }
            )
            return
        if parsed.path == "/api/run-benchmark-code":
            case_id = str(payload.get("case_id", "")).strip()
            if not case_id:
                self._send_json({"ok": False, "message": "case_id is required."})
                return
            result = _run_benchmark_case_code(case_id)
            self._send_json(result)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "API route not found")

    def log_message(self, format: str, *args: object) -> None:
        return

    def _read_payload(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        return json.loads(raw.decode("utf-8"))

    def _send_json(self, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_png(self, path: Path) -> None:
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Visualization not found")
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    ensure_directories()
    if RUN_STATUS_FILE.exists():
        loaded = _read_json(RUN_STATUS_FILE)
        if isinstance(loaded, dict):
            _update_run_state(**{key: loaded.get(key) for key in RUN_STATE})
    if EXECUTION_STATUS_FILE.exists():
        loaded = _read_json(EXECUTION_STATUS_FILE)
        if isinstance(loaded, dict):
            _update_execution_state(**{key: loaded.get(key) for key in EXECUTION_STATE})
    if VISUALIZATION_STATUS_FILE.exists():
        loaded = _read_json(VISUALIZATION_STATUS_FILE)
        if isinstance(loaded, dict):
            _update_visualization_state(**{key: loaded.get(key) for key in VISUALIZATION_STATE})
    if SECTION_DIAGRAM_STATUS_FILE.exists():
        loaded = _read_json(SECTION_DIAGRAM_STATUS_FILE)
        if isinstance(loaded, dict):
            _update_section_diagram_state(**{key: loaded.get(key) for key in SECTION_DIAGRAM_STATE})
    server = ThreadingHTTPServer(("127.0.0.1", 8000), MultiAgentWebHandler)
    print("Multi-agent UI is running at http://127.0.0.1:8000")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
