import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ToolType(str, Enum):
    SKILL = "skill"
    MCP = "mcp"
    REST = "rest"
    FUNCTION = "function"


class ToolCapability(str, Enum):
    QUERY = "query"
    ACTION = "action"
    TRANSFORM = "transform"
    MONITOR = "monitor"
    ANALYZE = "analyze"


class ToolStatus(str, Enum):
    REGISTERED = "registered"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"


class ToolDefinition(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    tool_type: ToolType = ToolType.FUNCTION
    category: str = "general"
    version: str = "1.0.0"
    danger_level: str = "low"
    capabilities: List[str] = Field(default_factory=list)
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    permissions: List[str] = Field(default_factory=list)
    semantic_tags: List[str] = Field(default_factory=list)
    opa_action: str = ""
    requires_opa_check: bool = False
    rate_limit: int = 100
    timeout_ms: int = 30000
    metadata: Dict[str, Any] = Field(default_factory=dict)
    status: ToolStatus = ToolStatus.REGISTERED
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ToolInvocation(BaseModel):
    tool_id: str
    params: Dict[str, Any] = Field(default_factory=dict)
    user: Optional[Dict[str, Any]] = None
    trace_id: Optional[str] = None


class ToolInvocationResult(BaseModel):
    tool_id: str
    tool_name: str = ""
    success: bool = False
    data: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
