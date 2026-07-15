from pydantic import BaseModel, Field
from typing import Dict, Any, List


class AuditRecord(BaseModel):
    audit_id: str = ""
    entity_type_id: str = ""
    source: str = ""
    process_steps: List[Dict[str, Any]] = Field(default_factory=list)
    transform_rules: List[Dict[str, Any]] = Field(default_factory=list)
    result: str = ""
    timestamp: str = ""
