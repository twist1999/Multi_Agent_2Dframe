from __future__ import annotations

import json
from pathlib import Path

from .config import PipelineConfig, ensure_directories
from .pipeline import StructuralModelingPipeline


def main() -> None:
    ensure_directories()
    example_path = Path(r"H:\codex\multiagent\example_input.json")
    payload = json.loads(example_path.read_text(encoding="utf-8"))
    user_input = payload["user_input"]
    pipeline = StructuralModelingPipeline(PipelineConfig())
    try:
        state = pipeline.run(user_input)
        print("Pipeline completed.")
        print("Outputs written to:", PipelineConfig().output_dir)
    except NotImplementedError as exc:
        print("Scaffold created successfully.")
        print("Next step: fill in the LLM API implementations for each agent.")
        print(str(exc))
    except Exception as exc:
        print("Pipeline failed.")
        print(str(exc))
