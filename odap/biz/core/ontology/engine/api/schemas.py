from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class CreateVersionRequest(BaseModel):
    ontology_id: str
    changelog: str = ""
    valid_time: str = ""
    snapshot: Dict[str, Any] = Field(default_factory=dict)


class RollbackRequest(BaseModel):
    target_version_id: str


class ValidateRequest(BaseModel):
    type_def: Dict[str, Any]
    properties: Optional[Dict[str, Any]] = None


class RecordAuditRequest(BaseModel):
    entity_type_id: str
    source: str = ""
    process_steps: List[Dict[str, Any]] = Field(default_factory=list)
    transform_rules: List[Dict[str, Any]] = Field(default_factory=list)
    result: str = ""
