#!/usr/bin/env python3
"""
Insert Phase 10 (Brainstorm Edge Cases) and Phase 11 (Palantir/OntoFlow)
into tasks.md after Phase 9 (line 469 in 1-based indexing, i.e. before the
`---` separator that precedes `## Dependencies & Execution Order`).
"""
import io
from pathlib import Path

TARGET = Path(r"e:\DEMO\AI\ontology-graphiti\specs\001-odap-platform\tasks.md")

PHASE10_AND_11 = r"""
---

## Phase 10: Brainstorm 边缘场景补全（2026-05-31 brainstorm 增量）

> 预计工期: 4-5 周 | 依赖 Phase 9 | 聚焦 6 个 brainstorm 边缘场景 | 任务编号 T313-T330

### SC-01: 多源冲突解决（OntoFlow 范式强化）

- [ ] T313 [P] 冲突解决策略领域模型 — `odap/biz/core/ontology/conflict/models/conflict_resolution.py` `ConflictResolution(str, Enum)` 含 FIRST_WINS / LAST_WINS / LLM_JUDGE / MANUAL 四种策略 + `ConflictRecord(BaseModel)` 含 entity_id / conflict_type / candidates / chosen
- [ ] T314 [P] 冲突解决器抽象接口 — `odap/biz/core/ontology/conflict/interfaces/conflict_resolver.py` `ConflictResolver(ABC)` 定义 resolve(conflict) / detect_conflicts(sources)
- [ ] T315 ConflictResolverImpl 实现 — `odap/biz/core/ontology/conflict/impl/conflict_resolver_impl.py` 实现 4 种策略：FIRST_WINS（取最早源）、LAST_WINS（取最新源）、LLM_JUDGE（调用 LLM 判断）、MANUAL（标记待人工处理）
- [ ] T316 ConflictService 编排层 — `odap/biz/core/ontology/conflict/services/conflict_service.py` 返回 Dict[str, Any]，集成到数据摄入流程
- [ ] T317 冲突解决 API 路由 — `odap/biz/core/ontology/conflict/api/routes.py` `APIRouter(prefix="/api/ontology/conflict")` POST `/detect` + POST `/resolve/{conflict_id}` + GET `/conflicts?status=pending`
- [ ] T318 冲突解决路由注册 — `odap/web/app.py` `include_router(conflict_router)`
- [ ] T319 冲突解决单元测试 — `tests/unit/test_conflict_resolver.py` 覆盖 4 种策略、检测逻辑、人工处理流程
- [ ] T320 前端冲突解决组件 — `frontend/src/modules/ontology/components/ConflictResolver.tsx` L3 组织组件，候选值对比 + 策略选择 + LLM 判断按钮

### SC-02: 冷启动数据稀疏

- [ ] T321 冷启动引导服务 — `odap/biz/core/ontology/cold_start/impl/bootstrap.py` 当新工作空间无数据时，从模板库加载示例本体（金融/医疗/制造三个行业模板）
- [ ] T322 冷启动单元测试 — `tests/unit/test_cold_start.py` 覆盖模板加载、数据稀疏检测、引导流程
- [ ] T323 行业模板库 — `odap/biz/core/ontology/cold_start/templates/` 三个 YAML 模板（finance.yaml / healthcare.yaml / manufacturing.yaml）

### SC-03: 大规模本体分片

- [ ] T324 本体分片器 — `odap/biz/core/ontology/sharding/impl/sharder.py` 当 ObjectType > 10000 实例时按主键 hash 自动分片，查询时并行扫描并合并
- [ ] T325 分片单元测试 — `tests/unit/test_sharding.py` 覆盖分片策略、并行查询、结果合并

### SC-04: 多租户隔离强化

- [ ] T326 租户隔离中间件 — `odap/infra/security/tenant_isolation.py` 所有 API 自动注入 ws_id 过滤条件，越权访问返回 403（不泄漏存在性）
- [ ] T327 租户隔离单元测试 — `tests/unit/test_tenant_isolation.py` 覆盖跨租户访问拦截、403 响应、审计日志

### SC-05: 审计日志保留策略

- [ ] T328 审计保留策略 — `odap/infra/security/audit_retention.py` 默认 90 天保留，支持按 workspace / classification 自定义保留期，过期自动归档到 MinIO
- [ ] T329 审计保留单元测试 — `tests/unit/test_audit_retention.py` 覆盖保留期计算、过期归档、查询历史归档

### SC-06: 错误降级与熔断

- [ ] T330 熔断器中间件 — `odap/infra/resilience/circuit_breaker.py` 对外部服务（LLM/Neo4j/OPA）实现熔断（错误率 > 50% 持续 30s 触发），半开探测恢复

---

## Phase 11: Palantir/OntoFlow 增强层（2026-06-05 brainstorm 增量）

> 预计工期: 12-15 周（4 个里程碑 M1-M4）| 依赖 Phase 3（FR-001/002/029）| 部分可并行
> 设计原则：零结构破坏（叠加于 FR-001）、职责分离（OPA vs Data Health）、Action-Skill 分层、Goal-driven 演化
> **本阶段为规划占位任务，实施前需根据业务反馈细化验收标准**

### M1 里程碑：Data Health + Branch & Merge（FR-031, FR-032）

#### FR-031: Data Health 数据健康引擎

- [ ] T331 [P] Health 模块目录结构创建 — `odap/biz/core/ontology/health/` 创建 `api/` `models/` `interfaces/` `impl/` `services/` `storage/` 子目录 + `__init__.py`
- [ ] T332 [P] HealthRule 领域模型定义 — `odap/biz/core/ontology/health/models/rule.py` `HealthRule(BaseModel)` 含 `target_type_id`、`check_expression` (JSON/YAML)、`severity` (info/warning/error/critical)、`schedule` (cron)、`notification_channel` (JSON)
- [ ] T333 [P] HealthReport 领域模型定义 — `odap/biz/core/ontology/health/models/report.py` `HealthReport(BaseModel)` 含 `instance_id`、`rule_id`、`status` (pass/warn/fail)、`details`、`scanned_at`
- [ ] T334 [P] HealthRuleRepository 抽象接口 — `odap/biz/core/ontology/health/interfaces/health_rule_repository.py` ABC 定义 CRUD + `list_by_target_type` + `list_by_severity`
- [ ] T335 [P] HealthScanner 抽象接口 — `odap/biz/core/ontology/health/interfaces/health_scanner.py` ABC 定义 `scan(rule_id: Optional[str]) -> List[HealthReport]`
- [ ] T336 SQLite Health Storage — `odap/biz/core/ontology/health/storage/sqlite_health_storage.py` 实现 `health_rules` / `health_reports` 表 CRUD + `__init__.py` 别名导出
- [ ] T337 HealthRuleRepositoryImpl — `odap/biz/core/ontology/health/impl/health_rule_repository_impl.py` 实现接口
- [ ] T338 HealthScannerImpl — `odap/biz/core/ontology/health/impl/health_scanner_impl.py` 支持 5 种规则：not_null / unique / regex / range / referential_integrity，使用 JSONLogic 引擎求值
- [ ] T339 NotificationDispatcher — `odap/biz/core/ontology/health/impl/notification_dispatcher.py` 支持 email / webhook / im 三种通道，异步发送（asyncio.create_task）
- [ ] T340 Health Service 编排层 — `odap/biz/core/ontology/health/services/health_service.py` 返回 Dict[str, Any]
- [ ] T341 Health API 路由 — `odap/biz/core/ontology/health/api/routes.py` `APIRouter(prefix="/api/ontology/health")` 35+ 端点（rules CRUD + scan + reports 查询）
- [ ] T342 Health schemas 定义 — `odap/biz/core/ontology/health/api/schemas.py` CreateHealthRuleRequest / HealthRuleResponse / ScanRequest / HealthReportResponse
- [ ] T343 Health 路由注册 — `odap/web/app.py` `include_router(health_router)`
- [ ] T344 Health 单元测试 — `tests/unit/test_health.py` 覆盖 5 种规则、CRUD、扫描调度、通知发送
- [ ] T345 前端 Health 规则编辑器 — `frontend/src/modules/ontology/components/HealthRuleEditor.tsx` L3 组件，YAML 编辑 + 表达式实时校验 + 严重程度选择
- [ ] T346 前端 Health 报告页面 — `frontend/src/modules/ontology/pages/HealthDashboard.tsx` L5 页面，规则列表 + 扫描触发 + 报告可视化（饼图+表格）

#### FR-032: 本体 Branch & Merge

- [ ] T347 [P] Branch 模块目录结构创建 — `odap/biz/core/ontology/branch/` 创建 `api/` `models/` `interfaces/` `impl/` `services/` `storage/` 子目录
- [ ] T348 [P] Branch 领域模型定义 — `odap/biz/core/ontology/branch/models/branch.py` `Branch(BaseModel)` 含 `id` / `name` / `ontology_id` / `base_version_id` / `head_version_id` / `status` (active/merged/abandoned)
- [ ] T349 [P] MergeRequest 领域模型 — `odap/biz/core/ontology/branch/models/merge_request.py` `MergeRequest(BaseModel)` 含 `source_branch_id` / `target_branch_id` / `conflicts` (JSON) / `status` (open/approved/merged/conflict)
- [ ] T350 [P] Conflict 领域模型 — `odap/biz/core/ontology/branch/models/conflict.py` `Conflict(BaseModel)` 含 `path` (JSON Pointer) / `base_value` / `ours_value` / `theirs_value` / `resolution`
- [ ] T351 BranchRepository 抽象接口 — `odap/biz/core/ontology/branch/interfaces/branch_repository.py` ABC 定义 CRUD + `list_by_ontology` + `get_active`
- [ ] T352 MergeEngine 抽象接口 — `odap/biz/core/ontology/branch/interfaces/merge_engine.py` ABC 定义 `merge(source, target) -> MergeResult` / `detect_conflicts(base, ours, theirs) -> List[Conflict]`
- [ ] T353 SQLite Branch Storage — `odap/biz/core/ontology/branch/storage/sqlite_branch_storage.py` 实现 `branches` / `merge_requests` / `conflicts` 表 CRUD
- [ ] T354 BranchRepositoryImpl — `odap/biz/core/ontology/branch/impl/branch_repository_impl.py`
- [ ] T355 ThreeWayMergeEngine — `odap/biz/core/ontology/branch/impl/merge_engine.py` 基于 RFC 6902 JSON Patch 实现 3-way merge，自动合并无冲突字段，冲突字段返回由用户解决
- [ ] T356 Branch Service 编排层 — `odap/biz/core/ontology/branch/services/branch_service.py` 集成 OntologyVersion 与 MergeEngine
- [ ] T357 Branch API 路由 — `odap/biz/core/ontology/branch/api/routes.py` 端点：POST `/api/ontology/branches` + GET `/api/ontology/branches` + POST `/api/ontology/branches/{id}/merge` + GET `/api/ontology/branches/{id}/conflicts`
- [ ] T358 Branch schemas 定义 — `odap/biz/core/ontology/branch/api/schemas.py` CreateBranchRequest / MergeRequestResponse / ConflictResolutionRequest
- [ ] T359 Branch 路由注册 — `odap/web/app.py` `include_router(branch_router)`
- [ ] T360 Branch 单元测试 — `tests/unit/test_branch.py` 覆盖 3-way merge、无冲突自动合并、冲突检测与解决、合并后版本生成
- [ ] T361 前端 Branch 可视化 — `frontend/src/modules/ontology/components/BranchGraph.tsx` L3 组件，G6 渲染分支树 + 合并箭头
- [ ] T362 前端 Merge 冲突解决器 — `frontend/src/modules/ontology/components/MergeConflictResolver.tsx` L3 组件，3 栏对比（base/ours/theirs）+ 选择按钮
- [ ] T363 前端 Branch 管理页面 — `frontend/src/modules/ontology/pages/BranchManager.tsx` L5 页面，分支列表 + 创建分支 + 发起合并

### M2 里程碑：Inheritance + Action Type（FR-033, FR-034）

#### FR-033: Object Type 继承 + Mixin

- [ ] T364 [P] Inheritance 模块目录创建 — `odap/biz/core/ontology/inheritance/` 标准分层
- [ ] T365 [P] InheritanceEdge 领域模型 — `odap/biz/core/ontology/inheritance/models/inheritance.py` `InheritanceEdge(BaseModel)` 含 `child_type_id` / `parent_type_id` / `depth` / `discriminator` (JSON)
- [ ] T366 [P] Mixin 领域模型 — `odap/biz/core/ontology/inheritance/models/mixin.py` `Mixin(BaseModel)` 含 `id` / `name` / `properties` (List[str]) / `target_type_ids` (List[str])
- [ ] T367 [P] InheritanceValidator — `odap/biz/core/ontology/inheritance/impl/validator.py` 检测循环继承（DFS）、最大深度限制（5 层）、Mixin 冲突
- [ ] T368 InheritanceResolver — `odap/biz/core/ontology/inheritance/impl/resolver.py` 给定 ObjectType + Property，解析完整属性链（parent → ... → root + mixins）
- [ ] T369 SQLite Inheritance Storage — `odap/biz/core/ontology/inheritance/storage/sqlite_inheritance_storage.py` 实现 `inheritance_edges` / `mixins` 表
- [ ] T370 InheritanceService 编排层 — `odap/biz/core/ontology/inheritance/services/inheritance_service.py`
- [ ] T371 Inheritance API 路由 — `odap/biz/core/ontology/inheritance/api/routes.py` POST `/api/ontology/inheritance/edges` + GET `/api/ontology/inheritance/resolve/{type_id}` + POST `/api/ontology/mixins`
- [ ] T372 Inheritance 单元测试 — `tests/unit/test_inheritance.py` 覆盖循环检测、深度限制、Mixin 解析、属性合并
- [ ] T373 前端继承关系可视化 — `frontend/src/modules/ontology/components/InheritanceGraph.tsx` L3 组件，G6 渲染继承树
- [ ] T374 前端 Mixin 管理组件 — `frontend/src/modules/ontology/components/MixinManager.tsx` L3 组件

#### FR-034: Action Type 一等公民

- [ ] T375 [P] Action Type 模块目录创建 — `odap/biz/core/ontology/action/` 标准分层
- [ ] T376 [P] ActionType 领域模型 — `odap/biz/core/ontology/action/models/action_type.py` `ActionType(BaseModel)` 含 `id` / `name` / `object_types` (List[str]) / `parameters` (JSON Schema) / `return_type` / `side_effects` / `linked_skill_id` / `opa_policy_ref`
- [ ] T377 [P] ActionExecution 领域模型 — `odap/biz/core/ontology/action/models/execution.py` `ActionExecution(BaseModel)` 含 `id` / `action_type_id` / `parameters` / `result` / `status` / `audit_record_id`
- [ ] T378 ActionTypeRepository 抽象接口 — `odap/biz/core/ontology/action/interfaces/action_type_repository.py`
- [ ] T379 ActionExecutor 抽象接口 — `odap/biz/core/ontology/action/interfaces/action_executor.py` 定义 `execute(action_type, params, user_context) -> ActionExecution`
- [ ] T380 SQLite Action Storage — `odap/biz/core/ontology/action/storage/sqlite_action_storage.py` 实现 `action_types` / `action_executions` 表
- [ ] T381 ActionTypeRepositoryImpl — `odap/biz/core/ontology/action/impl/action_type_repository_impl.py`
- [ ] T382 SkillBackedExecutor — `odap/biz/core/ontology/action/impl/skill_executor.py` Action Type 通过 linked_skill_id 委托给 Skill 系统执行（**Action Type = 业务接口，Skill = 工程实现**）
- [ ] T383 ActionService 编排层 — `odap/biz/core/ontology/action/services/action_service.py` 调用前 OPA 权限校验（OPA write-time check），调用后审计日志
- [ ] T384 Action API 路由 — `odap/biz/core/ontology/action/api/routes.py` POST `/api/ontology/actions` + POST `/api/ontology/actions/{id}/execute` + GET `/api/ontology/actions/{id}/executions`
- [ ] T385 Action schemas 定义 — `odap/biz/core/ontology/action/api/schemas.py`
- [ ] T386 Action 路由注册 — `odap/web/app.py` `include_router(action_router)`
- [ ] T387 Action 单元测试 — `tests/unit/test_action.py` 覆盖 Action Type CRUD、Skill 委托执行、OPA 权限校验、审计记录
- [ ] T388 前端 Action 列表页面 — `frontend/src/modules/ontology/pages/ActionLibrary.tsx` L5 页面，Action Type 库 + 参数编辑器 + 执行历史
- [ ] T389 前端 Action 执行组件 — `frontend/src/modules/ontology/components/ActionExecutor.tsx` L3 组件，表单生成（基于 JSON Schema）+ 执行结果展示

### M3 里程碑：Computed Property + Object View（FR-035, FR-036）

#### FR-035: 计算属性 + 物化视图

- [ ] T390 [P] ComputedProperty 模块目录创建 — `odap/biz/core/ontology/computed/` 标准分层
- [ ] T391 [P] ComputedProperty 领域模型 — `odap/biz/core/ontology/computed/models/property.py` `ComputedProperty(BaseModel)` 含 `id` / `name` / `target_type_id` / `expression` (DSL) / `dependencies` (List[str]) / `materialization` (none/full/incremental)
- [ ] T392 [P] MaterializationJob 领域模型 — `odap/biz/core/ontology/computed/models/job.py` `MaterializationJob(BaseModel)` 含 `id` / `property_id` / `status` (pending/running/done/failed) / `started_at` / `finished_at`
- [ ] T393 DependencyTracker — `odap/biz/core/ontology/computed/impl/dependency_tracker.py` 解析表达式依赖（基于 AST 遍历），构建 DAG
- [ ] T394 ExpressionEvaluator — `odap/biz/core/ontology/computed/impl/evaluator.py` 安全沙箱执行（RestrictedPython），支持数学/字符串/日期/聚合函数
- [ ] T395 IncrementalComputer — `odap/biz/core/ontology/computed/impl/incremental.py` 当依赖属性变化时，仅重算受影响对象（DAG 反向传播）
- [ ] T396 SQLite Computed Storage — `odap/biz/core/ontology/computed/storage/sqlite_computed_storage.py` 实现 `computed_properties` / `materialization_jobs` / `materialized_values` 表
- [ ] T397 ComputedService 编排层 — `odap/biz/core/ontology/computed/services/computed_service.py`
- [ ] T398 Computed API 路由 — `odap/biz/core/ontology/computed/api/routes.py` 端点：CRUD + POST `/recompute/{property_id}` + GET `/jobs/{id}/status`
- [ ] T399 Computed 单元测试 — `tests/unit/test_computed.py` 覆盖表达式求值、依赖追踪、增量重算、沙箱安全
- [ ] T400 前端计算属性编辑器 — `frontend/src/modules/ontology/components/ComputedPropertyEditor.tsx` L3 组件，DSL 编辑 + 依赖图可视化 + 表达式测试运行
- [ ] T401 前端物化任务监控 — `frontend/src/modules/ontology/components/MaterializationMonitor.tsx` L3 组件，任务列表 + 进度条 + 失败重试

#### FR-036: Object View 角色视图

- [ ] T402 [P] ObjectView 模块目录创建 — `odap/biz/core/ontology/view/` 标准分层
- [ ] T403 [P] ObjectView 领域模型 — `odap/biz/core/ontology/view/models/view.py` `ObjectView(BaseModel)` 含 `id` / `name` / `base_type_id` / `role` / `projected_properties` (List[str]) / `filters` (JSON) / `row_limit` / `sort_order`
- [ ] T404 [P] ViewPermission 领域模型 — `odap/biz/core/ontology/view/models/permission.py` `ViewPermission(BaseModel)` 含 `view_id` / `role` / `can_export` / `can_share` / `redaction_rules` (JSON)
- [ ] T405 ViewRepository 抽象接口 — `odap/biz/core/ontology/view/interfaces/view_repository.py`
- [ ] T406 ViewQueryEngine 抽象接口 — `odap/biz/core/ontology/view/interfaces/view_query_engine.py` 定义 `query(view_id, user_context) -> List[Dict]`
- [ ] T407 SQLite View Storage — `odap/biz/core/ontology/view/storage/sqlite_view_storage.py` 实现 `object_views` / `view_permissions` 表
- [ ] T408 ViewRepositoryImpl — `odap/biz/core/ontology/view/impl/view_repository_impl.py`
- [ ] T409 ViewQueryEngineImpl — `odap/biz/core/ontology/view/impl/view_query_engine_impl.py` 集成 OPA（读取时权限校验）+ 字段脱敏（redaction_rules）
- [ ] T410 ViewService 编排层 — `odap/biz/core/ontology/view/services/view_service.py`
- [ ] T411 View API 路由 — `odap/biz/core/ontology/view/api/routes.py` CRUD + POST `/api/ontology/views/{id}/query`
- [ ] T412 View 单元测试 — `tests/unit/test_view.py` 覆盖视图 CRUD、字段投影、过滤、权限校验、脱敏规则
- [ ] T413 前端视图设计器 — `frontend/src/modules/ontology/components/ViewDesigner.tsx` L3 组件，可视化属性选择 + 过滤条件构建 + 角色绑定
- [ ] T414 前端视图查询页面 — `frontend/src/modules/ontology/pages/ObjectViewPage.tsx` L5 页面，视图查询 + 导出（带权限控制）

### M4 里程碑：OntoFlow Goal-driven 演化（FR-037）

#### FR-037: OntoFlow Goal 驱动演化

- [ ] T415 [P] Goal 模块目录创建 — `odap/biz/core/ontology/goal/` 标准分层
- [ ] T416 [P] Goal 领域模型 — `odap/biz/core/ontology/goal/models/goal.py` `Goal(BaseModel)` 含 `id` / `title` / `description` / `business_objective` / `rationale` (LLM 生成) / `status` (proposed/approved/rejected/in-progress/achieved/abandoned) / `parent_goal_id`
- [ ] T417 [P] ChangeProposal 领域模型 — `odap/biz/core/ontology/goal/models/proposal.py` `ChangeProposal(BaseModel)` 含 `id` / `goal_id` / `changes` (JSON Patch) / `impact_analysis` / `estimated_benefit` / `status`
- [ ] T418 [P] ImpactAnalysis 领域模型 — `odap/biz/core/ontology/goal/models/impact.py` `ImpactAnalysis(BaseModel)` 含 `affected_types` / `affected_instances_count` / `breaking_changes` (List[str]) / `estimated_migration_cost`
- [ ] T419 GoalRepository 抽象接口 — `odap/biz/core/ontology/goal/interfaces/goal_repository.py`
- [ ] T420 ImpactAnalyzer 抽象接口 — `odap/biz/core/ontology/goal/interfaces/impact_analyzer.py` 定义 `analyze(changes: JSONPatch) -> ImpactAnalysis`
- [ ] T421 SQLite Goal Storage — `odap/biz/core/ontology/goal/storage/sqlite_goal_storage.py` 实现 `goals` / `change_proposals` / `impact_analyses` 表
- [ ] T422 GoalRepositoryImpl — `odap/biz/core/ontology/goal/impl/goal_repository_impl.py`
- [ ] T423 LLM Rationale Generator — `odap/biz/core/ontology/goal/impl/rationale_generator.py` 调用 LLM 为 Goal 生成 business_rationale（多轮追问澄清）
- [ ] T424 ImpactAnalyzerImpl — `odap/biz/core/ontology/goal/impl/impact_analyzer_impl.py` 静态分析：受影响 ObjectType / Action Type / 估算迁移成本
- [ ] T425 GoalService 编排层 — `odap/biz/core/ontology/goal/services/goal_service.py`
- [ ] T426 Goal API 路由 — `odap/biz/core/ontology/goal/api/routes.py` CRUD + POST `/api/ontology/goals/{id}/propose-change` + GET `/api/ontology/goals/{id}/lineage`
- [ ] T427 Goal 单元测试 — `tests/unit/test_goal.py` 覆盖 Goal CRUD、LLM rationale 生成、Impact 分析、Goal lineage
- [ ] T428 前端 Goal 看板 — `frontend/src/modules/ontology/pages/GoalKanban.tsx` L5 页面，Goal 状态看板（拖拽切换状态）+ 时间线
- [ ] T429 前端 Change Proposal 组件 — `frontend/src/modules/ontology/components/ChangeProposalCard.tsx` L3 组件，提案详情 + 影响分析可视化 + 审批按钮
- [ ] T430 前端 Goal Lineage 视图 — `frontend/src/modules/ontology/components/GoalLineage.tsx` L3 组件，父子 Goal + 关联变更 + G6 图谱渲染

### Phase 11 集成与文档

- [ ] T431 ADR-055 状态修正 — `docs/07-adr/ADR-055.md` 补充"Action Type = 业务接口，Skill = 工程实现"分层原则
- [ ] T432 FR-031..FR-037 用户文档 — `docs/03-modules/ontology/DESIGN.md` 补充 Data Health / Branch / Inheritance / Action / Computed / View / Goal 章节
- [ ] T433 API 契约文档 — `specs/001-odap-platform/contracts/core-ontology-p4.md` 已创建，补充 curl 示例和错误码表
- [ ] T434 Phase 11 集成测试 — `tests/integration/test_p4_features.py` 端到端测试 Branch 创建→Health 扫描→Action 执行→Goal 关联

"""

src = TARGET.read_text(encoding="utf-8")
lines = src.splitlines(keepends=True)

# Find the `---` separator immediately before `## Dependencies & Execution Order`.
# The pattern is: `---` (line N), blank line (N+1), `## Dependencies` (N+2).
insert_idx = None
for i, line in enumerate(lines):
    if line.strip() == "---":
        # Search ahead up to 3 lines for the Dependencies heading
        for j in range(i + 1, min(i + 4, len(lines))):
            if "## Dependencies & Execution Order" in lines[j]:
                insert_idx = i
                break
        if insert_idx is not None:
            break

if insert_idx is None:
    raise SystemExit("Could not find insertion point (--- before Dependencies)")

# Replace the existing `---` with the new content (the new content already starts with `---`)
new_block = PHASE10_AND_11  # already includes leading "\n---\n\n"
lines[insert_idx] = new_block

TARGET.write_text("".join(lines), encoding="utf-8")
print(f"Inserted Phase 10 and 11 at line {insert_idx + 1}")
print(f"New file size: {TARGET.stat().st_size} bytes")
