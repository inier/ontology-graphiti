from enum import Enum


class HarnessStage(str, Enum):
    DATA_SELECTION = "data_selection"
    DATA_PROCESSING = "data_processing"
    ONTOLOGY_MODELING = "ontology_modeling"
    QUERY_DESIGN = "query_design"
    API_SKILL_EXPORT = "api_skill_export"
    VALIDATION = "validation"


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    HITL_PENDING = "hitl_pending"
    APPROVED = "approved"
    SKIPPED = "skipped"


class HITLRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgentRole(str, Enum):
    PLANNING = "planning"
    ONTOLOGY = "ontology"
    EXECUTOR = "executor"
    VALIDATOR = "validator"
