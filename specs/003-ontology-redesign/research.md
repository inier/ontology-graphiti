# Research: 本体设计器彻底重构

**Branch**: `003-ontology-redesign` | **Date**: 2026-06-09 | **Spec**: [spec.md](spec.md)

## R1: 数据模型统一方案

### Decision
统一为一套 Pydantic 模型，Instance 层通过**引用**而非映射关联 Schema 层。

### Rationale
映射层（`ObjectTypeDefinition → OntologyEntity`）是架构负债：每次新增字段要同步修改两套模型+映射逻辑，映射本身的 bug 成为新的故障源，开发者认知负担翻倍。

从本体论看，T-box（类型定义）和 A-box（实例数据）是不同概念，但不需要两套独立的模型类。正确做法是：一套 Pydantic 模型覆盖 Schema 层，Instance 层通过 `object_type_id` 引用 Schema 定义，属性值用 `Dict[str, Any]` 按 Schema 约束但不做 Pydantic 硬编码。

### Alternatives Considered
1. **两层模型+映射层**：映射层是架构负债，每次字段变更需同步三处（两套模型+映射逻辑），且映射 bug 成为新的故障源
2. **全部迁移到 Pydantic**：会破坏 ADR-032 的 Graphiti Episode 写入链路，改动面太大
3. **保持三套模型不变**：同名类冲突无法解决，数据流断裂

### 具体方案

**Schema 层统一到 OMS 模型**（`application/oms/schemas.py`），因为它最完整：
- `ObjectTypeDefinition` 替代 `EntityTypeDefinition`（design/model 层）
- `PropertyDefinition`（OMS 版）替代 `Property`（design/model 层）和 `PropertyDefinition`（design/model 层）
- `LinkDefinition`（OMS 版）替代 `Relation`（design/model 层）和 `LinkDefinition`（design/model 层）
- `ActionTypeDefinition`（OMS 版）替代 `actions: List[str]`（design/model 层）

**Instance 层改为引用 Schema**：`OntologyEntity` 新增 `object_type_id` 字段引用 `ObjectTypeDefinition.type_id`，属性值 `properties: Dict[str, Any]` 由 Schema 约束。`OntologyDocument` 保留为 Graphiti Episode 写入格式，但不再独立定义属性结构。

**消除映射层**：Schema → Instance 不是映射转换，而是引用关系。Instance 的属性值天然受 Schema 约束，无需额外转换逻辑。

---

## R2: 数据库 Schema 抽取技术方案

### Decision
使用 SQLAlchemy Inspector 作为统一抽象层，支持 MySQL/PostgreSQL/SQLite 三种数据库的只读 Schema 内省。

### Rationale
SQLAlchemy Inspector 是 Python 生态最成熟的跨数据库 Schema 内省工具，提供统一 API（`get_table_names`/`get_columns`/`get_foreign_keys` 等）。虽然 SQLAlchemy 是一个重量级依赖，但 Inspector 只依赖 SQLAlchemy Core（非 ORM），且没有更轻量的替代品能同时支持三种数据库。

### Alternatives Considered
1. **每种数据库单独写原生 SQL**：避免新依赖，但三种数据库需写三套查询逻辑，违反 DRY 原则。且 `information_schema` 在 MySQL/PostgreSQL 间有差异，维护成本高
2. **使用 alembic**：alembic 依赖 sqlalchemy，且面向迁移而非只读内省，不合适
3. **仅支持 SQLite**：功能受限，不满足用户需求

### 架构反思

**映射规则硬编码是否合理？** 合理。Table→ObjectType、FK→LinkType 等映射是确定性的、无歧义的，不需要配置化。用户可在预览界面编辑结果，映射规则只是初始建议。

**抽取应在服务端还是客户端？** 服务端。数据库连接需要网络可达，客户端浏览器无法直连数据库。且 LLM 调用需要 API Key，不应暴露给前端。

