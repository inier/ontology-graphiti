"""Add Phase 10 and Phase 11 to tasks.md.

Phase 10: Brainstorm Edge Cases (2026-06-02) - 18 tasks (T253-T270)
Phase 11: Palantir/OntoFlow (2026-06-05) - 164 tasks (T271-T434)

This script carefully inserts the new content and updates related sections.
"""
import re

with open(r'specs\001-odap-platform\tasks.md', 'rb') as f:
    raw = f.read()

# ============================================================
# Step 1: Find the insertion point (after T312, before `---`)
# ============================================================
t312_marker = b'- [ ] T312 bootstep.py MinIO 服务集成'
t312_idx = raw.find(t312_marker)
print(f'T312 at byte {t312_idx}')

# Find the end of T312 line
t312_end = raw.find(b'\r\n', t312_idx) + 2  # position after the \r\n
print(f'T312 end at byte {t312_end}')

# ============================================================
# Step 2: Define Phase 10 content (18 tasks T253-T270)
# ============================================================
phase10_content = b'''
## Phase 10: Brainstorm Edge Cases（2026-06-02 头脑风暴边缘案例）

> 依赖 Phase 9 | 基于 2026-06-02 Brainstorm Session 新增的边缘案例补全
> **实施前需根据业务反馈细化验收标准**

### 编辑锁定机制

- [ ] T253 [P] 本体编辑锁服务 \xe2\x80\x94 `odap/biz/core/ontology/services/edit_lock_service.py` 实现 EditLockService：acquire_lock / release_lock / refresh_lock / get_lock_status，基于 WebSocket 心跳维持锁（超时 30s 自动释放），SQLite 持久化锁状态
- [ ] T254 本体编辑 WebSocket 集成 \xe2\x80\x94 `odap/web/ws/edit_lock_handler.py` 实现 WebSocket 端点，客户端发送心跳维持锁，断开自动释放；`odap/biz/core/ontology/api/routes.py` 更新/删除路由增加锁检查
- [ ] T255 前端编辑锁 UI \xe2\x80\x94 `frontend/src/modules/ontology/components/EditLockIndicator.tsx` 显示当前编辑者信息 + 锁定状态，编辑时自动获取锁，离开时释放

### LLM 不可用降级

- [ ] T256 LLM 降级策略统一 \xe2\x80\x94 `odap/infra/llm/llm_fallback.py` 统一 LLM 不可用时的降级行为：返回明确错误提示（含 LLM 不可用原因和建议重试时间），MUST NOT 静默降级；修复 `ingest_service.py` / `pipeline_service.py` / `manual_input.py` 中的静默降级为显式错误

### Neo4j 宕机降级

- [ ] T257 移除 NetworkX fallback 降级 \xe2\x80\x94 `odap/infra/graph/graph_service.py` 移除 `_use_fallback_mode()` 和所有 `_xxx_fallback()` 方法，Neo4j 不可用时返回 `{"status": "error", "message": "图数据库服务不可用，请稍后重试"}`；保留 NetworkX 仅用于单元测试 mock

### 推演排队机制

- [ ] T258 推演方案排队机制 \xe2\x80\x94 `odap/biz/simulation/simulation_sandbox/impl/parallel_runner.py` 新增 ScenarioQueue：超 10 并行时排队等待（FIFO），WebSocket 推送排队位置，方案完成时自动启动队列中下一个

### 三层安全防御

- [ ] T259 Cypher 注入修复 \xe2\x80\x94 `odap/infra/graph/graph_service.py` 修复所有字符串拼接为参数化查询，标签/关系类型增加白名单校验
- [ ] T260 LLM Prompt 注入防护 \xe2\x80\x94 `odap/infra/llm/prompt_sanitizer.py` 实现 PromptSanitizer：输入清洗（移除角色标记/指令注入模式）+ system prompt 隔离（角色标记包裹用户输入）；修复 `manual_input.py` / `qa_ontology_builder.py` / `news_ingester.py` 使用 sanitizer
- [ ] T261 前端 XSS 防护 \xe2\x80\x94 `frontend/src/modules/shared/utils/sanitize.ts` 封装 DOMPurify，所有渲染用户输入的组件使用 sanitize

### 工作空间级联删除

- [ ] T262 工作空间完整级联删除 \xe2\x80\x94 `odap/biz/platform/workspace/storage/sqlite_storage.py` 扩展 delete_workspace() 级联删除本体/Agent/Session/推演方案等所有关联数据；`odap/biz/platform/workspace/api/routes.py` 新增删除确认端点（返回将被删除的资源清单）
- [ ] T263 前端工作空间删除确认 \xe2\x80\x94 `frontend/src/modules/workspace/components/DeleteConfirmModal.tsx` 展示将被级联删除的资源清单 + 数量，二次确认后执行删除

### 引导性空状态

- [ ] T264 空状态组件库 \xe2\x80\x94 `frontend/src/modules/shared/components/organisms/EmptyState.tsx` 通用空状态组件（图标+标题+描述+操作按钮+示例数据加载）
- [ ] T265 示例数据生成服务 \xe2\x80\x94 `odap/biz/platform/workspace/services/sample_data_service.py` 一键生成示例数据（含示例本体 + 3 种实体类型 + 10 条实例 + 1 个 Agent 配置）
- [ ] T266 前端空状态集成 \xe2\x80\x94 各模块页面（本体/Agent/推演/问答）检测空数据时展示 EmptyState 组件，提供"加载示例数据"快捷操作

### 全局撤销

- [ ] T267 操作历史服务 \xe2\x80\x94 `odap/biz/platform/undo/services/operation_history_service.py` 记录所有写操作快照（action_type / resource_type / resource_id / before_state / after_state），SQLite 持久化，30 天自动清理
- [ ] T268 撤销/重做服务 \xe2\x80\x94 `odap/biz/platform/undo/services/undo_service.py` 实现 undo() / redo()，基于操作快照反向执行；`odap/biz/platform/undo/api/routes.py` 撤销/重做 API 端点
- [ ] T269 前端撤销/重做集成 \xe2\x80\x94 `frontend/src/modules/shared/hooks/useUndo.ts` 全局 Ctrl+Z/Ctrl+Y 快捷键绑定 + 撤销栈 UI 指示器

### 测试

- [ ] T270 Phase 10 单元测试 \xe2\x80\x94 `tests/unit/test_edit_lock.py` + `test_llm_fallback.py` + `test_prompt_sanitizer.py` + `test_operation_history.py` + `test_sample_data.py` 覆盖所有新增模块

'''

# ============================================================
# Step 3: Define Phase 11 content (164 tasks T271-T434)
# Use literal text without the corrupted "T475" duplicate
# ============================================================

