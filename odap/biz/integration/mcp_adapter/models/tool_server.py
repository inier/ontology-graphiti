"""Tool Server模型"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
from enum import Enum


class ServerStatus(str, Enum):
    """服务器状态"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class ServerCapability(str, Enum):
    """服务器能力"""
    TOOLS = "tools"
    RESOURCES = "resources"
    PROMPTS = "prompts"


class ToolServer(BaseModel):
    """Tool Server"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    url: str
    status: ServerStatus = ServerStatus.DISCONNECTED
    capabilities: List[ServerCapability] = Field(default_factory=list)
    tools: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    connected_at: Optional[datetime] = None
    last_pinged_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