**LLM 增强步骤是否必要？** 可选。规则映射（Table→ObjectType）是确定性的，不需要 LLM。LLM 增强用于补充业务语义描述（如表名 `t_order` → 显示名"订单"），这是锦上添花而非必需。应作为可选步骤，LLM 不可用时降级为纯规则映射。

### 新增依赖
```
sqlalchemy>=2.0.0          # Inspector（仅需 Core，非 ORM）
psycopg2-binary>=2.9.0     # PostgreSQL（可选，用户选择 PostgreSQL 时才需要）
pymysql>=1.1.0             # MySQL（可选，用户选择 MySQL 时才需要）
```

### 映射规则
| 数据库对象 | 本体概念 | 映射逻辑 | 确定性 |
|-----------|---------|---------|--------|
| Table | ObjectType | 表名→name，表注释→description | 确定 |
| Column | Property | 列名→name，SQL类型→PropertyType枚举 | 确定 |
| Foreign Key | LinkType | FK→source/target，ON DELETE→link_type | 确定 |
| CHECK Constraint | RuleType | CHECK表达式→condition | 确定 |
| Stored Procedure | ActionType | 过程名→name，参数→parameters | 需 LLM 补充语义 |
| Trigger | ActionType | 触发事件→action_type | 需 LLM 补充语义 |

### 安全约束
- 连接用户仅授予 `SELECT` on `information_schema` 权限
- 连接池限制 `pool_size=2, max_overflow=0`
- 连接超时 `connect_timeout=10`
- 密码加密存储（AES-256），API 传输时脱敏

---

## R3: 自然语言提取技术方案

### Decision
复用 LLM 基础设施（ZhipuAIClient + JSON 解析/字段校正链路），创建专用的 Schema 级提取器，不复用 NewsIngester 或 ManualInputHandler。

### Rationale
原方案说"复用 NewsIngester + ManualInputHandler"是误导。这两个提取器的输出是 Instance 级数据（`OntologyDocument`/`OntologyEntity`），而我们需要的是 Schema 级定义（`ObjectTypeDefinition`/`LinkTypeDefinition`）。输出格式根本不同，不能复用提取器本身。

应该复用的是 **LLM 基础设施**（客户端、JSON 解析、字段校正、降级策略），而非提取器逻辑。

### Alternatives Considered
1. **直接复用 NewsIngester**：输出格式不匹配（Instance 级 vs Schema 级），强行转换等于隐式映射层
2. **使用 LangChain structured output**：引入新依赖，违反宪法"优先使用项目已有依赖"
3. **纯规则提取（无 LLM）**：无法从自然语言中提取语义信息

### 架构反思

**联网检索是否应该自动触发？** 不应该自动触发。联网检索增加延迟和非确定性，应作为用户显式触发的选项（`auto_search: true` 参数由用户勾选控制）。当用户输入信息不足时，提示用户"建议开启联网检索补充领域知识"，而非自动执行。

**提取结果与已有本体的冲突检测应在哪一层？** 服务层。提取器返回纯数据，冲突检测和合并策略由 `ExtractionService` 编排层处理。这保持了提取器的单一职责。

**Schema 级提取 Prompt 与 Instance 级提取 Prompt 的关系？** 完全独立。Schema 级 Prompt 输出类型定义结构（属性名+类型+约束），Instance 级 Prompt 输出实体实例（属性名+值）。两者不应共享 Prompt 模板。

### Prompt 设计
新增 `ONTOLOGY_SCHEMA_EXTRACT_PROMPT`，输出格式：
- `object_types[]`: name, display_name, properties[{name, property_type, required}], classification_level
- `link_types[]`: name, source_type, target_type, cardinality, link_type
- `action_types[]`: name, target_object_type, parameters[], description
- `rule_types[]`: name, condition, consequence, priority
- `indicator_types[]`: name, indicator_type, calculation_formula, unit
- `process_types[]`: name, flow_nodes[], related_objects

