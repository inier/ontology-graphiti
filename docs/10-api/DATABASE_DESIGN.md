# ODAP 数据库设计文档

> **版本**: 1.0.0 | **日期**: 2026-05-18
> **状态**: 已发布 | **优先级**: P0

---

## 1. 概述

### 1.1 存储架构

ODAP 采用多存储引擎混合架构，根据数据特性选择最优存储方案：

| 存储引擎 | 用途 | 数据库实例 |
|----------|------|-----------|
| SQLite | 结构化业务数据、审计日志 | workspace.db, business.db, roles.db, audit.db |
| MongoDB | 文档型数据、本体文档、摄入记录 | workspace, ontology, audit |
| Neo4j/Graphiti | 知识图谱、时序推理 | graphiti (Graphiti) |
| Redis | 缓存、会话状态 | odap-cache |

### 1.2 存储选择原则

| 数据特性 | 推荐存储 | 理由 |
|----------|---------|------|
| 固定 Schema、强关系 | SQLite | 轻量、零配置、事务支持 |
| 灵活 Schema、大文档 | MongoDB | 文档模型、Schema-less |
| 图关系、时序推理 | Neo4j/Graphiti | 原生图查询、双时态支持 |
| 临时数据、高频读写 | Redis | 内存级性能、TTL 支持 |

### 1.3 降级策略

MongoDB 存储层实现内存降级模式：连接失败时自动切换为内存存储（仅用于开发/测试环境）。

---

## 2. SQLite 数据库

### 2.1 workspace.db — 工作空间模块

**文件路径**: `{DATA_DIR}/workspace.db`（DATA_DIR 默认为 `os.path.join(os.getcwd(), "data")`）

#### 2.1.1 workspaces 表

| 列名 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | TEXT | **PRIMARY KEY** | | 工作空间 UUID |
| name | TEXT | NOT NULL | | 工作空间名称 |
| description | TEXT | | NULL | 描述 |
| type | TEXT | NOT NULL | | 类型: default/shared/private/temporary |
| status | TEXT | NOT NULL | | 状态: creating/active/inactive/deleting/error |
| owner | TEXT | NOT NULL | | 所有者 |
| members | TEXT | | NULL | JSON 序列化的成员列表 |
| config | TEXT | | NULL | JSON 序列化的 WorkspaceConfig |
| tags | TEXT | | NULL | JSON 序列化的标签列表 |
| created_at | TEXT | NOT NULL | | ISO 格式时间戳 |
| updated_at | TEXT | NOT NULL | | ISO 格式时间戳 |

**WorkspaceConfig 嵌套结构**:
```json
{
  "isolation_level": "standard",
  "resource_quota": {},
  "network_policy": {},
  "environment_vars": {},
  "feature_flags": {}
}
```

**枚举定义**:
- `WorkspaceStatus`: CREATING, ACTIVE, INACTIVE, DELETING, ERROR
- `WorkspaceType`: DEFAULT, SHARED, PRIVATE, TEMPORARY

#### 2.1.2 isolation_policies 表

| 列名 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| workspace_id | TEXT | **PRIMARY KEY** | | 关联 workspaces.id |
| isolation_level | TEXT | | NULL | 隔离级别: low/standard/high/strict |
| resource_quota | TEXT | | NULL | JSON 序列化的 ResourceQuota |
| network_policy | TEXT | | NULL | JSON 序列化的 NetworkPolicy |
| created_at | TEXT | NOT NULL | | ISO 格式时间戳 |

**ResourceQuota 嵌套结构**:
```json
{
  "cpu": "string",
  "memory": "string",
  "storage": "string",
  "max_connections": 0,
  "max_processes": 0,
  "rate_limit": 0
}
```

**NetworkPolicy 嵌套结构**:
```json
{
  "allowed_ips": [],
  "blocked_ips": [],
  "allowed_ports": [],
  "blocked_ports": [],
  "egress_rules": [],
  "ingress_rules": [],
  "enable_firewall": false
}
```

#### 2.1.3 import_export_records 表

