from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from enum import Enum


class AgentRole(str, Enum):
    DIRECTOR = "director"
    INTELLIGENCE = "intelligence"
    OPERATIONS = "operations"


class AgentConfig(BaseModel):
    agent_id: str = ""
    name: str = ""
    role: AgentRole = AgentRole.INTELLIGENCE
    workspace_id: str = ""
    description: str = ""
    skills: List[str] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)

    # Loop 工程参数（可配置化，替代硬编码）
    max_iterations: int = Field(default=5, description="ReAct 最大迭代次数")
    max_correction_attempts: int = Field(default=3, description="自校正最大尝试次数")
    timeout_seconds: int = Field(default=300, description="执行超时（秒）")
    retry_count: int = Field(default=3, description="LLM 调用重试次数")
    max_ooda_loops: int = Field(default=3, description="OODA 最大循环次数")
