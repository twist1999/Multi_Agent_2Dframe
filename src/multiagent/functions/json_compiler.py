from __future__ import annotations


def compile_json(problem_analysis: dict, mapped_geometry: dict, load_output: dict) -> dict:
    return {
        "problem_analysis": problem_analysis,
        "geometry": mapped_geometry,
        "loads": load_output,
    }
