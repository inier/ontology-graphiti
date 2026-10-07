"""SQLiteGapStorage —— concept_gaps 单表存储（规则 8：每次 connect/close，JSON TEXT，ISO 时间）。"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..models.gap import GapStatus, make_scope_key

logger = logging.getLogger(__name__)

_SOURCES_CAP = 50


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_db_path() -> str:
    data_dir = os.environ.get(
        "DATA_DIR", os.path.join(os.getcwd(), "apps", "api", "data")
    )
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "concept_gaps.db")


class SQLiteGapStorage:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _default_db_path()
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS concept_gaps (
                    id TEXT PRIMARY KEY,
                    expression TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    heat INTEGER NOT NULL DEFAULT 1,
                    source_counts_json TEXT NOT NULL DEFAULT '{}',
                    sources_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'open',
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    promoted_candidate_id TEXT,
                    resolved_term_id TEXT,
                    dismiss_reason TEXT,
                    workspace_id TEXT,
                    domain_id TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS uq_gap_expr_scope
                    ON concept_gaps(expression, scope_key);
                CREATE INDEX IF NOT EXISTS idx_gap_status ON concept_gaps(status);
                CREATE INDEX IF NOT EXISTS idx_gap_heat   ON concept_gaps(heat DESC);
                """
            )
            conn.commit()
        finally:
            conn.close()

    # ---- JSON 容错 ----
    @staticmethod
    def _safe_json(raw: Any, default):
        if raw is None:
            return default
        if isinstance(raw, (dict, list)):
            return raw
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("concept_gaps JSON 解析失败，回退默认值: %r", raw)
            return default

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        d["source_counts_json"] = self._safe_json(d.get("source_counts_json"), {})
        d["sources_json"] = self._safe_json(d.get("sources_json"), [])
        return d

    # ---- 写 ----
    def record_signal(
        self, source, expression: str, *,
        workspace_id: Optional[str] = None, domain_id: Optional[str] = None,
        ref: Optional[str] = None, detail: Optional[str] = None,
    ) -> Dict[str, Any]:
        source_val = str(getattr(source, "value", source))
        expr = (expression or "").strip()
        if not expr:
            raise ValueError("expression 不能为空")
        scope_key = make_scope_key(workspace_id, domain_id)
        now = _utc_now_iso()
        occurrence = {"source": source_val, "ref": ref, "at": now, "detail": detail}

        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM concept_gaps WHERE expression=? AND scope_key=?",
                (expr, scope_key),
            ).fetchone()
            if row is None:
                gap_id = str(uuid.uuid4())
                counts = {source_val: 1}
                conn.execute(
                    """INSERT INTO concept_gaps (
                        id, expression, scope_key, heat, source_counts_json,
                        sources_json, status, first_seen, last_seen, updated_at,
                        workspace_id, domain_id
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (gap_id, expr, scope_key, 1,
                     json.dumps(counts, ensure_ascii=False),
                     json.dumps([occurrence], ensure_ascii=False),
                     GapStatus.OPEN.value, now, now, now, workspace_id, domain_id),
                )
                conn.commit()
                return self._row_to_dict(
                    conn.execute("SELECT * FROM concept_gaps WHERE id=?", (gap_id,)).fetchone()
                )
            # 既有：heat+1、计数累加、occurrence 追加（上限 50）、REJECTED 复活为 OPEN
            gap_id = row["id"]
            counts = self._safe_json(row["source_counts_json"], {})
            counts[source_val] = counts.get(source_val, 0) + 1
            sources = self._safe_json(row["sources_json"], [])
            sources.append(occurrence)
            sources = sources[-_SOURCES_CAP:]
            new_status = row["status"]
            revived = new_status == GapStatus.REJECTED.value
            if revived:
                new_status = GapStatus.OPEN.value
            # 复活时清空陈旧 dismiss_reason：缺口重新 open，旧「忽略原因」不再适用
            # （否则详情页会显示自相矛盾的忽略原因）。dismiss_clause 为硬编码字面量、
            # 无外部输入，无注入面。终审 n4。
            dismiss_clause = ", dismiss_reason=NULL" if revived else ""
            conn.execute(
                f"""UPDATE concept_gaps
                   SET heat=heat+1, source_counts_json=?, sources_json=?,
                       status=?, last_seen=?, updated_at=?{dismiss_clause}
                   WHERE id=?""",
                (json.dumps(counts, ensure_ascii=False),
                 json.dumps(sources, ensure_ascii=False),
                 new_status, now, now, gap_id),
            )
            conn.commit()
            return self._row_to_dict(
                conn.execute("SELECT * FROM concept_gaps WHERE id=?", (gap_id,)).fetchone()
            )
        finally:
            conn.close()

    def update_status(self, gap_id: str, status: str, **fields) -> bool:
        allowed = {"promoted_candidate_id", "resolved_term_id", "dismiss_reason"}
        sets = ["status=?", "updated_at=?"]
        params: List[Any] = [status, _utc_now_iso()]
        for k, v in fields.items():
            if k in allowed:
                sets.append(f"{k}=?")
                params.append(v)
        params.append(gap_id)
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                f"UPDATE concept_gaps SET {', '.join(sets)} WHERE id=?", params
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    # ---- 读 ----
    def get_gap(self, gap_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM concept_gaps WHERE id=?", (gap_id,)).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()

    def get_by_expression(self, expression: str, scope_key: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM concept_gaps WHERE expression=? AND scope_key=?",
                ((expression or "").strip(), scope_key),
            ).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()

    def get_by_candidate_id(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM concept_gaps WHERE promoted_candidate_id=?",
                (candidate_id,),
            ).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()

    def list_gaps(
        self, *, status: Optional[str] = None, source: Optional[str] = None,
        workspace_id: Optional[str] = None, page: int = 1, page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        where, params = [], []
        if status:
            where.append("status=?")
            params.append(status)
        if source:  # source 过滤在 SQL 侧一致计算（JSON1 json_extract），total 与分页同源
            where.append("json_extract(source_counts_json, ?) > 0")
            params.append(f"$.{source}")
        if workspace_id:
            where.append("workspace_id=?")
            params.append(workspace_id)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                f"SELECT COUNT(*) AS c FROM concept_gaps{clause}", params
            ).fetchone()["c"]
            offset = max(0, (page - 1) * page_size)
            rows = conn.execute(
                f"SELECT * FROM concept_gaps{clause} ORDER BY heat DESC, last_seen DESC "
                f"LIMIT ? OFFSET ?",
                (*params, page_size, offset),
            ).fetchall()
            items = [self._row_to_dict(r) for r in rows]
            return items, total
        finally:
            conn.close()

    def count_by_status(self) -> Dict[str, int]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT status, COUNT(*) AS c FROM concept_gaps GROUP BY status"
            ).fetchall()
            out = {s.value: 0 for s in GapStatus}
            for r in rows:
                out[r["status"]] = r["c"]
            return out
        finally:
            conn.close()

    def count_by_source(self) -> Dict[str, int]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT source_counts_json FROM concept_gaps").fetchall()
            out: Dict[str, int] = {}
            for r in rows:
                for k, v in self._safe_json(r["source_counts_json"], {}).items():
                    out[k] = out.get(k, 0) + int(v)
            return out
        finally:
            conn.close()

    def top_heat(self, n: int = 10) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM concept_gaps ORDER BY heat DESC, last_seen DESC LIMIT ?", (n,)
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()
