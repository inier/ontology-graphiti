"""版本管理模型"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
from enum import Enum


class VersionOperation(str, Enum):
    """版本操作"""
    CREATE = "create"
    UPDATE = "update"
    ROLLBACK = "rollback"
    MERGE = "merge"
    DELETE = "delete"


class VersionStatus(str, Enum):
    """版本状态"""
    DRAFT = "draft"
    RELEASED = "released"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class VersionChange(BaseModel):
    """版本变更"""
    change_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    field: str
    old_value: Any = None
    new_value: Any = None
    change_type: str = "update"
    timestamp: datetime = Field(default_factory=datetime.now)
    changed_by: str = "system"


class OntologyVersion(BaseModel):
    """本体版本"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ontology_id: str
    version_number: str
    parent_version_id: Optional[str] = None
    status: VersionStatus = VersionStatus.DRAFT
    changes: List[VersionChange] = Field(default_factory=list)
    change_summary: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    created_by: str = "system"
    is_current: bool = False
    is_stable: bool = False


class VersionComparison(BaseModel):
    """版本对比"""
    source_version_id: str
    target_version_id: str
    added_entities: List[str] = Field(default_factory=list)
    removed_entities: List[str] = Field(default_factory=list)
    modified_entities: List[str] = Field(default_factory=list)
    added_relations: List[str] = Field(default_factory=list)
    removed_relations: List[str] = Field(default_factory=list)
    modified_relations: List[str] = Field(default_factory=list)
    compatibility_score: float = 1.0
    comparison_time: datetime = Field(default_factory=datetime.now)
