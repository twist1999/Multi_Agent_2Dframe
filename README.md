# Multi-Agent Structural Modeling Scaffold

A Python scaffold for a multi-agent structural modeling pipeline that turns natural-language frame descriptions into structured model data and generated OpenSeesPy code.

The repository is organized around four stages:

- Analysis and planning
- Geometry assembly
- Load integration
- Code translation

## Pipeline overview

The current workflow is:

1. `ProblemAnalysisAgent`
2. `ConstructionPlanningAgent`
3. `NodeAgent`
4. `ElementAgent`
5. `connectivity_mapping`
6. `LoadAssignmentAgent`
7. `GeometryCodeTranslator`
8. `CompleteCodeGenerator`

Intermediate outputs are written to `outputs/` when enabled in the pipeline config.

## Project structure

```text
src/multiagent/
  agents/        Agent entrypoints
  functions/     Deterministic mapping/compiler helpers
  llm/           LLM client wrapper
  prompts/       Prompt templates
  validators/    Checkpoint validation logic
```

## Unified schema

The repository includes a canonical schema contract for all agents in [SCHEMA.md](SCHEMA.md). If you extend the prompts, validators, or code generators, use that document as the source of truth.

## Setup

Requirements:

- Python 3.11+

Install locally:

```powershell
cd H:\codex\multiagent
pip install -e .
```

Set your provider credentials before running the pipeline:

```powershell
$env:DEEPSEEK_API_KEY="your_api_key_here"
```

Optional:

```powershell
$env:DEEPSEEK_BASE_URL="https://api.deepseek.com"
```

## Run

```powershell
cd H:\codex\multiagent
python -m multiagent
```

The example request lives in `example_input.json`.

## Local web UI

This project also includes a lightweight local web interface for prompt entry, output inspection, and human feedback collection.

Start the UI server:

```powershell
cd H:\codex\multiagent
python -m multiagent.webapp
```

Then open:

```text
http://127.0.0.1:8000
```

The web UI currently provides:

- A prompt input panel
- A prompt run history panel for reviewing and rerunning previous benchmark prompts
- A benchmark batch runner that generates 30 randomized prompt cases and records token usage
- A pipeline visualization panel
- An output viewer focused on node output, element output, and complete code
- A Node / Element visualization panel rendered directly from agent JSON outputs
- Click-to-generate retry prompts for incorrect nodes or elements
- Correct / incorrect feedback buttons with notes
- A live pipeline run trigger with status updates
- A generated-code runner with stdout and stderr panels
- Opsvis-based axial force, shear force, and bending moment diagrams after code execution

To run generated code inside your ops virtual environment, set:

```powershell
$env:OPS_PYTHON="full\\path\\to\\ops\\python.exe"
```

Then start the web UI and use the `Run Generated Code` button.

The same environment also needs `openseespy` and `opsvis` installed if you want section-force diagrams.

## RL-style orchestration

This project now includes a first-pass RL-style system optimization layer for API-based LLM usage. It does not fine-tune the remote LLM. Instead, it records observable rewards and policy decisions around each run:

- Technical reward layer: scores pipeline completion, agent artifacts, generated code execution, opsvis diagrams, Python Check Agent diagnosis, and human correct / incorrect feedback.
- Policy optimization layer: recommends the next orchestration action, such as accept, retry code generation, repair visualization, targeted node / element reanalysis, or observe more signals.
- Repair loop layer: stores enough reward and policy context to build focused retry prompts for failing agents.

The reward history is stored locally in:

```text
outputs/rl_history.sqlite3
```

The current web snapshot is also written to:

```text
outputs/rl_status.json
```

In the web UI, the `RL-Style Optimization` panel shows the current total reward, inferred error type, policy action, and reward components. The SQLite database is intended as a lightweight local memory for comparing prompts, generated artifacts, failures, fixes, and human feedback over time.

Every submitted prompt is also saved in the same SQLite database under `prompt_history`, even before the pipeline finishes. This makes it easier to build a benchmark set and rerun previous cases from the frontend.

The benchmark runner stores each randomized case under `benchmark_cases`, including:

- pipeline status
- prompt, completion, and total tokens reported by the LLM API
- reward score and policy action
- manual review verdict and notes