| 列名 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | TEXT | **PRIMARY KEY** | | UUID |
| workspace_id | TEXT | | NULL | 关联工作空间 |
| operation | TEXT | NOT NULL | | import/export |
| status | TEXT | NOT NULL | | pending/processing/completed/failed |
| source | TEXT | | NULL | 来源 |
| destination | TEXT | | NULL | 目标 |
| progress | REAL | | 0 | 进度百分比 |
| file_size | INTEGER | | NULL | 文件大小 |
| errors | TEXT | | NULL | JSON 序列化的错误列表 |
| created_by | TEXT | NOT NULL | | 创建者 |
| start_time | TEXT | NOT NULL | | ISO 时间戳 |
| end_time | TEXT | | NULL | ISO 时间戳 |
| duration_seconds | REAL | | NULL | 耗时秒数 |

#### 2.1.4 scenarios 表

| 列名 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| scenario_id | TEXT | **PRIMARY KEY** | | 场景 ID |
| name | TEXT | NOT NULL | | 场景名称 |
| description | TEXT | | NULL | 描述 |
| workspace_id | TEXT | NOT NULL | | **FK → workspaces(id)** |
| ontology_id | TEXT | | NULL | 关联本体 ID |
| current_ontology_version | TEXT | | '' | 当前本体版本 |
| doc_count | INTEGER | | 0 | 文档数量 |
| event_count | INTEGER | | 0 | 事件数量 |
| entity_count | INTEGER | | 0 | 实体数量 |
| created_at | TEXT | NOT NULL | | ISO 时间戳 |
| updated_at | TEXT | NOT NULL | | ISO 时间戳 |

**外键关系**: `scenarios.workspace_id → workspaces.id`

---

### 2.2 business.db — 业务模块

**文件路径**: `{DATA_DIR}/business.db`

#### 2.2.1 business_processes 表

| 列名 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| process_id | TEXT | **PRIMARY KEY** | | 流程 ID |
| name | TEXT | NOT NULL | | 名称 |
| display_name | TEXT | | NULL | 显示名称 |
| description | TEXT | | NULL | 描述 |
| related_objects | TEXT | | NULL | JSON 数组 |
| related_processes | TEXT | | '[]' | JSON 数组 |
| related_rules | TEXT | | '[]' | JSON 数组 |
| related_logics | TEXT | | '[]' | JSON 数组 |
| related_indicators | TEXT | | '[]' | JSON 数组 |
| llm_description | TEXT | | NULL | LLM 生成的描述 |
| flow_nodes | TEXT | | NULL | JSON 数组，流程节点 |
| status | TEXT | | 'draft' | 状态 |
| created_by | TEXT | | 'system' | 创建者 |
| created_at | TEXT | | NULL | ISO 时间戳 |
| updated_at | TEXT | | NULL | ISO 时间戳 |
| yaml_definition | TEXT | | NULL | YAML 定义 |
| ontology_id | TEXT | | '' | 关联本体 ID |
| version_id | TEXT | | '' | 关联版本 ID |

#### 2.2.2 business_rules 表

| 列名 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| rule_id | TEXT | **PRIMARY KEY** | | 规则 ID |
| name | TEXT | NOT NULL | | 名称 |
| display_name | TEXT | | NULL | 显示名称 |
| description | TEXT | | NULL | 描述 |
| related_objects | TEXT | | NULL | JSON 数组 |
| related_processes | TEXT | | '[]' | JSON 数组 |
| related_rules | TEXT | | '[]' | JSON 数组 |
| related_logics | TEXT | | '[]' | JSON 数组 |
| related_indicators | TEXT | | '[]' | JSON 数组 |
| llm_description | TEXT | | NULL | LLM 生成的描述 |
| rule_conditions | TEXT | | NULL | JSON 数组，规则条件 |
| status | TEXT | | 'draft' | 状态 |
| created_by | TEXT | | 'system' | 创建者 |
| created_at | TEXT | | NULL | ISO 时间戳 |
| updated_at | TEXT | | NULL | ISO 时间戳 |
| yaml_definition | TEXT | | NULL | YAML 定义 |
| ontology_id | TEXT | | '' | 关联本体 ID |
| version_id | TEXT | | '' | 关联版本 ID |

#### 2.2.3 business_logics 表

