from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class CreateEntityTypeRequest(BaseModel):
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    properties: List[Dict[str, Any]] = Field(default_factory=list)
    primary_key: List[str] = Field(default_factory=list)
    links: List[Dict[str, Any]] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)
    constraints: List[Dict[str, Any]] = Field(default_factory=list)
    classification_level: str = "U"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UpdateEntityTypeRequest(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    properties: Optional[List[Dict[str, Any]]] = None
    primary_key: Optional[List[str]] = None
    links: Optional[List[Dict[str, Any]]] = None
    actions: Optional[List[str]] = None
    constraints: Optional[List[Dict[str, Any]]] = None
    classification_level: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CreateInstanceRequest(BaseModel):
    type_id: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    workspace_id: str = "default"


class UpdateInstanceRequest(BaseModel):
    properties: Optional[Dict[str, Any]] = None
    workspace_id: Optional[str] = None


class BatchImportRequest(BaseModel):
    instances: List[Dict[str, Any]]


class CreateDocumentRequest(BaseModel):
    name: str
    version: str = "1.0.0"
    object_types: List[Dict[str, Any]] = Field(default_factory=list)
    action_types: List[Dict[str, Any]] = Field(default_factory=list)
    relations: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
