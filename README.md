# Multi-Agent Structural Modeling Scaffold

A Python scaffold for a multi-agent structural modeling pipeline that turns natural-language 2D frame descriptions into structured model data and generated OpenSeesPy code.

> **Current version: v2.3**

## Pipeline overview

Eight agents in four stages:

| Stage | Agents |
|-------|--------|
| Analysis & Planning | `ProblemAnalysisAgent` → `ConstructionPlanningAgent` |
| Geometry Assembly | `NodeAgent` → `ElementAgent` → `connectivity_mapping` |
| Load Integration | `LoadAssignmentAgent` |
| Code Translation | `GeometryCodeTranslator` → `CompleteCodeGenerator` → `PythonCheckAgent` |

Intermediate outputs are written to `outputs/` when enabled in the pipeline config.

## Project structure

```text
src/multiagent/
  agents/        Agent entrypoints
  functions/     Deterministic mapping/compiler helpers
  llm/           LLM client wrapper
  prompts/       Prompt templates (v6)
  validators/    Checkpoint validation logic
  web/           Frontend (index.html, app.js, app.css)
outputs/         Runtime artifacts (gitignored)
scripts/         Report generation scripts
```

## Setup

Requirements: Python 3.11+

```powershell
cd H:\codex\multiagent
pip install -e .
```

Set API credentials before running:

```powershell
$env:DEEPSEEK_API_KEY = "your_api_key_here"
$env:DEEPSEEK_MODEL   = "deepseek-v4-pro"          # optional, default
$env:DEEPSEEK_BASE_URL = "https://api.deepseek.com" # optional, default
```

## Start the web UI

```powershell
cd H:\codex\multiagent\src
python -m multiagent.webapp
```

Then open `http://127.0.0.1:8000`.

## Web UI features

The interface is a single-page app with a sidebar navigation and dark/light theme toggle:

- **Run Pipeline** — prompt entry, pipeline progress, live status
- **Output Viewer** — node output, element output, complete code, geometry code
- **Benchmark** — batch case runner, retry failed cases, review set generation
- **RL & Feedback** — reward history, policy actions, human feedback buttons
- **Execution** — run generated code, axial/shear/moment diagrams
- **Agent Rewards** — per-agent reward breakdown
- **History** — past run table

## Tiered LLM configuration

Agents are grouped into three tiers. Each tier shares a unified API endpoint and model. Configure them in the **Agent LLM Settings** panel on the Run Pipeline page.

| Tier | Label | Agents | Recommended model |
|------|-------|--------|-------------------|
| Tier 1 | Core Modeling | `problem_analysis`, `construction_planning`, `node_agent`, `element_agent` | GPT-4o or Claude Sonnet (reasoning-heavy) |
| Tier 2 | Code Generation | `load_assignment`, `geometry_code_translator`, `complete_code_generator` | DeepSeek-V4-Pro (fast, cost-effective) |
| Tier 3 | Verification | `python_check_agent` | Any capable model |

Fill in **Model Name**, **API Key**, and **Base URL** for each tier. Leave blank to fall back to the server environment defaults (`DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL`).

### Using OpenRouter

OpenRouter provides a single API key to access GPT-4o, Claude, and other providers:

```
Base URL:   https://openrouter.ai/api/v1
API Key:    sk-or-v1-<your OpenRouter key>
Model Name: openai/gpt-4o  (or anthropic/claude-sonnet-4-6, etc.)
```

### DeepSeek direct

```
Base URL:   https://api.deepseek.com
API Key:    sk-<your DeepSeek key>
Model Name: deepseek-v4-pro  (or deepseek-chat)
```

Tier configs are saved server-side to `outputs/agent_llm_config.json` and applied on every pipeline run. API keys are never exposed to the browser.

## Deterministic geometry (v6 prompts)

The v6 prompt set implements the bay-by-bay, story-by-story construction methodology from arXiv:2603.07728.

**Key design:**

- `ProblemAnalysisAgent` extracts `per_bay_story_counts` — a list of story counts, one per bay (e.g. `[3, 2, 4]` for a stepped frame).
- `ConstructionPlanningAgent` pre-computes the full geometry: `column_lines_x`, `story_levels_y`, `levels_per_column`, and the cumulative node-ID formula.
- `NodeAgent` generates nodes column-by-column, bottom-to-top, using `node_id(c, s) = offset[c] + s + 1`.
- `ElementAgent` generates elements using a separate formula — **not** by reading IDs from the construction plan — guaranteeing uniqueness:
  - **Columns**: for each column line `c`, segment `s → s+1` (strictly vertical, same x)
  - **Girders**: for each bay `b` and story `s ≤ per_bay_story_counts[b-1]`, connect left and right column lines at level `s` (strictly horizontal, same y)

This ensures zero diagonal elements, zero duplicate elements, and correct connectivity for irregular (stepped) frames.

## API reliability

- **No `response_format`**: DeepSeek's `response_format={"type": "json_object"}` causes indefinite hangs (suspected rejection-sampling loop). The pipeline uses a three-layer fallback instead: v6 prompt engineering → `_extract_json_text()` regex → retry with repair hints.
- **Hard timeout**: `requests` timeout is set to `300` seconds (single float = total deadline).
- **TOCTOU fix**: `_clear_pipeline_artifacts()` runs on the main thread before the worker starts, preventing race conditions between file deletion and state reads.

## RL-style orchestration

The pipeline records observable rewards and policy decisions around each run without fine-tuning the remote LLM:

- **Reward layer**: scores pipeline completion, agent artifacts, code execution, diagrams, and human feedback.
- **Policy layer**: recommends the next orchestration action (accept, retry, targeted reanalysis).
- **Repair layer**: stores reward context to build focused retry prompts for failing agents.

Reward history: `outputs/rl_history.sqlite3`

## RAG integration

Code translation agents can use a local OpenSeesPy/OpsVis documentation knowledge base:

```powershell
$env:RAG_OS_ROOT          = "H:\codex\RAG_OS"
$env:MULTIAGENT_RAG_ENABLED = "true"
$env:MULTIAGENT_RAG_TOP_K   = "3"
$env:MULTIAGENT_RAG_MAX_CHARS = "6000"
```

## Section-force diagrams

After running generated code, if `openseespy` and `opsvis` are installed in the OPS Python environment:

```powershell
$env:OPS_PYTHON = "full\path\to\ops\python.exe"
```

The UI will render axial, shear, and bending moment diagrams.

## Python Check Agent

`PythonCheckAgent` analyzes execution failures and returns a structured diagnosis for repair and retry workflows.

Related files:
- `src/multiagent/agents/python_check_agent.py`
- `src/multiagent/prompts/python_check_agent.txt`
- `PYTHON_CHECK_AGENT.md`

## Security note

Do not commit real API keys or provider secrets. Configure credentials with environment variables only.
