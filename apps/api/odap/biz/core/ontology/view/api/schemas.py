"""Object View - Pydantic Schemas

API 请求/响应模型。

`filters` 归一（契约裁定 2026-10-17）：
- 线上真源形态是 `{field: {op: value}}`（`ViewQueryEngineImpl._compile_filters` 消费）；
- 视图设计器（`ViewDesigner` / `ViewFieldMapping`）编辑的是规则数组
  `[{field, op, value}]`，直接 PUT 会被 `dict.items()` 打挂（500）。
- 故在**请求边界**做归一：数组 → 字典；字典原样透传（存量调用方零影响）。
  响应始终是字典形态（读侧由前端把字典转回规则数组）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

#: 设计器算子 → 查询引擎算子（引擎只认 eq/ne/gt/lt/in/contains）
_OP_ALIASES: Dict[str, str] = {
    "=": "eq", "==": "eq", "eq": "eq",
    "!=": "ne", "<>": "ne", "ne": "ne",
    ">": "gt", "gt": "gt",
    "<": "lt", "lt": "lt",
    "in": "in",
    "contains": "contains", "like": "contains",
}


def normalize_view_filters(value: Any) -> Dict[str, Any]:
    """把 `{field: {op: value}}` / `[{field, op, value}]` 统一成字典形态。

    同一字段的多条规则合并进同一个操作符字典（语义等价于 AND，与引擎逐条 AND 一致）。
    """
    if value is None or value == []:
        return {}
    if isinstance(value, dict):
        return value
    if not isinstance(value, list):
        raise ValueError(
            f"filters 必须是对象或规则数组，收到 {type(value).__name__}"
        )
    normalized: Dict[str, Any] = {}
    for index, rule in enumerate(value):
        if not isinstance(rule, dict):
            raise ValueError(f"filters[{index}] 必须是规则对象，收到 {type(rule).__name__}")
        field = rule.get("field")
        if not field:
            raise ValueError(f"filters[{index}].field 不能为空")
        raw_op = str(rule.get("op") or "=").lower()
        op = _OP_ALIASES.get(raw_op)
        if op is None:
            raise ValueError(
                f"filters[{index}].op 不支持：{rule.get('op')!r}，"
                f"可选 {sorted(set(_OP_ALIASES))}"
            )
        bucket = normalized.get(str(field))
        if not isinstance(bucket, dict):
            bucket = {}
            normalized[str(field)] = bucket
        bucket[op] = rule.get("value")
    return normalized


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

    @field_validator("filters", mode="before")
    @classmethod
    def _normalize_filters(cls, value: Any) -> Dict[str, Any]:
        return normalize_view_filters(value)


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

    @field_validator("filters", mode="before")
    @classmethod
    def _normalize_filters(cls, value: Any) -> Any:
        return None if value is None else normalize_view_filters(value)


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
