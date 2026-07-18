"""查询审计存储 - SQLite 持久化"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from odap.biz.data.qa.models import QueryAuditRecord

logger = logging.getLogger(__name__)


class QueryAuditStorage:
    """查询审计 SQLite 存储"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "query_audit.db"
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS query_audit (
                    query_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    user_id TEXT DEFAULT '',
                    workspace_id TEXT DEFAULT '',
                    scenario_id TEXT,
                    original_query TEXT DEFAULT '',
                    intent TEXT DEFAULT '',
                    extracted_entities TEXT DEFAULT '[]',
                    rewritten_queries TEXT DEFAULT '[]',
                    query_plan TEXT DEFAULT '{}',
                    selected_pillars TEXT DEFAULT '[]',
                    pillar_results_count TEXT DEFAULT '{}',
                    cypher_generated TEXT,
                    execution_time_ms TEXT DEFAULT '{}',
                    total_results_before_fusion INTEGER DEFAULT 0,
                    total_results_after_fusion INTEGER DEFAULT 0,
                    rerank_model TEXT,
                    response_length INTEGER DEFAULT 0,
                    source_count INTEGER DEFAULT 0,
                    llm_model TEXT DEFAULT '',
                    total_time_ms REAL DEFAULT 0.0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_workspace
                ON query_audit(workspace_id, timestamp DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_user
                ON query_audit(user_id, timestamp DESC)
            """)
            conn.commit()
        finally:
            conn.close()

    def save(self, record: QueryAuditRecord) -> None:
        """保存审计记录"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT OR REPLACE INTO query_audit (
                    query_id, timestamp, user_id, workspace_id, scenario_id,
                    original_query, intent, extracted_entities, rewritten_queries,
                    query_plan, selected_pillars, pillar_results_count,
                    cypher_generated, execution_time_ms,
                    total_results_before_fusion, total_results_after_fusion,
                    rerank_model, response_length, source_count, llm_model, total_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.query_id,
                record.timestamp.isoformat() if isinstance(record.timestamp, datetime) else str(record.timestamp),
                record.user_id,
                record.workspace_id,
                record.scenario_id,
                record.original_query,
                record.intent,
                json.dumps(record.extracted_entities, ensure_ascii=False),
                json.dumps(record.rewritten_queries, ensure_ascii=False),
                json.dumps(record.query_plan, ensure_ascii=False, default=str),
                json.dumps(record.selected_pillars, ensure_ascii=False),
                json.dumps(record.pillar_results_count, ensure_ascii=False),
                record.cypher_generated,
                json.dumps(record.execution_time_ms, default=str),
                record.total_results_before_fusion,
                record.total_results_after_fusion,
                record.rerank_model,
                record.response_length,
                record.source_count,
                record.llm_model,
                record.total_time_ms,
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to save audit record: {e}")
        finally:
            conn.close()

    def get(self, query_id: str) -> Optional[Dict[str, Any]]:
        """获取单条审计记录"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM query_audit WHERE query_id = ?", (query_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)
            return None
        finally:
            conn.close()

    def list_records(self, workspace_id: Optional[str] = None,
                     user_id: Optional[str] = None,
                     limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """列出审计记录"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM query_audit WHERE 1=1"
            params: List[Any] = []
            if workspace_id:
                query += " AND workspace_id = ?"
                params.append(workspace_id)
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor = conn.execute(query, params)
            return [self._row_to_dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_stats(self, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """获取审计统计"""
        conn = sqlite3.connect(self.db_path)
        try:
            where = "WHERE workspace_id = ?" if workspace_id else ""
            params: List[Any] = [workspace_id] if workspace_id else []

            cursor = conn.execute(
                f"SELECT COUNT(*) as total, AVG(total_time_ms) as avg_time FROM query_audit {where}",
                params
            )
            row = cursor.fetchone()

            # 支柱使用统计
            pillar_cursor = conn.execute(
                f"SELECT selected_pillars FROM query_audit {where}",
                params
            )
            pillar_counts: Dict[str, int] = {}
            for (pillars_json,) in pillar_cursor.fetchall():
                try:
                    for p in json.loads(pillars_json):
                        pillar_counts[p] = pillar_counts.get(p, 0) + 1
                except Exception:
                    pass

            return {
                "total_queries": row[0] if row else 0,
                "avg_time_ms": round(row[1], 2) if row and row[1] else 0,
                "pillar_usage": pillar_counts,
            }
        finally:
            conn.close()

    def _row_to_dict(self, row) -> Dict[str, Any]:
        """将数据库行转为字典"""
        d = dict(row)
        # 反序列化 JSON 字段
        for key in ("extracted_entities", "rewritten_queries", "query_plan",
                     "selected_pillars", "pillar_results_count", "execution_time_ms"):
            if key in d and isinstance(d[key], str):
                try:
                    d[key] = json.loads(d[key])
                except Exception:
                    pass
        return d
