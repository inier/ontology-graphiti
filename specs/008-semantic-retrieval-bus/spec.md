# Feature Specification: Semantic Retrieval Service Bus (语义检索服务总线)

**Feature Branch**: `008-semantic-retrieval-bus`

**Created**: 2026-07-30

**Status**: Draft

**Input**: User description: "构建基于本体的数据服务'用本体'阶段的核心能力——语义检索服务总线。为 AI Agent 和 BI 工具提供统一的本体数据访问入口，包含统一检索、分项检索（链式推理/自然语言/MDL-DSL/图检索/指标查询）和混合检索三层架构。"

**Related ADR**: ADR-073 (基于本体的数据服务四步落地架构)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - AI Agent 自然语言查询本体 (Priority: P1)

作为一个 AI Agent 调用方（智能体应用），我希望通过一段自然语言描述查询本体中的实体、关系和推理结果，以便在不了解底层结构的情况下获取所需知识。例如，我输入"最近有哪些装备的 readiness 低于 0.6？它们之间有什么关联？"，系统应自动完成语义映射、图检索和链式推理，返回结构化结果。

**Why this priority**: 这是"用本体"的核心价值——让 AI Agent 能够像调用 API 一样使用本体，而无需了解 Neo4j、SQLite 等底层存储细节。是所有下游集成的基础。

**Independent Test**: 可独立测试——通过自然语言接口提交查询，验证是否返回正确的实体列表和关联路径。

**Acceptance Scenarios**:

1. **Given** 本体中存在 ObjectType="装备" 的实例，部分实例的 readiness 属性 < 0.6，**When** 用户/Agent 输入"readiness 低于 0.6 的装备有哪些"，**Then** 返回所有符合条件的实例及其关键属性
2. **Given** 本体中装备之间存在 RelationType="部署于" 的关系，**When** 用户/Agent 输入"低 readiness 装备部署在哪些系统上"，**Then** 返回装备→系统的完整关系路径
3. **Given** 查询涉及 USL 术语消歧（同义词映射），**When** 用户使用业务术语查询（如"平台"而非 ObjectType 名称"系统"），**Then** 系统自动完成术语映射并返回正确结果

---

### User Story 2 - BI 工具指标查询 (Priority: P1)

作为一个 BI 工具调用方（如 Superset、Metabase 或自定义看板），我希望通过标准化接口获取本体的聚合统计指标，以便构建报表和看板。例如，我需要"每个 ObjectType 的实例数量"、"各 RelationType 的连接密度"、"特定时间窗口内的变化趋势"等指标。

**Why this priority**: 数据服务不仅服务 AI，同样服务 BI。指标查询是 BI 集成的必要条件，与 AI 查询同等重要。

**Independent Test**: 可独立测试——调用指标查询接口，验证返回的聚合统计数值正确。

**Acceptance Scenarios**:

1. **Given** 本体中存在多个 ObjectType 实例，**When** BI 工具请求"按 ObjectType 统计实例数"，**Then** 返回各类型的实例计数
2. **Given** 本体中存在带时间属性的实例（如创建时间、更新时间），**When** BI 工具请求"最近 30 天新增的装备数量趋势"，**Then** 返回按日聚合的时间序列数据
3. **Given** 本体中存在 USL__Candidate 候选数据，**When** BI 工具请求统计数据，**Then** 默认过滤候选态和推演态数据（`valid=false`）

---

### User Story 3 - 链式推理执行 (Priority: P2)

作为一个本体使用者，我希望通过链式推理接口执行多步逻辑推导，以便获取更深层的知识。例如，从"装备 A 部署于系统 B"和"系统 B 依赖平台 C"推导出"装备 A 间接依赖平台 C"。

**Why this priority**: 链式推理是本体区别于普通数据库查询的核心能力，但实现复杂度高于简单查询，故排在 P1 之后。

**Independent Test**: 可独立测试——定义推理规则链，验证是否按预期执行多步推导。

**Acceptance Scenarios**:

1. **Given** 本体中存在"部署于"和"依赖"两种关系，且配置了传导推理规则，**When** 用户请求"装备 A 间接依赖的所有平台"，**Then** 返回完整的传导路径和每一步的中间结果
2. **Given** 推理链涉及规则冲突（如两条规则产生矛盾结论），**When** 执行链式推理，**Then** 返回冲突警告并标明冲突的具体规则和步骤
3. **Given** 推理链涉及 USL 审批后的正式概念，**When** 执行推理，**Then** 使用最新版本的概念定义

---

### User Story 4 - 混合检索编排 (Priority: P3)

作为一个高级调用方，我希望能够编排多种检索能力形成复杂的推理链，以便完成单一步骤无法实现的复杂任务。例如："先通过图检索找到所有装备 → 再通过链式推理分析风险传导 → 最后通过指标查询聚合统计结果"。

**Why this priority**: 混合检索是最灵活但最复杂的能力，依赖前三种分项检索的成熟度，故排在最后。

**Independent Test**: 可独立测试——编排多组件检索链，验证是否按预期顺序执行并合并结果。

**Acceptance Scenarios**:

1. **Given** 已注册的检索组件（chain, graph, metric），**When** 用户提交混合检索请求（如 graph → chain → metric），**Then** 按顺序执行每个组件并返回合并后的结果
2. **Given** 某个组件执行超时或失败，**When** 混合检索执行，**Then** 系统标记失败组件并可选择跳过或中止整条链

---

### User Story 5 - MCP Server 工具暴露 (Priority: P3)