| 列名 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| logic_id | TEXT | **PRIMARY KEY** | | 逻辑 ID |
| name | TEXT | NOT NULL | | 名称 |
| display_name | TEXT | | NULL | 显示名称 |
| description | TEXT | | NULL | 描述 |
| related_objects | TEXT | | NULL | JSON 数组 |
| related_processes | TEXT | | '[]' | JSON 数组 |
| related_rules | TEXT | | '[]' | JSON 数组 |
| related_logics | TEXT | | '[]' | JSON 数组 |
| related_indicators | TEXT | | '[]' | JSON 数组 |
| llm_description | TEXT | | NULL | LLM 生成的描述 |
| logic_type | TEXT | | 'filter' | 逻辑类型 |
| logic_expression | TEXT | | NULL | 逻辑表达式 |
| status | TEXT | | 'draft' | 状态 |
| created_by | TEXT | | 'system' | 创建者 |
| created_at | TEXT | | NULL | ISO 时间戳 |
| updated_at | TEXT | | NULL | ISO 时间戳 |
| yaml_definition | TEXT | | NULL | YAML 定义 |
| ontology_id | TEXT | | '' | 关联本体 ID |
| version_id | TEXT | | '' | 关联版本 ID |

#### 2.2.4 business_indicators 表

| 列名 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| indicator_id | TEXT | **PRIMARY KEY** | | 指标 ID |
| name | TEXT | NOT NULL | | 名称 |
| display_name | TEXT | | NULL | 显示名称 |
| description | TEXT | | NULL | 描述 |
| related_objects | TEXT | | NULL | JSON 数组 |
| related_processes | TEXT | | '[]' | JSON 数组 |
| related_rules | TEXT | | '[]' | JSON 数组 |
| related_logics | TEXT | | '[]' | JSON 数组 |
| related_indicators | TEXT | | '[]' | JSON 数组 |
| llm_description | TEXT | | NULL | LLM 生成的描述 |
| indicator_type | TEXT | | 'metric' | 指标类型 |
| calculation_formula | TEXT | | NULL | 计算公式 |
| unit | TEXT | | NULL | 单位 |
| status | TEXT | | 'draft' | 状态 |
| created_by | TEXT | | 'system' | 创建者 |
| created_at | TEXT | | NULL | ISO 时间戳 |
| updated_at | TEXT | | NULL | ISO 时间戳 |
| yaml_definition | TEXT | | NULL | YAML 定义 |
| ontology_id | TEXT | | '' | 关联本体 ID |
| version_id | TEXT | | '' | 关联版本 ID |

---

### 2.3 roles.db — 角色权限模块

**文件路径**: `{DATA_DIR}/roles.db`

#### 2.3.1 permissions 表

| 列名 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | TEXT | **PRIMARY KEY** | | 权限 ID |
| name | TEXT | NOT NULL | | 权限名称 |
| description | TEXT | | NULL | 描述 |
| scope | TEXT | NOT NULL | | 作用域: system/project/resource |
| actions | TEXT | NOT NULL | | JSON 序列化的操作列表 |
| created_at | TEXT | NOT NULL | | ISO 时间戳 |

**预置数据**:

| id | name | scope | actions |
|----|------|-------|---------|
| p1 | 系统管理 | system | ["*"] |
| p2 | 项目管理 | project | ["read","write","delete"] |
| p3 | 团队管理 | project | ["read","update"] |
| p4 | 资源访问 | resource | ["read"] |
| p5 | 有限访问 | resource | ["limited_read"] |

#### 2.3.2 roles 表

| 列名 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | TEXT | **PRIMARY KEY** | | 角色 ID |
| name | TEXT | NOT NULL | | 角色名称 |
| description | TEXT | | NULL | 描述 |
| role_type | TEXT | NOT NULL | | 角色类型枚举值 |
| permissions | TEXT | | NULL | JSON 序列化的权限 ID 列表 |
| created_at | TEXT | NOT NULL | | ISO 时间戳 |
| updated_at | TEXT | NOT NULL | | ISO 时间戳 |

**预置数据**:

| id | name | role_type | permissions |
|----|------|-----------|-------------|
| 1 | 系统管理员 | system_admin | ["p1"] |
| 2 | 项目所有者 | project_owner | ["p2"] |
| 3 | 团队领导 | team_leader | ["p3"] |
| 4 | 成员 | member | ["p4"] |
| 5 | 访客 | guest | ["p5"] |

