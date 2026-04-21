"""验证引擎模型"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
from enum import Enum


class ValidationSeverity(str, Enum):
    """验证严重程度"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationRule(BaseModel):
    """验证规则"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    rule_type: str  # entity/relation/property
    severity: ValidationSeverity = ValidationSeverity.WARNING
    expression: str  # 规则表达式
    params: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class ValidationResult(BaseModel):
    """验证结果"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ontology_id: str
    ontology_version: str
    validation_time: datetime = Field(default_factory=datetime.now)
    status: str = "pending"  # pending/running/complete/failed
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    info: List[Dict[str, Any]] = Field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    overall_score: float = 1.0  # 0-1
    duration_seconds: float = 0.0


class ValidationIssue(BaseModel):
    """验证问题"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_id: str
    rule_name: str
    severity: ValidationSeverity
    entity_id: Optional[str] = None
    relation_id: Optional[str] = None
    property_name: Optional[str] = None
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
