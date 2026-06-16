# Data Model: 本体设计器彻底重构

**Branch**: `003-ontology-redesign` | **Date**: 2026-06-09

## 统一 Schema 层模型

### Ontology（本体）

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| ontology_id | str | auto (uuid4) | - | 本体唯一标识 |
| name | str | yes | - | 本体名称 |
| description | str | no | "" | 本体描述 |
| workspace_id | str | yes | - | 所属工作空间 |
| scenario_id | str | no | null | 关联场景 |
| current_version | str | no | "v0.1.0" | 当前 Schema 版本号 |
| status | OntologyStatus | no | DRAFT | 状态 |
| created_at | str | auto | now | 创建时间 |
| updated_at | str | auto | now | 更新时间 |

**OntologyStatus**: `DRAFT` | `ACTIVE` | `ARCHIVED` | `DEPRECATED`

### OntologySchemaVersion（Schema 版本 — 独立于数据版本）

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| version_id | str | auto | - | 版本唯一标识（格式：v{YYYYMMDD}-{seq:03d}） |
| ontology_id | str | yes | - | 所属本体 |
| version_number | str | yes | - | 语义版本号（如 0.1.0） |
| parent_version_id | str | no | null | 父版本指针 |
| is_stable | bool | no | false | 是否为稳定版本 |
| changelog | str | no | "" | 变更日志 |
| schema_snapshot | str (JSON) | no | null | Schema 快照（所有类型定义的 JSON 序列化） |
| created_at | str | auto | now | 创建时间 |

> **设计决策**：Schema 版本与数据版本（现有 `ontology_versions`）使用独立的版本链。Schema 版本低频（天/周级手动 commit），数据版本高频（分钟/小时级自动 append），混在一起会导致 Schema 变更历史被淹没。

### ObjectTypeDefinition（对象类型定义 — Schema 层统一模型）

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| type_id | str | auto (uuid4) | - | 类型唯一标识 |
| ontology_id | str | yes | - | 所属本体 |
| version_id | str | no | null | 所属 Schema 版本 |
| name | str | yes | - | 类型名称（英文标识符） |
| display_name | str | no | null | 显示名称（中文） |
| description | str | no | "" | 描述 |
| properties | List[PropertyDefinition] | no | [] | 属性列表 |
| links | List[LinkDefinition] | no | [] | 关系列表 |
| actions | List[str] | no | [] | 关联动作类型 ID 列表 |
| primary_key | List[str] | no | [] | 主键列名列表 |
| classification_level | str | no | "U" | 密级（TS/S/C/U） |
| icon | str | no | null | 图标 |
| color | str | no | null | 颜色 |
| is_active | bool | no | true | 是否激活 |
| parent_type | str | no | null | 父类型 ID（继承） |
| created_at | str | auto | now | 创建时间 |
| updated_at | str | auto | now | 更新时间 |

### PropertyDefinition（属性定义 — 统一模型）

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| property_id | str | auto (uuid4) | - | 属性唯一标识 |
| name | str | yes | - | 属性名称 |
| display_name | str | no | null | 显示名称 |
| property_type | PropertyType | yes | - | 数据类型 |
| required | bool | no | false | 是否必填 |
| default_value | str | no | null | 默认值 |
| classification_level | str | no | "U" | 密级 |
| reference_type | str | no | null | 引用类型（当 property_type=REFERENCE 时） |
| enum_values | List[str] | no | [] | 枚举值列表 |
| constraints | Dict | no | {} | 约束条件 |

**PropertyType**: `STRING` | `INTEGER` | `FLOAT` | `BOOLEAN` | `DATETIME` | `GEOPOINT` | `JSON` | `REFERENCE`

### LinkDefinition（关系定义 — 统一模型）

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| link_id | str | auto (uuid4) | - | 关系唯一标识 |
| name | str | yes | - | 关系名称 |
| source_type | str | yes | - | 源对象类型 ID |
| target_type | str | yes | - | 目标对象类型 ID |
| cardinality | Cardinality | no | ONE_TO_MANY | 基数 |
| link_type | LinkType | no | ASSOCIATION | 关系类型 |
| is_bidirectional | bool | no | false | 是否双向 |
| reverse_name | str | no | null | 反向关系名称 |
| description | str | no | "" | 描述 |

