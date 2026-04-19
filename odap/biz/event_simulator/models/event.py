"""事件模拟器数据模型"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
from enum import Enum


class EventTemplate(BaseModel):
    """事件模板"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    event_type: str
    schema: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)


class GeneratedEvent(BaseModel):
    """生成的事件"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    template_id: str
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.now)
    data: Dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"


class TimeControl(BaseModel):
    """时间控制"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    simulation_speed: float = 1.0
    current_time: datetime = Field(default_factory=datetime.now)
    is_paused: bool = False
