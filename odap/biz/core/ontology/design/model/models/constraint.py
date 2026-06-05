from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class ConstraintType(str, Enum):
    UNIQUE = "unique"
    NOT_NULL = "not_null"
    RANGE = "range"
    REGEX = "regex"
    ENUM = "enum"
    CUSTOM = "custom"


class Constraint(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    object_type_id: Optional[str] = None
    constraint_type: ConstraintType = ConstraintType.CUSTOM
    expression: str
    error_message: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[str] = None
