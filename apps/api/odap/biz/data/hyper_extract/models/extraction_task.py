from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class ExtractionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExtractionTask(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text_hash: str = ""
    ontology_id: str = ""
    status: ExtractionStatus = ExtractionStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
