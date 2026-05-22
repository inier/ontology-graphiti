from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


class PerceptionSourceType(str, Enum):
    MCP = "mcp"
    FILE = "file"
    API = "api"
    SENSOR = "sensor"
    NEWS = "news"
    MANUAL = "manual"
    SIMULATION = "simulation"
    WEBHOOK = "webhook"


class PerceptionPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class PerceptionStatus(str, Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    MAPPED = "mapped"
    STORED = "stored"
    FAILED = "failed"


class PerceptionEvent(BaseModel):
    event_id: str = ""
    source_type: PerceptionSourceType
    source_name: str = ""
    raw_content: str = ""
    structured_data: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = {}
    priority: PerceptionPriority = PerceptionPriority.NORMAL
    workspace_id: Optional[str] = None
    scenario_id: Optional[str] = None
    timestamp: str = ""
    status: PerceptionStatus = PerceptionStatus.RECEIVED


class ExtractionResult(BaseModel):
    entities: List[Dict[str, Any]] = []
    relations: List[Dict[str, Any]] = []
    events: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []
    confidence: float = 0.0


class PerceptionOutput(BaseModel):
    event_id: str
    extraction: ExtractionResult
    ontology_document: Optional[Dict[str, Any]] = None
    graphiti_episode_id: Optional[str] = None
    oms_registered_types: List[str] = []
    status: PerceptionStatus
    error: Optional[str] = None


class ObserverConfig(BaseModel):
    observer_type: PerceptionSourceType
    name: str
    enabled: bool = True
    poll_interval: int = 60
    max_batch_size: int = 100
    filters: Dict[str, Any] = {}
