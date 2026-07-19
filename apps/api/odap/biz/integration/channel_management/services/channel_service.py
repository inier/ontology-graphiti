"""渠道配置服务层。

业务逻辑编排，处理凭证管理和 AI/Agent 隔离。
"""

from __future__ import annotations

import asyncio
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

# ── 审计工具（懒加载 + 容错，审计失败不打断业务） ──
def _channel_audit(action: str, *, result_status: str = "success",
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
        try:
            self._validate_config(channel_type, config)
        except ValueError as ve:
            _channel_audit(
                action="channel_register",
                result_status="failure",
                result_message=str(ve)[:200],
                resource="",
                details={
                    "workspace_id": workspace_id,
                    "channel_type": channel_type.value if hasattr(channel_type, "value") else str(channel_type),
                    "name_len": len(name),
                },
            )
            raise

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
        # 审计：注册渠道（不记凭证，只记统计量）
        _channel_audit(
            action="channel_register",
            result_status="success",
            resource=saved.id,
            details={
                "channel_id": saved.id,
                "workspace_id": workspace_id,
                "channel_type": channel_type.value if hasattr(channel_type, "value") else str(channel_type),
                "name_len": len(name),
                "enabled": enabled,
            },
        )
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
            _channel_audit(
                action="channel_update",
                result_status="failure",
                result_message="Channel not found",
                resource=config_id,
                details={"channel_id": config_id},
            )
            return None

        changed = []
        # 更新字段
        if name is not None:
            existing.name = name
            changed.append("name")
        if config is not None:
            self._validate_config(existing.channel_type, config)
            existing.config = config
            changed.append("config")
        if enabled is not None:
            existing.enabled = enabled
            changed.append("enabled")
        if allow_from is not None:
            existing.allow_from = allow_from
            changed.append("allow_from")

        saved = self._storage.save(existing)
        _channel_audit(
            action="channel_update",
            result_status="success",
            resource=config_id,
            details={
                "channel_id": config_id,
                "workspace_id": existing.workspace_id,
                "changed_fields": changed,
                "field_count": len(changed),
            },
        )
        return self._mask_credentials(saved)

    def delete_channel(self, config_id: str) -> bool:
        """删除渠道配置。

        Args:
            config_id: 配置 ID

        Returns:
            是否删除成功
        """
        result = self._storage.delete(config_id)
        _channel_audit(
            action="channel_unregister",
            result_status="success" if result else "failure",
            result_message="" if result else "Channel not found",
            resource=config_id,
            details={"channel_id": config_id},
        )
        return result

    def enable_channel(self, config_id: str) -> Optional[Dict[str, Any]]:
        """启用渠道（热更新）。

        Args:
            config_id: 配置 ID

        Returns:
            更新后的配置或 None
        """
        existing = self._storage.get(config_id)
        if not existing:
            _channel_audit(
                action="channel_connect",
                result_status="failure",
                result_message="Channel not found",
                resource=config_id,
                details={"channel_id": config_id, "status": "enable_failed"},
            )
            return None

        existing.enabled = True
        saved = self._storage.save(existing)

        # 审计：接入/启用渠道
        _channel_audit(
            action="channel_connect",
            result_status="success",
            resource=config_id,
            details={
                "channel_id": config_id,
                "workspace_id": existing.workspace_id,
                "channel_type": existing.channel_type.value if hasattr(existing.channel_type, "value") else str(existing.channel_type),
                "status": "enabled",
            },
        )

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
            _channel_audit(
                action="channel_disconnect",
                result_status="failure",
                result_message="Channel not found",
                resource=config_id,
                details={"channel_id": config_id, "status": "disable_failed"},
            )
            return None

        existing.enabled = False
        saved = self._storage.save(existing)

        # 审计：断开/停用渠道
        _channel_audit(
            action="channel_disconnect",
            result_status="success",
            resource=config_id,
            details={
                "channel_id": config_id,
                "workspace_id": existing.workspace_id,
                "channel_type": existing.channel_type.value if hasattr(existing.channel_type, "value") else str(existing.channel_type),
                "status": "disabled",
            },
        )

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
        import time as _time
        _t0 = _time.perf_counter()
        config = self._storage.get(config_id)
        if not config:
            _channel_audit(
                action="channel_test_connection",
                result_status="failure",
                result_message="Config not found",
                resource=config_id,
                details={"channel_id": config_id},
            )
            return {"success": False, "message": "配置不存在"}

        try:
            # 获取解密后的配置进行测试
            decrypted_config = self._storage.get_decrypted_config(config_id)
            if not decrypted_config:
                _dur = int((_time.perf_counter() - _t0) * 1000)
                _channel_audit(
                    action="channel_test_connection",
                    result_status="failure",
                    result_message="Decrypt failed",
                    resource=config_id,
                    details={"channel_id": config_id, "duration_ms": _dur},
                )
                return {"success": False, "message": "配置解密失败"}

            # _try_connect 当前仅做必填字段校验；真实网络连接测试应由
            # 各 channel adapter 在协议层实现（见 _try_connect 文档）
            success = self._try_connect(config.channel_type, decrypted_config)
            _dur = int((_time.perf_counter() - _t0) * 1000)

            # 审计：连接测试（绝不记明文凭证）
            _channel_audit(
                action="channel_test_connection",
                result_status="success" if success else "failure",
                resource=config_id,
                details={
                    "channel_id": config_id,
                    "channel_type": config.channel_type.value if hasattr(config.channel_type, "value") else str(config.channel_type),
                    "duration_ms": _dur,
                    "delivery_status": "delivered" if success else "failed",
                },
            )

            return {
                "success": success,
                "message": "连接成功" if success else "连接失败",
            }
        except Exception as e:
            _dur = int((_time.perf_counter() - _t0) * 1000)
            logger.error(f"连接测试失败: {e}")
            _channel_audit(
                action="channel_test_connection",
                result_status="failure",
                result_message=str(e)[:200],
                resource=config_id,
                details={"channel_id": config_id, "duration_ms": _dur},
            )
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
        """执行连接前的配置完整性校验。

        真实网络连接测试应由各 channel adapter 在协议层实现（如 TELEGRAM
        调用 getMe API 验证 token、EMAIL 通过 SMTP EHLO 验证服务器响应）。
        当前实现仅复用 _validate_config 做必填字段校验，避免 mock 返回
        True 误导审计与调用方。

        Args:
            channel_type: 渠道类型
            config: 解密后的渠道配置 dict

        Returns:
            True 如果必填字段完整；False 如果缺失关键字段
        """
        try:
            self._validate_config(channel_type, config)
            return True
        except ValueError as e:
            logger.warning(f"连接测试失败（必填字段缺失）: {e}")
            return False

    def _publish_config_change(self, config: ChannelConfig) -> None:
        """发布配置变更事件（供 OHMO ChannelManager 订阅）。

        通过 DomainEventBus 广播 'channel:config_changed' 事件类型。
        订阅者可在该事件类型上注册回调（参考
        odap.infra.events.DomainEventBus.subscribe）。

        事件发布采用 fire-and-forget 模式：在 event loop 中调度异步 emit，
        无 event loop 时降级为日志记录，事件发布失败不打断业务流程。
        """
        event_data = {
            "channel_id": config.id,
            "channel_type": config.channel_type.value,
            "workspace_id": config.workspace_id,
            "enabled": config.enabled,
            "name": config.name,
        }
        try:
            from odap.infra.events import get_event_bus
            bus = get_event_bus()
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    bus.emit(
                        "channel:config_changed",
                        event_data,
                        workspace_id=config.workspace_id,
                    )
                )
            except RuntimeError:
                # No running event loop — fall back to log only
                logger.info(
                    f"配置变更事件（无 event loop，跳过总线广播）: "
                    f"channel={config.channel_type.value}, "
                    f"workspace={config.workspace_id}, enabled={config.enabled}"
                )
                return
        except Exception as e:
            logger.warning(f"事件总线加载失败（不打断业务）: {e}")
            return
        logger.info(
            f"配置变更事件已发布: channel={config.channel_type.value}, "
            f"workspace={config.workspace_id}, enabled={config.enabled}"
        )
