from .types import MemoryType, MemoryStatus, RetrievalMethod
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class MemoryEntry(BaseModel):
    memory_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    memory_type: MemoryType = MemoryType.EPISODIC
    content: str
    summary: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    source_scenario_id: Optional[str] = None
    source_session_id: Optional[str] = None
    importance: float = 0.5
    access_count: int = 0
    decay_factor: float = 1.0
    embedding: Optional[List[float]] = None
    created_at: datetime = Field(default_factory=datetime.now)
    last_accessed_at: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[str] = None
    status: MemoryStatus = MemoryStatus.ACTIVE
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MemoryConsolidation(BaseModel):
    consolidation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_ids: List[str] = Field(default_factory=list)
    result_id: Optional[str] = None
    strategy: str = "merge"
    summary: str = ""
    importance: float = 0.5
    created_at: datetime = Field(default_factory=datetime.now)


class HybridRetrievalResult(BaseModel):
    entry: MemoryEntry
    score: float
    retrieval_methods: List[RetrievalMethod] = Field(default_factory=list)
    vector_score: float = 0.0
    keyword_score: float = 0.0
    graph_score: float = 0.0
    temporal_score: float = 0.0


class DecayConfig(BaseModel):
    half_life_days: float = 30.0
    min_decay_factor: float = 0.1
    access_boost: float = 0.2
    importance_weight: float = 0.3
    recency_weight: float = 0.4
    frequency_weight: float = 0.3
