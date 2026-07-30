"""MetricDefinitionStorage — 指标定义 SQLite 持久化 (spec 008 Phase 2 / Iter 1 / T023).

仅计算引擎所需的最小 CRUD（save/get/get_by_name/list/delete）。
CRUD API 留给 007 semantic-admin；本层只读 + upsert 供 MetricEngine 计算。

AGENTS.md 规则 8：每次 sqlite3.connect() → 用完立刻 conn.close()（无连接池）。
JSON 字段（bindings / tags）→ JSON TEXT（ensure_ascii=False 保持中文）。
Enum → .value 字符串存储。
datetime → isoformat 字符串。

参考模式：sqlite_usl_storage.py。
Constitution I：函数体 ≤ 40 行。
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_DB_DIR: str = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
DEFAULT_DB_PATH: str = os.path.join(DEFAULT_DB_DIR, "semantic_retrieval.db")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _loads(text: Any, default: Any) -> Any:
    if text is None or text == "":
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return default


class MetricDefinitionStorage:
    """MetricDefinition SQLite 持久化（幂等 DDL + 每次 connect/close）。"""

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            os.makedirs(DEFAULT_DB_DIR, exist_ok=True)
            db_path = DEFAULT_DB_PATH
        self.db_path: str = db_path
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(self._ddl())
            conn.execute(self._index_sql())
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _ddl() -> str:
        return (
            "CREATE TABLE IF NOT EXISTS metric_definitions ("
            "metric_id TEXT PRIMARY KEY,"
            "name TEXT NOT NULL UNIQUE,"
            "name_en TEXT DEFAULT '',"
            "description TEXT DEFAULT '',"
            "domain TEXT DEFAULT '',"
            "tags TEXT DEFAULT '[]',"
            "bindings TEXT DEFAULT '[]',"
            "formula TEXT,"
            "unit TEXT DEFAULT '',"
            "precision INTEGER DEFAULT 2,"
            "trend_direction TEXT DEFAULT 'neutral',"
            "version TEXT DEFAULT '1.0.0',"
            "ontology_id TEXT,"
            "created_at TEXT NOT NULL,"
            "updated_at TEXT NOT NULL"
            ")"
        )

    @staticmethod
    def _index_sql() -> str:
        return "CREATE INDEX IF NOT EXISTS idx_metric_domain ON metric_definitions(domain)"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def save(self, definition: Any) -> None:
        """upsert（同 metric_id 覆盖）。definition 可为 MetricDefinition 或 dict。"""
        d = self._coerce_dict(definition)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(self._upsert_sql(), self._upsert_params(d))
            conn.commit()
        finally:
            conn.close()

    def get(self, metric_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM metric_definitions WHERE metric_id = ?", (metric_id,)
            ).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()

    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM metric_definitions WHERE name = ?", (name,)
            ).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()

    def list(
        self,
        domain: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Tuple[List[Dict[str, Any]], int]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            where, params = self._list_where(domain)
            total = conn.execute(
                f"SELECT COUNT(*) FROM metric_definitions {where}", tuple(params)
            ).fetchone()[0]
            offset = max(0, (page - 1) * page_size)
            rows = conn.execute(
                f"SELECT * FROM metric_definitions {where} "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                tuple(params) + (page_size, offset),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows], total
        finally:
            conn.close()

    def delete(self, metric_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                "DELETE FROM metric_definitions WHERE metric_id = ?", (metric_id,)
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_dict(definition: Any) -> Dict[str, Any]:
        if isinstance(definition, dict):
            return definition
        if hasattr(definition, "model_dump"):
            return definition.model_dump(mode="json")
        raise TypeError(f"unsupported definition type: {type(definition)}")

    @staticmethod
    def _upsert_sql() -> str:
        return (
            "INSERT INTO metric_definitions "
            "(metric_id, name, name_en, description, domain, tags, bindings, "
            "formula, unit, precision, trend_direction, version, ontology_id, "
            "created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(metric_id) DO UPDATE SET "
            "name=excluded.name, name_en=excluded.name_en, "
            "description=excluded.description, domain=excluded.domain, "
            "tags=excluded.tags, bindings=excluded.bindings, "
            "formula=excluded.formula, unit=excluded.unit, "
            "precision=excluded.precision, trend_direction=excluded.trend_direction, "
            "version=excluded.version, ontology_id=excluded.ontology_id, "
            "updated_at=excluded.updated_at"
        )

    @staticmethod
    def _upsert_params(d: Dict[str, Any]) -> tuple:
        now = _utc_now_iso()
        bindings = d.get("bindings", [])
        if bindings and isinstance(bindings[0], dict):
            bindings = [b if isinstance(b, dict) else dict(b) for b in bindings]
        return (
            d.get("metric_id") or d.get("id") or "",
            d.get("name", ""),
            d.get("name_en", ""),
            d.get("description", ""),
            d.get("domain", ""),
            _dumps(d.get("tags", [])),
            _dumps(bindings),
            d.get("formula"),
            d.get("unit", ""),
            int(d.get("precision", 2)),
            d.get("trend_direction", "neutral"),
            d.get("version", "1.0.0"),
            d.get("ontology_id"),
            d.get("created_at", now),
            now,
        )

    @staticmethod
    def _list_where(domain: Optional[str]) -> Tuple[str, List[Any]]:
        if domain:
            return "WHERE domain = ?", [domain]
        return "", []

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        d["tags"] = _loads(d.get("tags"), [])
        d["bindings"] = _loads(d.get("bindings"), [])
        return d
