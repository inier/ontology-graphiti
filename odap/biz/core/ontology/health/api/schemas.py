"""Data Health - Pydantic Schemas (T342)

API 请求/响应模型。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CreateHealthRuleRequest(BaseModel):
    """创建健康规则请求"""
    name: str
    target_type_id: str
    description: str = ""
    rule_type: str = "not_null"
    check_expression: Dict[str, Any] = Field(default_factory=dict)
    severity: str = "warning"
    schedule: str = ""
    notification_channel: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class UpdateHealthRuleRequest(BaseModel):
    """更新健康规则请求（所有字段可选）"""
    name: Optional[str] = None
    target_type_id: Optional[str] = None
    description: Optional[str] = None
    rule_type: Optional[str] = None
    check_expression: Optional[Dict[str, Any]] = None
    severity: Optional[str] = None
    schedule: Optional[str] = None
    notification_channel: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


class HealthRuleResponse(BaseModel):
    """健康规则响应"""
    id: str
    target_type_id: str
    name: str
    description: str = ""
    rule_type: str
    check_expression: Dict[str, Any] = Field(default_factory=dict)
    severity: str
    schedule: str = ""
    notification_channel: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool
    created_at: str
    updated_at: str


class ListRulesResponse(BaseModel):
    """列出规则响应"""
    rules: List[HealthRuleResponse] = Field(default_factory=list)
    count: int = 0


class ScanRequest(BaseModel):
    """触发扫描请求"""
    rule_id: Optional[str] = None


class HealthReportResponse(BaseModel):
    """单条健康报告响应"""
    id: str
    rule_id: str
    instance_id: str
    target_type_id: str
    status: str
    severity: str
    message: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)
    scanned_at: str


class ListReportsResponse(BaseModel):
    """列出报告响应"""
    reports: List[HealthReportResponse] = Field(default_factory=list)
    count: int = 0
    total: int = 0
    limit: int = 100
    offset: int = 0


class ScanResponse(BaseModel):
    """扫描结果响应"""
    scanned_count: int = 0
    pass_count: int = 0
    warn_count: int = 0
    fail_count: int = 0
    rule_id: Optional[str] = None
    reports: List[HealthReportResponse] = Field(default_factory=list)


__all__ = [
    "CreateHealthRuleRequest",
    "UpdateHealthRuleRequest",
    "HealthRuleResponse",
    "ListRulesResponse",
    "ScanRequest",
    "HealthReportResponse",
    "ListReportsResponse",
    "ScanResponse",
]
