"""SHACL 治理持久化存储（ADR-085 S4a-1）。

两张派生表（仿 candidate_store 约定，AGENTS.md 规则 8：每次 connect/close，无连接池）：

  · sa_shacl_shape    — 版本键控形状派生缓存。ADR-077 裁决 1「派生不持久化」禁止的是
                        **无版本键的陈旧副本**，并明确允许「带 Schema 版本号失效键」的缓存；
                        本表即该许可的操作化。单一事实源仍是「ontology 类型定义 +
                        usl_cardinalities + usl_disjoint_pairs + L6 公理」，本表只是带
                        (ontology_version_id, constraint_revision, target_type) 复合失效键的副本，
                        版本/约束变更即重生成（幂等 upsert：DELETE-by-key 后 INSERT）。

  · sa_derived_axiom  — L6 AxiomDeriver.derive() 公理持久化（ADR-085 D2：停止只写计数、
                        丢弃公理本身）。作为形状生成与 G2.2/G2.3 真值的共同来源。
                        按 pipeline_run_id 整体替换（重跑幂等）。

JSON 列：source_type_defs / source_axioms / proof（Dict/List → JSON TEXT）。
datetime → ISO 字符串。min_card/max_card 为可空 INTEGER（非基数公理为 NULL）。
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now().isoformat()


def _json_dumps(value: Any) -> str:
    """Dict/List → JSON TEXT；已是字符串则原样存；None → 'null'。"""
    if value is None:
        return "null"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _json_loads(raw: Any, default: Any) -> Any:
    """JSON TEXT → Dict/List；解析失败回退默认值并告警（规则 14.3：不静默）。"""
    if raw is None or raw == "":
        return default
    if isinstance(raw, (list, dict)):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("sa_shacl JSON 列解析失败，回退默认值: %r", raw)
        return default


class SQLiteShaclStorage:
    """sa_shacl_shape + sa_derived_axiom 双表存储。"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            self.db_path = os.path.join(
                os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
                "shacl_store.db",
            )
        else:
            self.db_path = db_path
        parent_dir = os.path.dirname(self.db_path)
        if parent_dir and self.db_path != ":memory:":
            os.makedirs(parent_dir, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------
    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sa_shacl_shape (
                    shape_id TEXT PRIMARY KEY,
                    workspace_id TEXT,
                    ontology_version_id TEXT NOT NULL,
                    constraint_revision TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    shape_ttl TEXT NOT NULL,
                    source_type_defs TEXT,
                    source_axioms TEXT,
                    checksum TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS uq_shacl_shape_key
                    ON sa_shacl_shape(ontology_version_id, constraint_revision, target_type);
                CREATE INDEX IF NOT EXISTS idx_shacl_shape_ov
                    ON sa_shacl_shape(ontology_version_id);
                CREATE INDEX IF NOT EXISTS idx_shacl_shape_ws
                    ON sa_shacl_shape(workspace_id);

                CREATE TABLE IF NOT EXISTS sa_derived_axiom (
                    axiom_id TEXT PRIMARY KEY,
                    workspace_id TEXT,
                    domain_id TEXT,
                    ontology_version_id TEXT,
                    pipeline_run_id TEXT,
                    axiom_type TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    object TEXT,
                    min_card INTEGER,
                    max_card INTEGER,
                    confidence REAL,
                    source TEXT,
                    proof TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_axiom_run
                    ON sa_derived_axiom(pipeline_run_id);
                CREATE INDEX IF NOT EXISTS idx_axiom_domain
                    ON sa_derived_axiom(domain_id);
                CREATE INDEX IF NOT EXISTS idx_axiom_type
                    ON sa_derived_axiom(axiom_type);
                CREATE INDEX IF NOT EXISTS idx_axiom_ov
                    ON sa_derived_axiom(ontology_version_id);
                """
            )
            conn.commit()
        finally:
            conn.close()

    # ==================================================================
    # sa_shacl_shape —— 版本键控形状缓存
    # ==================================================================
    def save_shape(self, shape: Dict[str, Any]) -> Dict[str, Any]:
        """幂等 upsert：按 (ontology_version_id, constraint_revision, target_type)
        DELETE 旧行后 INSERT。缺失效键/目标类型 → ValueError（规则 14.2 显式失败）。
        """
        ov = str(shape.get("ontology_version_id") or "")
        rev = str(shape.get("constraint_revision") or "")
        target = str(shape.get("target_type") or "")
        if not ov or not target:
            raise ValueError(
                "save_shape 需要非空 ontology_version_id 与 target_type（形状失效键）"
            )
        shape_id = str(shape.get("shape_id") or uuid.uuid4())
        now = shape.get("created_at") or _utc_now_iso()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "DELETE FROM sa_shacl_shape "
                "WHERE ontology_version_id = ? AND constraint_revision = ? "
                "AND target_type = ?",
                (ov, rev, target),
            )
            conn.execute(
                """INSERT INTO sa_shacl_shape (
                    shape_id, workspace_id, ontology_version_id, constraint_revision,
                    target_type, shape_ttl, source_type_defs, source_axioms,
                    checksum, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    shape_id,
                    shape.get("workspace_id") or "",
                    ov,
                    rev,
                    target,
                    str(shape.get("shape_ttl") or ""),
                    _json_dumps(shape.get("source_type_defs")),
                    _json_dumps(shape.get("source_axioms")),
                    shape.get("checksum"),
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_shape_by_id(shape_id) or {
            "shape_id": shape_id,
            "ontology_version_id": ov,
            "constraint_revision": rev,
            "target_type": target,
        }

    def get_shape(
        self,
        *,
        ontology_version_id: str,
        constraint_revision: str,
        target_type: str,
    ) -> Optional[Dict[str, Any]]:
        """按版本键命中缓存（F7-a）；未命中返回 None。"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM sa_shacl_shape "
                "WHERE ontology_version_id = ? AND constraint_revision = ? "
                "AND target_type = ?",
                (ontology_version_id, constraint_revision, target_type),
            ).fetchone()
            return self._shape_row_to_dict(dict(row)) if row else None
        finally:
            conn.close()

    def get_shape_by_id(self, shape_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM sa_shacl_shape WHERE shape_id = ?", (shape_id,)
            ).fetchone()
            return self._shape_row_to_dict(dict(row)) if row else None
        finally:
            conn.close()

    def list_shapes(
        self,
        *,
        ontology_version_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        where: List[str] = []
        params: List[Any] = []
        if ontology_version_id:
            where.append("ontology_version_id = ?")
            params.append(ontology_version_id)
        if workspace_id:
            where.append("workspace_id = ?")
            params.append(workspace_id)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                f"SELECT COUNT(*) FROM sa_shacl_shape {clause}", params
            ).fetchone()[0]
            page = max(1, int(page))
            page_size = max(1, int(page_size))
            offset = (page - 1) * page_size
            rows = conn.execute(
                f"SELECT * FROM sa_shacl_shape {clause} "
                "ORDER BY created_at DESC, shape_id LIMIT ? OFFSET ?",
                params + [page_size, offset],
            ).fetchall()
            return [self._shape_row_to_dict(dict(r)) for r in rows], int(total)
        finally:
            conn.close()

    def delete_shape(self, shape_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                "DELETE FROM sa_shacl_shape WHERE shape_id = ?", (shape_id,)
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def delete_shapes_by_version(
        self,
        ontology_version_id: str,
        constraint_revision: Optional[str] = None,
    ) -> int:
        """失效键批量清理：给定 ontology_version（可选 constraint_revision）。"""
        conn = sqlite3.connect(self.db_path)
        try:
            if constraint_revision is None:
                cur = conn.execute(
                    "DELETE FROM sa_shacl_shape WHERE ontology_version_id = ?",
                    (ontology_version_id,),
                )
            else:
                cur = conn.execute(
                    "DELETE FROM sa_shacl_shape "
                    "WHERE ontology_version_id = ? AND constraint_revision = ?",
                    (ontology_version_id, constraint_revision),
                )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    @staticmethod
    def _shape_row_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "shape_id": row.get("shape_id"),
            "workspace_id": row.get("workspace_id"),
            "ontology_version_id": row.get("ontology_version_id"),
            "constraint_revision": row.get("constraint_revision"),
            "target_type": row.get("target_type"),
            "shape_ttl": row.get("shape_ttl"),
            "source_type_defs": _json_loads(row.get("source_type_defs"), []),
            "source_axioms": _json_loads(row.get("source_axioms"), []),
            "checksum": row.get("checksum"),
            "created_at": row.get("created_at"),
        }

    # ==================================================================
    # sa_derived_axiom —— L6 公理持久化
    # ==================================================================
    def replace_axioms_for_run(
        self,
        axioms: Iterable[Dict[str, Any]],
        *,
        pipeline_run_id: str,
        workspace_id: str = "",
        domain_id: str = "",
        ontology_version_id: str = "",
    ) -> int:
        """按 run 整体替换公理（重跑幂等）：DELETE WHERE pipeline_run_id 后批量 INSERT。

        每条公理 dict 取自 AxiomDeriver.derive()["axioms"]：
        axiom_type / subject / object / confidence / source / proof，
        基数类另含 min_card / max_card。缺 run_id → ValueError（规则 14.2）。
        返回写入条数。
        """
        run_id = str(pipeline_run_id or "")
        if not run_id:
            raise ValueError("replace_axioms_for_run 需要非空 pipeline_run_id（公理归属键）")
        items = list(axioms or [])
        now = _utc_now_iso()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "DELETE FROM sa_derived_axiom WHERE pipeline_run_id = ?", (run_id,)
            )
            for ax in items:
                conf = ax.get("confidence")
                conn.execute(
                    """INSERT INTO sa_derived_axiom (
                        axiom_id, workspace_id, domain_id, ontology_version_id,
                        pipeline_run_id, axiom_type, subject, object, min_card, max_card,
                        confidence, source, proof, created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        str(uuid.uuid4()),
                        workspace_id or "",
                        domain_id or "",
                        ontology_version_id or "",
                        run_id,
                        str(ax.get("axiom_type") or ""),
                        str(ax.get("subject") or ""),
                        str(ax.get("object") or ""),
                        ax.get("min_card"),
                        ax.get("max_card"),
                        float(conf) if conf is not None else None,
                        ax.get("source"),
                        _json_dumps(ax.get("proof")),
                        now,
                    ),
                )
            conn.commit()
            return len(items)
        finally:
            conn.close()

    def get_axiom(self, axiom_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM sa_derived_axiom WHERE axiom_id = ?", (axiom_id,)
            ).fetchone()
            return self._axiom_row_to_dict(dict(row)) if row else None
        finally:
            conn.close()

    def list_axioms(
        self,
        *,
        pipeline_run_id: Optional[str] = None,
        domain_id: Optional[str] = None,
        ontology_version_id: Optional[str] = None,
        axiom_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 200,
    ) -> Tuple[List[Dict[str, Any]], int]:
        where: List[str] = []
        params: List[Any] = []
        if pipeline_run_id:
            where.append("pipeline_run_id = ?")
            params.append(pipeline_run_id)
        if domain_id:
            where.append("domain_id = ?")
            params.append(domain_id)
        if ontology_version_id:
            where.append("ontology_version_id = ?")
            params.append(ontology_version_id)
        if axiom_type:
            where.append("axiom_type = ?")
            params.append(axiom_type)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                f"SELECT COUNT(*) FROM sa_derived_axiom {clause}", params
            ).fetchone()[0]
            page = max(1, int(page))
            page_size = max(1, int(page_size))
            offset = (page - 1) * page_size
            rows = conn.execute(
                f"SELECT * FROM sa_derived_axiom {clause} "
                "ORDER BY created_at DESC, axiom_id LIMIT ? OFFSET ?",
                params + [page_size, offset],
            ).fetchall()
            return [self._axiom_row_to_dict(dict(r)) for r in rows], int(total)
        finally:
            conn.close()

    def delete_axioms_by_run(self, pipeline_run_id: str) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                "DELETE FROM sa_derived_axiom WHERE pipeline_run_id = ?",
                (pipeline_run_id,),
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    @staticmethod
    def _axiom_row_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "axiom_id": row.get("axiom_id"),
            "workspace_id": row.get("workspace_id"),
            "domain_id": row.get("domain_id"),
            "ontology_version_id": row.get("ontology_version_id"),
            "pipeline_run_id": row.get("pipeline_run_id"),
            "axiom_type": row.get("axiom_type"),
            "subject": row.get("subject"),
            "object": row.get("object"),
            "min_card": row.get("min_card"),
            "max_card": row.get("max_card"),
            "confidence": row.get("confidence"),
            "source": row.get("source"),
            "proof": _json_loads(row.get("proof"), {}),
            "created_at": row.get("created_at"),
        }


__all__ = ["SQLiteShaclStorage"]
