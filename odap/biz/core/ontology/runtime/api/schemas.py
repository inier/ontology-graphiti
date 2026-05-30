from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from ..models.types import FunctionType, AggregateMethod, TriggerType

FunctionTypeRequest = FunctionType
AggregateMethodRequest = AggregateMethod
TriggerTypeRequest = TriggerType


class ContractEntryRequest(BaseModel):
    object_type: str
    property_name: Optional[str] = None
    description: str = ""


class CreateFunctionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    display_name: str = ""
    description: str = ""
    function_type: FunctionTypeRequest = FunctionTypeRequest.TRANSFORM
    target_object_type: str = Field(..., min_length=1)
    input_schema: Dict[str, Any] = {}
    output_schema: Dict[str, Any] = {}
    implementation: str = ""
    implementation_type: str = "python"
    dependencies: List[str] = []
    bound_action_contract: Optional[str] = None


class UpdateFunctionRequest(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    function_type: Optional[FunctionTypeRequest] = None
    status: Optional[str] = None
    implementation: Optional[str] = None
    dependencies: Optional[List[str]] = None


class CreateContractRequest(BaseModel):
    action_type_id: str = Field(..., min_length=1)
    action_name: str = ""
    description: str = ""
    read_set: List[ContractEntryRequest] = []
    write_set: List[ContractEntryRequest] = []
    side_effect_set: List[ContractEntryRequest] = []
    preconditions: List[str] = []
    postconditions: List[str] = []


class UpdateContractRequest(BaseModel):
    action_name: Optional[str] = None
    description: Optional[str] = None
    read_set: Optional[List[ContractEntryRequest]] = None
    write_set: Optional[List[ContractEntryRequest]] = None
    side_effect_set: Optional[List[ContractEntryRequest]] = None
    preconditions: Optional[List[str]] = None
    postconditions: Optional[List[str]] = None


class ExecuteFunctionRequest(BaseModel):
    context: Dict[str, Any] = {}


class ComputeImpactRequest(BaseModel):
    graph_id: str
    action_type_id: str
    target_object_type: str


class RecordMutationRequest(BaseModel):
    action_type_id: str = ""
    action_name: str = ""
    target_object_id: str = ""
    target_object_type: str = ""
    property_name: str = ""
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    mutation_type: str = "update"
    actor: str = ""
    scenario_id: Optional[str] = None



class CreateAggregateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    target_object_type: str = Field(..., min_length=1)
    target_property: str = Field(..., min_length=1)
    method: AggregateMethodRequest = AggregateMethodRequest.SUM
    window: str = "raw"
    group_by: List[str] = []
    output_property: str = ""


class ComputeAggregateRequest(BaseModel):
    data: List[Dict[str, Any]] = []


class CaptureSnapshotRequest(BaseModel):
    name: str = Field(..., min_length=1)
    scenario_id: Optional[str] = None
    is_baseline: bool = False


class CompareSnapshotsRequest(BaseModel):
    snapshot_id_a: str
    snapshot_id_b: str



class TriggerConditionRequest(BaseModel):
    condition_id: Optional[str] = None
    trigger_type: TriggerTypeRequest = TriggerTypeRequest.STATE_DRIVEN
    object_type: str = ""
    property_name: str = ""
    operator: str = "eq"
    threshold_value: Optional[Any] = None
    threshold_max: Optional[Any] = None
    description: str = ""
    is_active: bool = True


class CreateTriggerRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    conditions: List[TriggerConditionRequest] = []
    action_type_id: str = ""
    action_name: str = ""
    target_object_type: str = Field(..., min_length=1)
    target_object_id: Optional[str] = None
    parameters: Dict[str, Any] = {}
    is_active: bool = True
    priority: int = 0
    cooldown_seconds: int = 0


class EvaluateTriggersRequest(BaseModel):
    object_type: str = Field(..., min_length=1)
    object_id: str = Field(..., min_length=1)
    state_changes: Dict[str, Any] = {}


class ExecuteTriggerRequest(BaseModel):
    triggered_by: Dict[str, Any] = {}
