from __future__ import annotations

from typing import Any

from ..functions.schema_normalizer import normalize_elements, normalize_nodes
from ..schemas import ValidationResult


def _first_mapping_value(data: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in data:
            return data[name]
    return None


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _story_count_from_bay(bay: dict[str, Any]) -> int:
    explicit = _first_mapping_value(
        bay,
        (
            "Story_count",
            "story_count",
            "num_stories",
            "stories_count",
            "number_of_stories",
        ),
    )
    if explicit is not None:
        return _to_int(explicit)

    stories = _first_mapping_value(bay, ("stories", "Stories", "story_data", "Story_data"))
    if isinstance(stories, list):
        return len(stories)

    heights = _first_mapping_value(bay, ("story_heights", "story_heights_m", "Story_heights"))
    if isinstance(heights, list):
        return len(heights)

    return 0


def _extract_bay_story_counts(problem_analysis: dict[str, Any]) -> dict[int, int]:
    geometry = _first_mapping_value(problem_analysis, ("geometry", "Geometry")) or {}
    if not isinstance(geometry, dict):
        return {}

    # Priority 1: explicit per_bay_story_counts list (v5+ format)
    per_bay = _first_mapping_value(geometry, ("per_bay_story_counts", "Per_bay_story_counts"))
    if isinstance(per_bay, list) and all(isinstance(v, (int, float)) for v in per_bay):
        return {i + 1: int(v) for i, v in enumerate(per_bay)}

    # Priority 2: Bay_data / bays array
    bays = _first_mapping_value(geometry, ("Bay_data", "bays", "Bays", "bay_data"))
    bay_story_counts: dict[int, int] = {}
    if isinstance(bays, list):
        for index, bay in enumerate(bays, start=1):
            if not isinstance(bay, dict):
                continue
            bay_number = _to_int(
                _first_mapping_value(
                    bay,
                    ("Bay_number", "bay_number", "bay_id", "id", "number"),
                ),
                index,
            )
            bay_story_counts[bay_number] = _story_count_from_bay(bay)

    if bay_story_counts:
        return bay_story_counts

    # Priority 3: uniform bay_count × story_count (fallback)
    total_bays = _to_int(
        _first_mapping_value(geometry, ("Total_bays", "total_bays", "bay_count", "num_bays")),
    )
    story_count = _to_int(
        _first_mapping_value(geometry, ("Total_stories", "total_stories", "story_count", "num_stories")),
    )
    story_heights = _first_mapping_value(geometry, ("story_heights", "story_heights_m", "Story_heights"))
    if story_count == 0 and isinstance(story_heights, list):
        story_count = len(story_heights)
    if total_bays > 0 and story_count > 0:
        return {bay_number: story_count for bay_number in range(1, total_bays + 1)}

    return {}


def _extract_plan_steps(construction_plan: dict[str, Any]) -> list[dict[str, Any]]:
    steps = _first_mapping_value(construction_plan, ("Construction_steps", "construction_steps", "steps"))
    if not isinstance(steps, list):
        return []
    return [step for step in steps if isinstance(step, dict)]


def _step_value(step: dict[str, Any], *names: str) -> Any:
    return _first_mapping_value(step, names)


def validate_analysis_planning(problem_analysis: dict, construction_plan: dict) -> ValidationResult:
    errors: list[str] = []
    if not isinstance(problem_analysis, dict):
        return ValidationResult(ok=False, errors=["Problem analysis must be a JSON object."])
    if not isinstance(construction_plan, dict):
        return ValidationResult(ok=False, errors=["Construction plan must be a JSON object."])

    bay_story_counts = _extract_bay_story_counts(problem_analysis)
    steps = _extract_plan_steps(construction_plan)
    if not bay_story_counts:
        errors.append("Problem analysis does not contain readable bay/story geometry.")
    if not steps:
        errors.append("Construction plan does not contain readable construction steps.")
        return ValidationResult(ok=False, errors=errors)

    total_bays = len(bay_story_counts)
    seen_pairs: set[tuple[int, int]] = set()
    seen_step_numbers: set[int] = set()
    for index, step in enumerate(steps, start=1):
        step_number = _to_int(_step_value(step, "Step_number", "step_number"), index)
        if step_number in seen_step_numbers:
            errors.append(f"Duplicate construction step number detected: {step_number}.")
        seen_step_numbers.add(step_number)

        step_type = str(_step_value(step, "Step_type", "step_type") or "").lower()
        # Skip base_nodes step (bay=0, story=0) — not a bay/story pair
        if step_type == "base_nodes":
            continue

        bay_number = _to_int(_step_value(step, "Bay_number", "bay_number", "bay_id"), 0)
        story_number = _to_int(_step_value(step, "Story_number", "story_number", "story_id"), 0)
        if bay_number <= 0:
            errors.append(f"Construction step {step_number} has an invalid bay number: {bay_number}.")
            continue
        if total_bays and bay_number > total_bays:
            errors.append(
                f"Construction step {step_number} references bay {bay_number}, but only {total_bays} bays were parsed."
            )
            continue
        if story_number <= 0:
            errors.append(f"Construction step {step_number} has an invalid story number: {story_number}.")
            continue

        max_story = bay_story_counts.get(bay_number, 0)
        if max_story and story_number > max_story:
            errors.append(
                f"Construction step {step_number} references story {story_number} in bay {bay_number}, "
                f"but that bay has {max_story} stories."
            )
            continue
        seen_pairs.add((bay_number, story_number))

    for bay_number, story_count in sorted(bay_story_counts.items()):
        for story_number in range(1, story_count + 1):
            if (bay_number, story_number) not in seen_pairs:
                errors.append(f"Construction plan is missing bay {bay_number}, story {story_number}.")
    return ValidationResult(ok=not errors, errors=errors)


def validate_geometry(node_output: dict, element_output: dict) -> ValidationResult:
    errors: list[str] = []
    node_coords: dict[tuple[float, float], int] = {}
    node_ids: set[int] = set()
    all_nodes: dict[int, tuple[float, float]] = {}

    nodes, _ = normalize_nodes(node_output)
    element_nodes, _ = normalize_nodes(element_output)
    known_node_ids = {int(node["id"]) for node in nodes}
    for node in element_nodes:
        if int(node["id"]) not in known_node_ids:
            nodes.append(node)
            known_node_ids.add(int(node["id"]))
    if not nodes:
        errors.append("Node output does not contain readable nodes.")
    for node in nodes:
        node_id = int(node["id"])
        coord = (float(node["x"]), float(node["y"]))
        if node_id in node_ids:
            errors.append(f"Duplicate node id detected: {node_id}")
        node_ids.add(node_id)
        node_coords[coord] = node_id
        all_nodes[node_id] = coord

    element_ids: set[int] = set()
    seen_elements: set[tuple[int, int]] = set()
    elements = normalize_elements(element_output, node_coords)
    if not elements:
        errors.append("Element output does not contain readable elements.")
    for element in elements:
        element_id = int(element["id"])
        if element_id in element_ids:
            errors.append(f"Duplicate element id detected: {element_id}")
        element_ids.add(element_id)

        pair = (int(element["node_i"]), int(element["node_j"]))
        missing = [node_id for node_id in pair if node_id not in all_nodes]
        if missing:
            errors.append(f"Element {element_id} references missing node ids: {missing}.")
            continue
        ordered_pair = tuple(sorted(pair))
        seen_elements.add(ordered_pair)
    return ValidationResult(ok=not errors, errors=errors)


# ---------------------------------------------------------------------------
# Geometry consistency validator — automatically checks node/element outputs
# for structural plausibility after the basic schema validation passes.
# ---------------------------------------------------------------------------

def _extract_bay_widths(problem_analysis: dict[str, Any]) -> list[float]:
    """Extract bay widths (m) from problem analysis, best-effort."""
    geometry = _first_mapping_value(problem_analysis, ("geometry", "Geometry")) or {}
    if not isinstance(geometry, dict):
        return []

    widths = _first_mapping_value(geometry, ("bay_widths", "bay_widths_m", "Bay_widths"))
    if isinstance(widths, list) and all(isinstance(w, (int, float)) for w in widths):
        return [float(w) for w in widths]

    bays = _first_mapping_value(geometry, ("Bay_data", "bays", "Bays", "bay_data"))
    if isinstance(bays, list):
        result: list[float] = []
        for bay in bays:
            if isinstance(bay, dict):
                w = _first_mapping_value(bay, ("bay_width", "width", "bay_width_m"))
                if w is not None:
                    result.append(float(w))
        if result:
            return result

    return []


def _extract_story_heights(problem_analysis: dict[str, Any]) -> list[float]:
    """Extract story heights (m) from problem analysis, best-effort."""
    geometry = _first_mapping_value(problem_analysis, ("geometry", "Geometry")) or {}
    if not isinstance(geometry, dict):
        return []

    heights = _first_mapping_value(geometry, ("story_heights", "story_heights_m", "Story_heights"))
    if isinstance(heights, list) and all(isinstance(h, (int, float)) for h in heights):
        return [float(h) for h in heights]

    bays = _first_mapping_value(geometry, ("Bay_data", "bays", "Bays", "bay_data"))
    if isinstance(bays, list):
        for bay in bays:
            if isinstance(bay, dict):
                h = _first_mapping_value(bay, ("story_heights", "story_heights_m", "Story_heights"))
                if isinstance(h, list) and all(isinstance(v, (int, float)) for v in h):
                    return [float(v) for v in h]

    return []


def _cluster_values(values: list[float], tolerance: float) -> list[float]:
    """Cluster similar numeric values and return sorted cluster centres."""
    if not values:
        return []
    sorted_vals = sorted(values)
    clusters: list[list[float]] = [[sorted_vals[0]]]
    for v in sorted_vals[1:]:
        if abs(v - clusters[-1][-1]) <= tolerance:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    return [sum(c) / len(c) for c in clusters]


def validate_geometry_consistency(
    node_output: dict[str, Any],
    element_output: dict[str, Any],
    problem_analysis: dict[str, Any] | None = None,
    construction_plan: dict[str, Any] | None = None,
    tolerance: float = 0.5,
) -> ValidationResult:
    """Validate structural consistency of node and element outputs.

    Checks performed (all are warnings unless noted):
    1. Column-type elements are approximately vertical  (Δx ≈ 0)
    2. Beam-type elements are approximately horizontal (Δy ≈ 0)
    3. Nodes are organized in a regular grid (stories share Y, bays share X)
    4. Expected node/element counts roughly match geometry spec
    5. Boundary-condition nodes reference existing node IDs
    6. No orphan nodes (optional warning)
    7. No duplicate-position nodes (different ID, same coordinates)

    Returns a ValidationResult with per-node and per-element status in
    ``details["node_status"]`` and ``details["element_status"]`` for
    frontend visualization.
    """
    errors: list[str] = []
    warnings: list[str] = []
    node_status: dict[int, dict[str, Any]] = {}
    element_status: dict[int, dict[str, Any]] = {}

    # --- Normalize outputs ---------------------------------------------------
    nodes, boundary_conditions = normalize_nodes(node_output)
    element_nodes, _ = normalize_nodes(element_output)
    known_ids = {int(n["id"]) for n in nodes}
    for n in element_nodes:
        if int(n["id"]) not in known_ids:
            nodes.append(n)
            known_ids.add(int(n["id"]))

    node_map: dict[int, dict[str, Any]] = {int(n["id"]): n for n in nodes}
    for nid in node_map:
        node_status[nid] = {"status": "ok", "messages": []}

    coord_map: dict[tuple[float, float], int] = {}
    for n in nodes:
        coord = (float(n["x"]), float(n["y"]))
        coord_map[coord] = int(n["id"])

    elements = normalize_elements(element_output, coord_map)
    el_map: dict[int, dict[str, Any]] = {int(e["id"]): e for e in elements}
    for eid in el_map:
        element_status[eid] = {"status": "ok", "messages": []}

    if not nodes or not elements:
        return ValidationResult(
            ok=False,
            errors=["Node or element output is empty — cannot run consistency check."],
            warnings=warnings,
            details={"node_status": node_status, "element_status": element_status},
        )

    # --- Extract expected geometry from problem_analysis --------------------
    bay_story = _extract_bay_story_counts(problem_analysis) if problem_analysis else {}
    total_bays = len(bay_story)
    total_stories = max(bay_story.values()) if bay_story else 0
    bay_widths = _extract_bay_widths(problem_analysis) if problem_analysis else []
    story_heights = _extract_story_heights(problem_analysis) if problem_analysis else []

    # --- 1. Element orientation checks -------------------------------------
    for eid, el in el_map.items():
        ni = node_map.get(el["node_i"])
        nj = node_map.get(el["node_j"])
        if ni is None or nj is None:
            continue

        dx = abs(float(ni["x"]) - float(nj["x"]))
        dy = abs(float(ni["y"]) - float(nj["y"]))
        el_type = str(el.get("type", "")).lower().strip()

        # Infer type from geometry if not explicitly given
        inferred = ""
        if dy > dx * 3:
            inferred = "column"
        elif dx > dy * 3:
            inferred = "beam"

        effective_type = el_type or inferred

        if effective_type in ("column",) and dx > tolerance:
            msg = f"Column {eid} has Δx={dx:.2f}m (should be ≈0, vertical)"
            warnings.append(msg)
            element_status[eid]["status"] = "warning"
            element_status[eid]["messages"].append(msg)

        if effective_type in ("beam", "girder") and dy > tolerance:
            msg = f"Beam {eid} has Δy={dy:.2f}m (should be ≈0, horizontal)"
            warnings.append(msg)
            element_status[eid]["status"] = "warning"
            element_status[eid]["messages"].append(msg)

        if not el_type and not inferred:
            msg = f"Element {eid} has unknown type and ambiguous orientation (dx={dx:.2f}, dy={dy:.2f})"
            warnings.append(msg)
            element_status[eid]["status"] = "warning"
            element_status[eid]["messages"].append(msg)

    # --- 2. Node grid alignment -------------------------------------------
    xs = [float(n["x"]) for n in nodes]
    ys = [float(n["y"]) for n in nodes]

    x_clusters = _cluster_values(xs, tolerance)
    y_clusters = _cluster_values(ys, tolerance)

    # Check each node is near a grid line
    for n in nodes:
        nid = int(n["id"])
        nx, ny = float(n["x"]), float(n["y"])
        nearest_x = min(x_clusters, key=lambda c: abs(c - nx))
        nearest_y = min(y_clusters, key=lambda c: abs(c - ny))
        dx_grid = abs(nx - nearest_x)
        dy_grid = abs(ny - nearest_y)

        grid_issues = []
        if dx_grid > tolerance * 1.5:
            grid_issues.append(f"x={nx:.2f}m, nearest grid line at x={nearest_x:.2f}m (off by {dx_grid:.2f}m)")
        if dy_grid > tolerance * 1.5:
            grid_issues.append(f"y={ny:.2f}m, nearest grid line at y={nearest_y:.2f}m (off by {dy_grid:.2f}m)")

        if grid_issues:
            msg = f"Node {nid} is off-grid: " + "; ".join(grid_issues)
            warnings.append(msg)
            node_status[nid]["status"] = "warning"
            node_status[nid]["messages"].append(msg)

    # --- 3. Expected node / element counts ----------------------------------
    if total_bays > 0 and total_stories > 0:
        expected_nodes = (total_bays + 1) * (total_stories + 1)
        actual_nodes = len(nodes)
        if actual_nodes != expected_nodes:
            msg = (
                f"Node count mismatch: expected {expected_nodes} "
                f"({total_bays}+1 bays × {total_stories}+1 stories), got {actual_nodes}"
            )
            warnings.append(msg)

        # Rough element count: columns = (bays+1)*stories, beams = bays*(stories+1)
        expected_cols = (total_bays + 1) * total_stories
        expected_beams = total_bays * (total_stories + 1)
        col_count = sum(1 for e in el_map.values() if str(e.get("type", "")).lower() in ("column",))
        beam_count = sum(1 for e in el_map.values() if str(e.get("type", "")).lower() in ("beam", "girder"))
        unknown_count = len(el_map) - col_count - beam_count

        if col_count > 0 and col_count != expected_cols:
            msg = f"Column count: expected ~{expected_cols}, got {col_count}"
            warnings.append(msg)
        if beam_count > 0 and beam_count != expected_beams:
            msg = f"Beam count: expected ~{expected_beams}, got {beam_count}"
            warnings.append(msg)
        if unknown_count > len(el_map) * 0.3:
            msg = f"{unknown_count}/{len(el_map)} elements have unknown type — orientation checks may be incomplete"
            warnings.append(msg)

    # --- 4. Boundary condition node references -----------------------------
    for bc in boundary_conditions:
        bc_nid = int(bc.get("node_id", 0))
        if bc_nid <= 0:
            continue
        if bc_nid not in node_map:
            msg = f"Boundary condition references non-existent node {bc_nid}"
            errors.append(msg)
            if bc_nid in node_status:
                node_status[bc_nid]["status"] = "error"
                node_status[bc_nid]["messages"].append(msg)

    # --- 5. Duplicate-position nodes (same coords, different ID) -----------
    pos_to_ids: dict[tuple[float, float], list[int]] = {}
    for n in nodes:
        pos = (round(float(n["x"]), 3), round(float(n["y"]), 3))
        pos_to_ids.setdefault(pos, []).append(int(n["id"]))
    for pos, ids in pos_to_ids.items():
        if len(ids) > 1:
            msg = f"Nodes {ids} share the same position ({pos[0]:.2f}, {pos[1]:.2f})"
            warnings.append(msg)
            for nid in ids:
                node_status[nid]["status"] = "warning"
                node_status[nid]["messages"].append(msg)

    # --- 6. Orphan nodes (not referenced by any element) -------------------
    referenced: set[int] = set()
    for el in el_map.values():
        referenced.add(el["node_i"])
        referenced.add(el["node_j"])
    orphan_ids = set(node_map.keys()) - referenced
    if orphan_ids:
        msg = f"Orphan nodes (no element references them): {sorted(orphan_ids)}"
        warnings.append(msg)
        for nid in orphan_ids:
            node_status[nid]["status"] = "warning"
            node_status[nid]["messages"].append(msg)

    # --- Compute summary ---------------------------------------------------
    ok = len(errors) == 0

    summary = {
        "total_nodes": len(nodes),
        "total_elements": len(elements),
        "total_boundary_conditions": len(boundary_conditions),
        "total_errors": len(errors),
        "total_warnings": len(warnings),
        "nodes_ok": sum(1 for s in node_status.values() if s["status"] == "ok"),
        "nodes_warning": sum(1 for s in node_status.values() if s["status"] == "warning"),
        "nodes_error": sum(1 for s in node_status.values() if s["status"] == "error"),
        "elements_ok": sum(1 for s in element_status.values() if s["status"] == "ok"),
        "elements_warning": sum(1 for s in element_status.values() if s["status"] == "warning"),
        "elements_error": sum(1 for s in element_status.values() if s["status"] == "error"),
        "x_grid_lines": x_clusters,
        "y_grid_lines": y_clusters,
        "expected_nodes": (total_bays + 1) * (total_stories + 1) if total_bays and total_stories else None,
        "expected_columns": (total_bays + 1) * total_stories if total_bays and total_stories else None,
        "expected_beams": total_bays * (total_stories + 1) if total_bays and total_stories else None,
    }

    return ValidationResult(
        ok=ok,
        errors=errors,
        warnings=warnings,
        details={
            "node_status": node_status,
            "element_status": element_status,
            "summary": summary,
        },
    )


def _error_is_node_fault(error_text: str) -> bool:
    """Check if a consistency error is attributable to the Node Agent."""
    text = error_text.lower()
    node_keywords = [
        "node", "grid", "coordinate", "position", "orphan",
        "duplicate node", "duplicate-position", "off-grid",
    ]
    return any(kw in text for kw in node_keywords)


def _error_is_element_fault(error_text: str) -> bool:
    """Check if a consistency error is attributable to the Element Agent."""
    text = error_text.lower()
    elem_keywords = [
        "element", "column", "beam", "orientation", "connectivity",
        "δx", "δy", "vertical", "horizontal", "unknown type",
    ]
    return any(kw in text for kw in elem_keywords)
