# Data Model: LLM 与 API 密钥配置管理

**Branch**: `006-llm-config-management` | **Date**: 2026-06-14

## Entities

### ServiceCategory (枚举)

```python
class ServiceCategory(str, Enum):
    LLM = "llm"
    GRAPH_DB = "graph_db"
    OBJECT_STORAGE = "object_storage"
    SEARCH = "search"
    POLICY_ENGINE = "policy_engine"
    CACHE = "cache"
    AUTH = "auth"
    GENERAL = "general"
```

### ConfigValueType (枚举)

```python
class ConfigValueType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    URL = "url"
    PASSWORD = "password"
```

### ConfigItem (领域模型)

```python
class ConfigItem(BaseModel):
    key: str                                    # 配置键，如 "llm.api_key"
    value: Optional[str] = None                 # 配置值（敏感字段加密存储）
    display_value: Optional[str] = None         # 脱敏展示值（如 "sk-****abcd"）
    value_type: ConfigValueType = ConfigValueType.STRING
    category: ServiceCategory = ServiceCategory.GENERAL
    label: str = ""                             # 展示标签，如 "LLM API Key"
    description: str = ""                       # 配置说明
    is_sensitive: bool = False                  # 是否敏感（影响展示和加密）
    is_required: bool = False                   # 是否必填
    default_value: Optional[str] = None         # 默认值
    choices: List[str] = Field(default_factory=list)  # 可选值列表
    min_val: Optional[float] = None             # 数值最小值
    max_val: Optional[float] = None             # 数值最大值
    sort_order: int = 0                         # 同类别内排序
    group: str = ""                             # 同类别内分组（如 "connection"/"parameters"）
```

### ServiceConfig (聚合根)

```python
class ServiceConfig(BaseModel):
    category: ServiceCategory                   # 服务类别
    label: str                                  # 服务展示名，如 "LLM 大模型服务"
    description: str = ""                       # 服务描述
    icon: str = ""                              # 图标标识
    items: List[ConfigItem] = Field(default_factory=list)  # 该类别下所有配置项
    connection_status: ConnectionStatus = ConnectionStatus.UNKNOWN
    last_tested_at: Optional[str] = None        # 最后测试时间 ISO
    last_error: Optional[str] = None            # 最后测试错误信息
```

### ConnectionStatus (枚举)

```python
class ConnectionStatus(str, Enum):
    UNKNOWN = "unknown"          # 未测试
    CONNECTED = "connected"      # 连接正常
    DISCONNECTED = "disconnected"  # 连接失败
    NOT_CONFIGURED = "not_configured"  # 未配置
```

### ConfigRevision (变更记录)

```python
class ConfigRevision(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    revision_number: int                         # 递增修订号
    operator_id: str                             # 操作人用户 ID
    operator_name: str = ""                      # 操作人用户名
    changed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    changes: List[ConfigChange] = Field(default_factory=list)  # 变更项列表
```

### ConfigChange (单项变更)

```python
class ConfigChange(BaseModel):
    key: str                                     # 配置键
    old_value: Optional[str] = None              # 变更前值（敏感字段脱敏）
    new_value: Optional[str] = None              # 变更后值（敏感字段脱敏）
    is_sensitive: bool = False                   # 是否敏感
```

### ConfigValidationResult (验证结果)

```python
class ConfigValidationResult(BaseModel):
    category: ServiceCategory
    success: bool
    message: str = ""
    response_time_ms: int = 0
    tested_at: str = Field(default_factory=lambda: datetime.now().isoformat())
```

## SQLite Schema

### config_items 表

```sql
CREATE TABLE IF NOT EXISTS config_items (
    key TEXT PRIMARY KEY,
    value TEXT,                    -- 敏感字段加密存储
    value_type TEXT NOT NULL DEFAULT 'string',
    category TEXT NOT NULL DEFAULT 'general',
    label TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    is_sensitive INTEGER NOT NULL DEFAULT 0,
    is_required INTEGER NOT NULL DEFAULT 0,
    default_value TEXT,
    choices TEXT,                  -- JSON array
    min_val REAL,
    max_val REAL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    config_group TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    updated_by TEXT
);
```

