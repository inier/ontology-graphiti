"""操作历史服务"""

import sqlite3
import json
import os
import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DEFAULT_DB_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "operation_history.db")


class OperationHistoryService:
    """操作历史服务"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            os.makedirs(DEFAULT_DB_DIR, exist_ok=True)
            db_path = DEFAULT_DB_PATH
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS operation_history (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                user_id TEXT NOT NULL DEFAULT 'system',
                action_type TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                before_state TEXT,
                after_state TEXT,
                created_at TEXT NOT NULL,
                undone INTEGER NOT NULL DEFAULT 0
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_op_history_workspace
            ON operation_history(workspace_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_op_history_undone
            ON operation_history(undone)
        ''')

        conn.commit()
        conn.close()

    def record_operation(
        self,
        workspace_id: str,
        action_type: str,
        resource_type: str,
        resource_id: str,
        before_state: Dict[str, Any] = None,
        after_state: Dict[str, Any] = None,
        user_id: str = "system",
    ) -> Dict[str, Any]:
        """记录操作

        Args:
            workspace_id: 工作空间ID
            action_type: 操作类型 (create/update/delete)
            resource_type: 资源类型
            resource_id: 资源ID
            before_state: 操作前状态
            after_state: 操作后状态
            user_id: 操作用户

        Returns:
            操作记录
        """
        operation_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO operation_history
            (id, workspace_id, user_id, action_type, resource_type, resource_id,
             before_state, after_state, created_at, undone)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        ''', (
            operation_id,
            workspace_id,
            user_id,
            action_type,
            resource_type,
            resource_id,
            json.dumps(before_state, ensure_ascii=False) if before_state is not None else None,
            json.dumps(after_state, ensure_ascii=False) if after_state is not None else None,
            now,
        ))

        conn.commit()
        conn.close()

        return {
            "operation_id": operation_id,
            "workspace_id": workspace_id,
            "action_type": action_type,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "created_at": now,
        }

    def get_history(
        self,
        workspace_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """获取操作历史（分页）

        Args:
            workspace_id: 工作空间ID
            page: 页码
            page_size: 每页数量

        Returns:
            操作历史列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 总数
        cursor.execute(
            'SELECT COUNT(*) FROM operation_history WHERE workspace_id = ?',
            (workspace_id,),
        )
        total = cursor.fetchone()[0]

        # 分页查询
        cursor.execute('''
            SELECT * FROM operation_history
            WHERE workspace_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        ''', (workspace_id, page_size, (page - 1) * page_size))

        rows = cursor.fetchall()
        conn.close()

        operations = []
        for row in rows:
            operations.append({
                "operation_id": row["id"],
                "workspace_id": row["workspace_id"],
                "user_id": row["user_id"],
                "action_type": row["action_type"],
                "resource_type": row["resource_type"],
                "resource_id": row["resource_id"],
                "before_state": json.loads(row["before_state"]) if row["before_state"] else None,
                "after_state": json.loads(row["after_state"]) if row["after_state"] else None,
                "created_at": row["created_at"],
                "undone": bool(row["undone"]),
            })

        return {
            "operations": operations,
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    def get_operation(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """获取单个操作记录"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM operation_history WHERE id = ?', (operation_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "operation_id": row["id"],
            "workspace_id": row["workspace_id"],
            "user_id": row["user_id"],
            "action_type": row["action_type"],
            "resource_type": row["resource_type"],
            "resource_id": row["resource_id"],
            "before_state": json.loads(row["before_state"]) if row["before_state"] else None,
            "after_state": json.loads(row["after_state"]) if row["after_state"] else None,
            "created_at": row["created_at"],
            "undone": bool(row["undone"]),
        }

    def mark_undone(self, operation_id: str) -> bool:
        """标记操作为已撤销

        Args:
            operation_id: 操作ID

        Returns:
            是否成功
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            'UPDATE operation_history SET undone = 1 WHERE id = ?',
            (operation_id,),
        )

        affected = cursor.rowcount
        conn.commit()
        conn.close()

        return affected > 0

    def mark_redone(self, operation_id: str) -> bool:
        """标记操作为已重做（取消撤销标记）

        Args:
            operation_id: 操作ID

        Returns:
            是否成功
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            'UPDATE operation_history SET undone = 0 WHERE id = ?',
            (operation_id,),
        )

        affected = cursor.rowcount
        conn.commit()
        conn.close()

        return affected > 0

    def get_undoable_operations(self, workspace_id: str) -> List[Dict[str, Any]]:
        """获取可撤销的操作列表"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM operation_history
            WHERE workspace_id = ? AND undone = 0
            ORDER BY created_at DESC
            LIMIT 50
        ''', (workspace_id,))

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_dict(row) for row in rows]

    def get_redoable_operations(self, workspace_id: str) -> List[Dict[str, Any]]:
        """获取可重做的操作列表"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM operation_history
            WHERE workspace_id = ? AND undone = 1
            ORDER BY created_at DESC
            LIMIT 50
        ''', (workspace_id,))

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_dict(row) for row in rows]

    def cleanup_old_records(self, days: int = 30) -> int:
        """清理超过指定天数的记录

        Args:
            days: 保留天数

        Returns:
            删除的记录数
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            'DELETE FROM operation_history WHERE created_at < ?',
            (cutoff,),
        )

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        return deleted

    def _row_to_dict(self, row) -> Dict[str, Any]:
        """将数据库行转换为字典"""
        return {
            "operation_id": row["id"],
            "workspace_id": row["workspace_id"],
            "user_id": row["user_id"],
            "action_type": row["action_type"],
            "resource_type": row["resource_type"],
            "resource_id": row["resource_id"],
            "before_state": json.loads(row["before_state"]) if row["before_state"] else None,
            "after_state": json.loads(row["after_state"]) if row["after_state"] else None,
            "created_at": row["created_at"],
            "undone": bool(row["undone"]),
        }
