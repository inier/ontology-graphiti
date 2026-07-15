from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class CreateStateMachineRequest(BaseModel):
    name: str
    target_object_type: str
    states: List[Dict[str, Any]]
    transitions: List[Dict[str, Any]]
    initial_state: str = ""
    description: str = ""
    scenario_id: Optional[str] = None
    bound_action_type_ids: List[str] = Field(default_factory=list)


class TransitionRequest(BaseModel):
    object_id: str
    action_type_id: str
    context: Optional[Dict[str, Any]] = None


class BindActionRequest(BaseModel):
    action_type_id: str
