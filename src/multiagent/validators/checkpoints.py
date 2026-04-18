from __future__ import annotations

from ..schemas import ValidationResult


def validate_analysis_planning(problem_analysis: dict, construction_plan: dict) -> ValidationResult:
    errors: list[str] = []
    geometry = problem_analysis.get("Geometry", {})
    total_bays = geometry.get("Total_bays")
    bay_data = geometry.get("Bay_data", [])
    expected_steps = sum(int(item.get("Story_count", 0)) for item in bay_data)
    steps = construction_plan.get("Construction_steps", [])
    max_bay = max((int(step.get("Bay_number", 0)) for step in steps), default=0)

    if total_bays is not None and max_bay != int(total_bays):
        errors.append(f"Construction plan max bay {max_bay} does not match total bays {total_bays}.")
    if expected_steps != len(steps):
        errors.append(f"Construction plan steps {len(steps)} do not match expected story count {expected_steps}.")
    return ValidationResult(ok=not errors, errors=errors)


def validate_geometry(node_output: dict, element_output: dict) -> ValidationResult:
    errors: list[str] = []
    node_coords: dict[tuple[float, float], int] = {}
    node_ids: set[int] = set()
    all_nodes: dict[int, tuple[float, float]] = {}

    for step in node_output.get("Construction_steps", []):
        for node in step.get("Nodes", []):
            node_id = int(node["ID"])
            coord = (float(node["x"]), float(node["y"]))
            if node_id in node_ids:
                errors.append(f"Duplicate node id detected: {node_id}")
            if coord in node_coords:
                errors.append(f"Duplicate node coordinate detected: {coord}")
            node_ids.add(node_id)
            node_coords[coord] = node_id
            all_nodes[node_id] = coord

    element_ids: set[int] = set()
    used_nodes: set[int] = set()
    seen_elements: set[tuple[int, int]] = set()
    for step in element_output.get("Construction_steps", []):
        for element in step.get("Elements", []):
            element_id = int(element["ID"])
            if element_id in element_ids:
                errors.append(f"Duplicate element id detected: {element_id}")
            element_ids.add(element_id)

            coord_i = tuple(element["Coord_i"])
            coord_j = tuple(element["Coord_j"])
            if coord_i not in node_coords or coord_j not in node_coords:
                errors.append(f"Element {element_id} references coordinates with no matching node.")
                continue
            pair = (node_coords[coord_i], node_coords[coord_j])
            if pair in seen_elements:
                errors.append(f"Duplicate element connectivity detected: {pair}")
            seen_elements.add(pair)
            used_nodes.update(pair)

    for node_id in all_nodes:
        if node_id not in used_nodes:
            errors.append(f"Node {node_id} is not referenced by any element.")
    return ValidationResult(ok=not errors, errors=errors)
