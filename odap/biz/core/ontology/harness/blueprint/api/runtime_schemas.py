from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class StartExecutionRequest(BaseModel):
    execution_id: str = Field(..., min_length=1)
    blueprint_id: str = Field(..., min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)
