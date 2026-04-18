# Unified Agent Schema Contract

This project should use one canonical JSON contract across all seven agents.
The goal is to remove schema drift between prompts, validators, mapping functions, and code generation.

## Naming rules

- Use `snake_case` for every JSON key.
- Use numeric `id` values for nodes and elements after `problem_analysis`.
- Use one top-level payload name per agent output.
- Every structured output should include `schema_version`.
- `construction_steps` is the only accepted step container name.

## Agent I/O

### 1. ProblemAnalysisAgent

Input:
- `user_input: str`

Output key:
- `problem_analysis`

Canonical output shape:

```json
{
  "schema_version": "1.0",
  "project_name": "example_frame",
  "problem_statement": "Build a 2D frame with 3 bays and 2 stories.",
  "assumptions": ["Linear elastic behavior."],
  "geometry": {
    "system_type": "frame",
    "dimensionality": "2D",
    "coordinate_system": "global_xy",
    "story_count": 2,
    "bay_count": 3,
    "bay_widths": [6.0, 6.0, 6.0],
    "story_heights": [3.0, 3.0],
    "units": {
      "length": "m",
      "force": "kN"
    },
    "description": "Three-bay two-story planar frame."
  },
  "supports": [
    {
      "support_id": "S1",
      "level": "base",
      "location": "all base nodes",
      "constraint_type": "fixed",
      "constrained_dofs": ["ux", "uy", "rz"],
      "description": "Fixed supports at all column bases."
    }
  ],
  "materials": [
    {
      "material_id": "MAT1",
      "model": "elastic",
      "parameters": {
        "E": 200000000000.0
      },
      "description": "Elastic material."
    }
  ],
  "sections": [
    {
      "section_id": "SEC_BEAM",
      "element_type": "beam",
      "shape": "generic",
      "parameters": {
        "A": 0.01,
        "I": 8.33e-05
      },
      "description": "Beam section."
    }
  ],
  "load_cases": [
    {
      "load_case_id": "LC1",
      "load_type": "uniform",
      "direction": "global_y",
      "target": "girders",
      "magnitude": -1.0,
      "distribution": "uniform",
      "description": "Uniform downward load on all girders."
    }
  ],
  "modeling_intent": {
    "target_platform": "OpenSeesPy",
    "visualization": ["OpsVis"],
    "output_language": "python",
    "analysis_type": "structural_model_generation"
  }
}
```

### 2. ConstructionPlanningAgent

Input:
- `problem_analysis`

Output key:
- `construction_plan`

Canonical output shape:

```json
{
  "schema_version": "1.0",
  "total_steps": 14,
  "construction_steps": [
    {
      "step_number": 1,
      "step_type": "erect_column",
      "story_number": 1,
      "bay_number": 1,
      "node_ids": [1, 5],
      "element_ids": [1],
      "depends_on": [],
      "description": "Erect first-story column at bay 1."
    }
  ],
  "sequencing_notes": [
    "Columns before beams on each story.",
    "Loads applied after geometry creation."
  ]
}
```

### 3. NodeAgent

Input:
- `problem_analysis`
- `construction_plan`

Output key:
- `node_output`

Canonical output shape:

```json
{
  "schema_version": "1.0",
  "node_count": 12,
  "construction_steps": [
    {
      "step_number": 1,
      "nodes": [
        {
          "id": 1,
          "x": 0.0,
          "y": 0.0,
          "story_number": 0,
          "bay_position": 0,
          "label": "N1",
          "description": "Base node at left column."
        },
        {
          "id": 5,
          "x": 0.0,
          "y": 3.0,
          "story_number": 1,
          "bay_position": 0,
          "label": "N5",
          "description": "Top node of first-story left column."
        }
      ],
      "boundary_conditions": [
        {
          "node_id": 1,
          "step_number": 1,
          "constraint_type": "fixed",
          "constrained_dofs": ["ux", "uy", "rz"],
          "description": "Base fixed support."
        }
      ]
    }
  ]
}
```

### 4. ElementAgent

Input:
- `problem_analysis`
- `construction_plan`

Output key:
- `element_output`

Canonical output shape:

```json
{
  "schema_version": "1.0",
  "element_count": 14,
  "construction_steps": [
    {
      "step_number": 1,
      "elements": [
        {
          "id": 1,
          "type": "column",
          "node_i": 1,
          "node_j": 5,
          "section_id": "SEC_COLUMN",
          "material_id": "MAT1",
          "orientation": "vertical",
          "story_number": 1,
          "bay_number": 1,
          "description": "First-story column at bay 1."
        }
      ]
    }
  ]
}
```

### 5. Connectivity Mapping Function

Input:
- `node_output`
- `element_output`

Output key:
- `geometry`

Canonical output shape:

```json
{
  "schema_version": "1.0",
  "nodes": [],
  "boundary_conditions": [],
  "elements": []
}
```

Rules:
- Flatten all per-step node records into one `nodes` array.
- Flatten all per-step element records into one `elements` array.
- Preserve `step_number` in boundary conditions.
- Reject elements whose `node_i` or `node_j` do not exist in `nodes`.

### 6. LoadAssignmentAgent

Input:
- `problem_analysis`
- `geometry`

Output key:
- `load_output`

Canonical output shape:

```json
{
  "schema_version": "1.0",
  "assigned_loads": [
    {
      "load_case_id": "LC1",
      "target_type": "element",
      "target_ids": [9, 10, 11, 12, 13, 14],
      "load_type": "uniform",
      "direction": "global_y",
      "magnitude": -1.0,
      "coordinate_system": "global",
      "application_step": 15,
      "description": "Uniform downward load on all girders."
    }
  ]
}
```

### 7. GeometryCodeTranslator

Input:
- `compiled_model`

Output key:
- `geometry_code`

Output type:
- `str`

Rules:
- Must only emit geometry/model-definition code.
- Must consume ids from `compiled_model.geometry`.
- Must not invent missing nodes or elements.

### 8. CompleteCodeGenerator

Input:
- `compiled_model`
- `geometry_code`

Output key:
- `complete_code`

Output type:
- `str`

Rules:
- Must append materials, sections, loads, analysis setup, and optional visualization.
- Must not redefine nodes/elements with ids different from `geometry_code`.

## Compiled model contract

The JSON compiler should produce:

```json
{
  "schema_version": "1.0",
  "problem_analysis": {},
  "construction_plan": {},
  "geometry": {},
  "loads": {}
}
```

## Non-negotiable invariants

- `problem_analysis.geometry.story_count` and `bay_count` are the authoritative geometry counts.
- `construction_plan.total_steps == len(construction_steps)`.
- `node_output.node_count` equals the number of unique node ids across all steps.
- `element_output.element_count` equals the number of unique element ids across all steps.
- `geometry.nodes` must contain unique numeric node ids.
- `geometry.elements` must reference existing numeric node ids.
- `load_output.assigned_loads[*].target_ids` must reference existing ids from `geometry`.
- Code generators may enrich formatting, comments, and defaults, but not topology.
