"""USL Manager - SQLite 存储层。

6 张表：
- usl_domains         语义领域（UNIQUE code）
- usl_terms           规范术语（UNIQUE domain_id, canonical）
- usl_hierarchies     层级关系
- usl_property_specs  属性规约（UNIQUE domain_id, for_term, prop_name）
- usl_disjoint_pairs  不相交术语对（UNIQUE domain_id, term_a, term_b）
- usl_cardinalities   关系基数（UNIQUE domain_id, rel_name, domain_term, range_term）

AGENTS.md 规则 8：每次 sqlite3.connect() → 用完立刻 conn.close()（无连接池）。
JSON 字段（en_mapping / synonyms / near_synonyms / aliases）→ JSON TEXT。
Enum → .value 字符串存储。
datetime 字段（created_at / updated_at）→ isoformat 字符串。
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_USL_DB_DIR: str = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
DEFAULT_USL_DB_PATH: str = os.path.join(DEFAULT_USL_DB_DIR, "usl.db")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dumps(obj: Any) -> str:
    """安全 JSON 序列化，ensure_ascii=False 保持中文。"""
    return json.dumps(obj, ensure_ascii=False)


def _loads(text: Any, default: Any) -> Any:
    """安全 JSON 反序列化，失败返回 default。"""
    if text is None or text == "":
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return default


# =====================================================================
# SQLiteUslStorage
# =====================================================================


class SQLiteUslStorage:
    """统一语义层 SQLite 持久化（幂等 DDL + 每次 connect/close）。"""

    # -----------------------------------------------------------------
    # 初始化
    # -----------------------------------------------------------------

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            os.makedirs(DEFAULT_USL_DB_DIR, exist_ok=True)
            db_path = DEFAULT_USL_DB_PATH
        self.db_path: str = db_path
        self._init_db()

    def _init_db(self) -> None:
        """建表 + 索引（幂等：CREATE TABLE IF NOT EXISTS）。"""
        conn = sqlite3.connect(self.db_path)
        try:
            self._create_domains_table(conn)
            self._create_terms_table(conn)
            self._create_hierarchies_table(conn)
            self._create_property_specs_table(conn)
            self._create_disjoint_pairs_table(conn)
            self._create_cardinalities_table(conn)
            self._create_role_assignments_table(conn)
            self._create_indexes(conn)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _create_domains_table(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usl_domains (
                id TEXT PRIMARY KEY,
                code TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                description TEXT DEFAULT '',
                en_mapping TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    @staticmethod
    def _create_terms_table(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usl_terms (
                id TEXT PRIMARY KEY,
                domain_id TEXT NOT NULL,
                canonical TEXT NOT NULL,
                semantic_type TEXT NOT NULL DEFAULT '对象类型',
                synonyms TEXT DEFAULT '[]',
                near_synonyms TEXT DEFAULT '[]',
                aliases TEXT DEFAULT '[]',
                stoplist_flag INTEGER DEFAULT 0,
                definition TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(domain_id, canonical)
            )
            """
        )

    @staticmethod
    def _create_hierarchies_table(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usl_hierarchies (
                id TEXT PRIMARY KEY,
                domain_id TEXT NOT NULL,
                rel_type TEXT NOT NULL DEFAULT 'IS_A',
                parent_term TEXT NOT NULL,
                child_term TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                UNIQUE(domain_id, rel_type, parent_term, child_term)
            )
            """
        )

    @staticmethod
    def _create_property_specs_table(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usl_property_specs (
                id TEXT PRIMARY KEY,
                domain_id TEXT NOT NULL,
                for_term TEXT NOT NULL,
                prop_name TEXT NOT NULL,
                data_type TEXT NOT NULL DEFAULT 'STRING',
                unit TEXT,
                required_flag INTEGER DEFAULT 0,
                description TEXT DEFAULT '',
                UNIQUE(domain_id, for_term, prop_name)
            )
            """
        )

    @staticmethod
    def _create_disjoint_pairs_table(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usl_disjoint_pairs (
                id TEXT PRIMARY KEY,
                domain_id TEXT NOT NULL,
                term_a TEXT NOT NULL,
                term_b TEXT NOT NULL,
                reason TEXT DEFAULT '',
                UNIQUE(domain_id, term_a, term_b)
            )
            """
        )

    @staticmethod
    def _create_cardinalities_table(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usl_cardinalities (
                id TEXT PRIMARY KEY,
                domain_id TEXT NOT NULL,
                rel_name TEXT NOT NULL,
                domain_term TEXT NOT NULL,
                range_term TEXT NOT NULL,
                min_card INTEGER NOT NULL DEFAULT 0,
                max_card INTEGER,
                UNIQUE(domain_id, rel_name, domain_term, range_term)
            )
            """
        )

    @staticmethod
    def _create_role_assignments_table(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usl_role_assignments (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                user_name TEXT NOT NULL DEFAULT '',
                ws_role TEXT NOT NULL,
                assigned_by TEXT NOT NULL DEFAULT '',
                note TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(workspace_id, user_id)
            )
            """
        )

    @staticmethod
    def _create_indexes(conn: sqlite3.Connection) -> None:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_terms_domain ON usl_terms(domain_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_terms_type ON usl_terms(semantic_type)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hier_domain ON usl_hierarchies(domain_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_spec_domain "
            "ON usl_property_specs(domain_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_spec_for_term "
            "ON usl_property_specs(for_term)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_dj_domain ON usl_disjoint_pairs(domain_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_card_domain ON usl_cardinalities(domain_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_card_rel ON usl_cardinalities(rel_name)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_role_ws ON usl_role_assignments(workspace_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_role_user ON usl_role_assignments(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_role_role ON usl_role_assignments(ws_role)"
        )

    # =================================================================
    # 通用工具
    # =================================================================

    @staticmethod
    def _row_factory(row: sqlite3.Row) -> Dict[str, Any]:
        """sqlite3.Row -> dict。"""
        return dict(row)

    @staticmethod
    def _paginate(
        total_sql: str,
        list_sql: str,
        params: Tuple[Any, ...],
        page: int,
        page_size: int,
        conn: sqlite3.Connection,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """通用分页：返回 (rows_dicts, total_count)。"""
        total_cur = conn.execute(total_sql, params)
        total = int(total_cur.fetchone()[0] or 0)

        offset = (max(1, page) - 1) * max(1, page_size)
        limit_sql = f"{list_sql} LIMIT ? OFFSET ?"
        paged_params = params + (max(1, page_size), offset)
        conn.row_factory = sqlite3.Row
        cur = conn.execute(limit_sql, paged_params)
        rows = [dict(r) for r in cur.fetchall()]
        return rows, total

    # =================================================================
    # Domain
    # =================================================================

    def save_domain(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert 领域（UNIQUE code 冲突则更新 en_mapping/description/updated_at）。

        为避免 id / code 双主键在 update 时发生交叉冲突：
          1) 若传了 id，先 DELETE WHERE id（允许复合 UNIQUE 改变而不抛 PK 冲突），
          2) 再 INSERT ON CONFLICT(code) DO UPDATE SET 可变字段，
          3) 最终按 code 查回真实持久化记录（保证返回 id 与 DB 一致）。
        """
        conn = sqlite3.connect(self.db_path)
        try:
            if not d.get("id"):
                d["id"] = str(uuid.uuid4())
            now = _utc_now_iso()
            d.setdefault("created_at", now)
            d["updated_at"] = now

            # 1) 先按 id 删除旧行（若存在），允许用户通过更新 code 重映射
            conn.execute("DELETE FROM usl_domains WHERE id = ?", (d["id"],))

            # 2) 再 INSERT ON CONFLICT(code) DO UPDATE SET 可变字段（id 不变）
            conn.execute(
                """
                INSERT INTO usl_domains
                    (id, code, display_name, description,
                     en_mapping, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    display_name  = excluded.display_name,
                    description   = excluded.description,
                    en_mapping    = excluded.en_mapping,
                    updated_at    = excluded.updated_at
                """,
                (
                    d["id"],
                    d.get("code", ""),
                    d.get("display_name", ""),
                    d.get("description", ""),
                    _dumps(d.get("en_mapping", {})),
                    d["created_at"],
                    d["updated_at"],
                ),
            )
            conn.commit()
            # 3) 按 code 读回真实行，避免内存 id / DB 实际 id 不一致
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT * FROM usl_domains WHERE code = ?", (d.get("code", ""),)
            )
            row = cur.fetchone()
            return self._domain_row_to_model(dict(row))
        finally:
            conn.close()

    def get_domain(self, domain_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM usl_domains WHERE id = ?", (domain_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._domain_row_to_model(dict(row))
        finally:
            conn.close()

    def get_domain_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM usl_domains WHERE code = ?", (code,))
            row = cur.fetchone()
            if not row:
                return None
            return self._domain_row_to_model(dict(row))
        finally:
            conn.close()

    def list_domains(
        self, page: int = 1, page_size: int = 50
    ) -> Tuple[List[Dict[str, Any]], int]:
        conn = sqlite3.connect(self.db_path)
        try:
            total_sql = "SELECT COUNT(*) FROM usl_domains"
            list_sql = "SELECT * FROM usl_domains ORDER BY created_at DESC"
            rows, total = self._paginate(total_sql, list_sql, (), page, page_size, conn)
            return [self._domain_row_to_model(r) for r in rows], total
        finally:
            conn.close()

    def delete_domain(self, domain_id: str) -> bool:
        """级联删除领域及其所有子数据。"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "DELETE FROM usl_terms           WHERE domain_id = ?", (domain_id,)
            )
            conn.execute(
                "DELETE FROM usl_hierarchies     WHERE domain_id = ?", (domain_id,)
            )
            conn.execute(
                "DELETE FROM usl_property_specs  WHERE domain_id = ?", (domain_id,)
            )
            conn.execute(
                "DELETE FROM usl_disjoint_pairs  WHERE domain_id = ?", (domain_id,)
            )
            conn.execute(
                "DELETE FROM usl_cardinalities   WHERE domain_id = ?", (domain_id,)
            )
            cur = conn.execute("DELETE FROM usl_domains   WHERE id = ?", (domain_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def _domain_row_to_model(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": row.get("id", ""),
            "code": row.get("code", ""),
            "display_name": row.get("display_name", ""),
            "description": row.get("description", ""),
            "en_mapping": _loads(row.get("en_mapping"), {}),
            "created_at": row.get("created_at", ""),
            "updated_at": row.get("updated_at", ""),
        }

    # =================================================================
    # Term
    # =================================================================

    def save_term(self, t: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert 术语（UNIQUE(domain_id, canonical) 冲突则 UPDATE）。

        1) DELETE WHERE id 允许复合键变更；2) INSERT ON CONFLICT(复合) UPDATE；
        3) 按 (domain_id, canonical) 读回真实行。
        """
        conn = sqlite3.connect(self.db_path)
        try:
            if not t.get("id"):
                t["id"] = str(uuid.uuid4())
            now = _utc_now_iso()
            t.setdefault("created_at", now)
            t["updated_at"] = now

            domain_id = t.get("domain_id", "")
            canonical = t.get("canonical", "")

            conn.execute("DELETE FROM usl_terms WHERE id = ?", (t["id"],))

            conn.execute(
                """
                INSERT INTO usl_terms
                    (id, domain_id, canonical, semantic_type, synonyms, near_synonyms,
                     aliases, stoplist_flag, definition, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(domain_id, canonical) DO UPDATE SET
                    semantic_type = excluded.semantic_type,
                    synonyms      = excluded.synonyms,
                    near_synonyms = excluded.near_synonyms,
                    aliases       = excluded.aliases,
                    stoplist_flag = excluded.stoplist_flag,
                    definition    = excluded.definition,
                    updated_at    = excluded.updated_at
                """,
                (
                    t["id"],
                    domain_id,
                    canonical,
                    t.get("semantic_type", "对象类型"),
                    _dumps(t.get("synonyms", [])),
                    _dumps(t.get("near_synonyms", [])),
                    _dumps(t.get("aliases", [])),
                    1 if t.get("stoplist_flag", False) else 0,
                    t.get("definition", ""),
                    t["created_at"],
                    t["updated_at"],
                ),
            )
            conn.commit()
            # 按复合键读回
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT * FROM usl_terms WHERE domain_id = ? AND canonical = ?",
                (domain_id, canonical),
            )
            row = cur.fetchone()
            return self._term_row_to_model(dict(row))
        finally:
            conn.close()

    def get_term(self, term_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM usl_terms WHERE id = ?", (term_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._term_row_to_model(dict(row))
        finally:
            conn.close()

    def list_terms(
        self,
        domain_id: Optional[str] = None,
        semantic_type: Optional[str] = None,
        synonym_keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """分页列出术语，支持 domain_id / semantic_type 过滤 + 同义词 LIKE 模糊。"""
        conn = sqlite3.connect(self.db_path)
        try:
            where_clauses: List[str] = []
            params: List[Any] = []

            if domain_id:
                where_clauses.append("t.domain_id = ?")
                params.append(domain_id)
            if semantic_type:
                where_clauses.append("t.semantic_type = ?")
                params.append(semantic_type)
            if synonym_keyword:
                # LIKE synonyms JSON 文本；同时覆盖 near_synonyms / aliases / canonical
                kw = f"%{synonym_keyword}%"
                where_clauses.append(
                    "(t.synonyms LIKE ? OR t.near_synonyms LIKE ? "
                    "OR t.aliases LIKE ? OR t.canonical LIKE ?)"
                )
                params.extend([kw, kw, kw, kw])

            where_sql = (
                (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
            )
            total_sql = f"SELECT COUNT(DISTINCT t.id) FROM usl_terms t {where_sql}"
            list_sql = (
                f"SELECT DISTINCT t.* FROM usl_terms t {where_sql} "
                f"ORDER BY t.created_at DESC"
            )
            rows, total = self._paginate(
                total_sql,
                list_sql,
                tuple(params),
                page,
                page_size,
                conn,
            )
            return [self._term_row_to_model(r) for r in rows], total
        finally:
            conn.close()

    def delete_term(self, term_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute("DELETE FROM usl_terms WHERE id = ?", (term_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def _term_row_to_model(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": row.get("id", ""),
            "domain_id": row.get("domain_id", ""),
            "canonical": row.get("canonical", ""),
            "semantic_type": row.get("semantic_type", "对象类型"),
            "synonyms": _loads(row.get("synonyms"), []),
            "near_synonyms": _loads(row.get("near_synonyms"), []),
            "aliases": _loads(row.get("aliases"), []),
            "stoplist_flag": bool(row.get("stoplist_flag", 0)),
            "definition": row.get("definition", ""),
            "created_at": row.get("created_at", ""),
            "updated_at": row.get("updated_at", ""),
        }

    # =================================================================
    # Hierarchy
    # =================================================================

    def save_hierarchy(self, h: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert 层级关系（UNIQUE 4 列冲突 UPDATE confidence）。

        1) DELETE WHERE id；2) INSERT ON CONFLICT(4列) DO UPDATE；3) 按 4 列读回。
        """
        conn = sqlite3.connect(self.db_path)
        try:
            if not h.get("id"):
                h["id"] = str(uuid.uuid4())
            h.setdefault("created_at", _utc_now_iso())

            domain_id = h.get("domain_id", "")
            rel_type = h.get("rel_type", "IS_A")
            parent_term = h.get("parent_term", "")
            child_term = h.get("child_term", "")

            conn.execute("DELETE FROM usl_hierarchies WHERE id = ?", (h["id"],))
            conn.execute(
                """
                INSERT INTO usl_hierarchies
                    (id, domain_id, rel_type, parent_term,
                     child_term, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(domain_id, rel_type, parent_term, child_term)
                DO UPDATE SET confidence = excluded.confidence
                """,
                (
                    h["id"],
                    domain_id,
                    rel_type,
                    parent_term,
                    child_term,
                    float(h.get("confidence", 1.0)),
                    h["created_at"],
                ),
            )
            conn.commit()
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                """
                SELECT * FROM usl_hierarchies
                WHERE domain_id = ?
                  AND rel_type = ?
                  AND parent_term = ?
                  AND child_term = ?
                """,
                (domain_id, rel_type, parent_term, child_term),
            )
            row = cur.fetchone()
            return self._hierarchy_row_to_model(dict(row))
        finally:
            conn.close()

    def get_hierarchy(self, hierarchy_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT * FROM usl_hierarchies WHERE id = ?", (hierarchy_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            return self._hierarchy_row_to_model(dict(row))
        finally:
            conn.close()

    def list_hierarchies(
        self,
        domain_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 200,
    ) -> Tuple[List[Dict[str, Any]], int]:
        conn = sqlite3.connect(self.db_path)
        try:
            where_sql = ""
            params: Tuple[Any, ...] = ()
            if domain_id:
                where_sql = " WHERE domain_id = ?"
                params = (domain_id,)
            total_sql = f"SELECT COUNT(*) FROM usl_hierarchies {where_sql}"
            list_sql = (
                f"SELECT * FROM usl_hierarchies {where_sql} ORDER BY created_at DESC"
            )
            rows, total = self._paginate(
                total_sql, list_sql, params, page, page_size, conn
            )
            return [self._hierarchy_row_to_model(r) for r in rows], total
        finally:
            conn.close()

    def delete_hierarchy(self, hierarchy_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                "DELETE FROM usl_hierarchies WHERE id = ?", (hierarchy_id,)
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def _hierarchy_row_to_model(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": row.get("id", ""),
            "domain_id": row.get("domain_id", ""),
            "rel_type": row.get("rel_type", "IS_A"),
            "parent_term": row.get("parent_term", ""),
            "child_term": row.get("child_term", ""),
            "confidence": float(row.get("confidence", 1.0)),
            "created_at": row.get("created_at", ""),
        }

    # =================================================================
    # PropertySpec
    # =================================================================

    def save_property_spec(self, s: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert 属性规约（UNIQUE(domain_id, for_term, prop_name) 冲突 UPDATE）。

        1) DELETE WHERE id；2) INSERT ON CONFLICT(3列) DO UPDATE；3) 按 3 列读回。
        """
        conn = sqlite3.connect(self.db_path)
        try:
            if not s.get("id"):
                s["id"] = str(uuid.uuid4())

            domain_id = s.get("domain_id", "")
            for_term = s.get("for_term", "")
            prop_name = s.get("prop_name", "")

            conn.execute("DELETE FROM usl_property_specs WHERE id = ?", (s["id"],))
            conn.execute(
                """
                INSERT INTO usl_property_specs
                    (id, domain_id, for_term, prop_name, data_type,
                     unit, required_flag, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(domain_id, for_term, prop_name) DO UPDATE SET
                    data_type     = excluded.data_type,
                    unit          = excluded.unit,
                    required_flag = excluded.required_flag,
                    description   = excluded.description
                """,
                (
                    s["id"],
                    domain_id,
                    for_term,
                    prop_name,
                    s.get("data_type", "STRING"),
                    s.get("unit"),  # None -> NULL
                    1 if s.get("required_flag", False) else 0,
                    s.get("description", ""),
                ),
            )
            conn.commit()
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                """SELECT * FROM usl_property_specs
                   WHERE domain_id = ? AND for_term = ? AND prop_name = ?""",
                (domain_id, for_term, prop_name),
            )
            row = cur.fetchone()
            return self._spec_row_to_model(dict(row))
        finally:
            conn.close()

    def get_property_spec(self, spec_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT * FROM usl_property_specs WHERE id = ?", (spec_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            return self._spec_row_to_model(dict(row))
        finally:
            conn.close()

    def list_property_specs(
        self,
        domain_id: Optional[str] = None,
        for_term: Optional[str] = None,
        page: int = 1,
        page_size: int = 200,
    ) -> Tuple[List[Dict[str, Any]], int]:
        conn = sqlite3.connect(self.db_path)
        try:
            where_clauses: List[str] = []
            params: List[Any] = []
            if domain_id:
                where_clauses.append("domain_id = ?")
                params.append(domain_id)
            if for_term:
                where_clauses.append("for_term = ?")
                params.append(for_term)
            where_sql = (
                (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
            )
            total_sql = f"SELECT COUNT(*) FROM usl_property_specs {where_sql}"
            list_sql = (
                f"SELECT * FROM usl_property_specs {where_sql} "
                f"ORDER BY for_term, prop_name"
            )
            rows, total = self._paginate(
                total_sql,
                list_sql,
                tuple(params),
                page,
                page_size,
                conn,
            )
            return [self._spec_row_to_model(r) for r in rows], total
        finally:
            conn.close()

    def delete_property_spec(self, spec_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                "DELETE FROM usl_property_specs WHERE id = ?", (spec_id,)
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def _spec_row_to_model(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": row.get("id", ""),
            "domain_id": row.get("domain_id", ""),
            "for_term": row.get("for_term", ""),
            "prop_name": row.get("prop_name", ""),
            "data_type": row.get("data_type", "STRING"),
            "unit": row.get("unit"),
            "required_flag": bool(row.get("required_flag", 0)),
            "description": row.get("description", ""),
        }

    # =================================================================
    # DisjointPair
    # =================================================================

    def save_disjoint_pair(self, p: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert 不相交对（UNIQUE(domain_id, term_a, term_b) 冲突 UPDATE reason）。

        1) DELETE WHERE id；2) INSERT ON CONFLICT(3列) DO UPDATE；3) 按 3 列读回。
        """
        conn = sqlite3.connect(self.db_path)
        try:
            if not p.get("id"):
                p["id"] = str(uuid.uuid4())

            domain_id = p.get("domain_id", "")
            term_a = p.get("term_a", "")
            term_b = p.get("term_b", "")

            conn.execute("DELETE FROM usl_disjoint_pairs WHERE id = ?", (p["id"],))
            conn.execute(
                """
                INSERT INTO usl_disjoint_pairs (id, domain_id, term_a, term_b, reason)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(domain_id, term_a, term_b) DO UPDATE SET
                    reason = excluded.reason
                """,
                (
                    p["id"],
                    domain_id,
                    term_a,
                    term_b,
                    p.get("reason", ""),
                ),
            )
            conn.commit()
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                """SELECT * FROM usl_disjoint_pairs
                   WHERE domain_id = ? AND term_a = ? AND term_b = ?""",
                (domain_id, term_a, term_b),
            )
            row = cur.fetchone()
            return self._dj_row_to_model(dict(row))
        finally:
            conn.close()

    def get_disjoint_pair(self, pair_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT * FROM usl_disjoint_pairs WHERE id = ?", (pair_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            return self._dj_row_to_model(dict(row))
        finally:
            conn.close()

    def list_disjoint_pairs(
        self,
        domain_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 200,
    ) -> Tuple[List[Dict[str, Any]], int]:
        conn = sqlite3.connect(self.db_path)
        try:
            where_sql = ""
            params: Tuple[Any, ...] = ()
            if domain_id:
                where_sql = " WHERE domain_id = ?"
                params = (domain_id,)
            total_sql = f"SELECT COUNT(*) FROM usl_disjoint_pairs {where_sql}"
            list_sql = (
                f"SELECT * FROM usl_disjoint_pairs {where_sql} ORDER BY term_a, term_b"
            )
            rows, total = self._paginate(
                total_sql, list_sql, params, page, page_size, conn
            )
            return [self._dj_row_to_model(r) for r in rows], total
        finally:
            conn.close()

    def delete_disjoint_pair(self, pair_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                "DELETE FROM usl_disjoint_pairs WHERE id = ?", (pair_id,)
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def _dj_row_to_model(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": row.get("id", ""),
            "domain_id": row.get("domain_id", ""),
            "term_a": row.get("term_a", ""),
            "term_b": row.get("term_b", ""),
            "reason": row.get("reason", ""),
        }

    # =================================================================
    # Cardinality
    # =================================================================

    def save_cardinality(self, c: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert 关系基数（UNIQUE 4 列冲突 UPDATE min/max_card）。

        1) DELETE WHERE id；2) INSERT ON CONFLICT(4列) DO UPDATE；3) 按 4 列读回。
        """
        conn = sqlite3.connect(self.db_path)
        try:
            if not c.get("id"):
                c["id"] = str(uuid.uuid4())

            domain_id = c.get("domain_id", "")
            rel_name = c.get("rel_name", "")
            domain_term = c.get("domain_term", "")
            range_term = c.get("range_term", "")

            conn.execute("DELETE FROM usl_cardinalities WHERE id = ?", (c["id"],))
            conn.execute(
                """
                INSERT INTO usl_cardinalities
                    (id, domain_id, rel_name, domain_term,
                     range_term, min_card, max_card)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(domain_id, rel_name, domain_term, range_term)
                DO UPDATE SET
                    min_card = excluded.min_card,
                    max_card = excluded.max_card
                """,
                (
                    c["id"],
                    domain_id,
                    rel_name,
                    domain_term,
                    range_term,
                    int(c.get("min_card", 0)),
                    c.get("max_card"),  # None -> NULL
                ),
            )
            conn.commit()
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                """
                SELECT * FROM usl_cardinalities
                WHERE domain_id = ?
                  AND rel_name = ?
                  AND domain_term = ?
                  AND range_term = ?
                """,
                (domain_id, rel_name, domain_term, range_term),
            )
            row = cur.fetchone()
            return self._card_row_to_model(dict(row))
        finally:
            conn.close()

    def get_cardinality(self, card_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT * FROM usl_cardinalities WHERE id = ?", (card_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            return self._card_row_to_model(dict(row))
        finally:
            conn.close()

    def list_cardinalities(
        self,
        domain_id: Optional[str] = None,
        rel_name: Optional[str] = None,
        page: int = 1,
        page_size: int = 200,
    ) -> Tuple[List[Dict[str, Any]], int]:
        conn = sqlite3.connect(self.db_path)
        try:
            where_clauses: List[str] = []
            params: List[Any] = []
            if domain_id:
                where_clauses.append("domain_id = ?")
                params.append(domain_id)
            if rel_name:
                where_clauses.append("rel_name = ?")
                params.append(rel_name)
            where_sql = (
                (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
            )
            total_sql = f"SELECT COUNT(*) FROM usl_cardinalities {where_sql}"
            list_sql = f"SELECT * FROM usl_cardinalities {where_sql} ORDER BY rel_name"
            rows, total = self._paginate(
                total_sql,
                list_sql,
                tuple(params),
                page,
                page_size,
                conn,
            )
            return [self._card_row_to_model(r) for r in rows], total
        finally:
            conn.close()

    def delete_cardinality(self, card_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute("DELETE FROM usl_cardinalities WHERE id = ?", (card_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def _card_row_to_model(row: Dict[str, Any]) -> Dict[str, Any]:
        max_card = row.get("max_card")
        return {
            "id": row.get("id", ""),
            "domain_id": row.get("domain_id", ""),
            "rel_name": row.get("rel_name", ""),
            "domain_term": row.get("domain_term", ""),
            "range_term": row.get("range_term", ""),
            "min_card": int(row.get("min_card", 0)),
            "max_card": (int(max_card) if max_card is not None else None),
        }

    # =================================================================
    # Role Assignments
    # =================================================================

    _VALID_WS_ROLES: set = {
        "viewer", "term_editor", "domain_editor",
        "reviewer", "super_admin",
    }

    def assign_role(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert：按 UNIQUE(workspace_id, user_id) 更新或插入，返回 assignment dict。"""
        import uuid
        from datetime import datetime

        ws_id = str(payload.get("workspace_id", "")).strip()
        user_id = str(payload.get("user_id", "")).strip()
        ws_role_raw = str(payload.get("ws_role", "")).strip()
        ws_role = ws_role_raw if ws_role_raw else "viewer"
        if not ws_id or not user_id:
            raise ValueError("workspace_id 和 user_id 必填")
        if ws_role not in self._VALID_WS_ROLES:
            raise ValueError(
                f"ws_role 非法值 {ws_role!r}，合法集 {sorted(self._VALID_WS_ROLES)}"
            )
        user_name = str(payload.get("user_name", "")).strip()
        assigned_by = str(payload.get("assigned_by", "")).strip()
        note = str(payload.get("note", "")).strip()
        now = datetime.now().isoformat(timespec="seconds")

        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                "SELECT id FROM usl_role_assignments WHERE workspace_id = ? AND user_id = ?",
                (ws_id, user_id),
            )
            existing = cur.fetchone()
            if existing:
                assignment_id = existing["id"]
                conn.execute(
                    """
                    UPDATE usl_role_assignments
                       SET ws_role = ?, user_name = ?, assigned_by = ?, note = ?, updated_at = ?
                     WHERE id = ?
                    """,
                    (ws_role, user_name, assigned_by, note, now, assignment_id),
                )
            else:
                assignment_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO usl_role_assignments
                        (id, workspace_id, user_id, user_name, ws_role, assigned_by, note,
                         created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (assignment_id, ws_id, user_id, user_name, ws_role, assigned_by, note,
                     now, now),
                )
            conn.commit()
            return self._fetch_role_assignment(assignment_id, conn)
        finally:
            conn.close()

    def get_role_assignment(
        self, workspace_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                "SELECT * FROM usl_role_assignments WHERE workspace_id = ? AND user_id = ?",
                (workspace_id, user_id),
            )
            row = cur.fetchone()
            return self._normalize_role_row(row) if row else None
        finally:
            conn.close()

    def list_role_assignments(
        self,
        *,
        workspace_id: Optional[str] = None,
        ws_role: Optional[str] = None,
        user_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        conds: List[str] = []
        args: List[Any] = []
        if workspace_id:
            conds.append("workspace_id = ?")
            args.append(workspace_id)
        if ws_role:
            conds.append("ws_role = ?")
            args.append(ws_role)
        if user_id:
            conds.append("user_id = ?")
            args.append(user_id)
        where_sql = f"WHERE {' AND '.join(conds)}" if conds else ""
        total_sql = f"SELECT COUNT(*) FROM usl_role_assignments {where_sql}"
        list_sql = (
            f"SELECT * FROM usl_role_assignments {where_sql} "
            f"ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        )
        offset = (page - 1) * page_size
        conn = sqlite3.connect(self.db_path)
        try:
            total = conn.execute(total_sql, args).fetchone()[0]
            cur = conn.execute(list_sql, args + [page_size, offset])
            rows = [self._normalize_role_row(r) for r in cur.fetchall()]
            return rows, int(total)
        finally:
            conn.close()

    def delete_role_assignment(self, assignment_id: str) -> bool:
        if not assignment_id:
            return False
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                "DELETE FROM usl_role_assignments WHERE id = ?",
                (assignment_id,),
            )
            conn.commit()
            return bool(cur.rowcount and cur.rowcount > 0)
        finally:
            conn.close()

    # -----------------------------------------------------------------
    # Role internal helpers
    # -----------------------------------------------------------------

    def _fetch_role_assignment(
        self, assignment_id: str, conn: sqlite3.Connection
    ) -> Dict[str, Any]:
        cur = conn.execute(
            "SELECT * FROM usl_role_assignments WHERE id = ?",
            (assignment_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError(f"角色分配 {assignment_id} 写入后读取失败")
        result = self._normalize_role_row(row)
        assert isinstance(result, dict)
        return result

    @staticmethod
    def _normalize_role_row(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "workspace_id": row["workspace_id"],
            "user_id": row["user_id"],
            "user_name": row["user_name"],
            "ws_role": row["ws_role"],
            "assigned_by": row["assigned_by"],
            "note": row["note"] or "",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


__all__ = ["SQLiteUslStorage"]
