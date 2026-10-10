"""成本对账存储（ADR-089 C-D5/C-D9）——不可变 cost_audit 表。

每次 ontology_semantics 调用 / entity_extract 调用落一行，供 inject vs query
两模式均摊成本对比（补 EvoOntology 论文自承的 cost accounting 空白）。

纪律：只 INSERT，不 UPDATE/DELETE（「报告即不可变证据」，对齐 ADR-088/087）。
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from statistics import median
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CostAuditStorage:
    """cost_audit 不可变表存储。"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "cost_audit.db",
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS cost_audit (
                    id TEXT PRIMARY KEY,
                    call_kind TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    expression TEXT,
                    cost_json TEXT NOT NULL DEFAULT '{}',
                    model_id TEXT,
                    prompt_version TEXT,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_cost_mode ON cost_audit(mode);
                CREATE INDEX IF NOT EXISTS idx_cost_scope ON cost_audit(scope_key);
                """
            )
            conn.commit()
        finally:
            conn.close()

    def record(
        self,
        *,
        call_kind: str,
        mode: str,
        scope_key: str,
        expression: Optional[str] = None,
        cost: Optional[Dict[str, Any]] = None,
        model_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        rec = {
            "id": str(uuid.uuid4()),
            "call_kind": call_kind,
            "mode": mode,
            "scope_key": scope_key or "-",
            "expression": expression,
            "cost_json": json.dumps(cost or {}, ensure_ascii=False),
            "model_id": model_id,
            "prompt_version": prompt_version,
            "recorded_at": _utc_now_iso(),
        }
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO cost_audit (
                    id, call_kind, mode, scope_key, expression,
                    cost_json, model_id, prompt_version, recorded_at
                ) VALUES (?,?,?,?,?,?,?,?,?)""",
                (rec["id"], rec["call_kind"], rec["mode"], rec["scope_key"],
                 rec["expression"], rec["cost_json"], rec["model_id"],
                 rec["prompt_version"], rec["recorded_at"]),
            )
            conn.commit()
        finally:
            conn.close()
        return rec

    def list_records(
        self, *, call_kind: Optional[str] = None, mode: Optional[str] = None,
        scope_key: Optional[str] = None, limit: int = 200,
    ) -> List[Dict[str, Any]]:
        where, params = [], []
        if call_kind:
            where.append("call_kind=?")
            params.append(call_kind)
        if mode:
            where.append("mode=?")
            params.append(mode)
        if scope_key:
            where.append("scope_key=?")
            params.append(scope_key)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"SELECT * FROM cost_audit {clause} ORDER BY recorded_at DESC LIMIT ?",
                (*params, int(limit)),
            ).fetchall()
        finally:
            conn.close()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["cost"] = json.loads(d.pop("cost_json") or "{}")
            except (ValueError, TypeError):
                d["cost"] = {}
            out.append(d)
        return out

    def aggregate(
        self, *, call_kind: Optional[str] = None, scope_key: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """按 mode 聚合：count / avg_wall_ms / median_wall_ms / total_round_trips / tokens。"""
        recs = self.list_records(
            call_kind=call_kind, scope_key=scope_key, limit=100000)
        by_mode: Dict[str, List[Dict[str, Any]]] = {}
        for r in recs:
            by_mode.setdefault(r["mode"], []).append(r.get("cost") or {})
        out: Dict[str, Dict[str, Any]] = {}
        for mode, costs in by_mode.items():
            walls = [float(c.get("wall_ms") or 0.0) for c in costs]
            out[mode] = {
                "count": len(costs),
                "avg_wall_ms": round(sum(walls) / len(walls), 3) if walls else 0.0,
                "median_wall_ms": round(median(walls), 3) if walls else 0.0,
                "total_round_trips": sum(int(c.get("round_trips") or 0) for c in costs),
                "total_tokens_in": sum(int(c.get("llm_tokens_in") or 0) for c in costs),
                "total_tokens_out": sum(int(c.get("llm_tokens_out") or 0) for c in costs),
            }
        return out


__all__ = ["CostAuditStorage"]
