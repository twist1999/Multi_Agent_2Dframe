from __future__ import annotations

from .schema_normalizer import normalize_elements, normalize_nodes


def map_connectivity(node_output: dict, element_output: dict) -> dict:
    nodes, boundary_conditions = normalize_nodes(node_output)
    element_nodes, _ = normalize_nodes(element_output)
    known_node_ids = {int(node["id"]) for node in nodes}
    for node in element_nodes:
        if int(node["id"]) not in known_node_ids:
            nodes.append(node)
            known_node_ids.add(int(node["id"]))
    coord_to_node = {(float(node["x"]), float(node["y"])): int(node["id"]) for node in nodes}
    elements = normalize_elements(element_output, coord_to_node)

    return {
        "nodes": nodes,
        "boundary_conditions": boundary_conditions,
        "elements": elements,
    }
