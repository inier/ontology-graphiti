from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Any
from datetime import datetime


class TemporalDimension(str, Enum):
    PAST = "past"
    PRESENT = "present"
    FUTURE = "future"
    HYPOTHETICAL = "hypothetical"


class PatternType(str, Enum):
    STRUCTURAL = "structural"
    BEHAVIORAL = "behavioral"
    TEMPORAL = "temporal"
    CAUSAL = "causal"


class ForceType(str, Enum):
    DRIVING = "driving"
    RESTRAINING = "restraining"
    LEVERAGING = "leveraging"
    EMERGING = "emerging"


class ActionDimension(str, Enum):
    OBSERVE = "observe"
    ORIENT = "orient"
    DECIDE = "decide"
    ACT = "act"


@dataclass
class TemporalNode:
    node_id: str
    dimension: TemporalDimension
    timestamp: str
    description: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PatternNode:
    pattern_id: str
    pattern_type: PatternType
    name: str
    description: str
    evidence: List[str] = field(default_factory=list)
    strength: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ForceNode:
    force_id: str
    force_type: ForceType
    name: str
    magnitude: float = 0.0
    direction: float = 0.0
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionNode:
    action_id: str
    dimension: ActionDimension
    name: str
    trigger_condition: str = ""
    effect: str = ""
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AbutionGraphSnapshot:
    snapshot_id: str
    name: str
    temporal_nodes: List[TemporalNode] = field(default_factory=list)
    pattern_nodes: List[PatternNode] = field(default_factory=list)
    force_nodes: List[ForceNode] = field(default_factory=list)
    action_nodes: List[ActionNode] = field(default_factory=list)
    cross_dimension_links: List[Dict[str, str]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
