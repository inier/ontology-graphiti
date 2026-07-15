"""本体编辑锁服务

提供基于 SQLite 的编辑锁管理，支持锁获取、释放、心跳刷新和状态查询。
锁超时 30 秒，无心跳自动释放。
"""

import logging
import os
from odap.infra.storage.sqlite_base import SqliteBaseStorage
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

LOCK_TIMEOUT_SECONDS = 30

class EditLockService(SqliteBaseStorage):
    """本体编辑锁服务"""

    def __init__(self, db_path: str = None):
        super().__init__(db_path, db_name="edit_locks.db")

    def _init_db(self):
        conn = self._get_conn()
        try:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS edit_locks (
                ontology_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                acquired_at TEXT NOT NULL,
                last_heartbeat TEXT NOT NULL
            )''')
            conn.commit()
        finally:
            conn.close()

    def _is_lock_expired(self, last_heartbeat: str) -> bool:
        """检查锁是否已超时"""
        try:
            hb_time = datetime.fromisoformat(last_heartbeat)
            if hb_time.tzinfo is None:
                hb_time = hb_time.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            elapsed = (now - hb_time).total_seconds()
            return elapsed > LOCK_TIMEOUT_SECONDS
        except (ValueError, TypeError):
            return True

    def acquire_lock(self, ontology_id: str, user_id: str, session_id: str) -> Dict[str, Any]:
        """获取编辑锁

        Args:
            ontology_id: 本体 ID
            user_id: 用户 ID
            session_id: 会话 ID

        Returns:
            成功: {"status": "ok", "ontology_id": .., "user_id": .., "session_id": .., "acquired_at": .., "last_heartbeat": ..}
            失败: {"status": "error", "message": "本体正在被其他用户编辑", "locked_by": .., "locked_at": ..}
        """
        conn = self._get_conn()
        try:
            now = datetime.now(timezone.utc).isoformat()
            c = conn.cursor()

            # 检查现有锁
            c.execute(
                "SELECT * FROM edit_locks WHERE ontology_id = ?",
                (ontology_id,),
            )
            row = c.fetchone()

            if row:
                # 锁存在，检查是否超时
                if not self._is_lock_expired(row["last_heartbeat"]):
                    # 锁仍有效
                    if row["session_id"] == session_id:
                        # 同一会话重新获取，刷新心跳
                        c.execute(
                            "UPDATE edit_locks SET last_heartbeat = ? WHERE ontology_id = ?",
                            (now, ontology_id),
                        )
                        conn.commit()
                        return {
                            "status": "ok",
                            "ontology_id": ontology_id,
                            "user_id": row["user_id"],
                            "session_id": session_id,
                            "acquired_at": row["acquired_at"],
                            "last_heartbeat": now,
                        }
                    else:
                        # 被其他用户/会话持有
                        return {
                            "status": "error",
                            "message": "本体正在被其他用户编辑",
                            "locked_by": row["user_id"],
                            "locked_at": row["acquired_at"],
                            "session_id": row["session_id"],
                        }

            # 无锁或锁已超时，获取锁
            c.execute(
                """INSERT OR REPLACE INTO edit_locks (ontology_id, user_id, session_id, acquired_at, last_heartbeat)
                   VALUES (?, ?, ?, ?, ?)""",
                (ontology_id, user_id, session_id, now, now),
            )
            conn.commit()
            return {
                "status": "ok",
                "ontology_id": ontology_id,
                "user_id": user_id,
                "session_id": session_id,
                "acquired_at": now,
                "last_heartbeat": now,
            }
        finally:
            conn.close()

    def release_lock(self, ontology_id: str, session_id: str) -> Dict[str, Any]:
        """释放编辑锁

        Args:
            ontology_id: 本体 ID
            session_id: 会话 ID

        Returns:
            成功: {"status": "ok", "ontology_id": ..}
            失败: {"status": "error", "message": "锁不存在或不属于当前会话"}
        """
        conn = self._get_conn()
        try:
            c = conn.cursor()
            c.execute(
                "SELECT * FROM edit_locks WHERE ontology_id = ?",
                (ontology_id,),
            )
            row = c.fetchone()

            if not row:
                return {"status": "ok", "ontology_id": ontology_id, "message": "锁不存在，无需释放"}

            if row["session_id"] != session_id:
                return {
                    "status": "error",
                    "message": "锁不属于当前会话，无法释放",
                    "locked_by": row["user_id"],
                }

            c.execute("DELETE FROM edit_locks WHERE ontology_id = ?", (ontology_id,))
            conn.commit()
            return {"status": "ok", "ontology_id": ontology_id}
        finally:
            conn.close()

    def refresh_lock(self, ontology_id: str, session_id: str) -> Dict[str, Any]:
        """刷新锁心跳（由 WebSocket 心跳调用）

        Args:
            ontology_id: 本体 ID
            session_id: 会话 ID

        Returns:
            成功: {"status": "ok", "ontology_id": .., "last_heartbeat": ..}
            失败: {"status": "error", "message": "锁不存在或不属于当前会话"}
        """
        conn = self._get_conn()
        try:
            now = datetime.now(timezone.utc).isoformat()
            c = conn.cursor()
            c.execute(
                "SELECT * FROM edit_locks WHERE ontology_id = ?",
                (ontology_id,),
            )
            row = c.fetchone()

            if not row:
                return {"status": "error", "message": "锁不存在"}

            if row["session_id"] != session_id:
                return {"status": "error", "message": "锁不属于当前会话"}

            c.execute(
                "UPDATE edit_locks SET last_heartbeat = ? WHERE ontology_id = ? AND session_id = ?",
                (now, ontology_id, session_id),
            )
            conn.commit()
            return {
                "status": "ok",
                "ontology_id": ontology_id,
                "last_heartbeat": now,
            }
        finally:
            conn.close()

    def get_lock_status(self, ontology_id: str) -> Optional[Dict[str, Any]]:
        """获取锁状态

        Args:
            ontology_id: 本体 ID

        Returns:
            锁信息 dict 或 None（无锁或锁已超时）
        """
        conn = self._get_conn()
        try:
            c = conn.cursor()
            c.execute(
                "SELECT * FROM edit_locks WHERE ontology_id = ?",
                (ontology_id,),
            )
            row = c.fetchone()

            if not row:
                return None

            # 检查是否超时
            if self._is_lock_expired(row["last_heartbeat"]):
                # 锁已超时，清理
                c.execute("DELETE FROM edit_locks WHERE ontology_id = ?", (ontology_id,))
                conn.commit()
                return None

            return {
                "ontology_id": row["ontology_id"],
                "user_id": row["user_id"],
                "session_id": row["session_id"],
                "acquired_at": row["acquired_at"],
                "last_heartbeat": row["last_heartbeat"],
            }
        finally:
            conn.close()

    def force_release_lock(self, ontology_id: str) -> Dict[str, Any]:
        """强制释放锁（管理员操作）

        Args:
            ontology_id: 本体 ID

        Returns:
            {"status": "ok", "ontology_id": ..}
        """
        conn = self._get_conn()
        try:
            c = conn.cursor()
            c.execute("DELETE FROM edit_locks WHERE ontology_id = ?", (ontology_id,))
            conn.commit()
            return {"status": "ok", "ontology_id": ontology_id}
        finally:
            conn.close()

# 模块级单例
_edit_lock_service: Optional[EditLockService] = None

def get_edit_lock_service() -> EditLockService:
    global _edit_lock_service
    if _edit_lock_service is None:
        _edit_lock_service = EditLockService()
    return _edit_lock_service
