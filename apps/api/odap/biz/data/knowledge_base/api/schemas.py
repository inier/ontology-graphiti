from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None


class KnowledgeBase(BaseModel):
    """Uses ``extra="allow"`` to remain backward compatible with all existing
    storage columns that haven't been typed into the schema yet (e.g.
    ``cleaned_content``, ``cleaning_level``, ``raw_content``)."""
    model_config = ConfigDict(extra="allow")

    kb_id: str
    name: str
    description: str
    knowledge_count: int = 0
    category_count: int = 0
    updated_at: str
    created_at: str
    created_by: str = "system"
    status: str = "active"


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    parent_id: Optional[str] = None


class KnowledgeCategory(BaseModel):
    model_config = ConfigDict(extra="allow")

    category_id: str
    kb_id: str
    name: str
    parent_id: Optional[str] = None
    document_count: int = 0
    updated_at: str


class KnowledgeDocument(BaseModel):
    """Uses ``extra="allow"`` so storage-level fields (``segments_json``,
    ``entities_json``, ``cleaning_status``, etc.) flow through the API layer
    without triggering Pydantic errors on older / hand-written rows."""
    model_config = ConfigDict(extra="allow")

    doc_id: str
    kb_id: str
    category_id: Optional[str] = None
    title: str
    content_type: str = "text"
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    file_url: Optional[str] = None
    presigned_url: Optional[str] = None
    content: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    status: str = "pending"
    graph_built: bool = False
    created_at: str
    updated_at: str
