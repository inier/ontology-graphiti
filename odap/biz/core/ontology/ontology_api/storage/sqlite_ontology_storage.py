"""Ontology API - SQLite 存储层

11 张表：
- ontologies: 本体主表
- ontology_schema_versions: Schema 版本表
- object_type_definitions: 对象类型定义
- link_type_definitions: 关系类型定义
- action_type_definitions: 动作类型定义
- process_type_definitions: 业务过程类型定义
- rule_type_definitions: 规则类型定义
- function_type_definitions: 逻辑函数类型定义
- indicator_type_definitions: 指标类型定义
- database_connections: 数据库连接配置
- extraction_sessions: 抽取会话

AGENTS.md 规则 8：每次 connect/close，无连接池。
AGENTS.md 规则 5：JSON 字段用 TEXT 存储，datetime 用 ISO 字符串。
"""
from __future__ import annotations

import json
import os
from odap.infra.storage.sqlite_base import SqliteBaseStorage
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from odap.infra.security.encryption import ClassifiedFieldEncryptor

def _safe_json_loads(value: Any, default: Any) -> Any:
    """安全地解析 JSON 字符串；失败时返回 default"""
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default

class SQLiteOntologyStorage(SqliteBaseStorage):
    """Ontology API 模块的 SQLite 持久化"""

    def __init__(self, db_path: str = None):
        super().__init__(db_path, db_name="ontology_api.db")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _encrypt_password(password: str) -> str:
        """Encrypt a database connection password using AES-GCM."""
        if not password:
            return password
        encryptor = ClassifiedFieldEncryptor.get_instance()
        encrypted = encryptor.encrypt_if_classified(password, "S")
        return encrypted if isinstance(encrypted, str) else json.dumps(encrypted)

    @staticmethod
    def _decrypt_password(password_encrypted: str) -> str:
        """Decrypt a database connection password."""
        if not password_encrypted:
            return password_encrypted
        encryptor = ClassifiedFieldEncryptor.get_instance()
        return encryptor.decrypt_if_classified(password_encrypted, "S")

    # ------------------------------------------------------------------
    # 初始化表结构
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        conn = self._get_conn()
        try:
            self._create_ontologies_table(conn)
            self._create_schema_versions_table(conn)
            self._create_object_type_definitions_table(conn)
            self._create_link_type_definitions_table(conn)
            self._create_action_type_definitions_table(conn)
            self._create_process_type_definitions_table(conn)
            self._create_rule_type_definitions_table(conn)
            self._create_function_type_definitions_table(conn)
            self._create_indicator_type_definitions_table(conn)
            self._create_database_connections_table(conn)
            self._create_extraction_sessions_table(conn)
            self._create_indexes(conn)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _create_ontologies_table(conn) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ontologies (
                ontology_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                workspace_id TEXT NOT NULL,
                scenario_id TEXT,
                current_version TEXT DEFAULT 'v0.1.0',
                status TEXT DEFAULT 'DRAFT',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

    @staticmethod
    def _create_schema_versions_table(conn) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ontology_schema_versions (
                version_id TEXT PRIMARY KEY,
                ontology_id TEXT NOT NULL,
                version_number TEXT NOT NULL,
                parent_version_id TEXT,
                is_stable INTEGER DEFAULT 0,
                changelog TEXT DEFAULT '',
                schema_snapshot TEXT,
                created_at TEXT NOT NULL
            )
        """)

    @staticmethod
    def _create_object_type_definitions_table(conn) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS object_type_definitions (
                type_id TEXT PRIMARY KEY,
                ontology_id TEXT NOT NULL,
                version_id TEXT,
                name TEXT NOT NULL,
                display_name TEXT,
                description TEXT DEFAULT '',
                properties TEXT DEFAULT '[]',
                links TEXT DEFAULT '[]',
                actions TEXT DEFAULT '[]',
                primary_key TEXT DEFAULT '[]',
                classification_level TEXT DEFAULT 'U',
                icon TEXT,
                color TEXT,
                is_active INTEGER DEFAULT 1,
                parent_type TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

    @staticmethod
    def _create_link_type_definitions_table(conn) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS link_type_definitions (
                link_id TEXT PRIMARY KEY,
                ontology_id TEXT NOT NULL,
                version_id TEXT,
                name TEXT NOT NULL,
                display_name TEXT,
                source_type TEXT NOT NULL,
                target_type TEXT NOT NULL,
                cardinality TEXT DEFAULT 'ONE_TO_MANY',
                link_type TEXT DEFAULT 'ASSOCIATION',
                is_bidirectional INTEGER DEFAULT 0,
                reverse_name TEXT,
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)

    @staticmethod
    def _create_action_type_definitions_table(conn) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS action_type_definitions (
                action_type_id TEXT PRIMARY KEY,
                ontology_id TEXT NOT NULL,
                version_id TEXT,
                name TEXT NOT NULL,
                display_name TEXT,
                description TEXT DEFAULT '',
                target_object_type TEXT NOT NULL,
                parameters TEXT DEFAULT '[]',
                required_roles TEXT DEFAULT '[]',
                confirmation_required INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)

    @staticmethod
    def _create_process_type_definitions_table(conn) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS process_type_definitions (
                type_id TEXT PRIMARY KEY,
                ontology_id TEXT NOT NULL,
                version_id TEXT,
                name TEXT NOT NULL,
                display_name TEXT,
                description TEXT DEFAULT '',
                flow_node_schema TEXT DEFAULT '[]',
                related_object_types TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

    @staticmethod
    def _create_rule_type_definitions_table(conn) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rule_type_definitions (
                type_id TEXT PRIMARY KEY,
                ontology_id TEXT NOT NULL,
                version_id TEXT,
                name TEXT NOT NULL,
                display_name TEXT,
                description TEXT DEFAULT '',
                condition_schema TEXT DEFAULT '{}',
                consequence_schema TEXT DEFAULT '{}',
                priority_levels TEXT DEFAULT '["low","medium","high"]',
                related_object_types TEXT DEFAULT '[]',
                created_at TEXT NOT NULL
            )
        """)

    @staticmethod
    def _create_function_type_definitions_table(conn) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS function_type_definitions (
                type_id TEXT PRIMARY KEY,
                ontology_id TEXT NOT NULL,
                version_id TEXT,
                name TEXT NOT NULL,
                display_name TEXT,
                description TEXT DEFAULT '',
                logic_types TEXT DEFAULT '["filter","transform","validate","compute"]',
                expression_schema TEXT DEFAULT '{}',
                related_object_types TEXT DEFAULT '[]',
                created_at TEXT NOT NULL
            )
        """)

    @staticmethod
    def _create_indicator_type_definitions_table(conn) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS indicator_type_definitions (
                type_id TEXT PRIMARY KEY,
                ontology_id TEXT NOT NULL,
                version_id TEXT,
                name TEXT NOT NULL,
                display_name TEXT,
                description TEXT DEFAULT '',
                indicator_types TEXT DEFAULT '["kpi","metric","dimension"]',
                formula_schema TEXT DEFAULT '{}',
                allowed_units TEXT DEFAULT '[]',
                related_object_types TEXT DEFAULT '[]',
                created_at TEXT NOT NULL
            )
        """)

    @staticmethod
    def _create_database_connections_table(conn) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS database_connections (
                connection_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                db_type TEXT NOT NULL,
                host TEXT DEFAULT 'localhost',
                port INTEGER,
                database TEXT NOT NULL,
                username TEXT,
                password_encrypted TEXT,
                workspace_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

    @staticmethod
    def _create_extraction_sessions_table(conn) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS extraction_sessions (
                session_id TEXT PRIMARY KEY,
                ontology_id TEXT NOT NULL,
                extraction_type TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                input_data TEXT,
                result_data TEXT,
                conflicts TEXT DEFAULT '[]',
                created_at TEXT NOT NULL
            )
        """)

    @staticmethod
    def _create_indexes(conn) -> None:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ontologies_workspace "
            "ON ontologies(workspace_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ontologies_status "
            "ON ontologies(status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_schema_versions_ontology "
            "ON ontology_schema_versions(ontology_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_object_types_ontology "
            "ON object_type_definitions(ontology_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_object_types_version "
            "ON object_type_definitions(version_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_link_types_ontology "
            "ON link_type_definitions(ontology_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_action_types_ontology "
            "ON action_type_definitions(ontology_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_process_types_ontology "
            "ON process_type_definitions(ontology_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rule_types_ontology "
            "ON rule_type_definitions(ontology_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_function_types_ontology "
            "ON function_type_definitions(ontology_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_indicator_types_ontology "
            "ON indicator_type_definitions(ontology_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_db_connections_workspace "
            "ON database_connections(workspace_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_extraction_sessions_ontology "
            "ON extraction_sessions(ontology_id)"
        )

    # ------------------------------------------------------------------
    # 行解析辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_ontology_row(row) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        return dict(row)

    @staticmethod
    def _parse_schema_version_row(row) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        d = dict(row)
        d["is_stable"] = bool(d.get("is_stable", 0))
        d["schema_snapshot"] = _safe_json_loads(d.get("schema_snapshot"), None)
        return d

    @staticmethod
    def _parse_object_type_row(row) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        d = dict(row)
        d["properties"] = _safe_json_loads(d.get("properties"), [])
        d["links"] = _safe_json_loads(d.get("links"), [])
        d["actions"] = _safe_json_loads(d.get("actions"), [])
        d["primary_key"] = _safe_json_loads(d.get("primary_key"), [])
        d["is_active"] = bool(d.get("is_active", 1))
        return d

    @staticmethod
    def _parse_link_type_row(row) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        d = dict(row)
        d["is_bidirectional"] = bool(d.get("is_bidirectional", 0))
        return d

    @staticmethod
    def _parse_action_type_row(row) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        d = dict(row)
        d["parameters"] = _safe_json_loads(d.get("parameters"), [])
        d["required_roles"] = _safe_json_loads(d.get("required_roles"), [])
        d["confirmation_required"] = bool(d.get("confirmation_required", 1))
        return d

    @staticmethod
    def _parse_process_type_row(row) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        d = dict(row)
        d["flow_node_schema"] = _safe_json_loads(d.get("flow_node_schema"), [])
        d["related_object_types"] = _safe_json_loads(d.get("related_object_types"), [])
        return d

    @staticmethod
    def _parse_rule_type_row(row) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        d = dict(row)
        d["condition_schema"] = _safe_json_loads(d.get("condition_schema"), {})
        d["consequence_schema"] = _safe_json_loads(d.get("consequence_schema"), {})
        d["priority_levels"] = _safe_json_loads(
            d.get("priority_levels"), ["low", "medium", "high"]
        )
        d["related_object_types"] = _safe_json_loads(d.get("related_object_types"), [])
        return d

    @staticmethod
    def _parse_function_type_row(row) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        d = dict(row)
        d["logic_types"] = _safe_json_loads(
            d.get("logic_types"), ["filter", "transform", "validate", "compute"]
        )
        d["expression_schema"] = _safe_json_loads(d.get("expression_schema"), {})
        d["related_object_types"] = _safe_json_loads(d.get("related_object_types"), [])
        return d

    @staticmethod
    def _parse_indicator_type_row(row) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        d = dict(row)
        d["indicator_types"] = _safe_json_loads(
            d.get("indicator_types"), ["kpi", "metric", "dimension"]
        )
        d["formula_schema"] = _safe_json_loads(d.get("formula_schema"), {})
        d["allowed_units"] = _safe_json_loads(d.get("allowed_units"), [])
        d["related_object_types"] = _safe_json_loads(d.get("related_object_types"), [])
        return d

    @staticmethod
    def _parse_extraction_session_row(row) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        d = dict(row)
        d["input_data"] = _safe_json_loads(d.get("input_data"), None)
        d["result_data"] = _safe_json_loads(d.get("result_data"), None)
        d["conflicts"] = _safe_json_loads(d.get("conflicts"), [])
        return d

    # ==================================================================
    # ontologies CRUD
    # ==================================================================

    def save_ontology(self, ontology: Dict[str, Any]) -> Dict[str, Any]:
        """保存或更新本体（INSERT OR REPLACE），自动生成 ontology_id 和时间戳"""
        now = self._now()
        ontology_id = ontology.get("ontology_id") or str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO ontologies
                (ontology_id, name, description, workspace_id, scenario_id,
                 current_version, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ontology_id,
                    ontology.get("name", ""),
                    ontology.get("description", ""),
                    ontology.get("workspace_id", ""),
                    ontology.get("scenario_id"),
                    ontology.get("current_version", "v0.1.0"),
                    ontology.get("status", "DRAFT"),
                    ontology.get("created_at", now),
                    ontology.get("updated_at", now),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_ontology(ontology_id)

    def get_ontology(self, ontology_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM ontologies WHERE ontology_id = ?",
                (ontology_id,),
            ).fetchone()
            return self._parse_ontology_row(row)
        finally:
            conn.close()

    def list_ontologies(self, workspace_id: str = None) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            if workspace_id:
                rows = conn.execute(
                    "SELECT * FROM ontologies WHERE workspace_id = ? ORDER BY created_at DESC",
                    (workspace_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM ontologies ORDER BY created_at DESC"
                ).fetchall()
            return [self._parse_ontology_row(r) for r in rows]
        finally:
            conn.close()

    def delete_ontology(self, ontology_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM ontologies WHERE ontology_id = ?",
                (ontology_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ==================================================================
    # ontology_schema_versions CRUD
    # ==================================================================

    def save_schema_version(self, version: Dict[str, Any]) -> Dict[str, Any]:
        """保存或更新 Schema 版本（INSERT OR REPLACE），自动生成 version_id 和时间戳"""
        now = self._now()
        version_id = version.get("version_id") or str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO ontology_schema_versions
                (version_id, ontology_id, version_number, parent_version_id,
                 is_stable, changelog, schema_snapshot, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    version.get("ontology_id", ""),
                    version.get("version_number", ""),
                    version.get("parent_version_id"),
                    1 if version.get("is_stable", False) else 0,
                    version.get("changelog", ""),
                    json.dumps(version.get("schema_snapshot"), ensure_ascii=False)
                    if version.get("schema_snapshot") is not None
                    else None,
                    version.get("created_at", now),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_schema_version(version_id)

    def get_schema_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM ontology_schema_versions WHERE version_id = ?",
                (version_id,),
            ).fetchone()
            return self._parse_schema_version_row(row)
        finally:
            conn.close()

    def list_schema_versions(self, ontology_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM ontology_schema_versions WHERE ontology_id = ? ORDER BY created_at DESC",
                (ontology_id,),
            ).fetchall()
            return [self._parse_schema_version_row(r) for r in rows]
        finally:
            conn.close()

    def delete_schema_version(self, version_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM ontology_schema_versions WHERE version_id = ?",
                (version_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ==================================================================
    # object_type_definitions CRUD
    # ==================================================================

    def save_object_type(self, obj_type: Dict[str, Any]) -> Dict[str, Any]:
        """保存或更新对象类型定义（INSERT OR REPLACE），自动生成 type_id 和时间戳"""
        now = self._now()
        type_id = obj_type.get("type_id") or str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO object_type_definitions
                (type_id, ontology_id, version_id, name, display_name, description,
                 properties, links, actions, primary_key, classification_level,
                 icon, color, is_active, parent_type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    type_id,
                    obj_type.get("ontology_id", ""),
                    obj_type.get("version_id"),
                    obj_type.get("name", ""),
                    obj_type.get("display_name"),
                    obj_type.get("description", ""),
                    json.dumps(obj_type.get("properties", []), ensure_ascii=False),
                    json.dumps(obj_type.get("links", []), ensure_ascii=False),
                    json.dumps(obj_type.get("actions", []), ensure_ascii=False),
                    json.dumps(obj_type.get("primary_key", []), ensure_ascii=False),
                    obj_type.get("classification_level", "U"),
                    obj_type.get("icon"),
                    obj_type.get("color"),
                    1 if obj_type.get("is_active", True) else 0,
                    obj_type.get("parent_type"),
                    obj_type.get("created_at", now),
                    obj_type.get("updated_at", now),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_object_type(type_id)

    def get_object_type(self, type_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM object_type_definitions WHERE type_id = ?",
                (type_id,),
            ).fetchone()
            return self._parse_object_type_row(row)
        finally:
            conn.close()

    def list_object_types(self, ontology_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM object_type_definitions WHERE ontology_id = ? ORDER BY created_at DESC",
                (ontology_id,),
            ).fetchall()
            return [self._parse_object_type_row(r) for r in rows]
        finally:
            conn.close()

    def list_object_types_by_version(self, version_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM object_type_definitions WHERE version_id = ? ORDER BY created_at DESC",
                (version_id,),
            ).fetchall()
            return [self._parse_object_type_row(r) for r in rows]
        finally:
            conn.close()

    def delete_object_type(self, type_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM object_type_definitions WHERE type_id = ?",
                (type_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ==================================================================
    # link_type_definitions CRUD
    # ==================================================================

    def save_link_type(self, link_type: Dict[str, Any]) -> Dict[str, Any]:
        """保存或更新关系类型定义（INSERT OR REPLACE），自动生成 link_id 和时间戳"""
        now = self._now()
        link_id = link_type.get("link_id") or str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO link_type_definitions
                (link_id, ontology_id, version_id, name, display_name,
                 source_type, target_type, cardinality, link_type,
                 is_bidirectional, reverse_name, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    link_id,
                    link_type.get("ontology_id", ""),
                    link_type.get("version_id"),
                    link_type.get("name", ""),
                    link_type.get("display_name"),
                    link_type.get("source_type", ""),
                    link_type.get("target_type", ""),
                    link_type.get("cardinality", "ONE_TO_MANY"),
                    link_type.get("link_type", "ASSOCIATION"),
                    1 if link_type.get("is_bidirectional", False) else 0,
                    link_type.get("reverse_name"),
                    link_type.get("description", ""),
                    link_type.get("created_at", now),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_link_type(link_id)

    def get_link_type(self, link_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM link_type_definitions WHERE link_id = ?",
                (link_id,),
            ).fetchone()
            return self._parse_link_type_row(row)
        finally:
            conn.close()

    def list_link_types(self, ontology_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM link_type_definitions WHERE ontology_id = ? ORDER BY created_at DESC",
                (ontology_id,),
            ).fetchall()
            return [self._parse_link_type_row(r) for r in rows]
        finally:
            conn.close()

    def list_link_types_by_version(self, version_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM link_type_definitions WHERE version_id = ? ORDER BY created_at DESC",
                (version_id,),
            ).fetchall()
            return [self._parse_link_type_row(r) for r in rows]
        finally:
            conn.close()

    def delete_link_type(self, link_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM link_type_definitions WHERE link_id = ?",
                (link_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ==================================================================
    # action_type_definitions CRUD
    # ==================================================================

    def save_action_type(self, action_type: Dict[str, Any]) -> Dict[str, Any]:
        """保存或更新动作类型定义（INSERT OR REPLACE），自动生成 action_type_id 和时间戳"""
        now = self._now()
        action_type_id = action_type.get("action_type_id") or str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO action_type_definitions
                (action_type_id, ontology_id, version_id, name, display_name,
                 description, target_object_type, parameters, required_roles,
                 confirmation_required, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action_type_id,
                    action_type.get("ontology_id", ""),
                    action_type.get("version_id"),
                    action_type.get("name", ""),
                    action_type.get("display_name"),
                    action_type.get("description", ""),
                    action_type.get("target_object_type", ""),
                    json.dumps(action_type.get("parameters", []), ensure_ascii=False),
                    json.dumps(action_type.get("required_roles", []), ensure_ascii=False),
                    1 if action_type.get("confirmation_required", True) else 0,
                    action_type.get("created_at", now),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_action_type(action_type_id)

    def get_action_type(self, action_type_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM action_type_definitions WHERE action_type_id = ?",
                (action_type_id,),
            ).fetchone()
            return self._parse_action_type_row(row)
        finally:
            conn.close()

    def list_action_types(self, ontology_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM action_type_definitions WHERE ontology_id = ? ORDER BY created_at DESC",
                (ontology_id,),
            ).fetchall()
            return [self._parse_action_type_row(r) for r in rows]
        finally:
            conn.close()

    def list_action_types_by_version(self, version_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM action_type_definitions WHERE version_id = ? ORDER BY created_at DESC",
                (version_id,),
            ).fetchall()
            return [self._parse_action_type_row(r) for r in rows]
        finally:
            conn.close()

    def delete_action_type(self, action_type_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM action_type_definitions WHERE action_type_id = ?",
                (action_type_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ==================================================================
    # process_type_definitions CRUD
    # ==================================================================

    def save_process_type(self, process_type: Dict[str, Any]) -> Dict[str, Any]:
        """保存或更新业务过程类型定义（INSERT OR REPLACE），自动生成 type_id 和时间戳"""
        now = self._now()
        type_id = process_type.get("type_id") or str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO process_type_definitions
                (type_id, ontology_id, version_id, name, display_name, description,
                 flow_node_schema, related_object_types, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    type_id,
                    process_type.get("ontology_id", ""),
                    process_type.get("version_id"),
                    process_type.get("name", ""),
                    process_type.get("display_name"),
                    process_type.get("description", ""),
                    json.dumps(process_type.get("flow_node_schema", []), ensure_ascii=False),
                    json.dumps(process_type.get("related_object_types", []), ensure_ascii=False),
                    process_type.get("created_at", now),
                    process_type.get("updated_at", now),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_process_type(type_id)

    def get_process_type(self, type_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM process_type_definitions WHERE type_id = ?",
                (type_id,),
            ).fetchone()
            return self._parse_process_type_row(row)
        finally:
            conn.close()

    def list_process_types(self, ontology_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM process_type_definitions WHERE ontology_id = ? ORDER BY created_at DESC",
                (ontology_id,),
            ).fetchall()
            return [self._parse_process_type_row(r) for r in rows]
        finally:
            conn.close()

    def list_process_types_by_version(self, version_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM process_type_definitions WHERE version_id = ? ORDER BY created_at DESC",
                (version_id,),
            ).fetchall()
            return [self._parse_process_type_row(r) for r in rows]
        finally:
            conn.close()

    def delete_process_type(self, type_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM process_type_definitions WHERE type_id = ?",
                (type_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ==================================================================
    # rule_type_definitions CRUD
    # ==================================================================

    def save_rule_type(self, rule_type: Dict[str, Any]) -> Dict[str, Any]:
        """保存或更新规则类型定义（INSERT OR REPLACE），自动生成 type_id 和时间戳"""
        now = self._now()
        type_id = rule_type.get("type_id") or str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO rule_type_definitions
                (type_id, ontology_id, version_id, name, display_name, description,
                 condition_schema, consequence_schema, priority_levels,
                 related_object_types, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    type_id,
                    rule_type.get("ontology_id", ""),
                    rule_type.get("version_id"),
                    rule_type.get("name", ""),
                    rule_type.get("display_name"),
                    rule_type.get("description", ""),
                    json.dumps(rule_type.get("condition_schema", {}), ensure_ascii=False),
                    json.dumps(rule_type.get("consequence_schema", {}), ensure_ascii=False),
                    json.dumps(
                        rule_type.get("priority_levels", ["low", "medium", "high"]),
                        ensure_ascii=False,
                    ),
                    json.dumps(rule_type.get("related_object_types", []), ensure_ascii=False),
                    rule_type.get("created_at", now),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_rule_type(type_id)

    def get_rule_type(self, type_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM rule_type_definitions WHERE type_id = ?",
                (type_id,),
            ).fetchone()
            return self._parse_rule_type_row(row)
        finally:
            conn.close()

    def list_rule_types(self, ontology_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM rule_type_definitions WHERE ontology_id = ? ORDER BY created_at DESC",
                (ontology_id,),
            ).fetchall()
            return [self._parse_rule_type_row(r) for r in rows]
        finally:
            conn.close()

    def list_rule_types_by_version(self, version_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM rule_type_definitions WHERE version_id = ? ORDER BY created_at DESC",
                (version_id,),
            ).fetchall()
            return [self._parse_rule_type_row(r) for r in rows]
        finally:
            conn.close()

    def delete_rule_type(self, type_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM rule_type_definitions WHERE type_id = ?",
                (type_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ==================================================================
    # function_type_definitions CRUD
    # ==================================================================

    def save_function_type(self, function_type: Dict[str, Any]) -> Dict[str, Any]:
        """保存或更新逻辑函数类型定义（INSERT OR REPLACE），自动生成 type_id 和时间戳"""
        now = self._now()
        type_id = function_type.get("type_id") or str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO function_type_definitions
                (type_id, ontology_id, version_id, name, display_name, description,
                 logic_types, expression_schema, related_object_types, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    type_id,
                    function_type.get("ontology_id", ""),
                    function_type.get("version_id"),
                    function_type.get("name", ""),
                    function_type.get("display_name"),
                    function_type.get("description", ""),
                    json.dumps(
                        function_type.get("logic_types", ["filter", "transform", "validate", "compute"]),
                        ensure_ascii=False,
                    ),
                    json.dumps(function_type.get("expression_schema", {}), ensure_ascii=False),
                    json.dumps(function_type.get("related_object_types", []), ensure_ascii=False),
                    function_type.get("created_at", now),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_function_type(type_id)

    def get_function_type(self, type_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM function_type_definitions WHERE type_id = ?",
                (type_id,),
            ).fetchone()
            return self._parse_function_type_row(row)
        finally:
            conn.close()

    def list_function_types(self, ontology_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM function_type_definitions WHERE ontology_id = ? ORDER BY created_at DESC",
                (ontology_id,),
            ).fetchall()
            return [self._parse_function_type_row(r) for r in rows]
        finally:
            conn.close()

    def list_function_types_by_version(self, version_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM function_type_definitions WHERE version_id = ? ORDER BY created_at DESC",
                (version_id,),
            ).fetchall()
            return [self._parse_function_type_row(r) for r in rows]
        finally:
            conn.close()

    def delete_function_type(self, type_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM function_type_definitions WHERE type_id = ?",
                (type_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ==================================================================
    # indicator_type_definitions CRUD
    # ==================================================================

    def save_indicator_type(self, indicator_type: Dict[str, Any]) -> Dict[str, Any]:
        """保存或更新指标类型定义（INSERT OR REPLACE），自动生成 type_id 和时间戳"""
        now = self._now()
        type_id = indicator_type.get("type_id") or str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO indicator_type_definitions
                (type_id, ontology_id, version_id, name, display_name, description,
                 indicator_types, formula_schema, allowed_units,
                 related_object_types, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    type_id,
                    indicator_type.get("ontology_id", ""),
                    indicator_type.get("version_id"),
                    indicator_type.get("name", ""),
                    indicator_type.get("display_name"),
                    indicator_type.get("description", ""),
                    json.dumps(
                        indicator_type.get("indicator_types", ["kpi", "metric", "dimension"]),
                        ensure_ascii=False,
                    ),
                    json.dumps(indicator_type.get("formula_schema", {}), ensure_ascii=False),
                    json.dumps(indicator_type.get("allowed_units", []), ensure_ascii=False),
                    json.dumps(indicator_type.get("related_object_types", []), ensure_ascii=False),
                    indicator_type.get("created_at", now),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_indicator_type(type_id)

    def get_indicator_type(self, type_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM indicator_type_definitions WHERE type_id = ?",
                (type_id,),
            ).fetchone()
            return self._parse_indicator_type_row(row)
        finally:
            conn.close()

    def list_indicator_types(self, ontology_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM indicator_type_definitions WHERE ontology_id = ? ORDER BY created_at DESC",
                (ontology_id,),
            ).fetchall()
            return [self._parse_indicator_type_row(r) for r in rows]
        finally:
            conn.close()

    def list_indicator_types_by_version(self, version_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM indicator_type_definitions WHERE version_id = ? ORDER BY created_at DESC",
                (version_id,),
            ).fetchall()
            return [self._parse_indicator_type_row(r) for r in rows]
        finally:
            conn.close()

    def delete_indicator_type(self, type_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM indicator_type_definitions WHERE type_id = ?",
                (type_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ==================================================================
    # Batch delete by ontology_id (for cascade delete and rollback)
    # ==================================================================

    def delete_object_types_by_ontology(self, ontology_id: str) -> int:
        """删除指定本体的所有对象类型定义"""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM object_type_definitions WHERE ontology_id = ?",
                (ontology_id,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def delete_link_types_by_ontology(self, ontology_id: str) -> int:
        """删除指定本体的所有关系类型定义"""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM link_type_definitions WHERE ontology_id = ?",
                (ontology_id,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def delete_action_types_by_ontology(self, ontology_id: str) -> int:
        """删除指定本体的所有动作类型定义"""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM action_type_definitions WHERE ontology_id = ?",
                (ontology_id,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def delete_process_types_by_ontology(self, ontology_id: str) -> int:
        """删除指定本体的所有业务过程类型定义"""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM process_type_definitions WHERE ontology_id = ?",
                (ontology_id,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def delete_rule_types_by_ontology(self, ontology_id: str) -> int:
        """删除指定本体的所有规则类型定义"""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM rule_type_definitions WHERE ontology_id = ?",
                (ontology_id,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def delete_function_types_by_ontology(self, ontology_id: str) -> int:
        """删除指定本体的所有逻辑函数类型定义"""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM function_type_definitions WHERE ontology_id = ?",
                (ontology_id,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def delete_indicator_types_by_ontology(self, ontology_id: str) -> int:
        """删除指定本体的所有指标类型定义"""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM indicator_type_definitions WHERE ontology_id = ?",
                (ontology_id,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def delete_schema_versions_by_ontology(self, ontology_id: str) -> int:
        """删除指定本体的所有 Schema 版本"""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM ontology_schema_versions WHERE ontology_id = ?",
                (ontology_id,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def delete_extraction_sessions_by_ontology(self, ontology_id: str) -> int:
        """删除指定本体的所有抽取会话"""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM extraction_sessions WHERE ontology_id = ?",
                (ontology_id,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    # ==================================================================
    # database_connections CRUD
    # ==================================================================

    def save_database_connection(self, conn_data: Dict[str, Any]) -> Dict[str, Any]:
        """保存或更新数据库连接配置（INSERT OR REPLACE），自动生成 connection_id 和时间戳"""
        now = self._now()
        connection_id = conn_data.get("connection_id") or str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO database_connections
                (connection_id, name, db_type, host, port, database,
                 username, password_encrypted, workspace_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    connection_id,
                    conn_data.get("name", ""),
                    conn_data.get("db_type", ""),
                    conn_data.get("host", "localhost"),
                    conn_data.get("port"),
                    conn_data.get("database", ""),
                    conn_data.get("username"),
                    self._encrypt_password(conn_data.get("password_encrypted", "")) if conn_data.get("password_encrypted") else None,
                    conn_data.get("workspace_id", ""),
                    conn_data.get("created_at", now),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        result = self.get_database_connection(connection_id)
        return result

    def get_database_connection(self, connection_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM database_connections WHERE connection_id = ?",
                (connection_id,),
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            if result.get("password_encrypted"):
                result["password_encrypted"] = self._decrypt_password(result["password_encrypted"])
            return result
        finally:
            conn.close()

    def list_database_connections(self, workspace_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM database_connections WHERE workspace_id = ? ORDER BY created_at DESC",
                (workspace_id,),
            ).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                if d.get("password_encrypted"):
                    d["password_encrypted"] = self._decrypt_password(d["password_encrypted"])
                results.append(d)
            return results
        finally:
            conn.close()

    def delete_database_connection(self, connection_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM database_connections WHERE connection_id = ?",
                (connection_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ==================================================================
    # extraction_sessions CRUD
    # ==================================================================

    def save_extraction_session(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """保存或更新抽取会话（INSERT OR REPLACE），自动生成 session_id 和时间戳"""
        now = self._now()
        session_id = session.get("session_id") or str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO extraction_sessions
                (session_id, ontology_id, extraction_type, status,
                 input_data, result_data, conflicts, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    session.get("ontology_id", ""),
                    session.get("extraction_type", ""),
                    session.get("status", "pending"),
                    json.dumps(session.get("input_data"), ensure_ascii=False)
                    if session.get("input_data") is not None
                    else None,
                    json.dumps(session.get("result_data"), ensure_ascii=False)
                    if session.get("result_data") is not None
                    else None,
                    json.dumps(session.get("conflicts", []), ensure_ascii=False),
                    session.get("created_at", now),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_extraction_session(session_id)

    def get_extraction_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM extraction_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            return self._parse_extraction_session_row(row)
        finally:
            conn.close()

    def update_extraction_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """部分更新抽取会话（仅更新传入的字段）"""
        existing = self.get_extraction_session(session_id)
        if not existing:
            return False

        # 构建动态 SET 子句
        set_clauses = []
        params = []
        allowed_fields = {
            "extraction_type", "status", "input_data", "result_data", "conflicts",
        }
        for field in allowed_fields:
            if field in updates:
                set_clauses.append(f"{field} = ?")
                value = updates[field]
                # JSON 字段需要序列化
                if field in ("input_data", "result_data", "conflicts"):
                    if value is not None:
                        value = json.dumps(value, ensure_ascii=False)
                params.append(value)

        if not set_clauses:
            return True  # 无需更新

        params.append(session_id)
        conn = self._get_conn()
        try:
            conn.execute(
                f"UPDATE extraction_sessions SET {', '.join(set_clauses)} WHERE session_id = ?",
                params,
            )
            conn.commit()
        finally:
            conn.close()
        return True

    def list_extraction_sessions(self, ontology_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM extraction_sessions WHERE ontology_id = ? ORDER BY created_at DESC",
                (ontology_id,),
            ).fetchall()
            return [self._parse_extraction_session_row(r) for r in rows]
        finally:
            conn.close()

    def delete_extraction_session(self, session_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM extraction_sessions WHERE session_id = ?",
                (session_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
