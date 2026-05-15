from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import OUTPUT_ROOT


RL_DB_PATH = OUTPUT_ROOT / "rl_history.sqlite3"


class RLLogger:
    """Tiny SQLite event store for reward, policy, and feedback signals."""

    def __init__(self, db_path: Path = RL_DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    user_prompt TEXT,
                    status TEXT,
                    total_reward REAL,
                    success INTEGER,
                    error_type TEXT,
                    policy_action TEXT,
                    metadata_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reward_components (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    value REAL NOT NULL,
                    reason TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS policy_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    target_agent TEXT,
                    reason TEXT,
                    params_json TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    notes TEXT,
                    selected_object_json TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS prompt_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    source TEXT,
                    note TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS benchmark_cases (
                    case_id TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    error TEXT,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    reward REAL,
                    policy_action TEXT,
                    human_verdict TEXT,
                    human_notes TEXT
                )
                """
            )
            self._ensure_column(conn, "benchmark_cases", "retry_from_case_id", "TEXT")
            self._ensure_column(conn, "benchmark_cases", "artifact_dir", "TEXT")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS benchmark_token_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    model TEXT,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")

    def insert_prompt(
        self,
        *,
        run_id: str,
        prompt: str,
        source: str = "web",
        note: str = "",
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO prompt_history (run_id, created_at, prompt, source, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    datetime.now(timezone.utc).isoformat(),
                    prompt,
                    source,
                    note,
                ),
            )

    def upsert_run(
        self,
        *,
        run_id: str,
        prompt: str,
        status: str,
        reward_report: dict[str, Any],
        policy_action: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        components = reward_report.get("components", [])
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, created_at, updated_at, user_prompt, status, total_reward,
                    success, error_type, policy_action, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    updated_at=excluded.updated_at,
                    user_prompt=excluded.user_prompt,
                    status=excluded.status,
                    total_reward=excluded.total_reward,
                    success=excluded.success,
                    error_type=excluded.error_type,
                    policy_action=excluded.policy_action,
                    metadata_json=excluded.metadata_json
                """,
                (
                    run_id,
                    now,
                    now,
                    prompt,
                    status,
                    float(reward_report.get("total_reward", 0.0)),
                    1 if reward_report.get("success") else 0,
                    reward_report.get("error_type", "none"),
                    policy_action.get("action_type", "none"),
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
            conn.execute("DELETE FROM reward_components WHERE run_id = ?", (run_id,))
            conn.executemany(
                """
                INSERT INTO reward_components (run_id, name, value, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        str(component.get("name", "unknown")),
                        float(component.get("value", 0.0)),
                        str(component.get("reason", "")),
                        now,
                    )
                    for component in components
                ],
            )
            conn.execute(
                """
                INSERT INTO policy_actions (run_id, action_type, target_agent, reason, params_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    policy_action.get("action_type", "none"),
                    policy_action.get("target_agent", "none"),
                    policy_action.get("reason", ""),
                    json.dumps(policy_action.get("params", {}), ensure_ascii=False),
                    now,
                ),
            )

    def insert_feedback(
        self,
        *,
        run_id: str,
        verdict: str,
        notes: str,
        selected_object: dict[str, Any] | None = None,
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO feedback (run_id, verdict, notes, selected_object_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    verdict,
                    notes,
                    json.dumps(selected_object or {}, ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def latest_runs(self, limit: int = 5) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT run_id, updated_at, status, total_reward, success, error_type, policy_action
                FROM runs
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def prompt_history(self, limit: int = 25) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                    ph.id,
                    ph.run_id,
                    ph.created_at,
                    ph.prompt,
                    ph.source,
                    ph.note,
                    runs.status,
                    runs.total_reward,
                    runs.error_type,
                    runs.policy_action
                FROM prompt_history ph
                LEFT JOIN runs ON runs.run_id = ph.run_id
                ORDER BY ph.created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_benchmark_case(
        self,
        *,
        case_id: str,
        batch_id: str,
        prompt: str,
        status: str,
        started_at: str | None = None,
        finished_at: str | None = None,
        error: str | None = None,
        token_usage: dict[str, int] | None = None,
        reward: float | None = None,
        policy_action: str | None = None,
        retry_from_case_id: str | None = None,
        artifact_dir: str | None = None,
    ) -> None:
        usage = token_usage or {}
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO benchmark_cases (
                    case_id, batch_id, prompt, created_at, started_at, finished_at, status, error,
                    prompt_tokens, completion_tokens, total_tokens, reward, policy_action, retry_from_case_id,
                    artifact_dir
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(case_id) DO UPDATE SET
                    batch_id=excluded.batch_id,
                    prompt=excluded.prompt,
                    started_at=COALESCE(excluded.started_at, benchmark_cases.started_at),
                    finished_at=excluded.finished_at,
                    status=excluded.status,
                    error=excluded.error,
                    prompt_tokens=excluded.prompt_tokens,
                    completion_tokens=excluded.completion_tokens,
                    total_tokens=excluded.total_tokens,
                    reward=excluded.reward,
                    policy_action=excluded.policy_action,
                    retry_from_case_id=COALESCE(excluded.retry_from_case_id, benchmark_cases.retry_from_case_id),
                    artifact_dir=COALESCE(excluded.artifact_dir, benchmark_cases.artifact_dir)
                """,
                (
                    case_id,
                    batch_id,
                    prompt,
                    datetime.now(timezone.utc).isoformat(),
                    started_at,
                    finished_at,
                    status,
                    error,
                    int(usage.get("prompt_tokens", 0)),
                    int(usage.get("completion_tokens", 0)),
                    int(usage.get("total_tokens", 0)),
                    reward,
                    policy_action,
                    retry_from_case_id,
                    artifact_dir,
                ),
            )

    def review_benchmark_case(self, *, case_id: str, verdict: str, notes: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE benchmark_cases
                SET human_verdict = ?, human_notes = ?
                WHERE case_id = ?
                """,
                (verdict, notes, case_id),
            )

    def replace_benchmark_token_usage(self, *, case_id: str, records: list[dict[str, Any]]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM benchmark_token_usage WHERE case_id = ?", (case_id,))
            conn.executemany(
                """
                INSERT INTO benchmark_token_usage (
                    case_id, agent_name, model, prompt_tokens, completion_tokens, total_tokens, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        case_id,
                        str(record.get("agent_name", "unknown")),
                        str(record.get("model", "")),
                        int(record.get("prompt_tokens") or 0),
                        int(record.get("completion_tokens") or 0),
                        int(record.get("total_tokens") or 0),
                        datetime.now(timezone.utc).isoformat(),
                    )
                    for record in records
                ],
            )

    def benchmark_token_usage(self, case_id: str) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT agent_name, model, prompt_tokens, completion_tokens, total_tokens, created_at
                FROM benchmark_token_usage
                WHERE case_id = ?
                ORDER BY id
                """,
                (case_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def benchmark_cases(self, limit: int = 50) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT *
                FROM benchmark_cases
                ORDER BY created_at DESC, case_id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def latest_batch_id(self) -> str | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT batch_id
                FROM benchmark_cases
                ORDER BY created_at DESC
                LIMIT 1
                """
            ).fetchone()
        return str(row[0]) if row else None

    def latest_original_batch_id(self) -> str | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT batch_id
                FROM benchmark_cases
                WHERE batch_id LIKE 'batch-%'
                GROUP BY batch_id
                ORDER BY MIN(created_at) DESC
                LIMIT 1
                """
            ).fetchone()
        return str(row[0]) if row else None

    def failed_benchmark_cases(self, batch_id: str | None = None) -> list[dict[str, Any]]:
        batch_id = batch_id or self.latest_batch_id()
        if not batch_id:
            return []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT *
                FROM benchmark_cases
                WHERE batch_id = ? AND status = 'failed'
                ORDER BY case_id
                """,
                (batch_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def final_successful_original_cases(self, batch_id: str | None = None) -> list[dict[str, Any]]:
        batch_id = batch_id or self.latest_original_batch_id()
        if not batch_id:
            return []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT *
                FROM benchmark_cases
                WHERE batch_id = ?
                ORDER BY case_id
                """,
                (batch_id,),
            ).fetchall()
            all_rows = conn.execute(
                """
                SELECT case_id, retry_from_case_id, status
                FROM benchmark_cases
                """
            ).fetchall()
        children: dict[str, list[sqlite3.Row]] = {}
        for row in all_rows:
            parent = row["retry_from_case_id"]
            if parent:
                children.setdefault(parent, []).append(row)

        def has_success(case_id: str) -> bool:
            stack = list(children.get(case_id, []))
            while stack:
                item = stack.pop(0)
                if item["status"] == "succeeded":
                    return True
                stack.extend(children.get(item["case_id"], []))
            return False

        selected: list[dict[str, Any]] = []
        for row in rows:
            if row["status"] == "succeeded" or has_success(row["case_id"]):
                selected.append(dict(row))
        return selected