# Use placeholders for tasks; we'll renumber later
def make_task(n, prefix_b, desc, file_path, suffix_b=b''):
    """Helper to format a task line"""
    return prefix_b + f' T{n} '.encode('utf-8') + suffix_b + desc.encode('utf-8') + b' \xe2\x80\x94 ' + file_path.encode('utf-8') + b'\n'

# We'll build Phase 11 in 7 FR sections
phase11_content = b'''## Phase 11: Palantir/OntoFlow 增强层（2026-06-05 brainstorm 增量）

> 预计工期: 12-15 周（4 个里程碑 M1-M4）| 依赖 Phase 3（FR-001/002/029）| 部分可并行
> 设计原则：零结构破坏（叠加于 FR-001）、职责分离（OPA vs Data Health）、Action-Skill 分层、Goal-driven 演化
> **本阶段为规划占位任务，实施前需根据业务反馈细化验收标准**

### M1 里程碑：Data Health + Branch & Merge（FR-031, FR-032）

#### FR-031: Data Health 数据健康引擎

- [ ] T271 [P] Health 模块目录结构创建 \xe2\x80\x94 `odap/biz/core/ontology/health/` 创建 `api/` `models/` `interfaces/` `impl/` `services/` `storage/` 子目录 + `__init__.py`
- [ ] T272 [P] HealthRule 领域模型定义 \xe2\x80\x94 `odap/biz/core/ontology/health/models/rule.py` `HealthRule(BaseModel)` 含 `target_type_id`、`check_expression` (JSON/YAML)、`severity` (info/warning/error/critical)、`schedule` (cron)、`notification_channel` (JSON)
- [ ] T273 [P] HealthReport 领域模型定义 \xe2\x80\x94 `odap/biz/core/ontology/health/models/report.py` `HealthReport(BaseModel)` 含 `instance_id`、`rule_id`、`status` (pass/warn/fail)、`details`、`scanned_at`
- [ ] T274 [P] HealthScan 领域模型定义 \xe2\x80\x94 `odap/biz/core/ontology/health/models/scan.py` `HealthScan(BaseModel)` 含 `status` (pending/running/done/failed)、`progress`、`started_at`、`finished_at`、`total_reports`
- [ ] T275 HealthScanner 抽象接口定义 \xe2\x80\x94 `odap/biz/core/ontology/health/interfaces/scanner.py` ABC 定义 `scan(rule) -> Iterator[HealthReport]`、`scan_all() -> Iterator[HealthReport]`
- [ ] T276 NotificationDispatcher 抽象接口定义 \xe2\x80\x94 `odap/biz/core/ontology/health/interfaces/notifier.py` ABC 定义 `dispatch(reports, channel) -> bool`
- [ ] T277 DeclarativeHealthScanner 实现 \xe2\x80\x94 `odap/biz/core/ontology/health/impl/scanner.py` 解析 JSON/YAML 规则，增量扫描（基于 `last_scan_at`），分批进度上报
- [ ] T278 EmailNotifier + WebhookNotifier + IMNotifier 实现 \xe2\x80\x94 `odap/biz/core/ontology/health/impl/notification.py` 三种通知渠道，retry + dead-letter
- [ ] T279 SQLite Health Storage 实现 \xe2\x80\x94 `odap/biz/core/ontology/health/storage/sqlite_health_storage.py` health_rules + health_reports + health_scans 三表 CRUD + `__init__.py` 别名导出
- [ ] T280 HealthService 编排层 \xe2\x80\x94 `odap/biz/core/ontology/health/services/health_service.py` CRUD 规则、触发扫描、查询报告、汇总
- [ ] T281 Health schemas 定义 \xe2\x80\x94 `odap/biz/core/ontology/health/api/schemas.py` CreateHealthRuleRequest / HealthRuleResponse / TriggerScanRequest / HealthReportResponse 等 Pydantic 模型
- [ ] T282 Health 路由实现 \xe2\x80\x94 `odap/biz/core/ontology/health/api/routes.py` APIRouter(prefix="/api/ontology/health") rules + scan + reports 路由，`except HTTPException: raise`
- [ ] T283 Health 路由注册到生产入口 \xe2\x80\x94 `odap/web/app.py` `include_router(health_router)`
- [ ] T284 APScheduler 集成 \xe2\x80\x94 `odap/biz/core/ontology/health/scheduler.py` 集成 apscheduler 加载 cron 规则；BackgroundTasks 处理异步扫描
- [ ] T285 Health 模型单元测试 \xe2\x80\x94 `tests/unit/test_ontology_health.py` 覆盖 HealthRule / HealthReport / HealthScan 必填字段、容器字段、Enum 值
- [ ] T286 Health Storage 单元测试 \xe2\x80\x94 `tests/unit/test_ontology_health.py` 新增 TestSQLiteHealthStorage，tmp_path 真实 DB
- [ ] T287 Health Service 单元测试 \xe2\x80\x94 `tests/unit/test_ontology_health.py` 新增 TestHealthService，扁平 dict 返回、类型转换、错误处理
- [ ] T288 Health Routes 单元测试 \xe2\x80\x94 `tests/unit/test_ontology_health.py` 新增 TestHealthRoutes，HTTP 状态码、HTTPException 透传
- [ ] T289 Health Scanner 单元测试 \xe2\x80\x94 `tests/unit/test_ontology_health.py` 新增 TestDeclarativeHealthScanner，规则解析 + 增量扫描逻辑
- [ ] T290 前端 Health 规则管理页面 \xe2\x80\x94 `frontend/src/modules/ontology/pages/HealthRuleManager.tsx` 规则列表 + 编辑器 (Monaco YAML)
- [ ] T291 前端 Health 报告面板 \xe2\x80\x94 `frontend/src/modules/ontology/components/HealthReportPanel.tsx` 报告列表 + 严重级别 Tag + 详情抽屉
- [ ] T292 前端 Health API 服务 \xe2\x80\x94 `frontend/src/modules/ontology/services/healthApi.ts` 封装 /api/ontology/health/*
- [ ] T293 前端 Health 翻译文件 \xe2\x80\x94 `frontend/src/modules/ontology/locales/{zh-CN,en-US}/health.json`

#### FR-032: 本体分支与合并（Branch & Merge）

- [ ] T294 [P] Branch 模块目录结构创建 \xe2\x80\x94 `odap/biz/core/ontology/engine/branch/` 创建 models/interfaces/impl/services/api/storage 子目录
- [ ] T295 [P] OntologyBranch 领域模型定义 \xe2\x80\x94 `odap/biz/core/ontology/engine/branch/models/branch.py` `OntologyBranch(BaseModel)` 含 `name` (git-like ref)、`base_version_id`、`head_version_id`、`protected`、`merge_strategy` (auto/manual/3-way)
- [ ] T296 [P] MergeRequest 领域模型定义 \xe2\x80\x94 `odap/biz/core/ontology/engine/branch/models/merge_request.py` `MergeRequest(BaseModel)` 含 `source_branch_id`、`target_branch_id`、`diff` (JSON Patch)、`conflicts[]`、`status` (open/merged/conflicted)、`reviewers[]`、`approvals[]`
- [ ] T297 [P] Conflict 领域模型定义 \xe2\x80\x94 `odap/biz/core/ontology/engine/branch/models/conflict.py` `Conflict(BaseModel)` 含 `object_type_id`、`field_path`、`base_value`、`ours_value`、`theirs_value`、`resolution` (ours/theirs/manual)
- [ ] T298 BranchManager 抽象接口定义 \xe2\x80\x94 `odap/biz/core/ontology/engine/branch/interfaces/branch_manager.py` ABC 定义 create_branch / list_branches / get_branch / protect_branch / delete_branch
- [ ] T299 MergeEngine 抽象接口定义 \xe2\x80\x94 `odap/biz/core/ontology/engine/branch/interfaces/merge_engine.py` ABC 定义 merge(source, target) -> MergeResult
- [ ] T300 DiffEngine 抽象接口定义 \xe2\x80\x94 `odap/biz/core/ontology/engine/branch/interfaces/diff_engine.py` ABC 定义 diff(version_a, version_b) -> JSONPatch
- [ ] T301 BranchManagerImpl 实现 \xe2\x80\x94 `odap/biz/core/ontology/engine/branch/impl/branch_manager.py` Git-like ref 管理，保护分支不可直接 push
- [ ] T302 JSONPatchDiffEngine 实现 \xe2\x80\x94 `odap/biz/core/ontology/engine/branch/impl/diff_engine.py` 基于 RFC 6902 计算 JSON Patch
- [ ] T303 ThreeWayMergeEngine 实现 \xe2\x80\x94 `odap/biz/core/ontology/engine/branch/impl/merge_engine.py` base + ours + theirs 合并算法，冲突字段由用户解决
- [ ] T304 SQLite Branch Storage 实现 \xe2\x80\x94 `odap/biz/core/ontology/engine/branch/storage/sqlite_branch_storage.py` branches + merge_requests + conflicts 三表 + `__init__.py` 别名导出
- [ ] T305 BranchService 编排层 \xe2\x80\x94 `odap/biz/core/ontology/engine/branch/services/branch_service.py` 创建分支、触发合并、查询 MR、通知评审人
- [ ] T306 Branch schemas 定义 \xe2\x80\x94 `odap/biz/core/ontology/engine/branch/api/schemas.py` CreateBranchRequest / MergeRequestResponse / ConflictResponse
- [ ] T307 Branch 路由实现 \xe2\x80\x94 `odap/biz/core/ontology/engine/branch/api/routes.py` APIRouter(prefix="/api/ontology/branches") + merge-requests 子路由
- [ ] T308 Branch 路由注册到生产入口 \xe2\x80\x94 `odap/web/app.py` `include_router(branch_router)`
- [ ] T309 Branch 模型单元测试 \xe2\x80\x94 `tests/unit/test_ontology_branch.py` 覆盖 Branch / MergeRequest / Conflict 模型
- [ ] T310 Branch Storage 单元测试 \xe2\x80\x94 `tests/unit/test_ontology_branch.py` TestSQLiteBranchStorage
- [ ] T311 Branch Service 单元测试 \xe2\x80\x94 `tests/unit/test_ontology_branch.py` TestBranchService
- [ ] T312 Branch Routes 单元测试 \xe2\x80\x94 `tests/unit/test_ontology_branch.py` TestBranchRoutes
- [ ] T313 MergeEngine 单元测试 \xe2\x80\x94 `tests/unit/test_ontology_branch.py` TestThreeWayMergeEngine（无冲突自动合并、冲突检测、3-way 正确性）
- [ ] T314 前端分支可视化组件 \xe2\x80\x94 `frontend/src/modules/ontology/components/BranchGraph.tsx` 基于 G6 渲染分支 DAG
- [ ] T315 前端冲突解决 UI \xe2\x80\x94 `frontend/src/modules/ontology/components/ConflictResolver.tsx` 三方对比 + 字段选择器 + Monaco diff editor
- [ ] T316 前端 MR 评审页 \xe2\x80\x94 `frontend/src/modules/ontology/pages/MergeRequestPage.tsx` MR 列表 + 详情 + 审批/拒绝操作
- [ ] T317 前端 Branch API 服务 \xe2\x80\x94 `frontend/src/modules/ontology/services/branchApi.ts` 封装 branches / merge-requests 接口
- [ ] T318 前端 Branch 翻译文件 \xe2\x80\x94 `frontend/src/modules/ontology/locales/{zh-CN,en-US}/branch.json`

### M2 里程碑：继承 + Action Type（FR-033, FR-034）

#### FR-033: Object Type 继承 + 组合

- [ ] T319 [P] Mixin 领域模型定义 \xe2\x80\x94 `odap/biz/core/ontology/model/models/mixin.py` `Mixin(BaseModel)` 含 `name`、`properties[]`、`actions[]`，不支持嵌套继承
- [ ] T320 EntityType 扩展字段 \xe2\x80\x94 `odap/biz/core/ontology/model/models/entity_type.py` 扩展 `inherits: List[str]`（深度 ≤ 5）、`mixins: List[str]`，DAG 验证、循环检测、Mixin 冲突检测
- [ ] T321 InheritanceResolver 抽象接口 \xe2\x80\x94 `odap/biz/core/ontology/model/interfaces/inheritance_resolver.py` ABC 定义 `resolve(entity_type) -> EntityType`（扁平化继承链 + 应用 mixin）
- [ ] T322 InheritanceResolverImpl 实现 \xe2\x80\x94 `odap/biz/core/ontology/model/impl/inheritance_resolver.py` 深度优先解析 + 字段去重 + 冲突 throw
- [ ] T323 SQLite Model Storage 扩展 \xe2\x80\x94 `odap/biz/core/ontology/model/storage/sqlite_model_storage.py` 新增 entity_type_inheritance / mixin_definitions 表
- [ ] T324 ModelService 扩展方法 \xe2\x80\x94 `odap/biz/core/ontology/model/services/model_service.py` 新增 `get_effective_properties()`、`get_inheritance_graph()`、`validate_inheritance_chain()`
- [ ] T325 Model 路由扩展 \xe2\x80\x94 `odap/biz/core/ontology/model/api/routes.py` 新增 `/entity-types/{id}/effective-properties`、`/entity-types/{id}/inheritance-graph`、`/validate-inheritance` 端点
- [ ] T326 继承验证测试 \xe2\x80\x94 `tests/unit/test_ontology_inheritance.py` TestInheritanceResolver（深度 ≤ 5、循环检测、Mixin 冲突、字段覆盖）
- [ ] T327 继承 Service 测试 \xe2\x80\x94 `tests/unit/test_ontology_inheritance.py` TestInheritanceService
- [ ] T328 继承 Routes 测试 \xe2\x80\x94 `tests/unit/test_ontology_inheritance.py` TestInheritanceRoutes
- [ ] T329 前端继承关系可视化 \xe2\x80\x94 `frontend/src/modules/ontology/components/InheritanceGraph.tsx` G6 树形图，节点显示属性合并
- [ ] T330 前端 EntityType 编辑器扩展 \xe2\x80\x94 `frontend/src/modules/ontology/components/EntityTypeEditor.tsx` 新增 "Inheritance" / "Mixins" 标签页
- [ ] T331 前端继承冲突提示 \xe2\x80\x94 `frontend/src/modules/ontology/components/InheritanceConflictAlert.tsx` 实时校验 + Alert 提示

#### FR-034: Action Type 一等公民 + Skill 分层

- [ ] T332 [P] Action Type 模块目录结构 \xe2\x80\x94 `odap/biz/core/ontology/action_type/` 创建 models/interfaces/impl/services/api 子目录
- [ ] T333 [P] ActionParam 领域模型 \xe2\x80\x94 `odap/biz/core/ontology/action_type/models/action_type.py` `ActionParam(BaseModel)` 含 `name`、`type_ref` (ObjectType 引用)、`required`
- [ ] T334 [P] ActionReturn 领域模型 \xe2\x80\x94 同文件 `ActionReturn(BaseModel)` 含 `type_ref`、`is_list`
- [ ] T335 [P] ActionType 领域模型 \xe2\x80\x94 同文件 `ActionType(BaseModel)` 含 `name`、`parameters[]`、`return_type`、`implementation: List[str]` (Skill 引用)、`preconditions` (OPA 策略引用)、`postconditions`
- [ ] T336 [P] SkillBinding 领域模型 \xe2\x80\x94 `odap/biz/core/ontology/action_type/models/skill_binding.py` 映射 Action 步骤 → Skill 调用
- [ ] T337 ActionExecutor 抽象接口 \xe2\x80\x94 `odap/biz/core/ontology/action_type/interfaces/action_executor.py` ABC 定义 `execute(action_type_id, params, context) -> ActionResult`
- [ ] T338 SkillRegistry 抽象接口 \xe2\x80\x94 `odap/biz/core/ontology/action_type/interfaces/skill_registry.py` ABC 定义 register_skill / get_skill / list_skills / bind_to_action
- [ ] T339 ActionExecutorImpl 实现 \xe2\x80\x94 `odap/biz/core/ontology/action_type/impl/action_executor.py` 接收 Agent 调用 → 参数校验 → OPA 鉴权 → Skill 顺序执行 → 事务回滚
- [ ] T340 SkillRegistryImpl 实现 \xe2\x80\x94 `odap/biz/core/ontology/action_type/impl/skill_registry.py` 复用现有 ToolRegistry，标记 legacy 工具
- [ ] T341 SQLite Action Type Storage \xe2\x80\x94 `odap/biz/core/ontology/action_type/storage/sqlite_action_storage.py` action_types + skill_bindings + execution_logs 表
- [ ] T342 ActionService 编排层 \xe2\x80\x94 `odap/biz/core/ontology/action_type/services/action_service.py` CRUD + 执行 + 执行历史
- [ ] T343 Action Type schemas \xe2\x80\x94 `odap/biz/core/ontology/action_type/api/schemas.py` CreateActionTypeRequest / ActionTypeResponse / ExecuteActionRequest / ExecutionResultResponse
- [ ] T344 Action Type 路由实现 \xe2\x80\x94 `odap/biz/core/ontology/action_type/api/routes.py` APIRouter(prefix="/api/ontology/action-types") CRUD + execute + executions 路由
- [ ] T345 Skill 绑定路由 \xe2\x80\x94 `odap/biz/core/ontology/action_type/api/skill_routes.py` `/api/skill/bind-action` 等
- [ ] T346 Action Type 路由注册 \xe2\x80\x94 `odap/web/app.py` `include_router(action_type_router)` + `include_router(skill_bind_router)`
- [ ] T347 Action Type 模型测试 \xe2\x80\x94 `tests/unit/test_ontology_action_type.py` TestActionType / TestActionParam / TestActionReturn / TestSkillBinding
- [ ] T348 Action Type Storage 测试 \xe2\x80\x94 tests/unit/test_ontology_action_type.py TestSQLiteActionStorage
- [ ] T349 Action Type Service 测试 \xe2\x80\x94 tests/unit/test_ontology_action_type.py TestActionService
- [ ] T350 Action Type Routes 测试 \xe2\x80\x94 tests/unit/test_ontology_action_type.py TestActionTypeRoutes
- [ ] T351 ActionExecutor 测试 \xe2\x80\x94 tests/unit/test_ontology_action_type.py TestActionExecutorImpl（事务回滚、OPA 鉴权、Skill 顺序）
- [ ] T352 前端 Action Type 管理页 \xe2\x80\x94 `frontend/src/modules/ontology/pages/ActionTypeManager.tsx` 列表 + 参数编辑器（按 ObjectType 强类型）
- [ ] T353 前端 Action 执行控制台 \xe2\x80\x94 `frontend/src/modules/ontology/components/ActionExecutionConsole.tsx` 参数表单 + 执行日志 + 回滚
- [ ] T354 前端 Skill 绑定 UI \xe2\x80\x94 `frontend/src/modules/ontology/components/SkillBindingEditor.tsx` 拖拽排序 + OPA 策略选择
- [ ] T355 前端 Action Type API 服务 \xe2\x80\x94 `frontend/src/modules/ontology/services/actionTypeApi.ts`
- [ ] T356 前端 Action Type 翻译文件 \xe2\x80\x94 `frontend/src/modules/ontology/locales/{zh-CN,en-US}/action-type.json`

### M3 里程碑：计算属性 + Goal-driven 演化（FR-035, FR-036）

#### FR-035: 计算属性 (Computed Properties)

- [ ] T357 [P] Property 模型扩展 \xe2\x80\x94 `odap/biz/core/ontology/model/models/property.py` 新增 `is_computed: bool`、`depends_on: List[str]`、`cache_strategy` (none/lazy/eager/hybrid)、`materialize_view: Optional[str]`
- [ ] T358 [P] Materialization 模块目录 \xe2\x80\x94 `odap/biz/core/ontology/materialization/` 创建 models/interfaces/impl/services/api 子目录
- [ ] T359 [P] MaterializedView 领域模型 \xe2\x80\x94 `odap/biz/core/ontology/materialization/models/view.py` `MaterializedView(BaseModel)` 含 `name`、`source_type_id`、`expression`、`depends_on[]`、`refresh_strategy`、`last_refreshed_at`
- [ ] T360 ComputeEngine 抽象接口 \xe2\x80\x94 `odap/biz/core/ontology/materialization/interfaces/compute_engine.py` ABC 定义 `recompute(view) -> ComputeResult`、`resolve(entity_id, property) -> Any`
- [ ] T361 DependencyTracker 抽象接口 \xe2\x80\x94 `odap/biz/core/ontology/materialization/interfaces/dependency_tracker.py` ABC 定义 `add_dependency`、`get_dependents`（反向索引）、`get_dependencies`
- [ ] T362 DependencyTrackerImpl 实现 \xe2\x80\x94 `odap/biz/core/ontology/materialization/impl/dependency_tracker.py` 反向索引存储，链深度 ≤ 10 校验
- [ ] T363 IncrementalComputeEngine 实现 \xe2\x80\x94 `odap/biz/core/ontology/materialization/impl/compute_engine.py` 实体变更时基于 `depends_on` 反向索引找下游视图，增量重算
- [ ] T364 ViewManager 实现 \xe2\x80\x94 `odap/biz/core/ontology/materialization/impl/view_manager.py` 创建视图、调度全量刷新（cron）、查询路由（优先物化视图 → 实时计算）
- [ ] T365 SQLite Materialization Storage \xe2\x80\x94 `odap/biz/core/ontology/materialization/storage/sqlite_materialization_storage.py` materialized_views + compute_results + dependency_graph 表
- [ ] T366 ComputeService 编排层 \xe2\x80\x94 `odap/biz/core/ontology/materialization/services/compute_service.py` CRUD 视图、触发重算、查询状态、stale 检测
- [ ] T367 Materialization schemas \xe2\x80\x94 `odap/biz/core/ontology/materialization/api/schemas.py` CreateViewRequest / ViewResponse / RecomputeRequest
- [ ] T368 Materialization 路由实现 \xe2\x80\x94 `odap/biz/core/ontology/materialization/api/routes.py` APIRouter(prefix="/api/ontology/materialization") + /computed/resolve 子路由
- [ ] T369 Materialization 路由注册 \xe2\x80\x94 `odap/web/app.py` `include_router(materialization_router)`
- [ ] T370 QueryService 集成 \xe2\x80\x94 `odap/infra/query/query_service.py` 修改查询路径：物化视图优先 → 实时计算 → 附 `is_stale` 字段
- [ ] T371 Compute 模型测试 \xe2\x80\x94 `tests/unit/test_ontology_computation.py` TestMaterializedView / TestProperty 扩展
- [ ] T372 Compute Storage 测试 \xe2\x80\x94 `tests/unit/test_ontology_computation.py` TestSQLiteMaterializationStorage
- [ ] T373 Compute Service 测试 \xe2\x80\x94 `tests/unit/test_ontology_computation.py` TestComputeService
- [ ] T374 Compute Routes 测试 \xe2\x80\x94 `tests/unit/test_ontology_computation.py` TestMaterializationRoutes
- [ ] T375 ComputeEngine 测试 \xe2\x80\x94 `tests/unit/test_ontology_computation.py` TestIncrementalComputeEngine（增量重算、依赖反向索引）
- [ ] T376 前端计算属性面板 \xe2\x80\x94 `frontend/src/modules/ontology/components/ComputedPropertyPanel.tsx` 属性列表 + depends_on 编辑 + 缓存策略选择
- [ ] T377 前端物化视图管理 \xe2\x80\x94 `frontend/src/modules/ontology/pages/MaterializedViewManager.tsx` 视图列表 + 创建向导 + 刷新状态
- [ ] T378 前端 Materialization API \xe2\x80\x94 `frontend/src/modules/ontology/services/materializationApi.ts`
- [ ] T379 前端 Materialization 翻译 \xe2\x80\x94 `frontend/src/modules/ontology/locales/{zh-CN,en-US}/materialization.json`

#### FR-036: OntoFlow 目标导向演化 (Goal-driven Evolution)

- [ ] T380 [P] Goal 领域模型 \xe2\x80\x94 `odap/biz/core/ontology/engine/models/goal.py` `Goal(BaseModel)` 含 `name`、`description`、`rationale`、`priority` (low/medium/high/critical)、`linked_requirements[]`、`status` (active/achieved/abandoned)
- [ ] T381 [P] GoalLink 领域模型 \xe2\x80\x94 `odap/biz/core/ontology/engine/models/goal_link.py` `GoalLink(BaseModel)` 关联 Goal ↔ OntologyChange
- [ ] T382 OntologyChange 扩展 \xe2\x80\x94 `odap/biz/core/ontology/engine/models/change.py` 扩展 `goal_id: str`（必填）、`rationale: str`（必填）
- [ ] T383 GoalManager 抽象接口 \xe2\x80\x94 `odap/biz/core/ontology/engine/interfaces/goal_manager.py` ABC 定义 create_goal / get_goal / list_goals / update_goal / compute_impact
- [ ] T384 ChangeValidator 扩展 \xe2\x80\x94 `odap/biz/core/ontology/engine/impl/change_validator.py` 拒绝缺失 goal_id 或 rationale 的变更，raise ValueError
- [ ] T385 GoalManagerImpl 实现 \xe2\x80\x94 `odap/biz/core/ontology/engine/impl/goal_manager.py` Goal CRUD + 影响分析（统计关联的 ontology_types、rules、instances）
- [ ] T386 SQLite Goal Storage \xe2\x80\x94 `odap/biz/core/ontology/engine/storage/sqlite_engine_storage.py` 新增 goals + goal_changes 表
- [ ] T387 EngineService 扩展 \xe2\x80\x94 `odap/biz/core/ontology/engine/services/engine_service.py` 强制要求 goal_id + rationale（不满足抛 ValueError）
- [ ] T388 Goal schemas \xe2\x80\x94 `odap/biz/core/ontology/engine/api/schemas.py` 扩展 CreateChangeRequest 包含 goal_id + rationale
- [ ] T389 Goal 路由实现 \xe2\x80\x94 `odap/biz/core/ontology/engine/api/goal_routes.py` APIRouter(prefix="/api/ontology/goals") CRUD + impact 端点
- [ ] T390 Goal 路由注册 \xe2\x80\x94 `odap/web/app.py` `include_router(goal_router)`
- [ ] T391 Change API 改造 \xe2\x80\x94 `odap/biz/core/ontology/engine/api/routes.py` 所有变更端点强制校验 goal_id + rationale
- [ ] T392 Goal 模型测试 \xe2\x80\x94 `tests/unit/test_ontology_goal.py` TestGoal / TestGoalLink / TestOntologyChange 扩展
- [ ] T393 Goal Storage 测试 \xe2\x80\x94 `tests/unit/test_ontology_goal.py` TestSQLiteGoalStorage
- [ ] T394 Goal Service 测试 \xe2\x80\x94 `tests/unit/test_ontology_goal.py` TestGoalService
- [ ] T395 Goal Routes 测试 \xe2\x80\x94 `tests/unit/test_ontology_goal.py` TestGoalRoutes
- [ ] T396 Change 强制校验测试 \xe2\x80\x94 `tests/unit/test_ontology_goal.py` TestChangeValidation（缺失 goal 抛 ValueError）
- [ ] T397 前端 Goal 仪表盘 \xe2\x80\x94 `frontend/src/modules/ontology/pages/GoalDashboard.tsx` Goal 列表 + 进度跟踪 + 关联变更数
- [ ] T398 前端 Goal 创建向导 \xe2\x80\x94 `frontend/src/modules/ontology/components/GoalWizard.tsx` 模板选择 + rationale 必填 + 关联需求
- [ ] T399 前端变更向导改造 \xe2\x80\x94 `frontend/src/modules/ontology/components/ChangeWizard.tsx` 强制要求选择 Goal + 填写 rationale
- [ ] T400 前端 Goal API 服务 \xe2\x80\x94 `frontend/src/modules/ontology/services/goalApi.ts`
- [ ] T401 前端 Goal 翻译文件 \xe2\x80\x94 `frontend/src/modules/ontology/locales/{zh-CN,en-US}/goal.json`

### M4 里程碑：Object View + 集成收尾（FR-037 + Phase 11 集成）

#### FR-037: 对象视图 (Object View)

- [ ] T402 [P] View 模块目录结构 \xe2\x80\x94 `odap/biz/core/ontology/view/` 创建 models/interfaces/impl/services/api 子目录
- [ ] T403 [P] ObjectView 领域模型 \xe2\x80\x94 `odap/biz/core/ontology/view/models/view.py` `ObjectView(BaseModel)` 含 `name` (e.g. `commander-view`)、`target_type_id`、`included_properties[]`、`included_actions[]`、`role_binding[]`、`redaction_rules[]`
- [ ] T404 [P] RedactionRule 领域模型 \xe2\x80\x94 `odap/biz/core/ontology/view/models/redaction.py` `RedactionRule(BaseModel)` 含 `field`、`method` (mask/hash/partial/remove)、`params`
- [ ] T405 ViewResolver 抽象接口 \xe2\x80\x94 `odap/biz/core/ontology/view/interfaces/view_resolver.py` ABC 定义 `resolve(view_id, entity_id, user_id) -> ViewPayload`（应用脱敏规则）
- [ ] T406 ViewService 抽象接口 \xe2\x80\x94 `odap/biz/core/ontology/view/interfaces/view_service.py` ABC 定义 CRUD + 角色绑定
- [ ] T407 ViewResolverImpl 实现 \xe2\x80\x94 `odap/biz/core/ontology/view/impl/view_resolver.py` 角色匹配 + 字段白名单 + 脱敏应用；Redis 缓存 resolve 结果
- [ ] T408 ViewServiceImpl 实现 \xe2\x80\x94 `odap/biz/core/ontology/view/impl/view_service.py` CRUD + 角色绑定
- [ ] T409 SQLite View Storage \xe2\x80\x94 `odap/biz/core/ontology/view/storage/sqlite_view_storage.py` object_views + redaction_rules + view_role_bindings 表
- [ ] T410 View 编排层 \xe2\x80\x94 `odap/biz/core/ontology/view/services/view_service_orchestrator.py`
- [ ] T411 View schemas \xe2\x80\x94 `odap/biz/core/ontology/view/api/schemas.py` CreateViewRequest / ViewResponse / ResolveRequest / ResolveResponse
- [ ] T412 View 路由实现 \xe2\x80\x94 `odap/biz/core/ontology/view/api/routes.py` APIRouter(prefix="/api/ontology/views") CRUD + resolve + bind-role
- [ ] T413 View 路由注册 \xe2\x80\x94 `odap/web/app.py` `include_router(view_router)`
- [ ] T414 OPA 集成 \xe2\x80\x94 `odap/infra/opa/policy_engine.py` View 决策与 OPA 协同：View 决定"展示什么"、OPA 决定"能否访问"
- [ ] T415 View 模型测试 \xe2\x80\x94 `tests/unit/test_ontology_view.py` TestObjectView / TestRedactionRule
- [ ] T416 View Storage 测试 \xe2\x80\x94 `tests/unit/test_ontology_view.py` TestSQLiteViewStorage
- [ ] T417 View Service 测试 \xe2\x80\x94 `tests/unit/test_ontology_view.py` TestViewService
- [ ] T418 View Routes 测试 \xe2\x80\x94 `tests/unit/test_ontology_view.py` TestViewRoutes
- [ ] T419 ViewResolver 测试 \xe2\x80\x94 `tests/unit/test_ontology_view.py` TestViewResolverImpl（脱敏、角色匹配、Redis 缓存）
- [ ] T420 前端 ObjectView 编辑器 \xe2\x80\x94 `frontend/src/modules/ontology/components/ObjectViewEditor.tsx` 字段白名单 + 脱敏配置 + 角色绑定
- [ ] T421 前端 View 切换器 \xe2\x80\x94 `frontend/src/modules/ontology/components/ViewSwitcher.tsx` 用户切换不同 View，预览效果
- [ ] T422 前端 ObjectView API 服务 \xe2\x80\x94 `frontend/src/modules/ontology/services/objectViewApi.ts`
- [ ] T423 前端 ObjectView 翻译文件 \xe2\x80\x94 `frontend/src/modules/ontology/locales/{zh-CN,en-US}/object-view.json`

#### Phase 11 集成收尾

- [ ] T424 ADR-055 补充 Phase 11 章节 \xe2\x80\x94 `docs/07-adr/ADR-055-unified-query.md` 补充 MaterializedView 与 QueryService 集成说明
- [ ] T425 新增 ADR-060 \xe2\x80\x94 `docs/07-adr/ADR-060-palantir-integration.md` 记录 Palantir 范式集成（Branch&Merge、Action Type、Object View）的决策与权衡
- [ ] T426 新增 ADR-061 \xe2\x80\x94 `docs/07-adr/ADR-061-ontoflow-goal-driven.md` 记录 OntoFlow 目标导向演化决策（强制 goal_id + rationale）
- [ ] T427 API 契约文档更新 \xe2\x80\x94 `specs/001-odap-platform/contracts/core-ontology-p4.md` 补充 35+ 端点的 OpenAPI 3.1 Schema
- [ ] T428 Quickstart 更新 \xe2\x80\x94 `specs/001-odap-platform/quickstart.md` 补充 Phase 11 端点的 curl 示例（已完成验证）
- [ ] T429 Plan.md 任务同步 \xe2\x80\x94 `specs/001-odap-platform/plan.md` Phase 4 章节补充任务编号映射（T271-T423）
- [ ] T430 Spec.md 增量章节 \xe2\x80\x94 `specs/001-odap-platform/spec.md` 补充 FR-031..FR-037 详细描述（若无）
- [ ] T431 Constitution 合规检查 \xe2\x80\x94 G-1..G-12 全部通过，constitution v2.1.0 新增 G-13（Goal-driven 强制校验）
- [ ] T432 Phase 11 端到端冒烟 \xe2\x80\x94 `tests/e2e/test_phase11_smoke.py` 端到端冒烟（Data Health + Branch Merge + Action Type + Computed + Goal + View）
- [ ] T433 Phase 11 性能基准 \xe2\x80\x94 `tests/perf/test_phase11_benchmark.py` 验证 Branch Merge < 5s、View Resolve < 100ms、Health Scan 1K 实例 < 10s
- [ ] T434 文档更新（README/AGENTS.md）\xe2\x80\x94 同步 Phase 11 新增模块到 README.md 模块列表、AGENTS.md 编码规则补充

'''

