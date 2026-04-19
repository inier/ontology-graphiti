"""Skill实例模型"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
from enum import Enum


class InstanceStatus(str, Enum):
    """实例状态"""
    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class SkillInstance(BaseModel):
    """Skill实例"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    skill_id: str
    skill_version: str
    name: str
    status: InstanceStatus = InstanceStatus.PENDING
    config: Dict[str, Any] = Field(default_factory=dict)
    state: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    last_executed_at: Optional[datetime] = None
