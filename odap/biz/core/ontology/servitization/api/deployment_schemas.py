from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class DeployRequest(BaseModel):
    deployment_id: str = Field(..., min_length=1)
    service_id: str = Field(..., min_length=1)
    service_name: str = Field(..., min_length=1)
    version: str = "1.0.0"
    endpoint: str = ""
    config: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
