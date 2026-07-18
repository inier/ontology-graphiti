"""CollectionTask SQLite 持久化存储"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

from odap.biz.data.web_crawl.models.collection_task import (
    CollectionTask,
    CollectionTaskType,
    CollectionTaskStatus,
)


class SQLiteCollectionStorage:
    """CollectionTask SQLite 存储

    遵循项目约定：
    - 每次操作 connect/close，无连接池
    - 复杂字段 JSON TEXT 存储
    - Enum 存 .value 字符串
    - datetime 存 ISO 字符串
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "collection_tasks.db",
        )
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS collection_tasks (
                    id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    target TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    result TEXT,
                    error_message TEXT,
                    source TEXT DEFAULT 'external',
                    confidence TEXT DEFAULT 'medium',
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    workspace_id TEXT,
                    scenario_id TEXT
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def save(self, task: CollectionTask) -> CollectionTask:
        """保存/更新 CollectionTask（upsert）"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT OR REPLACE INTO collection_tasks
                   (id, task_type, target, status, result, error_message,
                    source, confidence, created_at, completed_at,
                    workspace_id, scenario_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task.id,
                    task.task_type.value,
                    task.target,
                    task.status.value,
                    json.dumps(task.result) if task.result else None,
                    task.error_message,
                    task.source,
                    task.confidence,
                    task.created_at.isoformat() if isinstance(task.created_at, datetime) else task.created_at,
                    task.completed_at.isoformat() if task.completed_at and isinstance(task.completed_at, datetime) else task.completed_at,
                    task.workspace_id,
                    task.scenario_id,
                ),
            )
            conn.commit()
            return task
        finally:
            conn.close()

    def get(self, task_id: str) -> Optional[CollectionTask]:
        """获取单个 CollectionTask"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM collection_tasks WHERE id = ?", (task_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_task(row)
        finally:
            conn.close()

    def list_tasks(self, workspace_id: str = None, task_type: str = None,
                   status: str = None, page: int = 1, page_size: int = 20) -> List[CollectionTask]:
        """列出 CollectionTask，支持过滤和分页"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            conditions = []
            params = []

            if workspace_id:
                conditions.append("workspace_id = ?")
                params.append(workspace_id)
            if task_type:
                conditions.append("task_type = ?")
                params.append(task_type)
            if status:
                conditions.append("status = ?")
                params.append(status)

            where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
            offset = (page - 1) * page_size

            cursor = conn.execute(
                f"SELECT * FROM collection_tasks{where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params + [page_size, offset],
            )
            return [self._row_to_task(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def update_status(self, task_id: str, status: CollectionTaskStatus,
                      result: Dict = None, error_message: str = None) -> bool:
        """更新任务状态"""
        conn = sqlite3.connect(self.db_path)
        try:
            completed_at = datetime.now().isoformat() if status in (
                CollectionTaskStatus.COMPLETED, CollectionTaskStatus.FAILED
            ) else None

            sets = ["status = ?"]
            params = [status.value]

            if result is not None:
                sets.append("result = ?")
                params.append(json.dumps(result))
            if error_message is not None:
                sets.append("error_message = ?")
                params.append(error_message)
            if completed_at:
                sets.append("completed_at = ?")
                params.append(completed_at)

            params.append(task_id)
            cursor = conn.execute(
                f"UPDATE collection_tasks SET {', '.join(sets)} WHERE id = ?",
                params,
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete(self, task_id: str) -> bool:
        """删除 CollectionTask"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM collection_tasks WHERE id = ?", (task_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> CollectionTask:
        """将数据库行转换为 CollectionTask"""
        result_data = None
        if row["result"]:
            try:
                result_data = json.loads(row["result"])
            except json.JSONDecodeError:
                result_data = {"raw": row["result"]}

        return CollectionTask(
            id=row["id"],
            task_type=CollectionTaskType(row["task_type"]),
            target=row["target"],
            status=CollectionTaskStatus(row["status"]),
            result=result_data,
            error_message=row["error_message"],
            source=row["source"],
            confidence=row["confidence"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
            workspace_id=row["workspace_id"],
            scenario_id=row["scenario_id"],
        )
