"""qa_traces / qa_provenance 持久化（F8，AC-36~AC-38）。

写入语义：
- 一次问答 = 1 行 `qa_traces` + 6 行 `qa_provenance`（`UNIQUE(trace_id, step)`）。
- steps 与 trace 在同一事务写入：要么全有要么全无，避免「有 trace 无证据」的残缺记录。
- `trace_id` 是主键 —— 重复写入必然失败（R1 唯一性的存储级保证），不静默覆盖。
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List, Optional

from odap.biz.core.ontology.orchestration.contracts import STEP_ORDER, Evidence
from odap.biz.core.ontology.orchestration.provenance import (
    Provenance,
    ProvenanceStep,
    normalize_step,
)
from odap.infra.storage.schema_v2 import connect, ensure_v2_schema


def _loads(raw: Any, default: Any) -> Any:
    if raw in (None, ""):
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


class QaTraceRepository:
    """问答流转与溯源存取。"""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path
        ensure_v2_schema(db_path)

    def _conn(self) -> sqlite3.Connection:
        return connect(self.db_path)

    def save(self, trace: Dict[str, Any], provenance: Provenance) -> None:
        """原子写入 trace + steps。`trace` 需含 trace_id/query/created_at 等字段。"""
        trace_id = provenance.trace_id
        if trace.get("trace_id") and trace["trace_id"] != trace_id:
            raise ValueError(
                f"trace.trace_id({trace['trace_id']}) 与 provenance.trace_id({trace_id}) 不一致"
            )
        conn = self._conn()
        try:
            with conn:  # 事务
                conn.execute(
                    """
                    INSERT INTO qa_traces (
                        trace_id, query, workspace_id, user_id, intent_json, tbox_version,
                        contract_ok, degraded, citations_json, created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        trace_id,
                        trace.get("query", ""),
                        trace.get("workspace_id", ""),
                        trace.get("user_id", ""),
                        json.dumps(trace.get("intent") or {}, ensure_ascii=False),
                        provenance.tbox_version,
                        1 if provenance.contract_ok else 0,
                        1 if trace.get("degraded") else 0,
                        json.dumps([e.model_dump(mode="json") for e in provenance.citations],
                                   ensure_ascii=False),
                        trace.get("created_at", ""),
                    ),
                )
                conn.executemany(
                    """
                    INSERT INTO qa_provenance (
                        id, trace_id, step, component, component_version, evidence, ts
                    ) VALUES (?,?,?,?,?,?,?)
                    """,
                    [
                        (
                            f"{trace_id}#{normalize_step(step.step)}",
                            trace_id,
                            normalize_step(step.step),
                            step.component,
                            step.version,
                            json.dumps([e.model_dump(mode="json") for e in step.evidence],
                                       ensure_ascii=False),
                            step.ts,
                        )
                        for step in provenance.steps
                    ],
                )
        finally:
            conn.close()

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM qa_traces WHERE trace_id = ?", (trace_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return {
            "trace_id": row["trace_id"],
            "query": row["query"],
            "workspace_id": row["workspace_id"],
            "user_id": row["user_id"],
            "intent": _loads(row["intent_json"], {}),
            "tbox_version": row["tbox_version"],
            "contract_ok": bool(row["contract_ok"]),
            "degraded": bool(row["degraded"]),
            "citations": _loads(row["citations_json"], []),
            "created_at": row["created_at"],
        }

    def get_provenance(self, trace_id: str) -> Optional[Provenance]:
        trace = self.get_trace(trace_id)
        if trace is None:
            return None
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM qa_provenance WHERE trace_id = ?", (trace_id,)
            ).fetchall()
        finally:
            conn.close()

        by_step: Dict[str, ProvenanceStep] = {}
        for row in rows:
            by_step[normalize_step(row["step"])] = ProvenanceStep(
                step=normalize_step(row["step"]),
                component=row["component"],
                version=row["component_version"],
                evidence=[Evidence.model_validate(e) for e in _loads(row["evidence"], [])],
                ts=row["ts"],
            )
        ordered: List[ProvenanceStep] = [
            by_step[step] for step in STEP_ORDER if step in by_step
        ]
        return Provenance(
            trace_id=trace_id,
            steps=ordered,
            citations=[Evidence.model_validate(e) for e in trace["citations"]],
            tbox_version=trace["tbox_version"],
            contract_ok=trace["contract_ok"],
        )

    def exists(self, trace_id: str) -> bool:
        return self.get_trace(trace_id) is not None


__all__ = ["QaTraceRepository"]
