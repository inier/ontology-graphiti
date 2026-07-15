"""Computed Property - Pydantic Schemas (T398-prep)

API 请求/响应模型。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CreateComputedPropertyRequest(BaseModel):
    """创建 ComputedProperty 请求"""
    name: str
    target_type_id: str
    expression: str
    dependencies: List[str] = Field(default_factory=list)
    materialization: str = "incremental"
    return_type: str = "any"
    description: str = ""
    enabled: bool = True


class UpdateComputedPropertyRequest(BaseModel):
    """更新 ComputedProperty 请求（所有字段可选）"""
    name: Optional[str] = None
    target_type_id: Optional[str] = None
    expression: Optional[str] = None
    dependencies: Optional[List[str]] = None
    materialization: Optional[str] = None
    return_type: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None


class ComputedPropertyResponse(BaseModel):
    """ComputedProperty 响应"""
    id: str
    name: str
    target_type_id: str
    expression: str
    dependencies: List[str] = Field(default_factory=list)
    materialization: str = "incremental"
    return_type: str = "any"
    description: str = ""
    enabled: bool = True
    created_at: str
    updated_at: str


class ListComputedPropertiesResponse(BaseModel):
    """列出 ComputedProperty 响应"""
    properties: List[ComputedPropertyResponse] = Field(default_factory=list)
    count: int = 0


class EvaluateRequest(BaseModel):
    """评估单实例请求"""
    instance_id: str
    instance_data: Dict[str, Any] = Field(default_factory=dict)


class EvaluateResponse(BaseModel):
    """评估单实例响应"""
    property_id: str
    instance_id: str
    value: Any = None
    status: str = "ok"


class RecomputeRequest(BaseModel):
    """触发重算请求"""
    mode: str = "incremental"
    changed_property_id: Optional[str] = None


class RecomputeResponse(BaseModel):
    """触发重算响应"""
    mode: str
    affected: List[str] = Field(default_factory=list)
    job_ids: List[str] = Field(default_factory=list)
    first_job_id: Optional[str] = None
    status: str = "ok"


class MaterializationJobResponse(BaseModel):
    """MaterializationJob 响应"""
    id: str
    property_id: str
    status: str
    started_at: str
    finished_at: Optional[str] = None
    processed_count: int = 0
    error_message: str = ""
    triggered_by: str = "manual"
    mode: str = "incremental"


class ListJobsResponse(BaseModel):
    """列出 Job 响应"""
    jobs: List[MaterializationJobResponse] = Field(default_factory=list)
    count: int = 0


__all__ = [
    "CreateComputedPropertyRequest",
    "UpdateComputedPropertyRequest",
    "ComputedPropertyResponse",
    "ListComputedPropertiesResponse",
    "EvaluateRequest",
    "EvaluateResponse",
    "RecomputeRequest",
    "RecomputeResponse",
    "MaterializationJobResponse",
    "ListJobsResponse",
]
