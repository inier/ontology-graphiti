from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class BatchImportRequest(BaseModel):
    entity_type_id: str
    data: Any
    format: str = "json"
    workspace_id: str = "default"


class ExtractRequest(BaseModel):
    task_id: str
    entity_type_id: Optional[str] = None
    workspace_id: str = "default"


class TaskResponse(BaseModel):
    task_id: str
    workspace_id: str
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    storage_key: Optional[str] = None
    status: str
    source: str = "upload"
    process_steps: List[Dict[str, Any]] = Field(default_factory=list)
    transform_rules: List[Dict[str, Any]] = Field(default_factory=list)
    extracted_text: Optional[str] = None
    extracted_tables: List[Dict[str, Any]] = Field(default_factory=list)
    error_message: Optional[str] = None
    created_at: str
    updated_at: str


class BatchImportResponse(BaseModel):
    status: str
    success_count: int = 0
    fail_count: int = 0
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    format: str
    entity_type_id: str
    workspace_id: str
