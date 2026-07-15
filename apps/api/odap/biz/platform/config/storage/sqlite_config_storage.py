"""SQLite 配置存储实现"""

import os
import json
import sqlite3
import logging
from typing import Dict, List, Optional, Any

from odap.biz.platform.config.interfaces.config_repository import ConfigRepository
from odap.infra.security.config_encryption import get_encryption

logger = logging.getLogger(__name__)


class SQLiteConfigStorage(ConfigRepository):
    """SQLite 配置持久化存储"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "config.db"
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._encryption = get_encryption()
        self._init_db()
        self._register_predefined_schemas()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        conn = self._connect()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS config_items (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    value_type TEXT NOT NULL DEFAULT 'string',
                    category TEXT NOT NULL DEFAULT 'general',
                    label TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    is_sensitive INTEGER NOT NULL DEFAULT 0,
                    is_required INTEGER NOT NULL DEFAULT 0,
                    default_value TEXT,
                    choices TEXT,
                    min_val REAL,
                    max_val REAL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    config_group TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    updated_by TEXT
                );

                CREATE TABLE IF NOT EXISTS config_revisions (
                    id TEXT PRIMARY KEY,
                    revision_number INTEGER NOT NULL UNIQUE,
                    operator_id TEXT NOT NULL,
                    operator_name TEXT NOT NULL DEFAULT '',
                    changed_at TEXT NOT NULL,
                    changes TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS config_schema_registry (
                    key TEXT PRIMARY KEY,
                    value_type TEXT NOT NULL DEFAULT 'string',
                    category TEXT NOT NULL DEFAULT 'general',
                    label TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    is_sensitive INTEGER NOT NULL DEFAULT 0,
                    is_required INTEGER NOT NULL DEFAULT 0,
                    default_value TEXT,
                    choices TEXT,
                    min_val REAL,
                    max_val REAL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    config_group TEXT NOT NULL DEFAULT '',
                    env_mapping TEXT
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def _register_predefined_schemas(self):
        """注册预定义配置项 schema"""
        from odap.biz.platform.config.models.config_models import PREDEFINED_CONFIG_ITEMS
        for item in PREDEFINED_CONFIG_ITEMS:
            self.register_schema(item)

    def register_schema(self, item: Dict[str, Any]) -> None:
        conn = self._connect()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO config_schema_registry
                (key, value_type, category, label, description, is_sensitive,
                 is_required, default_value, choices, min_val, max_val,
                 sort_order, config_group, env_mapping)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item["key"], item.get("value_type", "string"),
                item.get("category", "general"), item.get("label", ""),
                item.get("description", ""), int(item.get("is_sensitive", False)),
                int(item.get("is_required", False)), item.get("default_value"),
                json.dumps(item.get("choices", []), ensure_ascii=False) if item.get("choices") else None,
                item.get("min_val"), item.get("max_val"),
                item.get("sort_order", 0), item.get("group", ""),
                item.get("env_mapping"),
            ))
            conn.commit()
        finally:
            conn.close()

    def list_schemas(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            if category:
                rows = conn.execute(
                    "SELECT * FROM config_schema_registry WHERE category = ? ORDER BY sort_order",
                    (category,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM config_schema_registry ORDER BY category, sort_order"
                ).fetchall()
            cols = [d[0] for d in conn.execute("SELECT * FROM config_schema_registry LIMIT 0").description]
            results = [dict(zip(cols, row)) for row in rows]
            for item in results:
                if isinstance(item.get('choices'), str):
                    try:
                        item['choices'] = json.loads(item['choices'])
                    except (json.JSONDecodeError, TypeError):
                        item['choices'] = []
            return results
        finally:
            conn.close()

    def get_schema(self, key: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM config_schema_registry WHERE key = ?", (key,)).fetchone()
            if not row:
                return None
            cols = [d[0] for d in conn.execute("SELECT * FROM config_schema_registry LIMIT 0").description]
            result = dict(zip(cols, row))
            if isinstance(result.get('choices'), str):
                try:
                    result['choices'] = json.loads(result['choices'])
                except (json.JSONDecodeError, TypeError):
                    result['choices'] = []
            return result
        finally:
            conn.close()

    def save_config(self, key: str, value: str, updated_by: str = "") -> None:
        schema = self.get_schema(key)
        is_sensitive = schema.get("is_sensitive", 0) if schema else 0

        # 加密敏感值
        stored_value = value
        if is_sensitive and value and self._encryption.available:
            stored_value = self._encryption.encrypt(value)

        conn = self._connect()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO config_items
                (key, value, value_type, category, label, description,
                 is_sensitive, is_required, default_value, choices, min_val, max_val,
                 sort_order, config_group, updated_at, updated_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
            """, (
                key, stored_value,
                schema.get("value_type", "string") if schema else "string",
                schema.get("category", "general") if schema else "general",
                schema.get("label", "") if schema else "",
                schema.get("description", "") if schema else "",
                is_sensitive,
                schema.get("is_required", 0) if schema else 0,
                schema.get("default_value") if schema else None,
                schema.get("choices") if schema else None,
                schema.get("min_val") if schema else None,
                schema.get("max_val") if schema else None,
                schema.get("sort_order", 0) if schema else 0,
                schema.get("config_group", "") if schema else "",
                updated_by,
            ))
            conn.commit()
        finally:
            conn.close()

    def get_config(self, key: str) -> Optional[str]:
        raw = self.get_raw_config(key)
        if raw is None:
            return None
        # 检查是否需要解密
        schema = self.get_schema(key)
        is_sensitive = schema.get("is_sensitive", 0) if schema else 0
        if is_sensitive and self._encryption.available and self._encryption.is_encrypted(raw):
            return self._encryption.decrypt(raw)
        return raw

    def get_raw_config(self, key: str) -> Optional[str]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT value FROM config_items WHERE key = ?", (key,)).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def list_configs(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            if category:
                rows = conn.execute(
                    "SELECT * FROM config_items WHERE category = ? ORDER BY sort_order",
                    (category,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM config_items ORDER BY category, sort_order"
                ).fetchall()
            cols = [d[0] for d in conn.execute("SELECT * FROM config_items LIMIT 0").description]
            results = []
            for row in rows:
                item = dict(zip(cols, row))
                # 解密敏感值用于内部读取
                if item.get("is_sensitive") and item.get("value") and self._encryption.available and self._encryption.is_encrypted(item["value"]):
                    item["value"] = self._encryption.decrypt(item["value"])
                # 生成脱敏展示值
                if item.get("is_sensitive") and item.get("value"):
                    item["display_value"] = self._encryption.mask_value(item["value"])
                else:
                    item["display_value"] = item.get("value")
                item["has_value"] = item.get("value") is not None
                if isinstance(item.get("choices"), str):
                    try:
                        item["choices"] = json.loads(item["choices"])
                    except (json.JSONDecodeError, TypeError):
                        item["choices"] = []
                results.append(item)
            return results
        finally:
            conn.close()

    def delete_config(self, key: str) -> bool:
        conn = self._connect()
        try:
            cursor = conn.execute("DELETE FROM config_items WHERE key = ?", (key,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def save_revision(self, revision: Dict[str, Any]) -> None:
        conn = self._connect()
        try:
            conn.execute("""
                INSERT INTO config_revisions (id, revision_number, operator_id, operator_name, changed_at, changes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                revision["id"], revision["revision_number"],
                revision["operator_id"], revision["operator_name"],
                revision["changed_at"],
                json.dumps(revision["changes"], ensure_ascii=False),
            ))
            conn.commit()
        finally:
            conn.close()

    def list_revisions(self, category: Optional[str] = None, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        conn = self._connect()
        try:
            if category:
                count_row = conn.execute(
                    "SELECT COUNT(*) FROM config_revisions WHERE changes LIKE ?",
                    (f'%{category}%',)
                ).fetchone()
                rows = conn.execute(
                    "SELECT * FROM config_revisions WHERE changes LIKE ? ORDER BY revision_number DESC LIMIT ? OFFSET ?",
                    (f'%{category}%', limit, offset)
                ).fetchall()
            else:
                count_row = conn.execute("SELECT COUNT(*) FROM config_revisions").fetchone()
                rows = conn.execute(
                    "SELECT * FROM config_revisions ORDER BY revision_number DESC LIMIT ? OFFSET ?",
                    (limit, offset)
                ).fetchall()
            cols = [d[0] for d in conn.execute("SELECT * FROM config_revisions LIMIT 0").description]
            revisions = []
            for row in rows:
                rev = dict(zip(cols, row))
                if isinstance(rev.get("changes"), str):
                    rev["changes"] = json.loads(rev["changes"])
                revisions.append(rev)
            return {"revisions": revisions, "total": count_row[0]}
        finally:
            conn.close()

    def get_revision(self, revision_number: int) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM config_revisions WHERE revision_number = ?",
                (revision_number,)
            ).fetchone()
            if not row:
                return None
            cols = [d[0] for d in conn.execute("SELECT * FROM config_revisions LIMIT 0").description]
            rev = dict(zip(cols, row))
            if isinstance(rev.get("changes"), str):
                rev["changes"] = json.loads(rev["changes"])
            return rev
        finally:
            conn.close()

    def get_next_revision_number(self) -> int:
        conn = self._connect()
        try:
            row = conn.execute("SELECT MAX(revision_number) FROM config_revisions").fetchone()
            return (row[0] or 0) + 1
        finally:
            conn.close()

    def load_all_to_dict(self) -> Dict[str, str]:
        """加载所有配置项为 {key: decrypted_value} 字典"""
        items = self.list_configs()
        return {item["key"]: item["value"] for item in items if item.get("value") is not None}
