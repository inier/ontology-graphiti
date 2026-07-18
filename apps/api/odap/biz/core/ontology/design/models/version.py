import warnings
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


def __getattr__(name):
    if name in ("OntologyVersion", "OntologyDiff", "EntitySnapshot"):
        warnings.warn(
            f"models.version.{name} is deprecated. Use services.version_service instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from odap.biz.core.ontology.design.services.version_service import OntologyVersion, OntologyDiff, EntitySnapshot
        return locals().get(name, {"OntologyVersion": OntologyVersion, "OntologyDiff": OntologyDiff, "EntitySnapshot": EntitySnapshot}[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class VersionStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class VersionOperation(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ROLLBACK = "rollback"
    SWITCH = "switch"


class VersionChange(BaseModel):
    change_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    field_name: str = ""
    old_value: Any = None
    new_value: Any = None
    change_type: VersionOperation = VersionOperation.UPDATE
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
