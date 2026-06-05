from pydantic import BaseModel, Field
from typing import Dict, Any, List


class ValidationRule(BaseModel):
    rule_id: str = ""
    name: str
    rule_type: str = ""
    expression: str = ""
    severity: str = "error"


class ValidationResult(BaseModel):
    is_valid: bool = True
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)