#### 2.3.3 role_permissions 关联表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| role_id | TEXT | NOT NULL | **FK → roles(id)** |
| permission_id | TEXT | NOT NULL | **FK → permissions(id)** |

**联合主键**: `(role_id, permission_id)`

---

### 2.4 audit.db — 审计模块

**文件路径**: `./data/audit.db`

#### 2.4.1 audit_events 表

| 列名 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | TEXT | **PRIMARY KEY** | | 事件 UUID |
| timestamp | TIMESTAMP | NOT NULL | CURRENT_TIMESTAMP | 事件时间 |
| event_type | TEXT | NOT NULL | | 事件类型枚举值 |
| severity | TEXT | NOT NULL | 'info' | 严重级别 |
| actor_type | TEXT | NOT NULL | | 操作者类型 |
| actor_id | TEXT | NOT NULL | | 操作者 ID |
| actor_name | TEXT | NOT NULL | | 操作者名称 |
| action | TEXT | NOT NULL | | 操作动作 |
| resource_type | TEXT | NOT NULL | | 资源类型 |
| resource_id | TEXT | NOT NULL | | 资源 ID |
| result_status | TEXT | NOT NULL | | 结果状态: success/failure/denied |
| result_message | TEXT | | '' | 结果消息 |
| workspace_id | TEXT | NOT NULL | | 工作空间 ID |
| trace_id | TEXT | NOT NULL | | 分布式追踪 ID |
| parent_event_id | TEXT | | NULL | 父事件 ID (因果链) |
| duration_ms | INTEGER | | NULL | 操作耗时毫秒 |
| context | TEXT | | NULL | JSON 上下文信息 |
| changes | TEXT | | NULL | JSON 变更详情 |
| checksum | TEXT | NOT NULL | | SHA-256 防篡改校验 |

**索引**:

| 索引名 | 列 | 说明 |
|--------|-----|------|
| idx_audit_timestamp | timestamp | 时间查询 |
| idx_audit_event_type | event_type | 事件类型查询 |
| idx_audit_actor | actor_id | 操作者查询 |
| idx_audit_workspace | workspace_id | 工作空间查询 |
| idx_audit_resource | (resource_type, resource_id) | 资源复合查询 |
| idx_audit_trace | trace_id | 追踪 ID 查询 |

**特殊配置**: WAL 模式 (`PRAGMA journal_mode=WAL`)，支持批量缓冲写入和防篡改哈希链。

---

## 3. MongoDB 数据库

### 3.1 workspace 数据库

**连接**: `MONGODB_URI` 环境变量，默认 `mongodb://localhost:27017`

#### 3.1.1 workspaces 集合

```json
{
  "id": "UUID",
  "name": "string",
  "description": "string",
  "type": "default|shared|private|temporary",
  "status": "creating|active|inactive|deleting|error",
  "config": {
    "isolation_level": "string",
    "resource_quota": {},
    "network_policy": {},
    "environment_vars": {},
    "feature_flags": {}
  },
  "owner": "string",
  "members": ["string"],
  "resources": {},
  "created_at": "datetime",
  "updated_at": "datetime",
  "last_accessed_at": "datetime|null",
  "tags": ["string"]
}
```

**查询键**: `id`

#### 3.1.2 isolation_policies 集合

```json
{
  "workspace_id": "string",
  "isolation_level": "string",
  "resource_quota": {},
  "network_policy": {}
}
```

**查询键**: `workspace_id`

#### 3.1.3 import_export_records 集合

```json
{
  "id": "UUID",
  "workspace_id": "string",
  "operation": "import|export",
  "status": "pending|processing|completed|failed",
  "source": "string|null",
  "destination": "string|null",
  "file_path": "string|null",
  "file_size": "int|null",
  "progress": "float",
  "start_time": "datetime",
  "end_time": "datetime|null",
  "duration_seconds": "float|null",
  "errors": [],
  "created_by": "string"
}
```

**查询键**: `id`

#### 3.1.4 scenarios 集合

```json
{
  "scenario_id": "string",
  "name": "string",
  "description": "string",
  "workspace_id": "string",
  "ontology_id": "string|null",
  "current_ontology_version": "string|null",
  "doc_count": 0,
  "event_count": 0,
  "entity_count": 0,
  "created_at": "ISO datetime",
  "updated_at": "ISO datetime"
}
```

