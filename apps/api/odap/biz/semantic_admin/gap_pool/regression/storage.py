"""SQLiteGapRegressionStorage —— gap_regression_sets / gap_replay_reports 两表。

规则 8：每次 connect/close、JSON TEXT、ISO 时间。
ADR-088 D3/D7：两表均**不可变**——本类只提供 insert 与读方法，
刻意不提供 update/delete（不可变性由 API 缺失保证，非约定）。
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_db_path() -> str:
    data_dir = os.environ.get(
        "DATA_DIR", os.path.join(os.getcwd(), "apps", "api", "data")
    )
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "gap_regression.db")


class SQLiteGapRegressionStorage:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _default_db_path()
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS gap_regression_sets (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    cases_json TEXT NOT NULL DEFAULT '[]',
                    source_gap_ids_json TEXT NOT NULL DEFAULT '[]',
                    model_id TEXT NOT NULL DEFAULT '',
                    case_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_grs_scope
                    ON gap_regression_sets(scope_key, created_at DESC);

                CREATE TABLE IF NOT EXISTS gap_replay_reports (
                    id TEXT PRIMARY KEY,
                    set_id TEXT NOT NULL,
                    model_id TEXT NOT NULL DEFAULT '',
                    prompt_version TEXT NOT NULL DEFAULT '',
                    verdict TEXT NOT NULL,
                    fixed_count INTEGER NOT NULL DEFAULT 0,
                    regressed_count INTEGER NOT NULL DEFAULT 0,
                    unchanged_count INTEGER NOT NULL DEFAULT 0,
                    rounds_json TEXT NOT NULL DEFAULT '[]',
                    cost_json TEXT NOT NULL DEFAULT '{}',
                    error_detail TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_grr_set
                    ON gap_replay_reports(set_id, created_at DESC);
                """
            )
            conn.commit()
        finally:
            conn.close()

    # ---- JSON 容错（同 sqlite_gap_storage 模式） ----
    @staticmethod
    def _safe_json(raw: Any, default):
        if raw is None:
            return default
        if isinstance(raw, (dict, list)):
            return raw
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("gap_regression JSON 解析失败，回退默认值: %r", raw)
            return default

    def _set_row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        d["cases_json"] = self._safe_json(d.get("cases_json"), [])
        d["source_gap_ids_json"] = self._safe_json(d.get("source_gap_ids_json"), [])
        return d

    def _report_row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        d["rounds_json"] = self._safe_json(d.get("rounds_json"), [])
        d["cost_json"] = self._safe_json(d.get("cost_json"), {})
        return d

    # ---- 写（仅 insert：不可变） ----
    def save_set(self, s: Dict[str, Any]) -> Dict[str, Any]:
        set_id = s.get("id") or str(uuid.uuid4())
        now = _utc_now_iso()
        cases = s.get("cases") or []
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO gap_regression_sets (
                    id, name, scope_key, cases_json, source_gap_ids_json,
                    model_id, case_count, created_at
                ) VALUES (?,?,?,?,?,?,?,?)""",
                (set_id, s.get("name") or "", s.get("scope_key") or "",
                 json.dumps(cases, ensure_ascii=False),
                 json.dumps(s.get("source_gap_ids") or [], ensure_ascii=False),
                 s.get("model_id") or "", len(cases), now),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_set(set_id)  # type: ignore[return-value]

    def save_report(self, r: Dict[str, Any]) -> Dict[str, Any]:
        report_id = r.get("id") or str(uuid.uuid4())
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO gap_replay_reports (
                    id, set_id, model_id, prompt_version, verdict,
                    fixed_count, regressed_count, unchanged_count,
                    rounds_json, cost_json, error_detail, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (report_id, r.get("set_id") or "",
                 r.get("model_id") or "", r.get("prompt_version") or "",
                 r.get("verdict") or "error",
                 int(r.get("fixed_count") or 0),
                 int(r.get("regressed_count") or 0),
                 int(r.get("unchanged_count") or 0),
                 json.dumps(r.get("rounds") or [], ensure_ascii=False),
                 json.dumps(r.get("cost") or {}, ensure_ascii=False),
                 r.get("error_detail"),
                 r.get("created_at") or _utc_now_iso()),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_report(report_id)  # type: ignore[return-value]

    # ---- 读 ----
    def get_set(self, set_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM gap_regression_sets WHERE id=?", (set_id,)
            ).fetchone()
            return self._set_row_to_dict(row) if row else None
        finally:
            conn.close()

    def list_sets(self, *, page: int = 1, page_size: int = 20,
                  ) -> Tuple[List[Dict[str, Any]], int]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                "SELECT COUNT(*) AS c FROM gap_regression_sets").fetchone()["c"]
            offset = max(0, (page - 1) * page_size)
            rows = conn.execute(
                "SELECT * FROM gap_regression_sets ORDER BY created_at DESC "
                "LIMIT ? OFFSET ?", (page_size, offset),
            ).fetchall()
            return [self._set_row_to_dict(r) for r in rows], total
        finally:
            conn.close()

    def latest_set_for_scope(self, scope_key: str) -> Optional[Dict[str, Any]]:
        """writeback 侧道自动回放用：某 scope 最新回归集。"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM gap_regression_sets WHERE scope_key=? "
                "ORDER BY created_at DESC LIMIT 1", (scope_key,),
            ).fetchone()
            return self._set_row_to_dict(row) if row else None
        finally:
            conn.close()

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM gap_replay_reports WHERE id=?", (report_id,)
            ).fetchone()
            return self._report_row_to_dict(row) if row else None
        finally:
            conn.close()

    def list_reports(self, *, set_id: Optional[str] = None,
                     page: int = 1, page_size: int = 20,
                     ) -> Tuple[List[Dict[str, Any]], int]:
        where, params = [], []
        if set_id:
            where.append("set_id=?")
            params.append(set_id)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                f"SELECT COUNT(*) AS c FROM gap_replay_reports{clause}", params
            ).fetchone()["c"]
            offset = max(0, (page - 1) * page_size)
            rows = conn.execute(
                f"SELECT * FROM gap_replay_reports{clause} "
                f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (*params, page_size, offset),
            ).fetchall()
            return [self._report_row_to_dict(r) for r in rows], total
        finally:
            conn.close()
