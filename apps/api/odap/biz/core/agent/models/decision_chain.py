import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, Field


class DecisionPhase(str, Enum):
    OBSERVE = "observe"
    ORIENT = "orient"
    DECIDE = "decide"
    ACT = "act"


class DecisionStep(BaseModel):
    step_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    phase: DecisionPhase
    description: str = ""
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DecisionChain(BaseModel):
    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    steps: List[DecisionStep] = Field(default_factory=list)
    reasoning: str = ""
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    workspace_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
