"""场景模型"""

from enum import Enum
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid


class ScenarioStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class BindingStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"


class Scenario(BaseModel):
    """场景"""
    scenario_id: str = Field(default_factory=lambda: f"scenario-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}")
    name: str
    description: str = ""
    workspace_id: str
    status: ScenarioStatus = ScenarioStatus.DRAFT
    tags: List[str] = Field(default_factory=list)
    ontology_id: Optional[str] = None
    ontology_ids: List[str] = Field(default_factory=list)
    current_ontology_version: Optional[str] = None
    doc_count: int = 0
    event_count: int = 0
    entity_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
