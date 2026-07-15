"""SQLite 渠道配置存储实现。

支持工作空间级别的渠道配置，凭证加密存储。
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from odap.biz.integration.channel_management.crypto_utils import (
    decrypt_config,
    encrypt_config,
)
from odap.biz.integration.channel_management.models.channel import (
    ChannelConfig,
    ChannelStatus,
    ChannelType,
)

logger = logging.getLogger(__name__)

# ── 存储层审计工具（懒加载 + 容错） ──
def _channel_storage_audit(action: str, *, result_status: str = "success",
                           result_message: str = "", resource: str = None,
                           details: Dict[str, Any] = None) -> None:
    try:
        from odap.infra.security.audit_helper import storage_audit
        storage_audit(
            action=action,
            result_status=result_status,
            result_message=result_message,
            resource=resource,
            details=details or {},
            service="integration_channel",
        )
    except Exception as e:
        logger.warning(f"audit failed: {e}")


class SQLiteChannelStorage:
    """SQLite 渠道配置持久化存储。

    凭证以加密形式存储在 config 字段中。
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "channel_configs.db"
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """创建数据库连接。"""
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        """初始化数据库表。"""
        conn = self._connect()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS channel_configs (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    channel_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    enabled INTEGER DEFAULT 0,
                    allow_from TEXT NOT NULL DEFAULT '["*"]',
                    config TEXT NOT NULL DEFAULT '{}',
                    status TEXT DEFAULT 'disconnected',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(workspace_id, channel_type, name)
                );

                CREATE INDEX IF NOT EXISTS idx_channel_ws
                    ON channel_configs(workspace_id);
                CREATE INDEX IF NOT EXISTS idx_channel_type
                    ON channel_configs(channel_type);
            """)
            conn.commit()
        finally:
            conn.close()

    def save(self, channel_config: ChannelConfig) -> ChannelConfig:
        """保存或更新渠道配置。

        Args:
            channel_config: 渠道配置领域模型

        Returns:
            保存后的配置
        """
        conn = self._connect()
        # 判断是 insert 还是 update（通过检查 ID 是否存在）
        existing = conn.execute(
            "SELECT id FROM channel_configs WHERE id = ?",
            (channel_config.id,)
        ).fetchone()
        is_update = existing is not None
        try:
            # 加密敏感配置
            encrypted_config = encrypt_config(channel_config.config)

            now = datetime.now().isoformat()
            conn.execute("""
                INSERT OR REPLACE INTO channel_configs
                (id, workspace_id, channel_type, name, enabled, allow_from,
                 config, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                channel_config.id,
                channel_config.workspace_id,
                channel_config.channel_type.value,
                channel_config.name,
                int(channel_config.enabled),
                json.dumps(channel_config.allow_from, ensure_ascii=False),
                encrypted_config,
                channel_config.status.value,
                channel_config.created_at.isoformat(),
                now,
            ))
            conn.commit()

            # 返回更新后的配置
            channel_config.updated_at = datetime.fromisoformat(now)
        finally:
            conn.close()

        # 存储层审计：持久化写入
        _channel_storage_audit(
            action="channel_storage_save",
            result_status="success",
            resource=channel_config.id,
            details={
                "channel_id": channel_config.id,
                "workspace_id": channel_config.workspace_id,
                "channel_type": channel_config.channel_type.value,
                "name_len": len(channel_config.name),
                "config_keys_count": len(channel_config.config),
                "is_update": is_update,
                "side": "execution_storage",
            },
        )
        return channel_config

    def get(self, config_id: str) -> Optional[ChannelConfig]:
        """根据 ID 获取渠道配置。

        Args:
            config_id: 配置 ID

        Returns:
            渠道配置或 None
        """
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM channel_configs WHERE id = ?",
                (config_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_model(row, conn)
        finally:
            conn.close()

    def get_by_workspace(
        self,
        workspace_id: str,
        channel_type: Optional[ChannelType] = None,
    ) -> List[ChannelConfig]:
        """获取工作空间的所有渠道配置。

        Args:
            workspace_id: 工作空间 ID
            channel_type: 可选，按渠道类型过滤

        Returns:
            渠道配置列表
        """
        conn = self._connect()
        try:
            if channel_type:
                rows = conn.execute(
                    """SELECT * FROM channel_configs
                       WHERE workspace_id = ? AND channel_type = ?
                       ORDER BY name""",
                    (workspace_id, channel_type.value)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM channel_configs
                       WHERE workspace_id = ?
                       ORDER BY channel_type, name""",
                    (workspace_id,)
                ).fetchall()
            return [self._row_to_model(row, conn) for row in rows]
        finally:
            conn.close()

    def delete(self, config_id: str) -> bool:
        """删除渠道配置。

        Args:
            config_id: 配置 ID

        Returns:
            是否删除成功
        """
        conn = self._connect()
        try:
            cursor = conn.execute(
                "DELETE FROM channel_configs WHERE id = ?",
                (config_id,)
            )
            conn.commit()
            result = cursor.rowcount > 0
        finally:
            conn.close()

        _channel_storage_audit(
            action="channel_storage_delete",
            result_status="success" if result else "failure",
            result_message="" if result else "Not found",
            resource=config_id,
            details={
                "channel_id": config_id,
                "side": "execution_storage",
            },
        )
        return result

    def update_status(self, config_id: str, status: ChannelStatus) -> bool:
        """更新渠道状态。

        Args:
            config_id: 配置 ID
            status: 新状态

        Returns:
            是否更新成功
        """
        conn = self._connect()
        try:
            now = datetime.now().isoformat()
            cursor = conn.execute(
                """UPDATE channel_configs
                   SET status = ?, updated_at = ?
                   WHERE id = ?""",
                (status.value, now, config_id)
            )
            conn.commit()
            result = cursor.rowcount > 0
        finally:
            conn.close()

        _channel_storage_audit(
            action="channel_storage_status_change",
            result_status="success" if result else "failure",
            result_message="" if result else "Not found",
            resource=config_id,
            details={
                "channel_id": config_id,
                "status": status.value,
                "side": "execution_storage",
            },
        )
        return result

    def get_decrypted_config(self, config_id: str) -> Optional[Dict[str, Any]]:
        """获取解密后的配置（仅限内部管理使用）。

        Args:
            config_id: 配置 ID

        Returns:
            解密后的配置字典
        """
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT config FROM channel_configs WHERE id = ?",
                (config_id,)
            ).fetchone()
            if not row:
                return None
            return decrypt_config(row[0])
        finally:
            conn.close()

    def _row_to_model(self, row: tuple, conn: sqlite3.Connection) -> ChannelConfig:
        """将数据库行转换为领域模型。"""
        cols = [d[0] for d in conn.execute(
            "SELECT * FROM channel_configs LIMIT 0"
        ).description]
        data = dict(zip(cols, row))

        # 解密配置
        try:
            decrypted_config = decrypt_config(data["config"])
        except Exception as e:
            logger.error(f"配置解密失败: {e}")
            decrypted_config = {}

        return ChannelConfig(
            id=data["id"],
            workspace_id=data["workspace_id"],
            channel_type=ChannelType(data["channel_type"]),
            name=data["name"],
            enabled=bool(data["enabled"]),
            allow_from=json.loads(data["allow_from"]),
            config=decrypted_config,
            status=ChannelStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


# Storage 别名导出
Storage = SQLiteChannelStorage