# ============================================================
# Step 4: Insert content at the boundary (after T312, before `---`)
# ============================================================
new_content = phase10_content + phase11_content
# Find the `---` separator after T312
sep_idx = raw.find(b'\r\n---\r\n', t312_end)
if sep_idx == -1:
    print('ERROR: Could not find --- separator after T312')
    exit(1)
print(f'--- separator at byte {sep_idx}')

# Insert content before the `---`
new_raw = raw[:sep_idx + 2] + new_content + raw[sep_idx + 2:]  # +2 to keep the \r\n
print(f'New file size: {len(new_raw)} bytes (was {len(raw)})')

# ============================================================
# Step 5: Update header (Total Tasks / Phases)
# ============================================================
new_raw = new_raw.replace(
    b'**Total Tasks**: 252 | **Phases**: 9 | **User Stories**: 6',
    b'**Total Tasks**: 434 | **Phases**: 11 | **User Stories**: 6 | **Brainstorm Increments**: 2 (Phase 10, Phase 11)'
)
new_raw = new_raw.replace(
    b'**Date**: 2026-05-31',
    b'**Date**: 2026-06-05'
)
print('Header updated')

# ============================================================
# Step 6: Update dependencies table - add FR-031..FR-037
# ============================================================
fr019_marker = b'| FR-019 | FR-009, Graphiti | \xe5\x86\xb3\xe7\xad\x96\xe6\x8e\xa8\xe8\x8d\x90\xe4\xbe\x9d\xe8\xb5\x96\xe6\x8e\xa8\xe6\xbc\x94\xe7\xbb\x93\xe6\x9e\x9c'
fr019_idx = new_raw.find(fr019_marker)
if fr019_idx == -1:
    print('WARNING: FR-019 marker not found')
