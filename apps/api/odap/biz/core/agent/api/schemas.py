from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional


class DispatchRequest(BaseModel):
    intent: str
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    workspace_id: Optional[str] = None


class DispatchResponse(BaseModel):
    task_id: str
    assigned_agent: str
    confidence: float
    routing_source: str
    plan: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "dispatched"


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    phases_completed: List[str] = Field(default_factory=list)
    mission: Optional[str] = None
    final_decision: Optional[Dict[str, Any]] = None
    execution_time_ms: Optional[float] = None
    error_message: Optional[str] = None


class DecisionChainResponse(BaseModel):
    task_id: str
    chain: List[Dict[str, Any]] = Field(default_factory=list)
    final_decision: Optional[Dict[str, Any]] = None


class SwarmConfigRequest(BaseModel):
    agent_roles: Optional[Dict[str, Any]] = None
    routing_rules: Optional[List[Dict[str, Any]]] = None


class OrchestrateRequest(BaseModel):
    """统一编排请求"""
    query: str
    user_id: str = "anonymous"
    workspace_id: str = "default"
    scenario_id: Optional[str] = None
    agent_id: Optional[str] = None
    mode: str = "auto"  # "auto" | "swarm" | "react" | "harness"
    session_id: Optional[str] = None  # 会话 ID，用于持久化聊天历史


class OrchestrateResponse(BaseModel):
    """统一编排响应"""
    result_id: str = ""
    mode: str = ""
    answer: str = ""
    reasoning_chain: List[Dict[str, Any]] = Field(default_factory=list)
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class CreateSessionRequest(BaseModel):
    """创建 Agent 会话请求"""
    workspace_id: str = "default"
    title: str = ""
