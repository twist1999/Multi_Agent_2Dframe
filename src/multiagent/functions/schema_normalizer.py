from __future__ import annotations

import re
from typing import Any


def first_value(data: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in data:
            return data[name]
    return None


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).replace("N", "").replace("E", ""))
    except (TypeError, ValueError):
        match = re.search(r"-?\d+", str(value))
        return int(match.group(0)) if match else default


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def construction_steps(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in (
        "Construction_steps",
        "construction_steps",
        "node_generation_steps",
        "element_generation_steps",
        "construction_sequence",
        "steps",
    ):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def normalize_node_record(node: dict[str, Any]) -> dict[str, Any] | None:
    node_id = to_int(first_value(node, ("ID", "id", "node_id", "Node_ID")))
    x = first_value(node, ("x", "x_m", "X", "X_m"))
    y = first_value(node, ("y", "y_m", "Y", "Y_m", "z", "z_m", "Z", "Z_m"))
    if node_id <= 0 or x is None or y is None:
        return None
    return {
        "id": node_id,
        "x": to_float(x),
        "y": to_float(y),
        "description": str(first_value(node, ("Description", "description", "label")) or ""),
    }


def _nodes_from_mapping(nodes: dict[str, Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for node_id, coord in nodes.items():
        item = {"id": node_id}
        if isinstance(coord, (list, tuple)) and len(coord) >= 2:
            item.update({"x": coord[0], "y": coord[1]})
        elif isinstance(coord, dict):
            item.update(coord)
        node = normalize_node_record(item)
        if node:
            normalized.append(node)
    return normalized


def normalize_boundary_condition_record(bc: dict[str, Any]) -> dict[str, Any] | None:
    node_id = to_int(first_value(bc, ("Node_ID", "node_id", "id")))
    if node_id <= 0:
        return None
    constraints = first_value(bc, ("Constraints", "constraints", "constrained_dofs", "direction", "type"))
    return {
        "node_id": node_id,
        "constraints": constraints if constraints is not None else "fixed",
    }


def normalize_nodes(node_output: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes_by_id: dict[int, dict[str, Any]] = {}
    boundary_conditions: list[dict[str, Any]] = []

    def add_nodes(items: Any) -> None:
        if isinstance(items, dict):
            for normalized in _nodes_from_mapping(items):
                nodes_by_id[normalized["id"]] = normalized
            return
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            normalized = normalize_node_record(item)
            if normalized:
                nodes_by_id[normalized["id"]] = normalized

    def add_boundary_conditions(items: Any) -> None:
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            normalized = normalize_boundary_condition_record(item)
            if normalized:
                boundary_conditions.append(normalized)

    def add_created_items(items: Any) -> None:
        if not isinstance(items, list):
            return
        node_items: list[dict[str, Any]] = []
        support_items: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            item_type = str(first_value(item, ("type", "Type")) or "").lower()
            if item_type == "node":
                node_items.append(item)
            elif item_type == "support":
                support_items.append(
                    {
                        "node_id": first_value(item, ("node", "node_id", "id")),
                        "constraints": first_value(item, ("condition", "constraints", "type")),
                    }
                )
        add_nodes(node_items)
        add_boundary_conditions(support_items)

    add_nodes(first_value(node_output, ("nodes", "Nodes")))
    add_boundary_conditions(first_value(node_output, ("boundary_conditions", "Boundary_conditions")))
    for step in construction_steps(node_output):
        add_nodes(
            first_value(
                step,
                (
                    "Nodes",
                    "nodes",
                    "nodes_added",
                    "new_nodes",
                    "added_nodes",
                    "created_nodes",
                ),
            )
        )
        add_boundary_conditions(
            first_value(
                step,
                (
                    "Boundary_conditions",
                    "boundary_conditions",
                    "boundary_conditions_added",
                    "new_boundary_conditions",
                    "added_boundary_conditions",
                    "applied_boundary_conditions",
                ),
            )
        )
        add_created_items(first_value(step, ("created", "created_items")))

    return list(nodes_by_id.values()), boundary_conditions


def _coord_tuple(value: Any) -> tuple[float, float] | None:
    if isinstance(value, dict):
        x = first_value(value, ("x", "x_m", "X", "X_m"))
        y = first_value(value, ("y", "y_m", "Y", "Y_m", "z", "z_m", "Z", "Z_m"))
        if x is not None and y is not None:
            return (to_float(x), to_float(y))
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return (to_float(value[0]), to_float(value[1]))
    return None


def normalize_element_record(
    element: dict[str, Any],
    coord_to_node: dict[tuple[float, float], int] | None = None,
) -> dict[str, Any] | None:
    element_id = to_int(first_value(element, ("ID", "id", "element_id", "Element_ID")))
    node_i = to_int(
        first_value(
            element,
            ("node_i", "Node_i", "start_node", "start_node_id", "i_node", "node1"),
        )
    )
    node_j = to_int(
        first_value(
            element,
            ("node_j", "Node_j", "end_node", "end_node_id", "j_node", "node2"),
        )
    )

    pair = first_value(element, ("nodes", "Nodes", "node_ids"))
    if (node_i <= 0 or node_j <= 0) and isinstance(pair, list) and len(pair) >= 2:
        node_i = to_int(pair[0])
        node_j = to_int(pair[1])

    coord_i = _coord_tuple(first_value(element, ("Coord_i", "coord_i", "start_coord", "coord_start")))
    coord_j = _coord_tuple(first_value(element, ("Coord_j", "coord_j", "end_coord", "coord_end")))
    if coord_to_node:
        if node_i <= 0 and coord_i in coord_to_node:
            node_i = coord_to_node[coord_i]
        if node_j <= 0 and coord_j in coord_to_node:
            node_j = coord_to_node[coord_j]

    if element_id <= 0 or node_i <= 0 or node_j <= 0:
        return None
    return {
        "id": element_id,
        "node_i": node_i,
        "node_j": node_j,
        "type": str(first_value(element, ("Type", "type", "element_type")) or ""),
        "coord_i": list(coord_i) if coord_i else [],
        "coord_j": list(coord_j) if coord_j else [],
        "description": str(first_value(element, ("Description", "description", "label")) or ""),
    }


def normalize_elements(
    element_output: dict[str, Any],
    coord_to_node: dict[tuple[float, float], int] | None = None,
) -> list[dict[str, Any]]:
    elements_by_id: dict[int, dict[str, Any]] = {}

    def add_elements(items: Any) -> None:
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            normalized = normalize_element_record(item, coord_to_node)
            if normalized:
                while normalized["id"] in elements_by_id:
                    normalized = {**normalized, "id": max(elements_by_id) + 1}
                elements_by_id[normalized["id"]] = normalized

    add_elements(first_value(element_output, ("elements", "Elements", "element_definitions", "members")))
    for step in construction_steps(element_output):
        single = first_value(step, ("Element", "element"))
        if isinstance(single, dict):
            add_elements([single])
        created = first_value(step, ("created", "created_items"))
        if isinstance(created, list):
            add_elements(
                [
                    item
                    for item in created
                    if isinstance(item, dict)
                    and str(first_value(item, ("type", "Type")) or "").lower()
                    in {"beam", "element", "column", "girder"}
                ]
            )
        add_elements(first_value(step, ("Elements", "elements", "elements_added", "new_elements", "members")))

    return list(elements_by_id.values())
