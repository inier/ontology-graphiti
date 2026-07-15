from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
import uuid


class ThoughtType(str, Enum):
    OBSERVATION = "observation"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"
    DECISION = "decision"
    REFLECTION = "reflection"
    PLAN = "plan"


class ReasoningMethod(str, Enum):
    DEDUCTIVE = "deductive"
    INDUCTIVE = "inductive"
    ABDUCTIVE = "abductive"
    ANALOGICAL = "analogical"
    HEURISTIC = "heuristic"


@dataclass
class ThoughtNode:
    thought_id: str = field(default_factory=lambda: f"thought-{uuid.uuid4().hex[:8]}")
    thought_type: ThoughtType = ThoughtType.OBSERVATION
    content: str = ""
    premises: List[str] = field(default_factory=list)
    conclusion: str = ""
    confidence: float = 0.5
    reasoning_method: ReasoningMethod = ReasoningMethod.HEURISTIC
    source_entity_ids: List[str] = field(default_factory=list)
    source_scenario_id: Optional[str] = None
    agent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ReasoningChain:
    chain_id: str = field(default_factory=lambda: f"chain-{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    thought_ids: List[str] = field(default_factory=list)
    chain_type: str = "sequential"
    scenario_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