else:
    # Find the end of this row
    fr019_end = new_raw.find(b'\r\n', fr019_idx) + 2
    new_fr_rows = b'''| FR-031 | FR-001 | Data Health 规则作用于 EntityType/Property 实体 |
| FR-032 | FR-001, FR-029, Graphiti | Branch & Merge 操作 OntologyDocument 增量（基于 JSON Patch），需 Graphiti 持久化分支历史 |
| FR-033 | FR-001 | Object Type 继承扩展 EntityType 模型字段 |
| FR-034 | FR-001, FR-014 | Action Type 引用 ObjectType 强类型参数，复用现有 SkillRegistry |
| FR-035 | FR-001, FR-023 | Computed Property 依赖 QueryService 查询路由 + 物化视图 |
| FR-036 | FR-001, FR-002 | Goal-driven 变更强制关联 OntologyChange + OntologyVersion |
| FR-037 | FR-001, FR-007, OPA | Object View 角色绑定 + 属性脱敏需 OPA 鉴权协同 |
'''
    new_raw = new_raw[:fr019_end] + new_fr_rows + new_raw[fr019_end:]
    print('Dependencies table updated')

# ============================================================
# Step 7: Update Phase 依赖关系 - add Phase 10, 11
# ============================================================
# The current diagram has Phase 1-9. Add Phase 10, 11
old_diagram_end = b'Phase 9 (Polish)\n```'
new_diagram_end = b'''Phase 9 (Polish)
    \xe2\x86\x93
Phase 10 (Brainstorm Edge Cases 2026-06-02) \xe2\x86\x90\xe2\x88\x90\xe2\x88\x90 \xe8\xbe\xb9\xe7\xbc\x98\xe6\xa1\x88\xe4\xbe\x8b\xe8\xa1\xa5\xe5\x85\xa8
    \xe2\x86\x93
Phase 11 (Palantir/OntoFlow 2026-06-05) \xe2\x86\x90\xe2\x88\x90\xe2\x88\x90 \xe4\xbc\x81\xe4\xb8\x9a\xe7\xba\xa7\xe5\xa2\x9e\xe5\xbc\xba\xef\xbc\x88FR-031..FR-037\xef\xbc\x89
```'''
if old_diagram_end in new_raw:
    new_raw = new_raw.replace(old_diagram_end, new_diagram_end)
    print('Phase diagram updated')
