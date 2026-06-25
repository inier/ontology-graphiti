"""渠道配置服务层。

业务逻辑编排，处理凭证管理和 AI/Agent 隔离。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from odap.biz.integration.channel_management.models.channel import (
    CHANNEL_OPTIONAL_FIELDS,
    CHANNEL_REQUIRED_FIELDS,
    CHANNEL_TYPE_NAMES,
    ChannelConfig,
    ChannelStatus,
    ChannelType,
)
from odap.biz.integration.channel_management.storage.sqlite_channel_storage import (
    SQLiteChannelStorage,
)

logger = logging.getLogger(__name__)


class ChannelService:
    """渠道配置服务。

    职责：
    - CRUD 操作
    - 凭证脱敏（AI/Agent 不可读）
    - 配置验证
    """

    def __init__(self, storage: Optional[SQLiteChannelStorage] = None):
        self._storage = storage or SQLiteChannelStorage()

    def list_channels(
        self,
        workspace_id: str,
        channel_type: Optional[ChannelType] = None,
    ) -> List[Dict[str, Any]]:
        """获取工作空间的所有渠道配置（脱敏）。

        AI/Agent 调用此接口只能看到 has_xxx 标志，看不到实际凭证。

        Args:
            workspace_id: 工作空间 ID
            channel_type: 可选，按渠道类型过滤

        Returns:
            脱敏后的渠道配置列表
        """
        configs = self._storage.get_by_workspace(workspace_id, channel_type)
        return [self._mask_credentials(cfg) for cfg in configs]

    def get_channel(
        self,
        config_id: str,
        include_credentials: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """获取单个渠道配置。

        Args:
            config_id: 配置 ID
            include_credentials: 是否包含实际凭证（仅管理员可用）

        Returns:
            渠道配置或 None
        """
        config = self._storage.get(config_id)
        if not config:
            return None

        result = self._mask_credentials(config)
        if include_credentials:
            # 仅管理员可以看实际凭证
            result["_credentials"] = config.config
        return result

    def create_channel(
        self,
        workspace_id: str,
        channel_type: ChannelType,
        name: str,
        config: Dict[str, Any],
        enabled: bool = False,
        allow_from: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """创建渠道配置。

        Args:
            workspace_id: 工作空间 ID
            channel_type: 渠道类型
            name: 配置名称
            config: 渠道配置（含凭证）
            enabled: 是否启用
            allow_from: 允许访问的用户 ID 列表

        Returns:
            创建后的配置（脱敏）
        """
        # 验证必填字段
        self._validate_config(channel_type, config)

        channel_config = ChannelConfig(
            workspace_id=workspace_id,
            channel_type=channel_type,
            name=name,
            config=config,
            enabled=enabled,
            allow_from=allow_from or ["*"],
            status=ChannelStatus.DISCONNECTED,
        )

        saved = self._storage.save(channel_config)
        return self._mask_credentials(saved)

    def update_channel(
        self,
        config_id: str,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        enabled: Optional[bool] = None,
        allow_from: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """更新渠道配置。

        Args:
            config_id: 配置 ID
            name: 新名称
            config: 新配置（如果提供，凭证会被替换）
            enabled: 是否启用
            allow_from: 允许访问的用户 ID 列表

        Returns:
            更新后的配置（脱敏）或 None
        """
        existing = self._storage.get(config_id)
        if not existing:
            return None

        # 更新字段
        if name is not None:
            existing.name = name
        if config is not None:
            self._validate_config(existing.channel_type, config)
            existing.config = config
        if enabled is not None:
            existing.enabled = enabled
        if allow_from is not None:
            existing.allow_from = allow_from

        saved = self._storage.save(existing)
        return self._mask_credentials(saved)

    def delete_channel(self, config_id: str) -> bool:
        """删除渠道配置。

        Args:
            config_id: 配置 ID

        Returns:
            是否删除成功
        """
        return self._storage.delete(config_id)

    def enable_channel(self, config_id: str) -> Optional[Dict[str, Any]]:
        """启用渠道（热更新）。

        Args:
            config_id: 配置 ID

        Returns:
            更新后的配置或 None
        """
        existing = self._storage.get(config_id)
        if not existing:
            return None

        existing.enabled = True
        saved = self._storage.save(existing)

        # 发布配置变更事件（供 OHMO ChannelManager 订阅）
        self._publish_config_change(existing)

        return self._mask_credentials(saved)

    def disable_channel(self, config_id: str) -> Optional[Dict[str, Any]]:
        """停用渠道（热更新）。

        Args:
            config_id: 配置 ID

        Returns:
            更新后的配置或 None
        """
        existing = self._storage.get(config_id)
        if not existing:
            return None

        existing.enabled = False
        saved = self._storage.save(existing)

        # 发布配置变更事件
        self._publish_config_change(existing)

        return self._mask_credentials(saved)

    def test_connection(self, config_id: str) -> Dict[str, Any]:
        """测试渠道连接。

        Args:
            config_id: 配置 ID

        Returns:
            测试结果
        """
        config = self._storage.get(config_id)
        if not config:
            return {"success": False, "message": "配置不存在"}

        try:
            # 获取解密后的配置进行测试
            decrypted_config = self._storage.get_decrypted_config(config_id)
            if not decrypted_config:
                return {"success": False, "message": "配置解密失败"}

            # TODO: 实现实际的连接测试
            # 目前返回模拟结果
            success = self._try_connect(config.channel_type, decrypted_config)

            return {
                "success": success,
                "message": "连接成功" if success else "连接失败",
            }
        except Exception as e:
            logger.error(f"连接测试失败: {e}")
            return {"success": False, "message": str(e)}

    def get_channel_types(self) -> List[Dict[str, Any]]:
        """获取所有支持的渠道类型信息。

        Returns:
            渠道类型列表
        """
        return [
            {
                "type": ct.value,
                "name": CHANNEL_TYPE_NAMES[ct],
                "required_fields": CHANNEL_REQUIRED_FIELDS.get(ct, []),
                "optional_fields": CHANNEL_OPTIONAL_FIELDS.get(ct, []),
            }
            for ct in ChannelType
        ]

    def _mask_credentials(self, config: ChannelConfig) -> Dict[str, Any]:
        """将配置脱敏，AI/Agent 只能看到 has_xxx 标志。"""
        return {
            "id": config.id,
            "workspace_id": config.workspace_id,
            "channel_type": config.channel_type.value,
            "name": config.name,
            "enabled": config.enabled,
            "allow_from": config.allow_from,
            "config": config.mask_credentials(),
            "status": config.status.value,
            "has_credentials": config.has_any_credential(),
            "created_at": config.created_at.isoformat(),
            "updated_at": config.updated_at.isoformat(),
        }

    def _validate_config(
        self,
        channel_type: ChannelType,
        config: Dict[str, Any],
    ) -> None:
        """验证配置是否包含必填字段。"""
        required = CHANNEL_REQUIRED_FIELDS.get(channel_type, [])
        missing = [f for f in required if not config.get(f)]
        if missing:
            raise ValueError(
                f"渠道 {CHANNEL_TYPE_NAMES.get(channel_type, channel_type.value)} "
                f"缺少必填字段: {', '.join(missing)}"
            )

    def _try_connect(self, channel_type: ChannelType, config: Dict[str, Any]) -> bool:
        """尝试建立连接（占位实现）。"""
        # TODO: 实现实际的连接测试
        # 目前简单返回 True
        return True

    def _publish_config_change(self, config: ChannelConfig) -> None:
        """发布配置变更事件。"""
        # TODO: 实现事件发布（供 OHMO ChannelManager 订阅）
        logger.info(
            f"配置变更事件: channel={config.channel_type.value}, "
            f"workspace={config.workspace_id}, enabled={config.enabled}"
        )
