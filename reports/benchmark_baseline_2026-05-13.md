# Benchmark Baseline Report

Date: 2026-05-13  
Project: Multi-Agent Structural Modeling  
Benchmark source batch: `batch-20260506-141255`  
Case count: 30 randomized frame prompts  

## Executive Summary

This report records the current baseline quality of the multi-agent pipeline before the next optimization round.

The original 30-case benchmark had a first-pass pipeline success rate of 56.7%. After retry batches, 28 of 30 original prompts eventually reached pipeline success, giving a final technical success rate of 93.3%.

Important limitation: no human structural correctness review has been recorded yet. Therefore, "success" in this report means the pipeline completed technically; it does not yet guarantee that node layout, element connectivity, loads, generated OpenSeesPy code, or OpsVis diagrams are structurally correct.

## Overall Results

| Metric | Value |
|---|---:|
| Original cases | 30 |
| First-pass succeeded | 17 |
| First-pass failed | 13 |
| First-pass success rate | 56.7% |
| Succeeded after retry | 11 |
| Still failed after retries | 2 |
| Final technical success count | 28 |
| Final technical success rate | 93.3% |
| Human-reviewed cases | 0 |
| Unreviewed cases | 30 |

## Token Cost

| Metric | Value |
|---|---:|
| First-pass total tokens | 1,709,738 |
| First-pass prompt tokens | 415,486 |
| First-pass completion tokens | 1,294,252 |
| Average first-pass tokens per case | 56,991 |
| Total tokens including retry chains | 2,835,935 |
| Average tokens per original case including retries | 94,531 |

The retry mechanism improved the technical success rate substantially, but it increased token consumption by roughly 66% over the first pass.

## First-Pass Failure Types

| Failure type | Count | Interpretation |
|---|---:|---|
| Top-level list / schema drift | 9 | One or more agents returned a JSON list where the pipeline expected an object. |
| API payment required | 3 | DeepSeek returned HTTP 402, unrelated to model quality. |
| Network/proxy failure | 1 | Network/proxy connection failure, unrelated to model quality. |

The dominant model-side issue was schema instability, especially agents returning top-level arrays instead of schema objects.

## Final Unresolved Cases

| Original case | Attempts | Final error type | Latest error |
|---|---:|---|---|
| `batch-20260506-141255-case-03` | 5 | analysis/planning schema or count mismatch | Analysis and planning checkpoint failed after maximum retries. |
| `batch-20260506-141255-case-29` | 5 | analysis/planning schema or count mismatch | Analysis and planning checkpoint failed after maximum retries. |

These two cases no longer fail because of HTTP 402 or top-level list errors. They now fail because the analysis/planning checkpoint cannot reconcile `ProblemAnalysisAgent` output with `ConstructionPlanningAgent` output after repeated attempts.

## Retry Effectiveness

| Category | Count |
|---|---:|
| Succeeded in first pass | 17 |
| Failed first pass but later succeeded | 11 |
| Failed after all retries | 2 |

Retry was effective for most failures. It recovered schema drift, temporary API/network failures, and some node/element list-output failures. However, retry alone did not solve the two analysis/planning mismatch cases.

## Agent Token Usage In First Pass

| Agent | Calls | Total tokens | Prompt tokens | Completion tokens |
|---|---:|---:|---:|---:|
| `element_agent` | 19 | 398,824 | 42,382 | 356,442 |
| `node_agent` | 20 | 388,091 | 44,365 | 343,726 |
| `construction_planning` | 27 | 228,743 | 27,543 | 201,200 |
| `complete_code_generator` | 17 | 220,802 | 154,438 | 66,364 |
| `geometry_code_translator` | 17 | 190,225 | 119,572 | 70,653 |
| `load_assignment` | 17 | 169,922 | 16,500 | 153,422 |
| `problem_analysis` | 28 | 113,131 | 10,686 | 102,445 |

The largest token consumers are `element_agent` and `node_agent`, mainly because they generate long structured geometry outputs. The code generation agents also have high prompt-token cost, partly due to RAG/context injection and compiled model size.

## Output Quality Assessment

### Strengths

- The pipeline can complete most randomized structural frame prompts after retries.
- Retry orchestration is useful: 11 initially failed prompts were recovered.
- Token logging and retry lineage now make failure analysis reproducible.
- API/network failures are distinguishable from model/schema failures.

### Weaknesses

- First-pass stability is still weak at 56.7%.
- Agent schema drift is the largest technical failure mode.
- `ProblemAnalysisAgent` and `ConstructionPlanningAgent` can still disagree on expected bay/story construction steps.
- No human quality labels exist yet, so structural correctness is unknown.
- Token consumption is high, especially for geometry agents and retry chains.

### Current Confidence Level

| Quality dimension | Current confidence |
|---|---|
| Pipeline technical completion | Medium-high after retry |
| First-pass robustness | Medium-low |
| JSON schema consistency | Medium-low |
| OpenSeesPy/OpsVis syntax correctness | Unknown from this report alone |
| Structural engineering correctness | Unknown until manual review |
| Cost efficiency | Low-medium |

## Recommendations For Next Optimization Round

1. Add strict schema normalization for all JSON agents, not only `ConstructionPlanningAgent`.
2. Add wrappers for `NodeAgent` and `ElementAgent` when they return a top-level list.
3. Improve `validate_analysis_planning` diagnostics so failed cases report expected step count, actual step count, total bays, and max bay.
4. Reduce completion verbosity for `NodeAgent` and `ElementAgent`.
5. Separate technical success from human-reviewed correctness in the UI.
6. Add per-agent duration logging alongside token logging.
7. Use RAG only for code generation and repair stages, not for early planning agents.
8. Build a small curated few-shot set from the 17 first-pass successful cases and 11 retry-success cases.

## Baseline To Compare Against Later

Use the following numbers as the baseline for the next optimized version:

| Baseline metric | Current value |
|---|---:|
| First-pass success rate | 56.7% |
| Final success rate after retries | 93.3% |
| Unresolved cases | 2 |
| First-pass total tokens | 1,709,738 |
| Total tokens including retries | 2,835,935 |
| Human-reviewed correctness rate | Not available |

The next version should aim to increase first-pass success above 80%, reduce final unresolved cases to 0, and reduce average token usage per case by tightening schemas and shortening geometry outputs.
