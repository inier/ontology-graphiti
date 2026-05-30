from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from ..blueprint.api.schemas import (
    CreateBlueprintRequest as BlueprintCreateBlueprintRequest,
    UpdateBlueprintRequest as BlueprintUpdateBlueprintRequest,
)


class CreateSessionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    scenario_id: Optional[str] = None
    workspace_id: Optional[str] = None
    requirement: str = ""


class AdvanceStageRequest(BaseModel):
    stage_output: Dict[str, Any] = {}


class FailStageRequest(BaseModel):
    error: str = Field(..., min_length=1)


class CreateHITLRequest(BaseModel):
    stage: str
    risk_level: str = "medium"
    title: str = Field(..., min_length=1)
    description: str = ""
    affected_objects: List[str] = []


class ResolveHITLRequest(BaseModel):
    confirmation_id: str
    resolution: str = Field(..., min_length=1)
    resolved_by: str = ""


class AddAgentTaskRequest(BaseModel):
    agent_type: str
    stage: str
    description: str = ""
    input_data: Dict[str, Any] = {}


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
    affected_types: List[str] = []


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
