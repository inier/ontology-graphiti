from pydantic import BaseModel, Field
from typing import Optional


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