else:
    print('WARNING: Phase diagram not found')

# ============================================================
# Step 8: Update 关键路径
# ============================================================
old_keypath = b'T001-T025 \xe2\x86\x92 T026-T053 \xe2\x86\x92 T054-T133 \xe2\x86\x92 T134-T162 \xe2\x86\x92 T184-T239 \xe2\x86\x92 T240-T264 \xe2\x86\x92 T292-T312'
new_keypath = b'T001-T025 \xe2\x86\x92 T026-T053 \xe2\x86\x92 T054-T133 \xe2\x86\x92 T134-T162 \xe2\x86\x92 T184-T239 \xe2\x86\x92 T240-T264 \xe2\x86\x92 T292-T312 \xe2\x86\x92 T253-T270 (Phase 10) \xe2\x86\x92 T271-T434 (Phase 11)'
if old_keypath in new_raw:
    new_raw = new_raw.replace(old_keypath, new_keypath)
    print('Key path updated')
else:
    print('WARNING: Key path not found')

# ============================================================
# Step 9: Add Phase 11 里程碑并行 to Parallel Execution Examples
# ============================================================
# Find the "### Phase 7 + Phase 8 并行" section and add after it
phase78_marker = b'### Phase 7 + Phase 8 \xe5\xb9\xb6\xe8\xa1\x8c'
phase78_idx = new_raw.find(phase78_marker)
if phase78_idx != -1:
    # Find the end of the Phase 7+8 section (the closing ```)
    phase78_end = new_raw.find(b'```\r\n\r\n', phase78_idx)
    if phase78_end == -1:
        phase78_end = new_raw.find(b'```\n\n', phase78_idx)
    if phase78_end != -1:
        new_parallel = b'''
### Phase 11 里程碑并行（FR-031..FR-037 4 个 M1-M4）

```
M1 里程碑（Data Health + Branch & Merge）:  T271-T318 (FR-031, FR-032)
M2 里程碑（继承 + Action Type）:              T319-T356 (FR-033, FR-034)
M3 里程碑（计算属性 + Goal-driven）:          T357-T401 (FR-035, FR-036)
M4 里程碑（Object View + 集成收尾）:          T402-T434 (FR-037 + ADR + 冒烟)
```

**并行策略**:
- M1 与 M2 可并行：FR-031/032（独立模块 health + branch）vs FR-033/034（model + action_type）
- M3 依赖 M2 完成：FR-035（物化视图）依赖 FR-034（ActionType 已注册）+ QueryService
- M4 依赖 M3：FR-037（View Resolve）依赖 M3 的物化视图查询结果

**与 Phase 10（Brainstorm Edge Cases）关系**:
- Phase 10 完成 T253-T270（编辑锁、降级、注入防护等）→ Phase 11 直接继承
- Phase 11 不重复实施 Phase 10 已覆盖的边缘场景
'''
        # Find the end of the code block (```)
        code_end = new_raw.find(b'```', phase78_end + 5)
        if code_end != -1:
            code_end = new_raw.find(b'\n', code_end) + 1
            new_raw = new_raw[:code_end] + new_parallel + new_raw[code_end:]
            print('Phase 11 parallel section added')
        else:
            print('WARNING: Could not find end of Phase 7+8 code block')
    else:
        print('WARNING: Could not find end of Phase 7+8 section')
