# Python Check Agent

This document defines the role of the `PythonCheckAgent` in the multi-agent structural modeling workflow.

## Purpose

The `PythonCheckAgent` closes the loop between code generation and code execution.
It receives execution failures from the generated `complete_code.py`, analyzes the error in context, and returns a structured diagnosis that can be used for:

- user-facing debugging
- automated retry decisions
- targeted regeneration of upstream agents
- reward / penalty signals for a future compensation mechanism

## Recommended placement

```text
Code Translation
  -> Geometry Code Translator
  -> Complete Code Generator
  -> Run Generated Code
  -> Python Check Agent
  -> Repair / Retry Policy
```

## Inputs

- original `user_input`
- `compiled_model`
- `geometry_code`
- `complete_code`
- `execution_report`

## Output

The canonical output is a structured JSON diagnosis with:

- `error_type`
- `root_cause`
- `responsible_stage`
- `confidence`
- `repair_action`
- `should_retry`
- `suggested_target_agent`
- `notes`

## Why it matters

Existing checkpoints mainly detect structural consistency problems before execution.
The `PythonCheckAgent` adds a new execution-time validation layer that can capture:

- missing dependencies
- syntax and import errors
- OpenSeesPy API misuse
- topology issues that only surface during execution
- mismatches between generated code and compiled model assumptions

## Integration strategy

The most robust implementation is a two-layer design:

1. Deterministic classifier:
   - inspects return code, stderr, and known exception signatures
   - handles obvious failures like missing packages or timeouts
2. `PythonCheckAgent`:
   - performs higher-level diagnosis and repair guidance
   - reasons across code, execution trace, and upstream structured outputs

## Suggested next implementation step

Connect `build_execution_report()` and `PythonCheckAgent.run()` inside the web execution flow after `complete_code.py` finishes.
Store the resulting diagnosis to `outputs/python_check_output.json` and expose it in the local web UI.