**Cardinality**: `ONE_TO_ONE` | `ONE_TO_MANY` | `MANY_TO_ONE` | `MANY_TO_MANY`
**LinkType**: `ASSOCIATION` | `COMPOSITION` | `DEPENDENCY` | `INHERITANCE`

### ActionTypeDefinition（动作类型定义）

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| action_type_id | str | auto (uuid4) | - | 动作类型唯一标识 |
| ontology_id | str | yes | - | 所属本体 |
| version_id | str | no | null | 所属 Schema 版本 |
| name | str | yes | - | 动作名称 |
| target_object_type | str | yes | - | 目标对象类型 ID |
| description | str | no | "" | 描述 |
| parameters | List[Dict] | no | [] | 参数列表 |
| required_roles | List[str] | no | [] | 所需角色 |
| confirmation_required | bool | no | true | 是否需要确认 |

---

## 业务类型定义（本体类型系统 — 新增表）

> **设计决策**：类型定义与实例数据分表存储。类型定义属于本体类型系统，实例数据属于业务存储，职责天然分离。

### ProcessTypeDefinition（业务过程类型定义）

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| type_id | str | auto (uuid4) | - | 类型唯一标识 |
| ontology_id | str | yes | - | 所属本体 |
| version_id | str | no | null | 所属 Schema 版本 |
| name | str | yes | - | 类型名称 |
| display_name | str | no | null | 显示名称 |
| description | str | no | "" | 描述 |
| flow_node_schema | List[Dict] | no | [] | 流程节点 Schema（定义节点有哪些字段） |
| related_object_types | List[str] | no | [] | 关联的对象类型 ID |
| created_at | str | auto | now | 创建时间 |
| updated_at | str | auto | now | 更新时间 |

### RuleTypeDefinition（规则类型定义）

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| type_id | str | auto (uuid4) | - | 类型唯一标识 |
| ontology_id | str | yes | - | 所属本体 |
| version_id | str | no | null | 所属 Schema 版本 |
| name | str | yes | - | 类型名称 |
| display_name | str | no | null | 显示名称 |
| description | str | no | "" | 描述 |
| condition_schema | Dict | no | {} | 触发条件 Schema |
| consequence_schema | Dict | no | {} | 约束要求 Schema |
| priority_levels | List[str] | no | ["low","medium","high"] | 可选优先级 |
| related_object_types | List[str] | no | [] | 关联的对象类型 ID |
| created_at | str | auto | now | 创建时间 |

### FunctionTypeDefinition（逻辑函数类型定义）

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| type_id | str | auto (uuid4) | - | 类型唯一标识 |
| ontology_id | str | yes | - | 所属本体 |
| version_id | str | no | null | 所属 Schema 版本 |
| name | str | yes | - | 类型名称 |
| display_name | str | no | null | 显示名称 |
| description | str | no | "" | 描述 |
| logic_types | List[str] | no | ["filter","transform","validate","compute"] | 支持的逻辑类型 |
| expression_schema | Dict | no | {} | 表达式 Schema |
| related_object_types | List[str] | no | [] | 关联的对象类型 ID |
| created_at | str | auto | now | 创建时间 |

### IndicatorTypeDefinition（指标类型定义）

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| type_id | str | auto (uuid4) | - | 类型唯一标识 |
| ontology_id | str | yes | - | 所属本体 |
| version_id | str | no | null | 所属 Schema 版本 |
| name | str | yes | - | 类型名称 |
| display_name | str | no | null | 显示名称 |
| description | str | no | "" | 描述 |
| indicator_types | List[str] | no | ["kpi","metric","dimension"] | 支持的指标类型 |
| formula_schema | Dict | no | {} | 计算公式 Schema |
| allowed_units | List[str] | no | [] | 可选单位列表 |
| related_object_types | List[str] | no | [] | 关联的对象类型 ID |
| created_at | str | auto | now | 创建时间 |

---

## 业务实例数据（现有表扩展）

> **设计决策**：现有业务表不加 `is_schema` 字段。实例表新增 `schema_type_id` 列引用类型定义。

### BusinessProcess（业务过程实例 — 扩展）

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| process_id | str | auto (uuid4) | - | 唯一标识 |
| name | str | yes | - | 名称 |
| description | str | no | "" | 描述 |
| ontology_id | str | no | null | 所属本体 |
| version_id | str | no | null | 所属版本 |
| **schema_type_id** | **str** | no | null | **引用 ProcessTypeDefinition.type_id** |
| flow_nodes | List[Dict] | no | [] | 流程节点（实例数据） |
| related_objects | List[str] | no | [] | 关联对象 |
| status | str | no | "draft" | 状态 |
| created_at | str | auto | now | 创建时间 |
| updated_at | str | auto | now | 更新时间 |

