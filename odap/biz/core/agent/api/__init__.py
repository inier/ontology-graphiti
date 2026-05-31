from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from enum import Enum


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
