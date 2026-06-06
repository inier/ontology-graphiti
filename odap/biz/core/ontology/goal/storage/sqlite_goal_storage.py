"""SQLite Goal Storage (T421)

三张表:
- goals: Goal 元数据
- change_proposals: ChangeProposal 列表（含 JSON Patch changes）
- impact_analyses: ImpactAnalysis（受影响类型 + breaking changes）

AGENTS.md 规则 8: 每次 connect/close，无连接池。
AGENTS.md 规则 5: JSON 字段用 TEXT 存储，datetime 用 ISO 字符串，Enum 用 .value。
"""
from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Dict, List, Optional


DEFAULT_GOAL_DB_DIR = os.environ.get(
    "DATA_DIR", os.path.join(os.getcwd(), "data")
)
DEFAULT_GOAL_DB_PATH = os.path.join(DEFAULT_GOAL_DB_DIR, "goal.db")


def _safe_json_loads(value: Any, default: Any) -> Any:
    """安全地解析 JSON 字符串；失败时返回 default"""
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (int, float, bool)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _parse_dt_iso(value: Any):
    """从 ISO 字符串解析 datetime；失败时返回 None"""
    if not value:
        return None
    from datetime import datetime
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


class SQLiteGoalStorage:
    """OntoFlow Goal 的 SQLite 持久化"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            os.makedirs(DEFAULT_GOAL_DB_DIR, exist_ok=True)
            db_path = DEFAULT_GOAL_DB_PATH
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """初始化表结构（幂等）"""
        conn = sqlite3.connect(self.db_path)
        try:
            self._create_goals_table(conn)
            self._create_proposals_table(conn)
            self._create_impacts_table(conn)
            self._create_indexes(conn)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _create_goals_table(conn) -> None:
        """goals 表"""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS goals (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                business_objective TEXT NOT NULL,
                rationale TEXT DEFAULT '',
                status TEXT NOT NULL,
                parent_goal_id TEXT,
                workspace_id TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                tags TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}'
            )
            """
        )

    @staticmethod
    def _create_proposals_table(conn) -> None:
        """change_proposals 表"""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS change_proposals (
                id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                changes TEXT DEFAULT '[]',
                impact_analysis_id TEXT,
                estimated_benefit TEXT DEFAULT '',
                estimated_cost TEXT,
                status TEXT NOT NULL,
                proposed_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                reviewed_at TEXT,
                reviewer_notes TEXT
            )
            """
        )

    @staticmethod
    def _create_impacts_table(conn) -> None:
        """impact_analyses 表"""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS impact_analyses (
                id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                affected_object_types TEXT DEFAULT '[]',
                affected_action_types TEXT DEFAULT '[]',
                affected_instances_count INTEGER DEFAULT 0,
                breaking_changes TEXT DEFAULT '[]',
                estimated_migration_cost TEXT DEFAULT 'low',
                risk_level TEXT DEFAULT 'low',
                analysis_metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL
            )
            """
        )

    @staticmethod
    def _create_indexes(conn) -> None:
        """创建查询索引"""
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_goals_workspace "
            "ON goals(workspace_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_goals_status "
            "ON goals(status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_goals_parent "
            "ON goals(parent_goal_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_proposals_goal "
            "ON change_proposals(goal_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_proposals_status "
            "ON change_proposals(status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_impacts_proposal "
            "ON impact_analyses(proposal_id)"
        )

    # ---------- goals CRUD ----------

    def save_goal(self, goal: Dict[str, Any]) -> None:
        """保存 Goal (upsert)"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO goals
                (id, title, description, business_objective, rationale,
                 status, parent_goal_id, workspace_id, created_by,
                 created_at, updated_at, tags, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    goal.get("id", ""),
                    goal.get("title", ""),
                    goal.get("description", ""),
                    goal.get("business_objective", ""),
                    goal.get("rationale", "") or "",
                    goal.get("status", "proposed"),
                    goal.get("parent_goal_id"),
                    goal.get("workspace_id", ""),
                    goal.get("created_by", ""),
                    goal.get("created_at", ""),
                    goal.get("updated_at", ""),
                    json.dumps(goal.get("tags", []), ensure_ascii=False),
                    json.dumps(goal.get("metadata", {}), ensure_ascii=False),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_goal(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取 Goal；不存在返回 None"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM goals WHERE id = ?", (goal_id,)
            )
            row = cursor.fetchone()
            return self._row_to_goal(dict(row)) if row else None
        finally:
            conn.close()

    def list_goals(
        self,
        workspace_id: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """分页列出 Goal；可按 status / workspace_id 过滤"""
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        offset = (page - 1) * page_size
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            clauses: List[str] = ["workspace_id = ?"]
            params: List[Any] = [workspace_id]
            if status:
                clauses.append("status = ?")
                params.append(status)
            where_sql = " WHERE " + " AND ".join(clauses)
            count_sql = "SELECT COUNT(*) AS c FROM goals" + where_sql
            total = conn.execute(count_sql, tuple(params)).fetchone()["c"]
            list_sql = (
                "SELECT * FROM goals" + where_sql
                + " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            )
            cursor = conn.execute(
                list_sql, tuple(params) + (page_size, offset)
            )
            items = [self._row_to_goal(dict(r)) for r in cursor.fetchall()]
            return {
                "goals": items,
                "total": int(total),
                "page": int(page),
                "page_size": int(page_size),
            }
        finally:
            conn.close()

    def list_goals_by_parent(
        self, parent_goal_id: str
    ) -> List[Dict[str, Any]]:
        """列出某个父 Goal 下的所有子 Goal"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM goals WHERE parent_goal_id = ? "
                "ORDER BY created_at ASC",
                (parent_goal_id,),
            )
            return [self._row_to_goal(dict(r)) for r in cursor.fetchall()]
        finally:
            conn.close()

    def delete_goal(self, goal_id: str) -> bool:
        """删除 Goal；返回是否成功"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM goals WHERE id = ?", (goal_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ---------- change_proposals CRUD ----------

    def save_proposal(self, proposal: Dict[str, Any]) -> None:
        """保存 ChangeProposal (upsert)"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO change_proposals
                (id, goal_id, title, description, changes,
                 impact_analysis_id, estimated_benefit, estimated_cost,
                 status, proposed_by, created_at, reviewed_at,
                 reviewer_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal.get("id", ""),
                    proposal.get("goal_id", ""),
                    proposal.get("title", ""),
                    proposal.get("description", ""),
                    json.dumps(
                        proposal.get("changes", []), ensure_ascii=False
                    ),
                    proposal.get("impact_analysis_id"),
                    proposal.get("estimated_benefit", ""),
                    proposal.get("estimated_cost"),
                    proposal.get("status", "draft"),
                    proposal.get("proposed_by", ""),
                    proposal.get("created_at", ""),
                    proposal.get("reviewed_at"),
                    proposal.get("reviewer_notes"),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取 ChangeProposal；不存在返回 None"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM change_proposals WHERE id = ?",
                (proposal_id,),
            )
            row = cursor.fetchone()
            return self._row_to_proposal(dict(row)) if row else None
        finally:
            conn.close()

    def list_proposals(
        self,
        goal_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """列出 ChangeProposal；可按 goal_id / status 过滤"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            clauses: List[str] = []
            params: List[Any] = []
            if goal_id:
                clauses.append("goal_id = ?")
                params.append(goal_id)
            if status:
                clauses.append("status = ?")
                params.append(status)
            sql = "SELECT * FROM change_proposals"
            if clauses:
                sql += " WHERE " + " AND ".join(clauses)
            sql += " ORDER BY created_at DESC"
            cursor = conn.execute(sql, tuple(params))
            return [self._row_to_proposal(dict(r)) for r in cursor.fetchall()]
        finally:
            conn.close()

    def delete_proposals_by_goal(self, goal_id: str) -> int:
        """级联删除某 Goal 下的所有 ChangeProposal；返回条数"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM change_proposals WHERE goal_id = ?",
                (goal_id,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    # ---------- impact_analyses CRUD ----------

    def save_impact(self, impact: Dict[str, Any]) -> None:
        """保存 ImpactAnalysis (upsert)"""
        conn = sqlite3.connect(self.db_path)
        try:
            params = self._impact_to_params(impact)
            conn.execute(
                "INSERT OR REPLACE INTO impact_analyses "
                "(id, proposal_id, affected_object_types, "
                "affected_action_types, affected_instances_count, "
                "breaking_changes, estimated_migration_cost, risk_level, "
                "analysis_metadata, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                params,
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _impact_to_params(impact: Dict[str, Any]) -> tuple:
        return (
            impact.get("id", ""),
            impact.get("proposal_id", ""),
            json.dumps(
                impact.get("affected_object_types", []), ensure_ascii=False,
            ),
            json.dumps(
                impact.get("affected_action_types", []), ensure_ascii=False,
            ),
            int(impact.get("affected_instances_count", 0) or 0),
            json.dumps(
                impact.get("breaking_changes", []), ensure_ascii=False,
            ),
            impact.get("estimated_migration_cost", "low"),
            impact.get("risk_level", "low"),
            json.dumps(
                impact.get("analysis_metadata", {}), ensure_ascii=False,
            ),
            impact.get("created_at", ""),
        )

    def get_impact(self, impact_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取 ImpactAnalysis；不存在返回 None"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM impact_analyses WHERE id = ?", (impact_id,)
            )
            row = cursor.fetchone()
            return self._row_to_impact(dict(row)) if row else None
        finally:
            conn.close()

    def get_impact_by_proposal(
        self, proposal_id: str
    ) -> Optional[Dict[str, Any]]:
        """根据 proposal_id 获取 ImpactAnalysis；不存在返回 None"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM impact_analyses WHERE proposal_id = ?",
                (proposal_id,),
            )
            row = cursor.fetchone()
            return self._row_to_impact(dict(row)) if row else None
        finally:
            conn.close()

    def delete_impacts_by_proposal(self, proposal_id: str) -> int:
        """级联删除某 Proposal 下的所有 ImpactAnalysis；返回条数"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM impact_analyses WHERE proposal_id = ?",
                (proposal_id,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    # ---------- 私有工具 ----------

    @staticmethod
    def _row_to_goal(row: Dict[str, Any]) -> Dict[str, Any]:
        """SQLite row → dict；JSON 字段反序列化"""
        row = dict(row)
        row["tags"] = _safe_json_loads(row.get("tags"), [])
        row["metadata"] = _safe_json_loads(row.get("metadata"), {})
        return row

    @staticmethod
    def _row_to_proposal(row: Dict[str, Any]) -> Dict[str, Any]:
        """SQLite row → dict；changes 字段 JSON 反序列化"""
        row = dict(row)
        row["changes"] = _safe_json_loads(row.get("changes"), [])
        return row

    @staticmethod
    def _row_to_impact(row: Dict[str, Any]) -> Dict[str, Any]:
        """SQLite row → dict；JSON 字段反序列化"""
        row = dict(row)
        row["affected_object_types"] = _safe_json_loads(
            row.get("affected_object_types"), []
        )
        row["affected_action_types"] = _safe_json_loads(
            row.get("affected_action_types"), []
        )
        row["breaking_changes"] = _safe_json_loads(
            row.get("breaking_changes"), []
        )
        row["analysis_metadata"] = _safe_json_loads(
            row.get("analysis_metadata"), {}
        )
        row["affected_instances_count"] = int(
            row.get("affected_instances_count", 0) or 0
        )
        return row


__all__ = ["SQLiteGoalStorage"]
