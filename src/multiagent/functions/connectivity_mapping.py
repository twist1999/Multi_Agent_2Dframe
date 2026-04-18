from __future__ import annotations


def map_connectivity(node_output: dict, element_output: dict) -> dict:
    coord_to_node: dict[tuple[float, float], int] = {}
    boundary_conditions: list[dict] = []
    nodes: list[dict] = []
    elements: list[dict] = []

    for step in node_output.get("Construction_steps", []):
        for node in step.get("Nodes", []):
            coord = (float(node["x"]), float(node["y"]))
            coord_to_node[coord] = int(node["ID"])
            nodes.append(
                {
                    "id": int(node["ID"]),
                    "x": float(node["x"]),
                    "y": float(node["y"]),
                    "description": node.get("Description", ""),
                }
            )
        for bc in step.get("Boundary_conditions", []):
            boundary_conditions.append(
                {
                    "node_id": int(bc["Node_ID"]),
                    "constraints": bc["Constraints"],
                }
            )

    for step in element_output.get("Construction_steps", []):
        for element in step.get("Elements", []):
            coord_i = tuple(float(v) for v in element["Coord_i"])
            coord_j = tuple(float(v) for v in element["Coord_j"])
            elements.append(
                {
                    "id": int(element["ID"]),
                    "node_i": coord_to_node[coord_i],
                    "node_j": coord_to_node[coord_j],
                    "type": element.get("Type", ""),
                    "coord_i": list(coord_i),
                    "coord_j": list(coord_j),
                    "description": element.get("Description", ""),
                }
            )

    return {
        "nodes": nodes,
        "boundary_conditions": boundary_conditions,
        "elements": elements,
    }
