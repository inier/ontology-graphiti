# Research: Semantic Retrieval Service Bus

**Feature**: 008-semantic-retrieval-bus
**Date**: 2026-07-30
**Status**: Complete (all NEEDS CLARIFICATION resolved)

> 本文汇总两轮 grilling 决策（Q1-Q9）与代码探索结论（8 个集成点），作为 plan/data-model/contracts 的设计依据。

## 1. 领域术语边界（grilling Q1-Q4 决策）

### Decision
- **本体 (Ontology)** = TBox（结构 Schema）+ ABox（实例数据）组合体；**不**包含 USL
- **USL** = 独立横向语义规范总线，贯穿建/见/演/用四步
- **演本体** = 微观规则推演（Deduction）+ 宏观孪生推演（Decision）组合，共用 sandbox 隔离
- USL 在四步法中是横向能力（建/见/演/用全程参与）

### Rationale
钉死术语边界避免"本体"一词指代 4 种不同概念（TBox/ABox/USL/Candidate）导致 API 边界混乱。

### Alternatives considered
- 把 USL 纳入"本体"范畴 → 拒绝，因 USL 是元语言层，职责不同
- 演本体仅做微观推演 → 拒绝，决策推荐（宏观）已有实现，组合更完整

## 2. 语义检索服务总线路由形态（grilling Q5 决策）

### Decision
三层架构，全部位于 `/api/semantic-retrieval/*` 前缀下：
1. **统一检索** `POST /query` — 引擎自动路由（简单场景）
2. **分项检索** `POST /{chain|nl|mdl|graph|metric}` — 精确场景
3. **混合检索** `POST /hybrid` — `components: [{type, params}]` 编排（复杂场景）

### Rationale
用户要求"统一检索 + 分项检索 + 按需混合"三种模式并存。三层架构满足所有场景，且与现有 `/api/reasoning/retrieve` 并存不冲突。

### Alternatives considered
- 单一 endpoint + `mode` 参数 → 拒绝，违反 SRP，单端点职责过载
- 替换 `/api/reasoning/retrieve` → 拒绝，破坏向后兼容

## 3. MDL/DSL 策略（grilling Q6 决策）

### Decision
**禁止新发明 DSL**。复用：
1. Hyper-Extract YAML 模板语法（结构化推理）
2. UModel `.umodel/.entity/.topo` 语法（ADR-055 已提及）
3. OPA Rego（规则推理）

### Rationale
维护一套 DSL 需 parser + AST + 优化器，成本极高。现有 YAML/Rego 已能满足结构化推理需求。

### Alternatives considered
- 新发明 Ontology Query DSL（类 Cypher/GraphQL）→ 拒绝，季度级投入，ROI 不足

## 4. 推演数据隔离（grilling Q8 决策）

### Decision
推演数据双时态隔离：带 `scenario_id` + `valid=false` 标签，默认查询过滤；显式请求可包含；"采纳"操作可提升为正式数据。

### Rationale
与 ODAP 现有 Graphiti 双时态能力对齐，避免污染正式实例层。

### Alternatives considered
- 推演结果直接写入 ABox 仅用时间戳区分 → 拒绝，污染正式数据，回滚代价大

## 5. 集成点探索结论（代码扫描）

### 5.1 6 层 biz 模块结构
- **位置**: AGENTS.md L800-816
- **结构**: `api/` `models/` `interfaces/` `impl/` `services/` `storage/`
- **复用策略**: 新 `semantic_retrieval` 模块直接镜像此结构

### 5.2 现有 reasoning/query 服务
- **`/api/reasoning/retrieve`** (`biz/core/ontology/reasoning/api/routes.py` L21-69): 调用 `unified_retrieve` → `get_retrieve_engine()`，联邦检索 schema/entity/document 三源
- **QueryService** (`application/query_api/services`): `search_entities` 方法，含 workspace 隔离
- **复用策略**: 新模块的 `graph_engine` 适配 `QueryService.search_entities`；`/api/reasoning/retrieve` 保持并存（ADR-073），不替换

### 5.3 审计助手
- **位置**: `infra/security/audit_helper.py` L135-153
- **签名**: `storage_audit(action, *, result_status, result_message, resource, details, service)`
- **复用策略**: 直接复用，`service="semantic_retrieval"`。FR-013 要求只记统计不记内容 → `details` 仅放 `query_type/result_count/duration_ms`

### 5.4 workspace 隔离
- **位置**: `application/query_api/routes.py` L115-117
- **模式**: `workspace_id` 从 JWT 提取 → Cypher `MATCH (e:Entity {workspace_id: $workspace_id})`
- **复用策略**: 新模块所有查询沿用此模式（FR-012）

### 5.5 USL 术语消歧
- **位置**: `biz/semantic_admin/usl_manager/impl/usl_manager_service_impl.py` L114-125
- **签名**: `get_domain_by_term(self, term: str) -> Optional[str]`
- **复用策略**: `nl_engine` 调用此函数完成业务术语→ObjectType 映射（FR-016）

### 5.6 valid=false / candidate 过滤
- **位置**: `application/query_api/routes.py` L218-220
- **模式**: Cypher `WHERE NOT (e:USL__Candidate) AND e.valid = true`
- **复用策略**: 所有检索查询默认附加此过滤条件；`include_simulated` 参数可放开（FR-011）

### 5.7 PipelineService（混合编排）
- **位置**: `biz/core/ontology/design/services/pipeline_service.py` L10-30
- **能力**: 有序步骤执行 + 参数 + 失败处理
- **复用策略**: `hybrid_orchestrator` 适配 PipelineService，每个 component 作为一步（FR-007/008）

### 5.8 链式推理（deduction）
- **位置**: `biz/simulation/simulation_deduction/impl/deduction_engine_impl.py`（真实实现，非空桩）
- **能力**: `simulate_chain(scenario_id, chain_id)` 多步推导 + 中间结果 + 规则违反检测
- **复用策略**: `chain_engine` 适配 DeductionEngine，新增循环依赖检测层（FR-014，deduction_engine 现无此防护）

### 5.9 MCP 工具注册（待 Phase 3 确认）
- **位置**: ADR-026 提及 `openharness_bridge` / `mcp_protocol`
- **复用策略**: Phase 3 实现时镜像现有工具注册模式（Phase 1/2 不依赖）

## 6. 指标查询范围（grilling Q7 决策）

### Decision
- **Phase 1**: TBox 自动派生统计（ObjectType 实例数、RelationType 连接密度、时间窗口趋势）
- **Phase 2**: MetricType 一等公民（用户自定义 KPI）— 本特性不实现，留作后续

### Rationale
Phase 1 自动派生零额外 schema 成本，已能满足 BI 基础看板需求。MetricType 一等公民需新建实体 + 物化策略，过度设计风险高（Constitution IV）。

## 7. 见本体权限边界（grilling Q9 决策）

### Decision
- 编辑态（开发者）/ 探查态（业务人员）强制分离
- 候选态（USL__Candidate）默认对业务人员不可见

### Rationale
本特性（用本体）通过 `valid=false` + `USL__Candidate` 默认过滤实现 Q9 的"候选默认不可见"约束。编辑/探查态分离属"见本体"范畴，本特性不直接实现，但检索服务默认过滤与此约束一致。

## 结论

所有 NEEDS CLARIFICATION 已通过 grilling 决策 + 代码探索解决。新模块定位为 **Facade + 薄适配器**，90% 能力复用现有资产，新代码仅限：路由分发、请求归一化、结果合并、审计埋点、循环检测。符合 Constitution 简单 + 避免过度设计原则。
