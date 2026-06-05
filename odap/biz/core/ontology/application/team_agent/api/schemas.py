from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


class DictResponse(BaseModel):
    """Flexible response model that accepts arbitrary dict shapes from service layer.

    Uses ``extra="allow"`` to remain backward compatible with all existing
    service-layer dicts while still being a proper Pydantic model (eliminates
    ``response_model=dict`` usage).
    """
    model_config = ConfigDict(extra="allow")

    status: Optional[str] = None
    message: Optional[str] = None


class CreateTeamSessionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    requirement: str = Field(..., min_length=1)
    description: str = ""
    scenario_id: Optional[str] = None
    workspace_id: Optional[str] = None


class RunPlanningRequest(BaseModel):
    pass


class RunOntologyRequest(BaseModel):
    pass


class RunExecutionRequest(BaseModel):
    pass


class ApproveStepRequest(BaseModel):
    step: str = Field(..., min_length=1)
    comment: str = ""