else:
    print('WARNING: Phase 7+8 marker not found')

# ============================================================
# Step 10: Add Brainstorm 增量交付 to Implementation Strategy
# Insert before "### 5. 测试策略" and renumber
# ============================================================
ts_marker = b'### 5. \xe6\xb5\x8b\xe8\xaf\x95\xe7\xad\x96\xe7\x95\xa5'
ts_idx = new_raw.find(ts_marker)
if ts_idx != -1:
    new_strategy = b'''### 5. Brainstorm 增量交付（Phase 10-11）

基于两次头脑风暴（2026-06-02 边缘案例、2026-06-05 企业级增强）补充的增量任务：

**Phase 10（边缘案例补全，T253-T270）**:
- 编辑锁机制（WebSocket 心跳）
- LLM 不可用降级（显式错误，禁止静默）
- Neo4j 宕机降级（移除 NetworkX fallback）
- 推演排队机制（FIFO + 10 并行上限）
- 三层安全防御（Cypher 注入 + Prompt 注入 + XSS）
- 工作空间级联删除（二次确认）
- 引导性空状态（EmptyState 组件 + 示例数据）
- 全局撤销/重做（30 天快照）

**Phase 11（企业级增强，T271-T434）**:
- FR-031 Data Health 引擎：完整性 + 一致性 + 漂移检测
- FR-032 Branch & Merge：git-like 语义 + PR/MR 评审 + 3-way 冲突解决
- FR-033 Object Type 继承 + Mixin：继承深度 ≤ 5
- FR-034 Action Type 一等公民：1:N Skill 绑定 + 事务回滚
- FR-035 计算属性：depends_on 声明 + 物化视图 + 增量重算
- FR-036 Goal-driven 演化：强制 goal_id + rationale
- FR-037 Object View：跨角色属性隔离 + 字段脱敏

### 6. 测试策略
'''
    new_raw = new_raw[:ts_idx] + new_strategy + new_raw[ts_idx:]
    # Renumber the original "### 5. 测试策略" (now the second occurrence) to "### 7. 测试策略"
    new_raw = new_raw.replace(b'### 5. \xe6\xb5\x8b\xe8\xaf\x95\xe7\xad\x96\xe7\x95\xa5', b'### 7. \xe6\xb5\x8b\xe8\xaf\x95\xe7\xad\x96\xe7\x95\xa5', 1)
    # Renumber "### 6. 风险缓解" to "### 8. 风险缓解"
    new_raw = new_raw.replace(b'### 6. \xe9\xa3\x8e\xe9\x99\xa9\xe7\xbc\x93\xe8\xa7\xa3', b'### 8. \xe9\xa3\x8e\xe9\x99\xa9\xe7\xbc\x93\xe8\xa7\xa3', 1)
    print('Implementation Strategy updated')
