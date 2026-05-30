from .types import FunctionType, FunctionStatus, AggregateWindow, AggregateMethod, TriggerType
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime
import uuid


class ContractEntry(BaseModel):
    object_type: str
    property_name: Optional[str] = None
    description: str = ""


class ActionContract(BaseModel):
    contract_id: str = Field(default_factory=lambda: f"contract-{uuid.uuid4().hex[:8]}")
    action_type_id: str = ""
    action_name: str = ""
    description: str = ""
    read_set: List[ContractEntry] = Field(default_factory=list)
    write_set: List[ContractEntry] = Field(default_factory=list)
    side_effect_set: List[ContractEntry] = Field(default_factory=list)
    preconditions: List[str] = Field(default_factory=list)
    postconditions: List[str] = Field(default_factory=list)
    is_verified: bool = False
    verified_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class OntologyFunction(BaseModel):
    function_id: str = Field(default_factory=lambda: f"func-{uuid.uuid4().hex[:8]}")
    name: str = ""
    display_name: str = ""
    description: str = ""
    function_type: FunctionType = FunctionType.TRANSFORM
    status: FunctionStatus = FunctionStatus.DRAFT
    target_object_type: str = ""
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    implementation: str = ""
    implementation_type: str = "python"
    dependencies: List[str] = Field(default_factory=list)
    bound_action_contract: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class PropagationEdge(BaseModel):
    source_type: str
    source_property: Optional[str] = None
    action_name: str = ""
    target_type: str
    target_property: Optional[str] = None
    propagation_type: str = "direct"
    probability: float = 1.0
    latency_ms: int = 0
    condition: str = ""


class StatePropagationGraph(BaseModel):
    graph_id: str = Field(default_factory=lambda: f"spg-{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    edges: List[PropagationEdge] = Field(default_factory=list)
    object_types: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class MutationRecord(BaseModel):
    mutation_id: str = Field(default_factory=lambda: f"mut-{uuid.uuid4().hex[:8]}")
    action_type_id: str = ""
    action_name: str = ""
    target_object_id: str = ""
    target_object_type: str = ""
    property_name: str = ""
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    mutation_type: str = "update"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    actor: str = ""
    scenario_id: Optional[str] = None


class WorldStateSnapshot(BaseModel):
    snapshot_id: str = Field(default_factory=lambda: f"snap-{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    object_states: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    scenario_id: Optional[str] = None
    is_baseline: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class AggregateDefinition(BaseModel):
    agg_id: str = Field(default_factory=lambda: f"agg-{uuid.uuid4().hex[:8]}")
    name: str = ""
    target_object_type: str = ""
    target_property: str = ""
    method: AggregateMethod = AggregateMethod.SUM
    window: AggregateWindow = AggregateWindow.RAW
    group_by: List[str] = Field(default_factory=list)
    output_property: str = ""
    is_active: bool = True


class TriggerCondition(BaseModel):
    condition_id: str = Field(default_factory=lambda: f"cond-{uuid.uuid4().hex[:8]}")
    trigger_type: TriggerType = TriggerType.STATE_DRIVEN
    object_type: str = ""
    property_name: str = ""
    operator: str = "eq"
    threshold_value: Any = None
    threshold_max: Optional[Any] = None
    description: str = ""
    is_active: bool = True


class ActionTrigger(BaseModel):
    trigger_id: str = Field(default_factory=lambda: f"trig-{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    conditions: List[TriggerCondition] = Field(default_factory=list)
    action_type_id: str = ""
    action_name: str = ""
    target_object_type: str = ""
    target_object_id: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    priority: int = 0
    cooldown_seconds: int = 0
    last_fired_at: Optional[str] = None
    fire_count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class TriggerExecution(BaseModel):
    execution_id: str = Field(default_factory=lambda: f"exec-{uuid.uuid4().hex[:8]}")
    trigger_id: str = ""
    action_type_id: str = ""
    action_name: str = ""
    triggered_by: Dict[str, Any] = Field(default_factory=dict)
    target_object_id: str = ""
    target_object_type: str = ""
    parameters: Dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None


class ActionContext(BaseModel):
    context_id: str = Field(default_factory=lambda: f"ctx-{uuid.uuid4().hex[:8]}")
    action_type_id: str = ""
    action_name: str = ""
    target_object: Dict[str, Any] = Field(default_factory=dict)
    related_objects: List[Dict[str, Any]] = Field(default_factory=list)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    scenario_id: Optional[str] = None
    workspace_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
