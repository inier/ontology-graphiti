"""sa_config 请求/响应 Pydantic schema。"""
from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class SaConfigBaseResponse(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    status: str = "ok"


class SetConfigRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    value: Any = Field(..., description="配置值，可传任意 JSON 兼容类型")
    updated_by: str = Field(default="system", max_length=128)


class SaConfigEntryResponse(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    id: str
    scope: str
    config_key: str
    config_value: Dict[str, Any]
    updated_by: str
    created_at: str
    updated_at: str


class SaConfigListResponse(BaseModel):
    model_config = ConfigDict(strict=False, extra="forbid")
    items: List[SaConfigEntryResponse]
    count: int = 0


class SaConfigDeleteResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    scope: str
    config_key: str
    deleted: bool


class EnsureBuiltinResponse(BaseModel):
    model_config = ConfigDict(strict=False, extra="forbid")
    scopes: List[str] = Field(default_factory=list)
    migrated: Dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "SaConfigBaseResponse",
    "SetConfigRequest",
    "SaConfigEntryResponse",
    "SaConfigListResponse",
    "SaConfigDeleteResponse",
    "EnsureBuiltinResponse",
]
