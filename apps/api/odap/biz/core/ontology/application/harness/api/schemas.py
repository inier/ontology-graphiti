from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict, Any
from ..blueprint.api.schemas import (
    CreateBlueprintRequest as BlueprintCreateBlueprintRequest,
    UpdateBlueprintRequest as BlueprintUpdateBlueprintRequest,
)


class DictResponse(BaseModel):
    """Flexible response model that accepts arbitrary dict shapes from service layer.

    Uses ``extra="allow"`` to remain backward compatible with all existing
    service-layer dicts while still being a proper Pydantic model (eliminates
    ``response_model=dict`` usage).
    """
    model_config = ConfigDict(extra="allow")

    status: Optional[str] = None
    message: Optional[str] = None


class CreateSessionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    scenario_id: Optional[str] = None
    workspace_id: Optional[str] = None
    requirement: str = ""


class AdvanceStageRequest(BaseModel):
    stage_output: Dict[str, Any] = Field(default_factory=dict)


class FailStageRequest(BaseModel):
    error: str = Field(..., min_length=1)


class CreateHITLRequest(BaseModel):
    stage: str
    risk_level: str = "medium"
    title: str = Field(..., min_length=1)
    description: str = ""
    affected_objects: List[str] = Field(default_factory=list)


class ResolveHITLRequest(BaseModel):
    confirmation_id: str
    resolution: str = Field(..., min_length=1)
    resolved_by: str = ""


class AddAgentTaskRequest(BaseModel):
    agent_type: str
    stage: str
    description: str = ""
    input_data: Dict[str, Any] = Field(default_factory=dict)


class UpdateAgentTaskRequest(BaseModel):
    task_id: str
    output_data: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    error: Optional[str] = None


class UpdateContextRequest(BaseModel):
    key: str
    value: Any


class CheckHITLRequest(BaseModel):
    operation: str
    affected_types: List[str] = Field(default_factory=list)


class CreateBlueprintRequest(BlueprintCreateBlueprintRequest):
    session_id: Optional[str] = None


UpdateBlueprintRequest = BlueprintUpdateBlueprintRequest


class RunPlanningRequest(BaseModel):
    pass


class RunOntologyRequest(BaseModel):
    pass


class RunExecutionRequest(BaseModel):
    pass


class ApproveStepRequest(BaseModel):
    stage: str = Field(..., min_length=1)
    approved_by: str = ""


class RejectStepRequest(BaseModel):
    stage: str = Field(..., min_length=1)
    reason: str = ""
