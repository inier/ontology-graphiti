from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from ..models.types import ServiceType

ServiceTypeRequest = ServiceType


class CreateTemplateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    service_type: ServiceTypeRequest = ServiceTypeRequest.SKILL
    object_type: str = ""
    function_mappings: List[Dict[str, Any]] = Field(default_factory=list)
    parameter_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    code_template: str = ""


class GenerateServiceRequest(BaseModel):
    template_id: str = Field(..., min_length=1)
    name: Optional[str] = None
    description: Optional[str] = None
    source_ontology_id: str = ""
    source_object_type: str = ""
    source_function_ids: List[str] = Field(default_factory=list)
    parameter_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    endpoint_path: Optional[str] = None


class DeployServiceRequest(BaseModel):
    service_id: str = Field(..., min_length=1)


class GenerateFromOntologyRequest(BaseModel):
    ontology_id: str = Field(..., min_length=1)
    service_type: ServiceTypeRequest = ServiceTypeRequest.SKILL
