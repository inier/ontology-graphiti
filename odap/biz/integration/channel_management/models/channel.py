"""渠道配置领域模型。

定义渠道配置的领域实体和枚举类型。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChannelType(str, Enum):
    """支持的 IM 渠道类型。"""

    TELEGRAM = "telegram"
    SLACK = "slack"
    DISCORD = "discord"
    FEISHU = "feishu"
    DINGTALK = "dingtalk"
    EMAIL = "email"
    QQ = "qq"
    MATRIX = "matrix"
    WHATSAPP = "whatsapp"
    MOCHAT = "mochat"


class ChannelStatus(str, Enum):
    """渠道连接状态。"""

    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ERROR = "error"


class ChannelConfig(BaseModel):
    """渠道配置领域模型。

    Attributes:
        id: 配置唯一标识
        workspace_id: 所属工作空间 ID
        channel_type: 渠道类型
        name: 配置名称
        enabled: 是否启用
        allow_from: 允许访问的用户 ID 列表
        config: 渠道配置（加密存储）
        status: 连接状态
        created_at: 创建时间
        updated_at: 更新时间
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workspace_id: str
    channel_type: ChannelType
    name: str
    enabled: bool = False
    allow_from: List[str] = Field(default_factory=lambda: ["*"])
    config: Dict[str, Any] = Field(default_factory=dict)
    status: ChannelStatus = ChannelStatus.DISCONNECTED
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def mask_credentials(self) -> Dict[str, Any]:
        """返回脱敏后的配置（不含实际凭证值）。

        AI/Agent 只能看到 has_xxx 标志，不能看到实际凭证。
        """
        masked = {}
        for key, value in self.config.items():
            if self._is_sensitive_field(key):
                masked[f"has_{key}"] = bool(value)
            else:
                masked[key] = value
        return masked

    @staticmethod
    def _is_sensitive_field(key: str) -> bool:
        """判断字段是否为敏感凭证字段。"""
        sensitive_keywords = [
            "secret",
            "password",
            "token",
            "access_token",
            "encrypt_key",
            "app_secret",
            "smtp_password",
            "client_secret",
        ]
        key_lower = key.lower()
        return any(kw in key_lower for kw in sensitive_keywords)

    def has_any_credential(self) -> bool:
        """检查是否配置了任何凭证。"""
        return any(
            self._is_sensitive_field(key) and bool(value)
            for key, value in self.config.items()
        )

    def to_storage_dict(self) -> Dict[str, Any]:
        """转换为用于存储的字典格式。"""
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "channel_type": self.channel_type.value,
            "name": self.name,
            "enabled": self.enabled,
            "allow_from": self.allow_from,
            "config": self.config,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_storage_dict(cls, data: Dict[str, Any]) -> ChannelConfig:
        """从存储字典恢复领域模型。"""
        return cls(
            id=data["id"],
            workspace_id=data["workspace_id"],
            channel_type=ChannelType(data["channel_type"]),
            name=data["name"],
            enabled=bool(data.get("enabled", False)),
            allow_from=data.get("allow_from", ["*"]),
            config=data.get("config", {}),
            status=ChannelStatus(data.get("status", "disconnected")),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


# 渠道类型中文名称映射
CHANNEL_TYPE_NAMES: Dict[ChannelType, str] = {
    ChannelType.TELEGRAM: "Telegram",
    ChannelType.SLACK: "Slack",
    ChannelType.DISCORD: "Discord",
    ChannelType.FEISHU: "飞书",
    ChannelType.DINGTALK: "钉钉",
    ChannelType.EMAIL: "Email",
    ChannelType.QQ: "QQ",
    ChannelType.MATRIX: "Matrix",
    ChannelType.WHATSAPP: "WhatsApp",
    ChannelType.MOCHAT: "Mochat",
}


# 各渠道类型需要的配置字段
CHANNEL_REQUIRED_FIELDS: Dict[ChannelType, List[str]] = {
    ChannelType.TELEGRAM: ["token"],
    ChannelType.SLACK: ["bot_token", "app_token", "signing_secret"],
    ChannelType.DISCORD: ["token"],
    ChannelType.FEISHU: ["app_id", "app_secret"],
    ChannelType.DINGTALK: ["client_id", "client_secret"],
    ChannelType.EMAIL: ["smtp_host", "smtp_port", "smtp_username", "smtp_password", "from_address"],
    ChannelType.QQ: ["token", "app_id", "app_secret"],
    ChannelType.MATRIX: ["homeserver", "access_token", "user_id"],
    ChannelType.WHATSAPP: ["access_token", "phone_number_id", "verify_token"],
    ChannelType.MOCHAT: ["endpoint", "token"],
}


# 各渠道类型可选的配置字段
CHANNEL_OPTIONAL_FIELDS: Dict[ChannelType, List[str]] = {
    ChannelType.TELEGRAM: ["chat_id", "proxy"],
    ChannelType.SLACK: [],
    ChannelType.DISCORD: [],
    ChannelType.FEISHU: ["encrypt_key", "verification_token"],
    ChannelType.DINGTALK: ["robot_code"],
    ChannelType.EMAIL: [],
    ChannelType.QQ: [],
    ChannelType.MATRIX: [],
    ChannelType.WHATSAPP: [],
    ChannelType.MOCHAT: [],
}
