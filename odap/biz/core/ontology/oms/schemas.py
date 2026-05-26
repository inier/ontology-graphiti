from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class PropertyType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    GEOPOINT = "geopoint"
    JSON = "json"
    REFERENCE = "reference"


class PropertyDefinition(BaseModel):
    name: str
    display_name: str = ""
    property_type: PropertyType = PropertyType.STRING
    required: bool = False
    default: Optional[Any] = None
    description: str = ""
    reference_type: Optional[str] = None
    enum_values: Optional[List[str]] = None
    constraints: Optional[Dict[str, Any]] = None


class LinkCardinality(str, Enum):
    ONE_TO_ONE = "1:1"
    ONE_TO_MANY = "1:N"
    MANY_TO_ONE = "N:1"
    MANY_TO_MANY = "N:N"


class LinkDefinition(BaseModel):
    name: str
    display_name: str = ""
    source_type: str
    target_type: str
    cardinality: LinkCardinality = LinkCardinality.MANY_TO_MANY
    description: str = ""
    properties: List[PropertyDefinition] = []
    is_bidirectional: bool = False
    reverse_name: Optional[str] = None


class ActionParameter(BaseModel):
    name: str
    display_name: str = ""
    param_type: PropertyType = PropertyType.STRING
    required: bool = True
    default: Optional[Any] = None
    description: str = ""


class ActionTypeDefinition(BaseModel):
    action_type_id: str
    name: str
    display_name: str = ""
    description: str = ""
    target_object_type: str
    parameters: List[ActionParameter] = []
    opa_policy: Optional[str] = None
    required_roles: List[str] = []
    writeback_config: Optional[Dict[str, Any]] = None
    confirmation_required: bool = False
    is_active: bool = True


class ObjectTypeDefinition(BaseModel):
    type_id: str
    name: str
    display_name: str = ""
    description: str = ""
    properties: List[PropertyDefinition] = []
    links: List[LinkDefinition] = []
    actions: List[str] = []
    icon: str = ""
    color: str = ""
    is_active: bool = True
    parent_type: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


class OntologySchemaCreate(BaseModel):
    type_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = ""
    description: str = ""
    properties: List[PropertyDefinition] = []
    links: List[LinkDefinition] = []
    actions: List[str] = []
    icon: str = ""
    color: str = ""


class OntologySchemaUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    display_name: Optional[str] = None
    description: Optional[str] = None
    properties: Optional[List[PropertyDefinition]] = None
    links: Optional[List[LinkDefinition]] = None
    actions: Optional[List[str]] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    is_active: Optional[bool] = None


class ActionTypeCreate(BaseModel):
    action_type_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = ""
    description: str = ""
    target_object_type: str
    parameters: List[ActionParameter] = []
    opa_policy: Optional[str] = None
    required_roles: List[str] = []
    writeback_config: Optional[Dict[str, Any]] = None
    confirmation_required: bool = False


class ActionTypeUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    target_object_type: Optional[str] = None
    parameters: Optional[List[ActionParameter]] = None
    opa_policy: Optional[str] = None
    required_roles: Optional[List[str]] = None
    writeback_config: Optional[Dict[str, Any]] = None
    confirmation_required: Optional[bool] = None
    is_active: Optional[bool] = None
