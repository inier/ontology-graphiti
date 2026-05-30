from .types import ServiceType, GenerationStatus, CatalogEntryStatus
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid


class SkillTemplate(BaseModel):
    template_id: str = Field(default_factory=lambda: f"tpl-{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    service_type: ServiceType = ServiceType.SKILL
    object_type: str = ""
    function_mappings: List[Dict[str, Any]] = Field(default_factory=list)
    parameter_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    code_template: str = ""
    created_at: datetime = Field(default_factory=datetime.now)


class GeneratedService(BaseModel):
    service_id: str = Field(default_factory=lambda: f"svc-{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    service_type: ServiceType = ServiceType.SKILL
    source_ontology_id: str = ""
    source_object_type: str = ""
    source_function_ids: List[str] = Field(default_factory=list)
    template_id: Optional[str] = None
    code: str = ""
    parameter_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    endpoint_path: Optional[str] = None
    status: GenerationStatus = GenerationStatus.PENDING
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ServiceDeployment(BaseModel):
    deployment_id: str = Field(default_factory=lambda: f"dpl-{uuid.uuid4().hex[:8]}")
    service_id: str = ""
    endpoint_url: str = ""
    deployed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    is_active: bool = True
    health_status: str = "unknown"
    last_health_check: Optional[str] = None