else:
    print('WARNING: ### 5. 测试策略 not found')

# ============================================================
# Step 11: Add new risk rows to the 风险缓解 table
# ============================================================
# Find the last row "T247, T241 |" (might not exist; use generic pattern)
risk_table_end = b'\r\n### '
# Find the risk table and append new rows before the next section
risk_last_row_pattern = rb'\|\s*T\d+,\s*T\d+\s*\|\s*\r\n'
risk_matches = list(re.finditer(risk_last_row_pattern, new_raw))
if risk_matches:
    last_risk_row = risk_matches[-1]
    insert_pos = last_risk_row.end()
    new_risks = b'''
| Branch & Merge 冲突解决 UI 复杂 | MVP 仅支持 JSON Patch 文本 diff，3-way 可视化推后 | T301-T303 |
| 计算属性依赖图过大 | 限制 depends_on 链深度 ≤ 10 + 物化视图 + 增量重算 | T357-T364 |
| Action Type 与 ToolRegistry 冲突 | 现有 Tool 标记为 legacy，逐步迁移 | T339-T340 |
| OntoFlow Goal 强制导致用户抵触 | 提供 Goal 模板 + 快捷创建（默认 Goal "功能改进"） | T383-T387 |
| Object View 性能开销 | Redis 缓存 resolve 结果 + OPA 批量校验 | T407, T414 |
| Phase 10/11 任务数激增（182 个） | 按 M1-M4 里程碑分批交付 + 强制 constitution 质量门禁 | T253-T434 |
'''
    new_raw = new_raw[:insert_pos] + new_risks + new_raw[insert_pos:]
    print('Risk table updated')
else:
    print('WARNING: Risk table last row not found')

# Save
with open(r'specs\001-odap-platform\tasks.md', 'wb') as f:
    f.write(new_raw)

print(f'Final size: {len(new_raw)} bytes')
print(f'Growth: {len(new_raw) - 59369} bytes')
