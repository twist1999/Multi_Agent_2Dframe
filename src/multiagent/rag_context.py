from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import RagConfig


@dataclass(frozen=True)
class RagQuery:
    query: str
    source: str | None = None


class RAGContextProvider:
    def __init__(self, config: RagConfig) -> None:
        self.config = config
        self._retrieve_module: Any | None = None
        self._load_error: str | None = None

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    def geometry_context(self, compiled_json: dict) -> str:
        queries = [
            RagQuery("OpenSeesPy basic model ndm ndf node fix geomTransf Linear elasticBeamColumn 2D", "openseespy"),
            RagQuery("OpenSeesPy elasticBeamColumn 2D syntax A E Iz transfTag", "openseespy"),
            RagQuery("OpenSeesPy node coordinates fixity support boundary conditions", "openseespy"),
        ]
        return self._build_context("Geometry Code Translator", queries, compiled_json)

    def complete_code_context(self, compiled_json: dict, geometry_code: str) -> str:
        queries = [
            RagQuery("OpenSeesPy timeSeries Plain pattern load eleLoad beamUniform syntax", "openseespy"),
            RagQuery("OpenSeesPy static analysis system numberer constraints algorithm integrator analyze", "openseespy"),
            RagQuery("OpenSeesPy nodeDisp nodeReaction localForces output results", "openseespy"),
            RagQuery("OpsVis section_force_diagram_2d plot_model usage axial shear moment", "opsvis"),
        ]
        payload = {"compiled_json": compiled_json, "geometry_code_preview": geometry_code[:1500]}
        return self._build_context("Complete Code Generator", queries, payload)

    def _build_context(self, title: str, queries: list[RagQuery], payload: dict) -> str:
        if not self.enabled:
            return ""
        rows: list[dict] = []
        for query in queries:
            rows.extend(self._query(query.query, query.source))
        if not rows:
            if self._load_error:
                return (
                    "Retrieved Documentation Context:\n"
                    f"RAG_OS was requested but unavailable: {self._load_error}\n"
                    "Continue using conservative OpenSeesPy syntax and avoid undocumented calls.\n"
                )
            return ""

        context_items = self._dedupe(rows)
        rendered = [
            "Retrieved Documentation Context:",
            f"Purpose: Ground the {title} output in local OpenSeesPy/OpsVis documentation.",
            "Instruction: Treat these references as API constraints. If they conflict with prior assumptions, follow these references.",
            "",
            "Task payload summary:",
            json.dumps(self._summarize_payload(payload), ensure_ascii=False, indent=2),
            "",
            "References:",
        ]
        for index, item in enumerate(context_items, start=1):
            rendered.extend(self._render_item(index, item))
        text = "\n".join(rendered).strip()
        if len(text) <= self.config.max_chars:
            return text + "\n"
        return text[: self.config.max_chars].rsplit("\n", 1)[0] + "\n[truncated]\n"

    def _query(self, query: str, source: str | None) -> list[dict]:
        retrieve = self._load_retriever()
        if retrieve is None:
            return []
        try:
            rows = retrieve.hybrid_query(query, top_k=self.config.top_k, source=source)
            return retrieve.format_results_for_display(rows)
        except Exception as exc:
            self._load_error = f"query failed for {source or 'all'}: {exc}"
            return []

    def _load_retriever(self) -> Any | None:
        if self._retrieve_module is not None:
            return self._retrieve_module
        src_root = self.config.project_root / "src"
        if not src_root.exists():
            self._load_error = f"RAG_OS src directory does not exist at {src_root}"
            return None
        if str(src_root) not in sys.path:
            sys.path.insert(0, str(src_root))
        try:
            from rag_os import retrieve
        except Exception as exc:
            self._load_error = str(exc)
            return None
        self._retrieve_module = retrieve
        return retrieve

    def _dedupe(self, rows: list[dict]) -> list[dict]:
        seen: set[tuple[str, str, str]] = set()
        deduped: list[dict] = []
        for row in rows:
            key = (
                str(row.get("source", "")),
                str(row.get("title", "")),
                str(row.get("url", "")),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        return deduped

    def _render_item(self, index: int, item: dict) -> list[str]:
        lines = [
            f"{index}. source={item.get('source', 'unknown')} title={item.get('title', 'Untitled')}",
            f"   url={item.get('url', '')}",
        ]
        signatures = item.get("signatures") or []
        if signatures:
            lines.append("   signatures:")
            lines.extend(f"   - {signature}" for signature in signatures[:4])
        parameters = item.get("parameters") or []
        if parameters:
            lines.append("   parameters:")
            for param in parameters[:8]:
                lines.append(
                    "   - "
                    f"{param.get('name', '')}: {param.get('type', '')}; {param.get('meaning', '')[:220]}"
                )
        summary = item.get("summary")
        if summary:
            lines.append(f"   summary={summary[:500]}")
        return lines

    def _summarize_payload(self, payload: dict) -> dict:
        compiled_json = payload.get("compiled_json", payload)
        if not isinstance(compiled_json, dict):
            return {}
        summary: dict[str, Any] = {}
        problem = compiled_json.get("problem_analysis") or compiled_json.get("ProblemAnalysis") or {}
        geometry = compiled_json.get("geometry") or compiled_json.get("mapped_geometry") or {}
        loads = compiled_json.get("loads") or compiled_json.get("load_output") or {}
        if isinstance(problem, dict):
            summary["problem_keys"] = sorted(problem.keys())
        if isinstance(geometry, dict):
            summary["node_count"] = len(geometry.get("nodes", [])) if isinstance(geometry.get("nodes"), list) else None
            summary["element_count"] = len(geometry.get("elements", [])) if isinstance(geometry.get("elements"), list) else None
        if isinstance(loads, dict):
            summary["load_keys"] = sorted(loads.keys())
        if "geometry_code_preview" in payload:
            summary["geometry_code_preview"] = payload["geometry_code_preview"]
        return summary
