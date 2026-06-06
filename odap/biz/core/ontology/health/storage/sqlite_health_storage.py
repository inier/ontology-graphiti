"""Data Health - SQLite 存储层 (T336)

两张表：
- health_rules: 健康规则元数据
- health_reports: 扫描结果报告

AGENTS.md 规则 8：每次 connect/close，无连接池。
AGENTS.md 规则 5：JSON 字段用 TEXT 存储，datetime 用 ISO 字符串。
"""
from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Dict, List, Optional


DEFAULT_HEALTH_DB_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
DEFAULT_HEALTH_DB_PATH = os.path.join(DEFAULT_HEALTH_DB_DIR, "data_health.db")


class SQLiteHealthStorage:
    """健康规则与报告的 SQLite 持久化"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            os.makedirs(DEFAULT_HEALTH_DB_DIR, exist_ok=True)
            db_path = DEFAULT_HEALTH_DB_PATH
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化表结构（幂等）"""
        conn = sqlite3.connect(self.db_path)
        try:
            self._create_rules_table(conn)
            self._create_reports_table(conn)
            self._create_indexes(conn)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _create_rules_table(conn):
        """health_rules 表"""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS health_rules (
                id TEXT PRIMARY KEY,
                target_type_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                rule_type TEXT NOT NULL,
                check_expression TEXT DEFAULT '{}',
                severity TEXT NOT NULL,
                schedule TEXT DEFAULT '',
                notification_channel TEXT DEFAULT '{}',
                enabled INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    @staticmethod
    def _create_reports_table(conn):
        """health_reports 表"""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS health_reports (
                id TEXT PRIMARY KEY,
                rule_id TEXT NOT NULL,
                instance_id TEXT NOT NULL,
                target_type_id TEXT NOT NULL,
                status TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT DEFAULT '',
                details TEXT DEFAULT '{}',
                scanned_at TEXT NOT NULL
            )
            """
        )

    @staticmethod
    def _create_indexes(conn):
        """创建 3 个查询索引"""
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_health_rules_target ON health_rules(target_type_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_health_reports_rule ON health_reports(rule_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_health_reports_status ON health_reports(status)"
        )

    # ---------- health_rules CRUD ----------

    def save_rule(self, rule: Dict[str, Any]) -> None:
        """保存或更新规则（upsert）"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO health_rules
                (id, target_type_id, name, description, rule_type, check_expression,
                 severity, schedule, notification_channel, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rule.get("id", ""),
                    rule.get("target_type_id", ""),
                    rule.get("name", ""),
                    rule.get("description", ""),
                    rule.get("rule_type", "not_null"),
                    json.dumps(rule.get("check_expression", {}), ensure_ascii=False),
                    rule.get("severity", "warning"),
                    rule.get("schedule", ""),
                    json.dumps(rule.get("notification_channel", {}), ensure_ascii=False),
                    1 if rule.get("enabled", True) else 0,
                    rule.get("created_at", ""),
                    rule.get("updated_at", ""),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取规则；不存在返回 None"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM health_rules WHERE id = ?", (rule_id,))
            row = cursor.fetchone()
            return self._row_to_rule(dict(row)) if row else None
        finally:
            conn.close()

    def list_rules(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """列出所有规则；enabled_only 仅返回启用的"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            if enabled_only:
                cursor = conn.execute(
                    "SELECT * FROM health_rules WHERE enabled = 1 ORDER BY created_at DESC"
                )
            else:
                cursor = conn.execute("SELECT * FROM health_rules ORDER BY created_at DESC")
            return [self._row_to_rule(dict(r)) for r in cursor.fetchall()]
        finally:
            conn.close()

    def list_rules_by_target_type(self, target_type_id: str) -> List[Dict[str, Any]]:
        """按 target_type_id 过滤规则"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM health_rules WHERE target_type_id = ? ORDER BY created_at DESC",
                (target_type_id,),
            )
            return [self._row_to_rule(dict(r)) for r in cursor.fetchall()]
        finally:
            conn.close()

    def list_rules_by_severity(self, severity: str) -> List[Dict[str, Any]]:
        """按 severity 过滤规则"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM health_rules WHERE severity = ? ORDER BY created_at DESC",
                (severity,),
            )
            return [self._row_to_rule(dict(r)) for r in cursor.fetchall()]
        finally:
            conn.close()

    def delete_rule(self, rule_id: str) -> bool:
        """删除规则；返回是否存在并删除"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("DELETE FROM health_rules WHERE id = ?", (rule_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ---------- health_reports CRUD ----------

    def save_report(self, report: Dict[str, Any]) -> None:
        """保存扫描结果报告"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO health_reports
                (id, rule_id, instance_id, target_type_id, status, severity,
                 message, details, scanned_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.get("id", ""),
                    report.get("rule_id", ""),
                    report.get("instance_id", ""),
                    report.get("target_type_id", ""),
                    report.get("status", "pass"),
                    report.get("severity", "warning"),
                    report.get("message", ""),
                    json.dumps(report.get("details", {}), ensure_ascii=False),
                    report.get("scanned_at", ""),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取报告"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM health_reports WHERE id = ?", (report_id,))
            row = cursor.fetchone()
            return self._row_to_report(dict(row)) if row else None
        finally:
            conn.close()

    def list_reports(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        target_type_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """多条件过滤报告，支持分页"""
        clauses, params = [], []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if severity:
            clauses.append("severity = ?")
            params.append(severity)
        if target_type_id:
            clauses.append("target_type_id = ?")
            params.append(target_type_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (
            f"SELECT * FROM health_reports{where} "
            f"ORDER BY scanned_at DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, params)
            return [self._row_to_report(dict(r)) for r in cursor.fetchall()]
        finally:
            conn.close()

    def count_reports(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        target_type_id: Optional[str] = None,
    ) -> int:
        """统计报告数量"""
        clauses, params = [], []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if severity:
            clauses.append("severity = ?")
            params.append(severity)
        if target_type_id:
            clauses.append("target_type_id = ?")
            params.append(target_type_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM health_reports{where}", params
            )
            return cursor.fetchone()[0]
        finally:
            conn.close()

    # ---------- 私有工具 ----------

    @staticmethod
    def _row_to_rule(row: Dict[str, Any]) -> Dict[str, Any]:
        """将 SQLite 行转为 dict；JSON 字段反序列化"""
        row = dict(row)
        row["check_expression"] = _safe_json_loads(row.get("check_expression"), {})
        row["notification_channel"] = _safe_json_loads(row.get("notification_channel"), {})
        row["enabled"] = bool(row.get("enabled", 0))
        return row

    @staticmethod
    def _row_to_report(row: Dict[str, Any]) -> Dict[str, Any]:
        """将 SQLite 行转为 dict；JSON 字段反序列化"""
        row = dict(row)
        row["details"] = _safe_json_loads(row.get("details"), {})
        return row


def _safe_json_loads(value, default):
    """安全地解析 JSON 字符串；失败时返回 default"""
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default