**查询键**: `scenario_id`, `workspace_id`

#### 3.1.5 scenario_documents 集合

```json
{
  "scenario_id": "string",
  "events": [],
  "entities": []
}
```

**查询键**: `scenario_id`

---

### 3.2 ontology 数据库

**连接**: `MONGODB_URI` 环境变量，默认 `mongodb://localhost:27017`

#### 3.2.1 ingest_records 集合

```json
{
  "ingest_id": "string",
  "source": "api|file|database|stream|manual|news|natural_language|random|qa_query",
  "source_details": {},
  "data_schema": {},
  "record_count": 0,
  "processed_count": 0,
  "failed_count": 0,
  "status": "pending|processing|completed|failed",
  "start_time": "datetime",
  "end_time": "datetime|null",
  "duration_seconds": "float|null",
  "errors": [],
  "quality_metrics": {},
  "created_by": "system",
  "version_id": "string|null",
  "logs": [],
  "original_content": "string|null"
}
```

**索引**: `ingest_id`, `status`, `created_at`

#### 3.2.2 audit_logs 集合

```json
{
  "event_id": "string",
  "ingest_id": "string",
  "timestamp": "datetime",
  "level": "info",
  "message": "string",
  "details": {},
  "actor": "system"
}
```

**索引**: `event_id`, `timestamp`

#### 3.2.3 build_results 集合

```json
{
  "build_id": "UUID",
  "source_ingest_id": "string",
  "entity_count": 0,
  "relation_count": 0,
  "property_count": 0,
  "status": "pending|processing|completed|failed",
  "start_time": "datetime",
  "end_time": "datetime|null",
  "duration_seconds": "float|null",
  "errors": [],
  "warnings": [],
  "ontology_version": "1.0.0"
}
```

**索引**: `build_id`, `status`

#### 3.2.4 ontology_documents 集合

```json
{
  "document_id": "string",
  "type": "string",
  "$schema": "https://odap.local/schemas/ontology-document/v1.json",
  "$version": "1.0.0",
  "doc_id": "string",
  "doc_type": "event|entity|scenario|batch",
  "source": {
    "type": "manual|news_ingest|random_gen|import|simulation",
    "url": "string|null",
    "collected_at": "ISO datetime",
    "confidence": 1.0,
    "author": "string|null"
  },
  "meta": {
    "title": "string",
    "description": "string",
    "tags": [],
    "language": "zh",
    "classification": "SIM"
  },
  "entities": [OntologyEntity],
  "relations": [OntologyRelation],
  "events": [OntologyEvent],
  "actions": [OntologyAction],
  "rules": [OntologyRule],
  "constraints": [OntologyConstraint],
  "ontology_version": {
    "version_id": "string",
    "parent_version": "string|null",
    "commit_message": "string",
    "schema_version": "1.0.0"
  },
  "transformation_status": "pending|processing|completed|failed",
  "transformation_steps": [],
  "transformation_errors": [],
  "build_history": [],
  "scenario_id": "string|null",
  "ontology_id": "string|null"
}
```

**索引**: `document_id`, `type`

**子结构定义**:

