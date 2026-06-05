from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from enum import Enum


class AgentRole(str, Enum):
    COMMANDER = "commander"
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
