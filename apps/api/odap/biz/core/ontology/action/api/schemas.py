"""Action Type - Pydantic Schemas (T385)

API 请求/响应模型。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CreateActionTypeRequest(BaseModel):
    """创建 ActionType 请求"""
    name: str
    description: str = ""
    object_types: List[str] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    return_type: str = "void"
    side_effects: List[str] = Field(default_factory=list)
    linked_skill_id: Optional[str] = None
    opa_policy_ref: str = ""
    enabled: bool = True


class UpdateActionTypeRequest(BaseModel):
    """更新 ActionType 请求（所有字段可选）"""
    name: Optional[str] = None
    description: Optional[str] = None
    object_types: Optional[List[str]] = None
    parameters: Optional[Dict[str, Any]] = None
    return_type: Optional[str] = None
    side_effects: Optional[List[str]] = None
    linked_skill_id: Optional[str] = None
    opa_policy_ref: Optional[str] = None
    enabled: Optional[bool] = None


class ActionTypeResponse(BaseModel):
    """ActionType 响应"""
    id: str
    name: str
    description: str = ""
    object_types: List[str] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    return_type: str = "void"
    side_effects: List[str] = Field(default_factory=list)
    linked_skill_id: Optional[str] = None
    opa_policy_ref: str = ""
    enabled: bool = True
    created_at: str
    updated_at: str


class ListActionTypesResponse(BaseModel):
    """列出 ActionType 响应"""
    action_types: List[ActionTypeResponse] = Field(default_factory=list)
    count: int = 0


class ExecuteActionRequest(BaseModel):
    """执行 ActionType 请求"""
    parameters: Dict[str, Any] = Field(default_factory=dict)
    user_context: Dict[str, Any] = Field(default_factory=dict)


class ActionExecutionResponse(BaseModel):
    """ActionExecution 响应"""
    id: str
    action_type_id: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    result: Dict[str, Any] = Field(default_factory=dict)
    status: str
    error_message: str = ""
    audit_record_id: Optional[str] = None
    user_id: str = "system"
    workspace_id: str = "default"
    started_at: str
    finished_at: Optional[str] = None
    duration_ms: Optional[int] = None


class ListExecutionsResponse(BaseModel):
    """列出执行历史响应"""
    executions: List[ActionExecutionResponse] = Field(default_factory=list)
    count: int = 0


__all__ = [
    "CreateActionTypeRequest",
    "UpdateActionTypeRequest",
    "ActionTypeResponse",
    "ListActionTypesResponse",
    "ExecuteActionRequest",
    "ActionExecutionResponse",
    "ListExecutionsResponse",
]