| 子结构 | 字段 | 类型 | 说明 |
|--------|------|------|------|
| OntologyEntity | entity_id | str | 默认 `entity-{uuid[:8]}` |
| | entity_type | str | Unit/Equipment/Location/Person/Organization/EventNode |
| | name | str | 名称 |
| | name_en | str | 英文名 |
| | aliases | List[str] | 别名列表 |
| | basic_properties | Dict | 基础属性 |
| | statistical_properties | Dict | 统计属性 |
| | capabilities | Dict | 能力属性 |
| | constraints | List[Dict] | 约束列表 |
| OntologyRelation | relation_id | str | 默认 `rel-{uuid[:8]}` |
| | relation_type | str | 默认 "related_to" |
| | source_entity | str | 源实体 ID |
| | target_entity | str | 目标实体 ID |
| | properties | Dict | 关系属性 |
| | temporal | TemporalInfo | 时序信息 |
| OntologyEvent | event_id | str | 默认 `evt-{uuid[:8]}` |
| | event_type | str | 事件类型 |
| | timestamp | str | ISO 时间戳 |
| | location | str | 地点 |
| | coordinates | List[float]|null | 坐标 |
| | participants | List[str] | 参与者实体 ID |
| | description | str | 描述 |
| | outcome | Dict | 结果 |
| | phase | str | 阶段 |
| OntologyAction | action_id | str | 默认 `act-{uuid[:8]}` |
| | action_type | str | 行动类型 |
| | actor | str | 执行者 |
| | target | str | 目标 |
| | timestamp | str | ISO 时间戳 |
| | parameters | Dict | 参数 |
| | opa_required | bool | 是否需要 OPA 策略 |
| | status | str | pending/executed/cancelled/failed |
| OntologyRule | rule_id | str | 默认 `rule-{uuid[:8]}` |
| | rule_type | str | 规则类型 |
| | description | str | 描述 |
| | condition | str | 条件 |
| | consequence | str | 后果 |
| | priority | str | 优先级 |
| | source | str | 来源 |
| OntologyConstraint | constraint_id | str | 默认 `cst-{uuid[:8]}` |
| | constraint_type | str | 约束类型 |
| | description | str | 描述 |
| | scope | Dict | 作用域 |
| | violation_consequence | str | 违规后果，默认 "warning" |
| | legal_basis | str | 法律依据 |

#### 3.2.5 versions 集合

```json
{
  "version_id": "UUID",
  "ontology_id": "string",
  "version_number": "string",
  "parent_version_id": "string|null",
  "status": "draft|released|deprecated|archived",
  "change_summary": "string",
  "created_at": "ISO datetime",
  "created_by": "system",
  "is_current": false,
  "is_stable": false,
  "ingest_id": "string|null",
  "entity_count": 0,
  "relation_count": 0,
  "changes": [VersionChange],
  "logs": [],
  "scenario_id": "string|null"
}
```

**索引**: `version_id`, `ontology_id`

**VersionChange 子结构**:

| 字段 | 类型 | 说明 |
|------|------|------|
| change_id | str | UUID |
| field | str | 变更字段 |
| old_value | Any | 旧值 |
| new_value | Any | 新值 |
| change_type | str | 默认 "update" |
| timestamp | datetime | 变更时间 |
| changed_by | str | 默认 "system" |

#### 3.2.6 validation_rules 集合

```json
{
  "rule_id": "UUID",
  "name": "string",
  "description": "string",
  "rule_type": "entity|relation|property",
  "severity": "error|warning|info",
  "expression": "string",
  "params": {},
  "enabled": true
}
```

**索引**: `rule_id`, `rule_type`

#### 3.2.7 validation_results 集合

```json
{
  "result_id": "UUID",
  "ontology_id": "string",
  "ontology_version": "string",
  "validation_time": "datetime",
  "status": "pending|running|complete|failed",
  "errors": [],
  "warnings": [],
  "info": [],
  "error_count": 0,
  "warning_count": 0,
  "info_count": 0,
  "overall_score": 1.0,
  "duration_seconds": 0.0,
  "rule_id": "string|null"
}
```

**索引**: `result_id`, `rule_id`

---

### 3.3 audit 数据库

**连接**: `MONGODB_URI` 环境变量，默认 `mongodb://localhost:27017`

#### 3.3.1 audit_events 集合

```json
{
  "id": "UUID",
  "event_type": "string",
  "severity": "debug|info|warn|error|critical",
  "actor": {
    "actor_type": "user|agent|system|skill",
    "actor_id": "string",
    "actor_name": "string",
    "roles": ["string"]
  },
  "action": "string",
  "resource": {
    "resource_type": "workspace|ontology|node|edge|policy|skill|simulation",
    "resource_id": "string",
    "resource_name": "string",
    "attributes": {}
  },
  "result": {
    "status": "success|failure|denied",
    "message": "string",
    "error_code": "string|null",
    "changes": {}
  },
  "timestamp": "datetime",
  "workspace_id": "string",
  "source": "system",
  "trace_id": "UUID",
  "context": {},
  "signature": "string|null"
}
```

**索引**:

| 索引键 | 选项 | 说明 |
|--------|------|------|
| timestamp | 普通 | 时间查询 |
| workspace_id | 普通 | 工作空间查询 |
| event_type | 普通 | 事件类型查询 |
| severity | 普通 | 严重级别查询 |
| source | 普通 | 来源查询 |
| timestamp | **TTL: 30天** | 自动过期 |

