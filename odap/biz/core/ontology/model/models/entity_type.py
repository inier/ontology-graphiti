from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from enum import Enum


class Cardinality(str, Enum):
    ONE_TO_ONE = "1:1"
    ONE_TO_MANY = "1:N"
    MANY_TO_ONE = "N:1"
    MANY_TO_MANY = "N:N"


class LinkType(str, Enum):
    ASSOCIATION = "association"
    COMPOSITION = "composition"
    DEPENDENCY = "dependency"
    INHERITANCE = "inheritance"


class PropertyDefinition(BaseModel):
    name: str
    data_type: str = "string"
    required: bool = False
    default_value: Any = None
    classification_level: str = "U"
    constraints: List[str] = Field(default_factory=list)
    display_name: Optional[str] = None
    description: Optional[str] = None


class LinkDefinition(BaseModel):
    name: str
    target_type: str
    cardinality: Cardinality = Cardinality.ONE_TO_MANY
    link_type: LinkType = LinkType.ASSOCIATION
    description: Optional[str] = None


class ConstraintDefinition(BaseModel):
    name: str
    constraint_type: str
    expression: str
    error_message: str = ""


class EntityTypeDefinition(BaseModel):
    type_id: str = ""
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    properties: List[PropertyDefinition] = Field(default_factory=list)
    primary_key: List[str] = Field(default_factory=list)
    links: List[LinkDefinition] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)
    constraints: List[ConstraintDefinition] = Field(default_factory=list)
    classification_level: str = "U"
    metadata: Dict[str, Any] = Field(default_factory=dict)
