"""SQLiteGapStorage —— concept_gaps 单表存储（规则 8：每次 connect/close，JSON TEXT，ISO 时间）。"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..models.gap import GapLayer, GapStatus, make_scope_key

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
                    attribution_counts_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'open',
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    promoted_candidate_id TEXT,
                    promoted_proposal_id TEXT,
                    promoted_ticket_id TEXT,
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
            # 旧库迁移（ADR-088 子项目 A）：无 attribution_counts_json 列时幂等加列。
            # 旧数据该列为 NULL → 读侧 _safe_json 回退 {}（既有容错已覆盖）。
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(concept_gaps)").fetchall()}
            if "attribution_counts_json" not in cols:
                conn.execute(
                    "ALTER TABLE concept_gaps "
                    "ADD COLUMN attribution_counts_json TEXT"
                )
            # 旧库迁移（ADR-090 子项目 D）：按 layer 路由的两条回填列。
            # 旧行该列为 NULL → promote 幂等判定视为「未 promote」（行为同今天）。
            for col in ("promoted_proposal_id", "promoted_ticket_id"):
                if col not in cols:
                    conn.execute(
                        f"ALTER TABLE concept_gaps ADD COLUMN {col} TEXT"
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
        # 旧库迁移行该列为 NULL → 回退 {}（attribution 归因缺失 = 无归因，不造数）
        d["attribution_counts_json"] = self._safe_json(
            d.get("attribution_counts_json"), {})
        return d

    # ---- 归因清洗（ADR-088 D2：最佳努力、不造数） ----
    @staticmethod
    def _sanitize_attribution(attribution: Any) -> Optional[Dict[str, Any]]:
        """校验 attribution：非 dict 或 layer 非法 → None（warning 可观测，规则 14）。

        只保留已知键（其余丢弃）：
          layer / target_kind / target_ref —— ADR-088 三个基础键
          parent —— ADR-090 子项目 D 追加：schema 层 property 缺口需要「父对象类型」
                    才能推导 RFC 6902 路径（否则只能落到 /object_types/Unknown/...，
                    不可用）。仍是白名单已知键，不放行任意字段。
        """
        if attribution is None:
            return None
        if not isinstance(attribution, dict):
            logger.warning("attribution 非 dict，忽略: %r", attribution)
            return None
        layer = attribution.get("layer")
        try:
            layer_val = GapLayer(str(layer)).value
        except ValueError:
            logger.warning("attribution.layer 非法，忽略: %r", attribution)
            return None
        out: Dict[str, Any] = {"layer": layer_val}
        for k in ("target_kind", "target_ref", "parent"):
            v = attribution.get(k)
            if v is not None:
                out[k] = str(v)
        return out

    # ---- 写 ----
    def record_signal(
        self, source, expression: str, *,
        workspace_id: Optional[str] = None, domain_id: Optional[str] = None,
        ref: Optional[str] = None, detail: Optional[str] = None,
        attribution: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        source_val = str(getattr(source, "value", source))
        expr = (expression or "").strip()
        if not expr:
            raise ValueError("expression 不能为空")
        scope_key = make_scope_key(workspace_id, domain_id)
        now = _utc_now_iso()
        occurrence = {"source": source_val, "ref": ref, "at": now, "detail": detail}
        attr = self._sanitize_attribution(attribution)
        if attr is not None:
            # 仅在归因有效时携带 attribution 键——旧签名路径（None）保持旧 shape
            occurrence["attribution"] = attr

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
                attr_counts = {attr["layer"]: 1} if attr else {}
                conn.execute(
                    """INSERT INTO concept_gaps (
                        id, expression, scope_key, heat, source_counts_json,
                        sources_json, attribution_counts_json,
                        status, first_seen, last_seen, updated_at,
                        workspace_id, domain_id
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (gap_id, expr, scope_key, 1,
                     json.dumps(counts, ensure_ascii=False),
                     json.dumps([occurrence], ensure_ascii=False),
                     json.dumps(attr_counts, ensure_ascii=False),
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
            attr_counts = self._safe_json(row["attribution_counts_json"], {})
            if attr:
                # 归因全量计数（镜像 source_counts 模式；无归因信号不计入 by_layer）
                attr_counts[attr["layer"]] = attr_counts.get(attr["layer"], 0) + 1
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
                       attribution_counts_json=?,
                       status=?, last_seen=?, updated_at=?{dismiss_clause}
                   WHERE id=?""",
                (json.dumps(counts, ensure_ascii=False),
                 json.dumps(sources, ensure_ascii=False),
                 json.dumps(attr_counts, ensure_ascii=False),
                 new_status, now, now, gap_id),
            )
            conn.commit()
            return self._row_to_dict(
                conn.execute("SELECT * FROM concept_gaps WHERE id=?", (gap_id,)).fetchone()
            )
        finally:
            conn.close()

    def update_status(self, gap_id: str, status: str, **fields) -> bool:
        allowed = {
            "promoted_candidate_id", "promoted_proposal_id",
            "promoted_ticket_id", "resolved_term_id", "dismiss_reason",
        }
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
        layer: Optional[str] = None,
        workspace_id: Optional[str] = None, page: int = 1, page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        where, params = [], []
        if status:
            where.append("status=?")
            params.append(status)
        if source:  # source 过滤在 SQL 侧一致计算（JSON1 json_extract），total 与分页同源
            where.append("json_extract(source_counts_json, ?) > 0")
            params.append(f"$.{source}")
        if layer:  # layer 过滤同 source 模式（ADR-088 子项目 A）
            try:
                layer_val = GapLayer(str(layer)).value
            except ValueError:
                return [], 0  # 非法 layer 显式空结果（不造数、不猜）
            where.append("json_extract(attribution_counts_json, ?) > 0")
            params.append(f"$.{layer_val}")
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

    def count_by_layer(self) -> Dict[str, int]:
        """归因层全量计数（ADR-088）。只统计真实记录的归因，无归因信号不计入。"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT attribution_counts_json FROM concept_gaps").fetchall()
            out: Dict[str, int] = {}
            for r in rows:
                for k, v in self._safe_json(r["attribution_counts_json"], {}).items():
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
