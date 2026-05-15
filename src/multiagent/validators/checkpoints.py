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
