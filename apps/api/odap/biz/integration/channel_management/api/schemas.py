"""渠道配置 API 请求/响应模型。

Pydantic 模型定义。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CreateChannelRequest(BaseModel):
    """创建渠道配置请求。"""

    channel_type: str = Field(..., description="渠道类型: telegram, slack, feishu, etc.")
    name: str = Field(..., description="配置名称")
    workspace_id: str = Field(..., description="工作空间 ID")
    enabled: bool = Field(default=False, description="是否启用")
    allow_from: List[str] = Field(default_factory=lambda: ["*"], description="允许访问的用户 ID 列表")
    config: Dict[str, Any] = Field(default_factory=dict, description="渠道配置（含凭证）")


class UpdateChannelRequest(BaseModel):
    """更新渠道配置请求。"""

    name: Optional[str] = Field(None, description="新名称")
    config: Optional[Dict[str, Any]] = Field(None, description="新配置（凭证会被替换）")
    enabled: Optional[bool] = Field(None, description="是否启用")
    allow_from: Optional[List[str]] = Field(None, description="允许访问的用户 ID 列表")


class ChannelResponse(BaseModel):
    """渠道配置响应（凭证已脱敏）。"""

    id: str
    workspace_id: str
    channel_type: str
    name: str
    enabled: bool
    allow_from: List[str]
    config: Dict[str, Any]  # 已脱敏，只有 has_xxx 标志
    status: str
    has_credentials: bool
    created_at: str
    updated_at: str


class ChannelListResponse(BaseModel):
    """渠道列表响应。"""

    channels: List[ChannelResponse]
    total: int


class ChannelTypeInfo(BaseModel):
    """渠道类型信息。"""

    type: str
    name: str
    required_fields: List[str]
    optional_fields: List[str]


class TestConnectionResponse(BaseModel):
    """连接测试响应。"""

    success: bool
    message: str


class EnableDisableResponse(BaseModel):
    """启用/停用响应。"""

    status: str
    message: str
    channel: Optional[ChannelResponse] = None


class ErrorResponse(BaseModel):
    """错误响应。"""

    detail: str
