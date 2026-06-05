from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class Cardinality(str, Enum):
    ONE_TO_ONE = "1:1"
    ONE_TO_MANY = "1:N"
    MANY_TO_ONE = "N:1"
    MANY_TO_MANY = "N:N"


class LinkType(str, Enum):
    HARD = "hard"
    SOFT = "soft"


class Relation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    source_type: str
    target_type: str
    relation_type: Optional[str] = None
    cardinality: Cardinality = Cardinality.ONE_TO_MANY
    link_type: LinkType = LinkType.HARD
    description: Optional[str] = None
    properties: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[str] = None