### config_revisions 表

```sql
CREATE TABLE IF NOT EXISTS config_revisions (
    id TEXT PRIMARY KEY,
    revision_number INTEGER NOT NULL UNIQUE,
    operator_id TEXT NOT NULL,
    operator_name TEXT NOT NULL DEFAULT '',
    changed_at TEXT NOT NULL,
    changes TEXT NOT NULL          -- JSON array of ConfigChange
);
```

### config_schema_registry 表（配置项注册表）

```sql
CREATE TABLE IF NOT EXISTS config_schema_registry (
    key TEXT PRIMARY KEY,
    value_type TEXT NOT NULL DEFAULT 'string',
    category TEXT NOT NULL DEFAULT 'general',
    label TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    is_sensitive INTEGER NOT NULL DEFAULT 0,
    is_required INTEGER NOT NULL DEFAULT 0,
    default_value TEXT,
    choices TEXT,
    min_val REAL,
    max_val REAL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    config_group TEXT NOT NULL DEFAULT '',
    env_mapping TEXT               -- 对应的环境变量名，如 "OPENAI_API_KEY"
);
```

## Entity Relationships

```
ServiceCategory 1:N ConfigItem          (一个服务类别包含多个配置项)
ConfigItem N:1 config_schema_registry   (配置项值引用 schema 定义)
ConfigRevision 1:N ConfigChange         (一次修订包含多个变更项)
ServiceCategory 1:1 ConfigValidationResult  (每个服务类别有一个最新验证结果)
```

## Pre-registered Config Items

系统启动时自动注册以下配置项到 `config_schema_registry`：

| key | category | label | is_sensitive | is_required | env_mapping |
|-----|----------|-------|:---:|:---:|-------------|
| llm.api_key | llm | LLM API Key | Yes | Yes | OPENAI_API_KEY |
| llm.api_base | llm | API 基地址 | No | Yes | OPENAI_API_BASE |
| llm.model | llm | 模型名称 | No | Yes | OPENAI_MODEL |
| llm.temperature | llm | 温度参数 | No | No | OPENAI_TEMPERATURE |
| graph_db.uri | graph_db | Neo4j URI | No | Yes | NEO4J_URI |
| graph_db.user | graph_db | 用户名 | No | Yes | NEO4J_USER |
| graph_db.password | graph_db | 密码 | Yes | Yes | NEO4J_PASSWORD |
| object_storage.endpoint | object_storage | MinIO 端点 | No | No | MINIO_ENDPOINT |
| object_storage.access_key | object_storage | 访问密钥 | Yes | No | MINIO_ACCESS_KEY |
| object_storage.secret_key | object_storage | 密钥 | Yes | No | MINIO_SECRET_KEY |
| object_storage.secure | object_storage | HTTPS | No | No | MINIO_SECURE |
| search.tavily_api_key | search | Tavily API Key | Yes | No | TAVILY_API_KEY |
| search.ddg_api_url | search | DuckDuckGo URL | No | No | DDG_API_URL |
| search.serpapi_key | search | SerpAPI Key | Yes | No | SERPAPI_KEY |
| policy_engine.opa_url | policy_engine | OPA URL | No | No | OPA_URL |
| cache.redis_url | cache | Redis URL | No | No | REDIS_URL |
| auth.jwt_secret | auth | JWT 密钥 | Yes | Yes | JWT_SECRET |
| auth.jwt_algorithm | auth | JWT 算法 | No | No | JWT_ALGORITHM |
| auth.jwt_expiration | auth | Token 过期时间(秒) | No | No | JWT_EXPIRATION |
| general.cors_origins | general | CORS 白名单 | No | No | CORS_ORIGINS |
| general.log_level | general | 日志级别 | No | No | LOG_LEVEL |
