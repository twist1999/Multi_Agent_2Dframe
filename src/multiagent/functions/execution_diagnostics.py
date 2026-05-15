from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def build_execution_report(
    python_path: str,
    returncode: int | None,
    stdout_path: Path,
    stderr_path: Path,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> dict:
    return {
        "python_path": python_path,
        "returncode": returncode,
        "stdout": stdout_path.read_text(encoding="utf-8") if stdout_path.exists() else "",
        "stderr": stderr_path.read_text(encoding="utf-8") if stderr_path.exists() else "",
        "started_at": started_at or datetime.now(timezone.utc).isoformat(),
        "finished_at": finished_at or datetime.now(timezone.utc).isoformat(),
    }