---

## R4: 结构与实例统一方案

### Decision
结构定义存入本体类型系统（新增类型定义表），实例数据保持现有业务表不变，通过 `schema_type_id` 引用关联。

### Rationale
`is_schema` 布尔标志方案是反模式：一行数据同时承载两种语义，违反单一职责；Schema 和 Instance 生命周期不同（Schema 随本体版本变更，Instance 独立演进）；访问模式不同（设计器查 Schema，业务页面查 Instance）；权限不同（Schema 修改需设计器权限，Instance CRUD 需业务权限）。

架构上，类型定义属于本体类型系统，实例数据属于业务存储，两者天然分离。这不是工作量问题，是职责边界问题。

### Alternatives Considered
1. **`is_schema` 共享表**：一行两义，隐式 union type，查询每次需过滤，权限控制复杂，扩展性差
2. **Schema 存在 OntologyDocument JSON 中**：Schema 无法被子菜单页面直接查询（需反序列化），且无法独立 CRUD
3. **完全不分**：无法区分"结构定义"和"实例数据"，语义不清

### 具体方案

**本体类型系统**（新增表，归 `ontology_api/storage` 管理）：
- `object_type_definitions` — 对象类型定义
- `link_type_definitions` — 关系类型定义
- `action_type_definitions` — 动作类型定义
- `process_type_definitions` — 业务过程类型定义（新增）
- `function_type_definitions` — 逻辑函数类型定义（新增）
- `rule_type_definitions` — 规则类型定义（新增）
- `indicator_type_definitions` — 指标类型定义（新增）

**业务实例存储**（现有表不变，不加 `is_schema`）：
- `business_processes` — 业务过程实例
- `business_rules` — 业务规则实例
- `business_logics` — 业务逻辑实例
- `business_indicators` — 业务指标实例

**引用关系**：实例表新增 `schema_type_id TEXT` 列，引用对应的类型定义。子菜单页面创建实例时，从类型系统加载可选类型（下拉选择）。

### 对比

| 维度 | `is_schema` 共享表 | 类型系统分离 |
|------|-------------------|-------------|
| 职责清晰度 | 模糊（一行两义） | 清晰（类型归类型，数据归数据） |
| 查询复杂度 | 每次需 `WHERE is_schema=?` | 天然隔离，无需过滤 |
| 权限控制 | 行级，复杂 | 表级，简单 |
| 生命周期 | 耦合 | 独立 |
| 扩展性 | 差（更多标志位？） | 好（类型系统天然可扩展） |

---

## R5: 图谱可视化方案

### Decision
复用现有 `GraphCanvas` 组件（AntV G6 5.x），扩展编辑交互回调。语义图谱作为设计器内的 Tab 保留，同时新增独立路由页面。

### Rationale
GraphCanvas 是通用图谱组件，接口足够抽象（`nodes: GraphNode[]` + `edges: GraphEdge[]` + `onNodeClick`/`onEdgeClick` 回调），可同时用于 Instance 级和 Schema 级可视化。只需将 `ObjectTypeDefinition` 映射为 `GraphNode`、`LinkTypeDefinition` 映射为 `GraphEdge`，并实现编辑回调即可。

### Alternatives Considered
1. **重新开发图谱组件**：违反宪法"避免过度设计"和"优先使用项目已有依赖"
2. **使用 OntologySemanticNetwork 组件**：使用 Mock 数据，`SemanticNode` 接口与 `GraphNode` 不兼容，且无编辑能力
3. **使用 React Flow**：项目已有 React Flow 用于蓝图设计器，但图谱可视化（大量节点+力导向布局）用 G6 更合适

### 架构反思

**GraphCanvas 同时用于 Schema 级和 Instance 级是否会产生冲突？** 不会。GraphCanvas 是无状态组件（接收 nodes/edges 作为 props），不同使用场景传入不同数据即可。但需要注意：

