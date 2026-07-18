from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class ExtractRequest(BaseModel):
    text: str = Field(..., min_length=1)
    ontology_id: str = Field(..., min_length=1)
    scenario_id: Optional[str] = None
    workspace_id: Optional[str] = None
    template_override: Optional[Dict[str, Any]] = None


class ExtractResponse(BaseModel):
    status: str
    entities_count: int = 0
    relations_count: int = 0
    valid_time: Optional[str] = None


class BatchExtractRequest(BaseModel):
    texts: List[str] = Field(..., min_length=1)
    ontology_id: str = Field(..., min_length=1)
    scenario_id: Optional[str] = None
    workspace_id: Optional[str] = None
    max_concurrency: int = Field(default=5, ge=1, le=20)


class TemplateResponse(BaseModel):
    ontology_id: str
    template: Dict[str, Any] = Field(default_factory=dict)