Benchmark geometry prompts randomize bay count, bay lengths, per-bay story counts, uniform loads, and node forces. Story heights are generated from a shared story-level height table, so the same story level has the same height across all bays. For example, if the first story is 7 m, every bay that contains a first story uses 7 m for that level.

Use `Retry Failed Cases` in the web UI to create a new retry batch from failed cases only. Successful cases from previous batches are preserved and are not rerun or overwritten; retry records keep a `retry_from_case_id` link to the original failed case.

Use `Run Review Set` when you want to preserve the already successful prompts and create fresh, case-specific artifacts for human review. This starts a new `review-*` batch from the latest original `batch-*` run, selects cases that either succeeded directly or succeeded through a retry descendant, and archives each case's node output, element output, complete code, debug files, and pipeline log under:

```text
outputs/benchmark_artifacts/
```

The review batch uses a lighter orchestration profile so repeated review runs are faster than the default exploratory pipeline:

```powershell
$env:MULTIAGENT_REVIEW_RETRIES_ANALYSIS="2"
$env:MULTIAGENT_REVIEW_RETRIES_GEOMETRY="2"
$env:MULTIAGENT_REVIEW_RETRIES_CODE="2"
$env:MULTIAGENT_REVIEW_RAG_TOP_K="1"
$env:MULTIAGENT_REVIEW_RAG_MAX_CHARS="2500"
```

After the review batch finishes, click `View Outputs` on each case to inspect the archived `Node`, `Element`, `Complete Code`, `Geometry Code`, `Pipeline Log`, and debug outputs before marking it `Correct` or `Incorrect`.

## RAG_OS integration

The code translation stage can use the local `RAG_OS` documentation knowledge base to ground OpenSeesPy and OpsVis API usage before asking the LLM to generate code.

By default, the pipeline looks for:

```text
H:\codex\RAG_OS
```

Relevant settings:

```powershell
$env:RAG_OS_ROOT="H:\codex\RAG_OS"
$env:MULTIAGENT_RAG_ENABLED="true"
$env:MULTIAGENT_RAG_TOP_K="3"
$env:MULTIAGENT_RAG_MAX_CHARS="6000"
```

The first integration pass adds retrieved documentation context to:

- `GeometryCodeTranslator`
- `CompleteCodeGenerator`

To use the node / element interaction flow:

1. Run the pipeline so `outputs/geometry_code.py` exists
2. Inspect the `Node Agent Output` or `Element Agent Output`
3. Click a node or element in the visualization panel
4. Review the generated retry prompt
5. Use `Run Reanalysis` to send the targeted prompt back through the pipeline

To render the section-force diagrams after execution:

1. Run the pipeline so `outputs/complete_code.py` exists
2. Click `Run Generated Code`
3. If execution succeeds and `openseespy` plus `opsvis` are available in the `OPS_PYTHON` environment, the UI will show:
   - axial force diagram
   - shear force diagram
   - bending moment diagram

If opsvis diagram rendering fails, inspect:

- `outputs/section_diagram_stdout.txt`
- `outputs/section_diagram_stderr.txt`

## Python Check Agent

This repository now includes a scaffold for a `PythonCheckAgent`, which is intended to analyze execution failures from generated OpenSeesPy code and return a structured diagnosis for repair and retry workflows.

Related files:

- `src/multiagent/agents/python_check_agent.py`
- `src/multiagent/functions/execution_diagnostics.py`
- `src/multiagent/prompts/python_check_agent.txt`
- `PYTHON_CHECK_AGENT.md`

## Current status

This repository is a scaffold, not a production-ready generator. The pipeline structure, prompts, validators, and schema are in place, but the agent outputs still need to be aligned to the unified contract for reliable end-to-end generation.

## What is included

- Multi-agent pipeline orchestration
- Shared pipeline state model
- Structured schema definitions
- Prompt templates for each agent
- Deterministic validation checkpoints
- Connectivity mapping and JSON compilation helpers
- Example input and output artifacts

## Security note

Do not commit real API keys or provider secrets to the repository. Configure credentials with environment variables instead.

## Recommended next steps

1. Align all agent outputs to the schema in `SCHEMA.md`
2. Update validators and mapping functions to consume the canonical schema
3. Tighten prompts so each agent returns valid structured output
4. Add tests for schema validation, geometry mapping, and code generation
