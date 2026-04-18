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
