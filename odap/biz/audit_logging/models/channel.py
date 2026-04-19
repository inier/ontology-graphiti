"""异步通道模型"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
from enum import Enum


class ChannelStatus(str, Enum):
    """通道状态"""
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    CLOSED = "closed"


class ChannelType(str, Enum):
    """通道类型"""
    MEMORY = "memory"
    REDIS = "redis"
    KAFKA = "kafka"
    RABBITMQ = "rabbitmq"


class Channel(BaseModel):
    """异步通道"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: ChannelType = ChannelType.MEMORY
    status: ChannelStatus = ChannelStatus.ACTIVE
    config: Dict[str, Any] = Field(default_factory=dict)
    capacity: int = 10000
    current_size: int = 0
    processed_count: int = 0
    failed_count: int = 0
    last_processed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
