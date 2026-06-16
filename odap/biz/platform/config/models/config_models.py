"""配置管理领域模型"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field


class ServiceCategory(str, Enum):
    LLM = "llm"
    GRAPH_DB = "graph_db"
    OBJECT_STORAGE = "object_storage"
    SEARCH = "search"
    POLICY_ENGINE = "policy_engine"
    CACHE = "cache"
    AUTH = "auth"
    GENERAL = "general"


class ConfigValueType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    URL = "url"
    PASSWORD = "password"


class ConnectionStatus(str, Enum):
    UNKNOWN = "unknown"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    NOT_CONFIGURED = "not_configured"


class ConfigItem(BaseModel):
    key: str
    value: Optional[str] = None
    display_value: Optional[str] = None
    value_type: ConfigValueType = ConfigValueType.STRING
    category: ServiceCategory = ServiceCategory.GENERAL
    label: str = ""
    description: str = ""
    is_sensitive: bool = False
    is_required: bool = False
    default_value: Optional[str] = None
    choices: List[str] = Field(default_factory=list)
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    sort_order: int = 0
    group: str = ""
    has_value: bool = False


class ServiceConfig(BaseModel):
    category: ServiceCategory
    label: str = ""
    description: str = ""
    icon: str = ""
    items: List[ConfigItem] = Field(default_factory=list)
    connection_status: ConnectionStatus = ConnectionStatus.UNKNOWN
    last_tested_at: Optional[str] = None
    last_error: Optional[str] = None


class ConfigChange(BaseModel):
    key: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    is_sensitive: bool = False


class ConfigRevision(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    revision_number: int = 0
    operator_id: str = ""
    operator_name: str = ""
    changed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    changes: List[ConfigChange] = Field(default_factory=list)


class ConfigValidationResult(BaseModel):
    category: ServiceCategory
    success: bool = False
    message: str = ""
    response_time_ms: int = 0
    tested_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# 服务类别元数据
SERVICE_CATEGORY_META: Dict[str, Dict[str, str]] = {
    ServiceCategory.LLM: {"label": "LLM 大模型服务", "description": "配置大模型 API 连接参数", "icon": "robot"},
    ServiceCategory.GRAPH_DB: {"label": "图数据库", "description": "配置 Neo4j 图数据库连接", "icon": "database"},
    ServiceCategory.OBJECT_STORAGE: {"label": "对象存储", "description": "配置 MinIO 对象存储连接", "icon": "cloud"},
    ServiceCategory.SEARCH: {"label": "搜索服务", "description": "配置搜索增强服务", "icon": "search"},
    ServiceCategory.POLICY_ENGINE: {"label": "策略引擎", "description": "配置 OPA 策略引擎", "icon": "safety"},
    ServiceCategory.CACHE: {"label": "缓存服务", "description": "配置 Redis 缓存服务", "icon": "thunderbolt"},
    ServiceCategory.AUTH: {"label": "认证服务", "description": "配置 JWT 认证参数", "icon": "lock"},
    ServiceCategory.GENERAL: {"label": "通用设置", "description": "系统通用配置", "icon": "setting"},
}

# 预定义配置项注册表
PREDEFINED_CONFIG_ITEMS: List[Dict[str, Any]] = [
    # LLM
    {"key": "llm.api_key", "value_type": "password", "category": "llm", "label": "LLM API Key", "description": "OpenAI 兼容 API 的访问密钥", "is_sensitive": True, "is_required": True, "sort_order": 1, "group": "connection", "env_mapping": "OPENAI_API_KEY"},
    {"key": "llm.api_base", "value_type": "url", "category": "llm", "label": "API 基地址", "description": "LLM API 基地址", "is_sensitive": False, "is_required": True, "sort_order": 2, "group": "connection", "env_mapping": "OPENAI_API_BASE"},
    {"key": "llm.model", "value_type": "string", "category": "llm", "label": "模型名称", "description": "LLM 模型名称", "is_sensitive": False, "is_required": True, "sort_order": 3, "group": "connection", "env_mapping": "OPENAI_MODEL"},
    {"key": "llm.temperature", "value_type": "float", "category": "llm", "label": "温度参数", "description": "LLM 生成温度 (0.0-2.0)", "is_sensitive": False, "is_required": False, "default_value": "0.7", "min_val": 0.0, "max_val": 2.0, "sort_order": 4, "group": "parameters", "env_mapping": "LLM_TEMPERATURE"},
    # Graph DB
    {"key": "graph_db.uri", "value_type": "url", "category": "graph_db", "label": "Neo4j URI", "description": "Neo4j 连接地址", "is_sensitive": False, "is_required": True, "default_value": "bolt://localhost:7687", "sort_order": 1, "group": "connection", "env_mapping": "NEO4J_URI"},
    {"key": "graph_db.user", "value_type": "string", "category": "graph_db", "label": "用户名", "description": "Neo4j 用户名", "is_sensitive": False, "is_required": True, "default_value": "neo4j", "sort_order": 2, "group": "connection", "env_mapping": "NEO4J_USER"},
    {"key": "graph_db.password", "value_type": "password", "category": "graph_db", "label": "密码", "description": "Neo4j 密码", "is_sensitive": True, "is_required": True, "sort_order": 3, "group": "connection", "env_mapping": "NEO4J_PASSWORD"},
    # Object Storage
    {"key": "object_storage.endpoint", "value_type": "string", "category": "object_storage", "label": "MinIO 端点", "description": "MinIO 服务端点", "is_sensitive": False, "is_required": False, "default_value": "minio:9000", "sort_order": 1, "group": "connection", "env_mapping": "MINIO_ENDPOINT"},
    {"key": "object_storage.access_key", "value_type": "password", "category": "object_storage", "label": "访问密钥", "description": "MinIO 访问密钥", "is_sensitive": True, "is_required": False, "default_value": None, "sort_order": 2, "group": "connection", "env_mapping": "MINIO_ACCESS_KEY"},
    {"key": "object_storage.secret_key", "value_type": "password", "category": "object_storage", "label": "密钥", "description": "MinIO 密钥", "is_sensitive": True, "is_required": False, "default_value": None, "sort_order": 3, "group": "connection", "env_mapping": "MINIO_SECRET_KEY"},
    {"key": "object_storage.secure", "value_type": "boolean", "category": "object_storage", "label": "HTTPS", "description": "是否使用 HTTPS", "is_sensitive": False, "is_required": False, "default_value": "false", "sort_order": 4, "group": "connection", "env_mapping": "MINIO_SECURE"},
    # Search
    {"key": "search.tavily_api_key", "value_type": "password", "category": "search", "label": "Tavily API Key", "description": "Tavily 搜索 API Key", "is_sensitive": True, "is_required": False, "sort_order": 1, "group": "search_services", "env_mapping": "TAVILY_API_KEY"},
    {"key": "search.ddg_api_url", "value_type": "url", "category": "search", "label": "DuckDuckGo URL", "description": "DuckDuckGo 搜索 API URL", "is_sensitive": False, "is_required": False, "sort_order": 2, "group": "search_services", "env_mapping": "DDG_API_URL"},
    {"key": "search.serpapi_key", "value_type": "password", "category": "search", "label": "SerpAPI Key", "description": "SerpAPI 搜索 Key", "is_sensitive": True, "is_required": False, "sort_order": 3, "group": "search_services", "env_mapping": "SERPAPI_KEY"},
    # Policy Engine
    {"key": "policy_engine.opa_url", "value_type": "url", "category": "policy_engine", "label": "OPA URL", "description": "OPA 策略引擎地址", "is_sensitive": False, "is_required": False, "default_value": "http://localhost:8181", "sort_order": 1, "group": "connection", "env_mapping": "OPA_URL"},
    # Cache
    {"key": "cache.redis_url", "value_type": "url", "category": "cache", "label": "Redis URL", "description": "Redis 缓存连接地址", "is_sensitive": False, "is_required": False, "default_value": "redis://localhost:6379/0", "sort_order": 1, "group": "connection", "env_mapping": "REDIS_URL"},
    # Auth
    {"key": "auth.jwt_secret", "value_type": "password", "category": "auth", "label": "JWT 密钥", "description": "JWT 签名密钥 (>=32字符)", "is_sensitive": True, "is_required": True, "sort_order": 1, "group": "jwt", "env_mapping": "JWT_SECRET"},
    {"key": "auth.jwt_algorithm", "value_type": "string", "category": "auth", "label": "JWT 算法", "description": "JWT 签名算法", "is_sensitive": False, "is_required": False, "default_value": "HS256", "choices": ["HS256", "RS256"], "sort_order": 2, "group": "jwt", "env_mapping": "JWT_ALGORITHM"},
    {"key": "auth.jwt_expiration", "value_type": "integer", "category": "auth", "label": "Token 过期时间(秒)", "description": "Access Token 过期时间", "is_sensitive": False, "is_required": False, "default_value": "3600", "sort_order": 3, "group": "jwt", "env_mapping": "JWT_EXPIRATION"},
    # General
    {"key": "general.cors_origins", "value_type": "string", "category": "general", "label": "CORS 白名单", "description": "跨域白名单（逗号分隔）", "is_sensitive": False, "is_required": False, "sort_order": 1, "group": "network", "env_mapping": "CORS_ORIGINS"},
    {"key": "general.log_level", "value_type": "string", "category": "general", "label": "日志级别", "description": "系统日志级别", "is_sensitive": False, "is_required": False, "default_value": "INFO", "choices": ["DEBUG", "INFO", "WARNING", "ERROR"], "sort_order": 2, "group": "logging", "env_mapping": "LOG_LEVEL"},
]
