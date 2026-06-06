"""Object View - Pydantic Schemas

API 请求/响应模型。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CreateViewRequest(BaseModel):
    """创建视图请求"""
    name: str
    base_type_id: str
    role: str
    description: str = ""
    projected_properties: List[str] = Field(default_factory=list)
    filters: Dict[str, Any] = Field(default_factory=dict)
    row_limit: int = 100
    sort_order: List[Dict[str, str]] = Field(default_factory=list)
    enabled: bool = True
    created_by: str = "system"


class UpdateViewRequest(BaseModel):
    """更新视图请求（所有字段可选）"""
    name: Optional[str] = None
    description: Optional[str] = None
    base_type_id: Optional[str] = None
    role: Optional[str] = None
    projected_properties: Optional[List[str]] = None
    filters: Optional[Dict[str, Any]] = None
    row_limit: Optional[int] = None
    sort_order: Optional[List[Dict[str, str]]] = None
    enabled: Optional[bool] = None


class ViewResponse(BaseModel):
    """视图响应"""
    id: str
    name: str
    description: str = ""
    base_type_id: str
    role: str
    projected_properties: List[str] = Field(default_factory=list)
    filters: Dict[str, Any] = Field(default_factory=dict)
    row_limit: int = 100
    sort_order: List[Dict[str, str]] = Field(default_factory=list)
    enabled: bool = True
    created_by: str = "system"
    created_at: str
    updated_at: str


class ListViewsResponse(BaseModel):
    """列出视图响应"""
    views: List[ViewResponse] = Field(default_factory=list)
    count: int = 0


class QueryViewRequest(BaseModel):
    """视图查询请求"""
    user_id: str = ""
    ws_id: str = ""
    role: str = ""


class QueryViewResponse(BaseModel):
    """视图查询响应"""
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    total_count: int = 0
    truncated: bool = False


class AttachPermissionRequest(BaseModel):
    """添加/更新视图权限请求"""
    role: str
    can_export: bool = False
    can_share: bool = False
    redaction_rules: Dict[str, Any] = Field(default_factory=dict)


class PermissionResponse(BaseModel):
    """权限响应"""
    id: str
    view_id: str
    role: str
    can_export: bool = False
    can_share: bool = False
    redaction_rules: Dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ListPermissionsResponse(BaseModel):
    """权限列表响应"""
    permissions: List[PermissionResponse] = Field(default_factory=list)
    count: int = 0


__all__ = [
    "CreateViewRequest",
    "UpdateViewRequest",
    "ViewResponse",
    "ListViewsResponse",
    "QueryViewRequest",
    "QueryViewResponse",
    "AttachPermissionRequest",
    "PermissionResponse",
    "ListPermissionsResponse",
]
