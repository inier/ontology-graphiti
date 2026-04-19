"""Skill模型"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
from enum import Enum


class SkillStatus(str, Enum):
    """Skill状态"""
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"


class SkillType(str, Enum):
    """Skill类型"""
    ACTION = "action"
    QUERY = "query"
    TRANSFORM = "transform"
    INTEGRATION = "integration"


class SkillVersion(BaseModel):
    """Skill版本"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    skill_id: str
    version: str
    schema: Dict[str, Any] = Field(default_factory=dict)
    implementation: str
    changelog: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    created_by: str = "system"
    is_stable: bool = False


class Skill(BaseModel):
    """Skill"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    type: SkillType = SkillType.ACTION
    status: SkillStatus = SkillStatus.DRAFT
    category: str = "general"
    tags: List[str] = Field(default_factory=list)
    current_version: str = "1.0.0"
    versions: List[SkillVersion] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: str = "system"
