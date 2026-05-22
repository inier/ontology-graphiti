from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class SimulationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class MetricChange(BaseModel):
    metric_name: str
    before: Any = None
    after: Any = None
    delta: Optional[float] = None
    unit: str = ""


class WhatIfScenario(BaseModel):
    scenario_id: str = ""
    name: str = ""
    description: str = ""
    action_type_id: str
    target_object_id: str
    target_object_type: str
    parameters: Dict[str, Any] = {}
    variant_parameters: List[Dict[str, Any]] = []


class WhatIfResult(BaseModel):
    scenario_id: str
    status: SimulationStatus
    baseline_metrics: Dict[str, Any] = {}
    projected_metrics: List[Dict[str, Any]] = []
    metric_changes: List[MetricChange] = []
    risk_assessment: Dict[str, Any] = {}
    recommendation: str = ""
    confidence: float = 0.0
    error: Optional[str] = None


class WhatIfComparison(BaseModel):
    scenarios: List[WhatIfResult] = []
    best_scenario_id: Optional[str] = None
    summary: str = ""
