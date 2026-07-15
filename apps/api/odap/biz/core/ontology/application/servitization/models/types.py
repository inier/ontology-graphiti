from enum import Enum


class ServiceType(str, Enum):
    SKILL = "skill"
    MCP_TOOL = "mcp_tool"
    REST_API = "rest_api"
    GRAPHQL = "graphql"


class GenerationStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    DEPLOYED = "deployed"


class CatalogEntryStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"
    NEEDS_UPDATE = "needs_update"
    RETIRED = "retired"
