from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict, Any
from ..models.types import ServiceType

ServiceTypeRequest = ServiceType


class DictResponse(BaseModel):
    """Flexible response model that accepts arbitrary dict shapes from service layer.

    Uses ``extra="allow"`` to remain backward compatible with all existing
    service-layer dicts while still being a proper Pydantic model (eliminates
    ``response_model=dict`` usage).
    """
    model_config = ConfigDict(extra="allow")

    status: Optional[str] = None
    message: Optional[str] = None


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
