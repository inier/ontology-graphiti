from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class CreateScenarioRequest(BaseModel):
    name: str
    description: str = ""
    source_recommendation_id: Optional[str] = None
    source_analysis_id: Optional[str] = None
    target_object_id: str = ""
    target_object_type: str = ""


class AddChainRequest(BaseModel):
    name: str
    description: str = ""
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    conditions: List[Dict[str, Any]] = Field(default_factory=list)


class UpdateConditionRequest(BaseModel):
    value: Any = None


class SimulateChainRequest(BaseModel):
    chain_id: str


class CompareChainsRequest(BaseModel):
    chain_ids: List[str] = Field(default_factory=list)


class ListScenariosRequest(BaseModel):
    filters: Dict[str, Any] = Field(default_factory=dict)
    page: int = 1
    page_size: int = 20