---

## 4. 跨模块关系图

```
workspace.db (SQLite)
  workspaces.id ←───────── scenarios.workspace_id (FK)
  workspaces.id ←───────── isolation_policies.workspace_id (PK, 逻辑FK)

business.db (SQLite)
  business_processes.ontology_id ──→ ontology_documents (逻辑关联)
  business_processes.version_id ──→ versions (逻辑关联)
  (同上适用于 business_rules, business_logics, business_indicators)

roles.db (SQLite)
  roles.id ←───────── role_permissions.role_id (FK)
  permissions.id ←─── role_permissions.permission_id (FK)

audit.db (SQLite)
  audit_events.workspace_id ──→ workspaces.id (逻辑关联)
  audit_events.parent_event_id → audit_events.id (自引用因果链)

ontology (MongoDB)
  versions.ontology_id ──→ ontology_documents (逻辑关联)
  versions.ingest_id ──→ ingest_records (逻辑关联)
  versions.scenario_id ──→ workspace.scenarios (跨库关联)

workspace (MongoDB)
  scenarios.workspace_id ──→ workspaces.id (逻辑关联)
  scenario_documents.scenario_id ──→ scenarios.scenario_id (逻辑关联)
```

---

## 5. 数据模型枚举汇总

### 5.1 AuditEventType (审计事件类型)

| 类型 | 枚举值 | 说明 |
|------|--------|------|
| 用户操作 | user.login/logout/create/update/delete | 用户行为 |
| 工作空间 | workspace.create/switch/delete/export/import | 工作空间操作 |
| 本体管理 | ontology.create/update/version/rollback | 本体变更 |
| Agent 操作 | agent.execute/decision/error | 智能体行为 |
| 技能管理 | skill.register/execute/disable | 技能生命周期 |
| 策略管理 | policy.update/evaluate/violation | OPA 策略 |
| 模拟推演 | simulation.start/complete/rollback | 推演控制 |
| 系统事件 | system.error/health/config | 系统级事件 |
| 数据操作 | data.ingest | 数据摄入 |
| 查询操作 | query.execute | 图谱查询 |
| 问答交互 | qa.ask/feedback | QA 对话 |
| 反馈闭环 | feedback.action/decision | 闭环反馈 |

### 5.2 AuditSeverity (严重级别)

| 级别 | 枚举值 | 说明 |
|------|--------|------|
| 调试 | debug | 开发调试信息 |
| 信息 | info | 常规操作记录 |
| 警告 | warn | 潜在问题 |
| 错误 | error | 操作失败 |
| 严重 | critical | 安全违规/系统故障 |

---

## 6. 环境变量配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| DATA_DIR | `os.path.join(os.getcwd(), "data")` | SQLite 数据库目录 |
| MONGODB_URI | `mongodb://localhost:27017` | MongoDB 连接字符串 |

---

## 7. 已知问题与改进建议

| 编号 | 问题 | 影响 | 建议 |
|------|------|------|------|
| DB-001 | SQLite 存储每个方法创建新连接，无连接池 | 性能瓶颈 | 引入连接池或共享连接 |
| DB-002 | MongoDB 存储无重连机制 | 连接断开后不可恢复 | 添加自动重连逻辑 |
| DB-003 | workspace.db 中 delete_workspace 不删除关联 scenarios | 数据残留 | 添加级联删除 |
| DB-004 | business.db 中使用 conn.total_changes 判断删除 | 误判 | 改用 cursor.rowcount |
| DB-005 | roles.db 存储层从路由导入模型 | 循环依赖风险 | 将模型提取到独立模块 |
| DB-006 | audit.db 路径硬编码为 `./data/audit.db` | 不一致 | 使用 DATA_DIR 环境变量 |
| DB-007 | 场景查询存在三个独立 ScenarioStore 实例 | 数据不一致 | 统一为单一数据源 |
| DB-008 | MongoDB workspace 集合未过滤 _id 字段 | 序列化失败 | 查询结果统一过滤 _id |

---

**文档版本历史**:

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0.0 | 2026-05-18 | 初始版本，基于代码分析梳理 |