> 同样模式适用于 `BusinessRule`（新增 `schema_type_id` 引用 `RuleTypeDefinition`）、`BusinessLogic`（引用 `FunctionTypeDefinition`）、`BusinessIndicator`（引用 `IndicatorTypeDefinition`）。

---

## 新增实体

### DatabaseConnection（数据库连接配置）

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| connection_id | str | auto (uuid4) | - | 连接唯一标识 |
| name | str | yes | - | 连接名称 |
| db_type | str | yes | - | 数据库类型（mysql/postgresql/sqlite） |
| host | str | no | "localhost" | 主机 |
| port | int | no | 3306/5432/0 | 端口 |
| database | str | yes | - | 数据库名/文件路径 |
| username | str | no | null | 用户名 |
| password_encrypted | str | no | null | AES-256 加密密码 |
| workspace_id | str | yes | - | 所属工作空间 |
| created_at | str | auto | now | 创建时间 |

### ExtractionSession（抽取/提取会话）

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| session_id | str | auto (uuid4) | - | 会话唯一标识 |
| ontology_id | str | yes | - | 目标本体 |
| extraction_type | str | yes | - | 抽取类型（database/natural_language） |
| status | str | no | "pending" | 状态（pending/extracting/reviewing/completed/failed） |
| input_data | str (JSON) | no | null | 输入数据（连接配置或自然语言文本） |
| result_data | str (JSON) | no | null | 抽取结果 JSON（Schema 级类型定义） |
| conflicts | List[Dict] | no | [] | 冲突列表 |
| created_at | str | auto | now | 创建时间 |

---

## 实体关系图

```
Workspace ─ 1:N ─→ Ontology ─ 1:N ─→ OntologySchemaVersion（Schema 版本链）
                     │
                     ├─ 1:N ─→ ObjectTypeDefinition ─ 1:N ─→ PropertyDefinition
                     │                                    ─ 1:N ─→ LinkDefinition
                     │                                    ─ N:M ─→ ActionTypeDefinition
                     │
                     ├─ 1:N ─→ ProcessTypeDefinition  ←───┐
                     ├─ 1:N ─→ RuleTypeDefinition         │ 类型定义
                     ├─ 1:N ─→ FunctionTypeDefinition     │ （本体类型系统）
                     └─ 1:N ─→ IndicatorTypeDefinition ←──┘
                                  │
                                  │ schema_type_id 引用
                                  ↓
                     BusinessProcess（实例）  ←───┐
                     BusinessRule（实例）         │ 实例数据
                     BusinessLogic（实例）         │ （业务存储）
                     BusinessIndicator（实例） ←───┘

Workspace ─ 1:N ─→ DatabaseConnection
Ontology ─ 1:N ─→ ExtractionSession

Ontology ─ 1:N ─→ OntologyVersion（数据版本链，现有，不变）
```

---

## SQLite 存储变更

### 新增表

1. **ontologies** — 本体主表
2. **ontology_schema_versions** — Schema 版本表（独立于数据版本）
3. **object_type_definitions** — 对象类型定义
4. **link_type_definitions** — 关系类型定义
5. **action_type_definitions** — 动作类型定义
6. **process_type_definitions** — 业务过程类型定义
7. **rule_type_definitions** — 规则类型定义
8. **function_type_definitions** — 逻辑函数类型定义
9. **indicator_type_definitions** — 指标类型定义
10. **database_connections** — 数据库连接配置
11. **extraction_sessions** — 抽取会话

### 修改表（新增列）

1. **business_processes** — 新增 `schema_type_id TEXT`（引用 process_type_definitions）
2. **business_rules** — 新增 `schema_type_id TEXT`（引用 rule_type_definitions）
3. **business_logics** — 新增 `schema_type_id TEXT`（引用 function_type_definitions）
4. **business_indicators** — 新增 `schema_type_id TEXT`（引用 indicator_type_definitions）

### 迁移策略

所有新增列使用 `ALTER TABLE ... ADD COLUMN`，新增表使用 `CREATE TABLE IF NOT EXISTS`，确保向后兼容。不修改现有表结构，不删除现有列。
