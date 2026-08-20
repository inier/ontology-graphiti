"""SQLiteRuleStorage — 推理规则持久化 (ADR-075 §3.2)。

odap_business_rules 表：
- 规则随本体版本管理，version_id 关联版本。
- 版本级回滚恢复快照（事务内 DELETE + INSERT），valid_from 重写。
- Pipeline/Batch 级回滚不触碰规则（规则是 TBox）。
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models import BusinessRule, from_storage_dict, to_storage_dict

DEFAULT_RULE_DB_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
DEFAULT_RULE_DB_PATH = os.path.join(DEFAULT_RULE_DB_DIR, "business_rules.db")


class SQLiteRuleStorage:
    """推理规则 SQLite 持久化（odap_business_rules 表）"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            os.makedirs(DEFAULT_RULE_DB_DIR, exist_ok=True)
            db_path = DEFAULT_RULE_DB_PATH
        self.db_path = db_path
        self._init_db()

    # ── 建表 ──

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS odap_business_rules (
                    rule_id      TEXT PRIMARY KEY,
                    ontology_id  TEXT NOT NULL,
                    workspace_id TEXT NOT NULL DEFAULT 'default',
                    name         TEXT NOT NULL,
                    description  TEXT NOT NULL DEFAULT '',
                    rule_text    TEXT NOT NULL,
                    enabled      INTEGER NOT NULL DEFAULT 1,
                    priority     TEXT NOT NULL DEFAULT 'normal',
                    valid_from   TEXT NOT NULL,
                    created_by   TEXT NOT NULL DEFAULT 'system',
                    version_id   TEXT,
                    metadata     TEXT NOT NULL DEFAULT '{}',
                    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_business_rules_ontology
                ON odap_business_rules (ontology_id, workspace_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_business_rules_version
                ON odap_business_rules (version_id)
                """
            )
            conn.commit()
        finally:
            conn.close()

    # ── CRUD ──

    def save(self, rule: BusinessRule) -> BusinessRule:
        """保存或更新规则（upsert）"""
        d = to_storage_dict(rule)
        d["metadata"] = json.dumps(d["metadata"], ensure_ascii=False)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO odap_business_rules
                (rule_id, ontology_id, workspace_id, name, description, rule_text,
                 enabled, priority, valid_from, created_by, version_id, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    d["rule_id"], d["ontology_id"], d["workspace_id"], d["name"],
                    d["description"], d["rule_text"], d["enabled"], d["priority"],
                    d["valid_from"], d["created_by"], d["version_id"], d["metadata"],
                ),
            )
            conn.commit()
            return rule
        finally:
            conn.close()

    def get(self, rule_id: str) -> Optional[BusinessRule]:
        """根据 ID 获取规则；不存在返回 None"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM odap_business_rules WHERE rule_id = ?", (rule_id,)
            )
            row = cursor.fetchone()
            return self._row_to_rule(dict(row)) if row else None
        finally:
            conn.close()

    def list(
        self,
        ontology_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        enabled_only: bool = False,
    ) -> List[BusinessRule]:
        """列出规则；可按本体/工作空间过滤，enabled_only 仅返回启用"""
        sql = "SELECT * FROM odap_business_rules"
        clauses: List[str] = []
        params: List[Any] = []
        if ontology_id:
            clauses.append("ontology_id = ?")
            params.append(ontology_id)
        if workspace_id:
            clauses.append("workspace_id = ?")
            params.append(workspace_id)
        if enabled_only:
            clauses.append("enabled = 1")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY valid_from ASC"

        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, params)
            return [self._row_to_rule(dict(r)) for r in cursor.fetchall()]
        finally:
            conn.close()

    def list_by_version(self, version_id: str) -> List[BusinessRule]:
        """按本体版本列出规则（§3.2 版本关联）"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM odap_business_rules WHERE version_id = ? ORDER BY valid_from ASC",
                (version_id,),
            )
            return [self._row_to_rule(dict(r)) for r in cursor.fetchall()]
        finally:
            conn.close()

    def delete(self, rule_id: str) -> bool:
        """删除规则；返回是否存在并删除"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM odap_business_rules WHERE rule_id = ?", (rule_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ── 版本级回滚联动（ADR-075 §3.2）──

    def snapshot_for_version(self, version_id: str, ontology_id: str, workspace_id: str) -> int:
        """为版本创建规则快照表 odap_business_rules_snapshot_<version_id>。

        仅快照该本体/工作空间下的启用规则（valid_from 一并固化）。
        返回快照行数。幂等：已存在则先重建。
        """
        table = self._snapshot_table(version_id)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(f'DROP TABLE IF EXISTS "{table}"')
            conn.execute(
                """
                CREATE TABLE "{table}" (
                    rule_id      TEXT PRIMARY KEY,
                    ontology_id  TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    name         TEXT NOT NULL,
                    description  TEXT NOT NULL DEFAULT '',
                    rule_text    TEXT NOT NULL,
                    enabled      INTEGER NOT NULL DEFAULT 1,
                    priority     TEXT NOT NULL DEFAULT 'normal',
                    valid_from   TEXT NOT NULL,
                    created_by   TEXT NOT NULL DEFAULT 'system',
                    version_id   TEXT,
                    metadata     TEXT NOT NULL DEFAULT '{{}}'
                )
                """.format(table=table)
            )
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM odap_business_rules
                WHERE ontology_id = ? AND workspace_id = ? AND enabled = 1
                """,
                (ontology_id, workspace_id),
            )
            rows = [dict(r) for r in cursor.fetchall()]
            for r in rows:
                r["version_id"] = version_id
                conn.execute(
                    f'INSERT OR REPLACE INTO "{table}" VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                    (
                        r["rule_id"], r["ontology_id"], r["workspace_id"], r["name"],
                        r["description"], r["rule_text"], r["enabled"], r["priority"],
                        r["valid_from"], r["created_by"], r["version_id"], r["metadata"],
                    ),
                )
            conn.commit()
            return len(rows)
        finally:
            conn.close()

    def restore_version(self, version_id: str) -> int:
        """版本级回滚：恢复快照到主表（事务内 DELETE + INSERT）。

        valid_from 重写为当前 UTC 时刻（恢复动作即生效）。
        返回恢复的规则数；快照不存在返回 0。
        """
        table = self._snapshot_table(version_id)
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            )
            if cursor.fetchone() is None:
                return 0

            now = datetime.now(timezone.utc).isoformat()
            conn.execute("BEGIN")
            snapshot_rows = conn.execute(
                f'SELECT * FROM "{table}"'
            ).fetchall()
            if snapshot_rows:
                # 以快照首行的本体/工作空间为覆盖范围
                ontology_id, workspace_id = snapshot_rows[0][1], snapshot_rows[0][2]
                conn.execute(
                    "DELETE FROM odap_business_rules WHERE ontology_id = ? AND workspace_id = ?",
                    (ontology_id, workspace_id),
                )
                for r in snapshot_rows:
                    conn.execute(
                        """
                        INSERT INTO odap_business_rules
                        (rule_id, ontology_id, workspace_id, name, description, rule_text,
                         enabled, priority, valid_from, created_by, version_id, metadata)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7],
                            now, r[9], r[10], r[11],
                        ),
                    )
            conn.commit()
            return len(snapshot_rows)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── 辅助 ──

    @staticmethod
    def _snapshot_table(version_id: str) -> str:
        # version_id 为系统生成 ID，做基本净化防注入
        safe = "".join(c for c in version_id if c.isalnum() or c in "-_")
        return f"odap_business_rules_snapshot_{safe}"

    @staticmethod
    def _row_to_rule(row: Dict[str, Any]) -> BusinessRule:
        if "metadata" in row and isinstance(row["metadata"], str):
            try:
                row["metadata"] = json.loads(row["metadata"])
            except json.JSONDecodeError:
                row["metadata"] = {}
        return from_storage_dict(row)


_instance: Optional[SQLiteRuleStorage] = None


def get_rule_storage() -> SQLiteRuleStorage:
    """获取规则存储单例"""
    global _instance
    if _instance is None:
        _instance = SQLiteRuleStorage()
    return _instance


__all__ = ["SQLiteRuleStorage", "get_rule_storage", "DEFAULT_RULE_DB_PATH"]
