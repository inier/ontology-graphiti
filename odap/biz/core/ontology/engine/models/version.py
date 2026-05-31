from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from enum import Enum


class VersionStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
    ROLLED_BACK = "rolled_back"


class VersionRecord(BaseModel):
    version_id: str = ""
    ontology_id: str
    version_number: str = "1.0.0"
    changelog: str = ""
    valid_time: str = ""
    transaction_time: str = ""
    status: VersionStatus = VersionStatus.DRAFT
    snapshot: Dict[str, Any] = Field(default_factory=dict)
