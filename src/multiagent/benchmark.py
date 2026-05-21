from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone


MATERIAL_TEXT = (
    "Material Properties: Considering elastic material properties with a Young's modulus of 2.0e11 Pa. "
    "The vertical columns have a cross-sectional area of 2.0e-3 m2 and a moment of inertia of 1.6e-5 m4. "
    "The horizontal girders have a cross-sectional area of 6.0e-3 m2 and a moment of inertia of 5.4e-5 m4."
)


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    batch_id: str
    prompt: str


def generate_benchmark_cases(count: int = 30, seed: int = 20260506, start_from: int = 1) -> list[BenchmarkCase]:
    rng = random.Random(seed)
    batch_id = datetime.now(timezone.utc).strftime("batch-%Y%m%d-%H%M%S")

    bay_length_pool = [4.5, 5.0, 6.0, 7.5, 8.0]
    story_height_pool = [3.6, 4.0, 4.5, 5.0, 5.5, 6.0, 7.0]
    uniform_load_pool = [5, 8, 10, 12, 15, 18, 20, 25]
    node_force_pool = [20, 30, 40, 50, 60, 75, 90, 100]

    # Advance RNG past skipped cases
    for _ in range(1, start_from):
        _consume_rng_case(rng, bay_length_pool, story_height_pool, uniform_load_pool, node_force_pool)

    cases: list[BenchmarkCase] = []
    for index in range(start_from, start_from + count):
        bay_count = rng.randint(3, 7)
        bay_lengths = [rng.choice(bay_length_pool) for _ in range(bay_count)]
        story_counts = [rng.randint(2, 6) for _ in range(bay_count)]
        max_stories = max(story_counts)
        shared_story_heights = [rng.choice(story_height_pool) for _ in range(max_stories)]
        story_heights = [shared_story_heights[:sc] for sc in story_counts]
        uniform_load = rng.choice(uniform_load_pool)
        node_force = rng.choice(node_force_pool)
        force_side = rng.choice(["leftmost side", "rightmost side"])
        direction = "rightward" if force_side == "leftmost side" else "leftward"
        prompt = build_prompt(
            bay_lengths=bay_lengths,
            story_counts=story_counts,
            story_heights=story_heights,
            uniform_load=uniform_load,
            node_force=node_force,
            force_side=force_side,
            direction=direction,
        )
        cases.append(BenchmarkCase(case_id=f"{batch_id}-case-{index:03d}", batch_id=batch_id, prompt=prompt))
    return cases


def _consume_rng_case(rng, bay_length_pool, story_height_pool, uniform_load_pool, node_force_pool) -> None:
    """Advance the RNG through one case-worth of random calls without storing the result."""
    bay_count = rng.randint(3, 7)
    for _ in range(bay_count):
        rng.choice(bay_length_pool)
    story_counts = [rng.randint(2, 6) for _ in range(bay_count)]
    max_stories = max(story_counts)
    for _ in range(max_stories):
        rng.choice(story_height_pool)
    rng.choice(uniform_load_pool)
    rng.choice(node_force_pool)
    rng.choice(["leftmost side", "rightmost side"])


def build_prompt(
    *,
    bay_lengths: list[float],
    story_counts: list[int],
    story_heights: list[list[float]],
    uniform_load: int,
    node_force: int,
    force_side: str,
    direction: str,
) -> str:
    bay_count = len(bay_lengths)
    geometry_parts = [f"Geometry: The frame has {bay_count} bays."]
    for index, (length, stories, heights) in enumerate(zip(bay_lengths, story_counts, story_heights), start=1):
        ordinal = _ordinal(index)
        geometry_parts.append(
            f"The length of the {ordinal} bay is {_fmt(length)} meters. "
            f"The {ordinal} bay has {stories} stories. "
            f"The height of the {_list_ordinals(stories)} story are {_list_values(heights)}."
        )
    return " ".join(
        [
            " ".join(geometry_parts),
            "Boundary Conditions: All supports are fixed at the base.",
            (
                f"Load Patterns: A uniformly distributed load of {uniform_load} kN/m is applied downward "
                "along each horizontal girder. "
                f"A horizontal concentrated load of {node_force} kN is applied to the topstory nodes at the "
                f"{force_side} of the first bay, acting in the {direction} direction."
            ),
            MATERIAL_TEXT,
        ]
    )


def _ordinal(value: int) -> str:
    names = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth"}
    return names.get(value, f"{value}th")


def _list_ordinals(count: int) -> str:
    ordinals = [_ordinal(index) for index in range(1, count + 1)]
    if count == 1:
        return ordinals[0]
    return ", ".join(ordinals[:-1]) + f", and {ordinals[-1]}"


def _list_values(values: list[float]) -> str:
    formatted = [f"{_fmt(value)} m" for value in values]
    if len(formatted) == 1:
        return formatted[0]
    return ", ".join(formatted[:-1]) + f", and {formatted[-1]}"


def _fmt(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)
