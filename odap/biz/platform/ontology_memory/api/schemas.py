from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

from odap.biz.platform.ontology_memory.models import MemoryType, MemoryStatus


class StoreMemoryRequest(BaseModel):
    memory_type: MemoryType = MemoryType.EPISODIC
    content: str
    summary: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    source_scenario_id: Optional[str] = None
    source_session_id: Optional[str] = None
    importance: float = 0.5
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RetrieveMemoryRequest(BaseModel):
    query: str
    memory_type: Optional[MemoryType] = None
    top_k: int = 10
    scenario_id: Optional[str] = None
    method_weights: Optional[Dict[str, float]] = None


class ConsolidateMemoriesRequest(BaseModel):
    memory_ids: List[str] = Field(default_factory=list)
    strategy: str = "merge"


class DecayUpdateRequest(BaseModel):
    half_life_days: Optional[float] = None
    min_decay_factor: Optional[float] = None
    access_boost: Optional[float] = None
    importance_weight: Optional[float] = None
    recency_weight: Optional[float] = None
    frequency_weight: Optional[float] = None


class ForgetRequest(BaseModel):
    threshold: float = 0.1
    archive: bool = False
