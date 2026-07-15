from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class DataType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    JSON = "json"
    REFERENCE = "reference"


class Property(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    display_name: Optional[str] = None
    data_type: DataType = DataType.STRING
    required: bool = False
    default_value: Optional[Any] = None
    classification_level: str = "U"
    description: Optional[str] = None
    constraints: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[str] = None
