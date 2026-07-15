"""沙箱模型"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid


class SandboxConfig(BaseModel):
    """沙箱配置"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    max_memory_mb: int = 128
    max_cpu_percent: int = 50
    max_execution_time_ms: int = 5000
    allowed_modules: List[str] = Field(default_factory=list)
    blocked_modules: List[str] = Field(default_factory=list)
    network_enabled: bool = False
    filesystem_enabled: bool = False


class SandboxResult(BaseModel):
    """沙箱执行结果"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sandbox_config_id: str
    execution_time_ms: int = 0
    memory_used_mb: float = 0.0
    cpu_used_percent: float = 0.0
    status: str = "pending"
    output: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