1. **节点样式区分**：Schema 级节点（ObjectTypeDefinition）和 Instance 级节点（OntologyEntity）应有不同的视觉样式，通过 `type` 字段区分
2. **编辑回调不同**：Schema 级点击打开类型定义编辑器，Instance 级点击打开实例详情。由调用方通过 `onNodeClick` 回调控制

**独立图谱页面 vs 设计器 Tab？** 两者都需要。设计器内的 Tab 用于快速预览（边设计边看），独立页面用于深度探索（缩放、搜索、筛选）。但遵循"避免过度设计"，先实现设计器 Tab，独立页面作为后续增强。

**节点/边编辑面板是否应内嵌在 GraphCanvas 中？** 不应该。GraphCanvas 应保持纯可视化职责，编辑面板作为独立组件通过回调触发。这保持了组件的单一职责和可复用性。

### 菜单恢复
在 `AppLayout.tsx` 侧边栏菜单中新增"语义图谱"入口，路由 `/ontology/graph`。先使用与设计器 Tab 相同的 GraphCanvas 组件，数据来源为本体类型系统。

---

## R6: 本体版本管理方案

### Decision
复用 `OntologyVersionManager` 的 append/commit/diff/rollback 机制，但版本快照内容从 `OntologyDocument`（Instance 级）改为 Schema 快照（所有类型定义的 JSON 序列化）。

### Rationale
版本管理的机制（append追加/commit快照/diff对比/rollback回滚）与被版本化的内容无关，是通用的。当前 `OntologyVersionManager` 版本化的是 `OntologyDocument`（Instance 级数据摄入），而本体设计器需要版本化的是 Schema 定义。

关键区别：**版本化的内容不同，但版本管理的机制相同**。因此复用机制，替换内容。

### Alternatives Considered
1. **直接复用 OntologyVersionManager 不做修改**：版本快照存的是 OntologyDocument，与 Schema 定义无关，语义错误
2. **新建 SchemaVersionManager**：机制完全相同，重复造轮子
3. **让 OntologyVersionManager 同时支持两种快照**：增加复杂度，违反单一职责

### 架构反思

**Schema 版本与数据版本是否应该是同一个版本链？** 不应该。Schema 版本（类型定义变更）和数据版本（实例数据摄入）是不同的变更维度，频率和触发条件不同：

- Schema 版本：用户手动 commit，低频（天/周级）
- 数据版本：IngestService 自动 append，高频（分钟/小时级）

混在同一个版本链中会导致：数据摄入的频繁 append 淹没 Schema 变更历史，diff 结果混杂了 Schema 变更和数据变更。

**正确方案**：Schema 版本和数据版本使用独立的版本链，但通过 `ontology_id` 关联。Schema 版本表新增 `schema_snapshot` 列存储类型定义快照，数据版本表保持现有 `doc_snapshot` 不变。

**版本回滚的语义**：回滚 Schema 版本 = 恢复类型定义到历史状态，不影响已摄入的实例数据。回滚数据版本 = 恢复实例数据到历史状态，不影响类型定义。两者独立，符合单一职责。

### 具体方案

**新增 `ontology_schema_versions` 表**：
- `version_id` — 版本唯一标识
- `ontology_id` — 所属本体
- `version_number` — 语义版本号
- `parent_version_id` — 父版本指针
- `is_stable` — 是否稳定版本
- `changelog` — 变更日志
- `schema_snapshot` — Schema 快照（所有类型定义的 JSON 序列化）
- `created_at` — 创建时间

**保留现有 `ontology_versions`（数据版本）不变**。

**前端增强**：
- 设计器入口新增本体选择器
- 版本面板显示 Schema 版本历史（独立于数据版本）
- 版本对比：diff 两个 Schema 快照的类型定义差异
- 回滚确认对话框：明确提示"仅回滚类型定义，不影响实例数据"