作为一个 AI Agent 平台管理员，我希望将语义检索服务注册为 MCP Server 工具集，以便 OpenHarness 等 Agent 框架能够直接调用本体能力。

**Why this priority**: MCP 暴露是跨平台集成的关键，但需要先有稳定的服务总线，故排在最后。

**Independent Test**: 可独立测试——通过 MCP 客户端调用本体工具，验证返回结果的正确性。

**Acceptance Scenarios**:

1. **Given** 语义检索服务已启动，**When** MCP 客户端列出可用工具，**Then** 显示 `ontology_query`, `ontology_reason`, `ontology_metric` 等工具
2. **Given** MCP 客户端调用 `ontology_query` 工具，**When** 提交查询参数，**Then** 返回与直接 REST API 调用相同的结果

---

### Edge Cases

- 当本体中没有任何数据时，查询接口应返回空结果集而非错误
- 当查询涉及跨 workspace 的实体时，应明确返回权限不足或跨 workspace 不可见的提示
- 当链式推理产生循环依赖（A→B→C→A）时，应检测并中止推理，返回循环路径信息
- 当推演态数据（`valid=false`）被显式请求时，应允许通过参数控制是否包含
- 当混合检索编排包含超过 5 个组件时，应给出性能警告
- 当 BI 指标查询涉及大数据量聚合时，应支持分页和采样

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统必须提供统一检索端点，接收自然语言或结构化查询输入，自动路由到最合适的检索引擎
- **FR-002**: 系统必须提供链式推理分项检索端点，支持多步逻辑推导，返回每步中间结果和最终结论
- **FR-003**: 系统必须提供自然语言分项检索端点，将自然语言输入映射到本体术语后执行查询
- **FR-004**: 系统必须提供 MDL/DSL 分项检索端点，支持基于预定义模板语法的结构化推理
- **FR-005**: 系统必须提供图检索分项检索端点，支持基于图结构的实体和关系查询
- **FR-006**: 系统必须提供指标查询分项检索端点，支持聚合统计（计数、求和、平均等）
- **FR-007**: 系统必须提供混合检索编排端点，支持调用方显式编排多种检索组件的执行顺序
- **FR-008**: 混合检索必须支持单组件失败时的容错策略（跳过/中止/降级）
- **FR-009**: 系统必须通过 RESTful API 对外暴露所有检索能力
- **FR-010**: 系统必须通过 MCP Server 工具集暴露核心检索能力，供 Agent 框架直接调用
- **FR-011**: 系统必须在所有查询中默认过滤推演态数据（`valid=false`）和候选态数据（USL__Candidate），除非调用方显式请求包含
- **FR-012**: 系统必须支持 workspace 级别的数据隔离，不同 workspace 的查询结果互不可见
- **FR-013**: 所有检索操作必须记录审计日志（操作人、查询类型、结果数量、耗时），但不得记录查询内容本身
- **FR-014**: 系统必须对链式推理的循环依赖进行检测和防护
- **FR-015**: 指标查询必须支持时间窗口过滤和聚合粒度选择
- **FR-016**: 自然语言检索必须支持 USL 术语消歧（同义词映射）

### Key Entities

- **检索请求 (SearchRequest)**: 包含查询输入、检索模式、过滤条件、workspace 标识的请求载体
- **检索结果 (SearchResult)**: 包含命中的实体列表、关系路径、推理结论、置信度的响应载体
- **检索组件 (SearchComponent)**: 混合检索中的原子执行单元，包含类型（chain/nl/mdl/graph/metric）和参数
- **推理链 (ReasoningChain)**: 链式推理的执行路径，包含步骤序列、中间结果、规则引用
- **指标定义 (MetricDefinition)**: 指标的描述，包含聚合方式、筛选条件、时间窗口
- **MCP 工具注册 (MCPToolRegistration)**: 语义检索能力向 MCP Server 的注册记录

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: AI Agent 通过自然语言查询本体时，95% 的有效查询能在 3 秒内返回结构化结果
- **SC-002**: BI 工具的指标查询 P95 响应时间在 5 秒以内（10 万级实例聚合）
- **SC-003**: 链式推理的正确率（返回结果符合本体语义规则的比例）达到 90% 以上
- **SC-004**: 混合检索编排支持至少 5 种检索组件的自由组合
- **SC-005**: MCP Server 工具集暴露后，OpenHarness 等 Agent 框架可在 1 分钟内完成集成对接
- **SC-006**: 所有检索操作的审计日志完整覆盖率达到 100%（无审计空洞）
- **SC-007**: 推演态数据默认过滤率 100%（业务人员探查时看不到推演数据）

## Assumptions

- 假设 ODAP 项目采用模块化单体架构（ADR-046），语义检索服务作为现有单体应用的新模块，不需要独立部署
- 假设 Neo4j 和 SQLite 存储层已稳定运行，不需要为本特性新建存储
- 假设 Hyper-Extract 模板引擎和 USL OL 流水线（006/007 特性）在本特性第一阶段完成前已就绪
- 假设推演模块（`biz/simulation/`）的双时态标记能力在本特性之前已完成（或作为本特性的前置依赖）
- 假设 MCP 协议集成（ADR-026）已具备，本特性仅需注册新的工具集
- 假设指标查询的 Phase 1 范围为"基于 TBox 的自动派生统计"，不包含用户自定义 MetricType（Phase 2 范围）
- 假设本特性不引入新的 DSL 语法，复用 HE YAML 模板和 UModel `.umodel/.entity/.topo` 语法
