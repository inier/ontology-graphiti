"""连接模型"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime
import uuid


class Connection(BaseModel):
    """连接"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    server_id: str
    status: str = "active"
    created_at: datetime = Field(default_factory=datetime.now)
    last_used_at: Optional[datetime] = None
    request_count: int = 0


class ConnectionPool(BaseModel):
    """连接池"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    server_id: str
    max_connections: int = 10
    min_connections: int = 2
    current_connections: int = 0
    acquired_connections: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
