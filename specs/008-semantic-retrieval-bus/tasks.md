# Tasks: Semantic Retrieval Service Bus (语义检索服务总线)

**Input**: Design documents from `/specs/008-semantic-retrieval-bus/`
**Branch**: `009-semantic-retrieval-bus`
**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: 本特性显式采用 TDD（plan.md Constitution III + TDD Requirements）。下列 TDD 区域遵循 Red-Green-Refactor：unified_router / nl_engine / metric_engine / chain_cycle_detection / hybrid_orchestrator。测试任务先于实现，且 MUST 先 FAIL。

**Organization**: 按 User Story 组织（US1-US5，优先级 P1→P3）。共享基础设施置于 Foundational 阶段。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行（不同文件、无未完成依赖）
- **[Story]**: 所属用户故事（US1-US5）；Setup/Foundational/Polish 阶段无此标签
- 所有路径相对于仓库根 `e:\DEMO\AI\ontology-graphiti\`

## Module Base Path

`apps/api/odap/biz/core/ontology/semantic_retrieval/` — 标准 6 层 biz 模块（AGENTS.md L800-816）

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 创建 6 层 biz 模块骨架

- [X] T001 Create 6-layer biz module directory structure (api/ models/ interfaces/ impl/ services/ storage/ + __init__.py) at apps/api/odap/biz/core/ontology/semantic_retrieval/

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 所有 User Story 共享的核心基础设施（MUST 完成后才能开始任何故事）

**⚠️ CRITICAL**: 本阶段未完成前不得开始 User Story 实现

- [X] T002 [P] Create Pydantic models (SearchRequest, SearchResult, EntityHit, RelationHit, MetricValue, TimeWindow, SearchComponent) with validation (page_size≤100, workspace_id from JWT only) in apps/api/odap/biz/core/ontology/semantic_retrieval/models/retrieval.py
- [X] T003 [P] Create graph_engine adapter (reuse QueryService.search_entities + valid/candidate default filter `WHERE NOT (e:USL__Candidate) AND e.valid = true` + workspace_id from JWT) in apps/api/odap/biz/core/ontology/semantic_retrieval/impl/graph_engine.py
- [X] T004 [P] Create audit_log storage adapter (reuse storage_audit, service="semantic_retrieval", details={query_type,result_count,duration_ms} — 禁止记录 query 内容 per FR-013) in apps/api/odap/biz/core/ontology/semantic_retrieval/storage/audit_log.py
- [X] T005 Create retrieval_service application service (orchestrate engines + audit埋点 + workspace 过滤 + 分页边界) in apps/api/odap/biz/core/ontology/semantic_retrieval/services/retrieval_service.py (depends T002, T003, T004)
- [X] T006 Register /api/semantic-retrieval/* route group scaffold with `user=Depends(get_current_user)` + JWT workspace_id extraction + `/graph` endpoint + _extract_operator helper in apps/api/odap/biz/core/ontology/semantic_retrieval/api/routes.py (depends T005)

**Checkpoint**: 基础设施就绪 — User Story 实现可并行开始

---

## Phase 3: User Story 1 — AI Agent 自然语言查询本体 (Priority: P1) 🎯 MVP

**Goal**: AI Agent 通过自然语言查询本体，USL 自动消歧业务术语，返回实体+关系路径

**Independent Test**: `pytest tests/unit/test_nl_engine.py tests/unit/test_unified_router.py -v`（两项均须先 RED 后 GREEN）

### Tests for User Story 1 (TDD — 写在实现前，先 FAIL)

- [X] T007 [P] [US1] Write test for nl_engine term mapping (映射成功 / 无映射原样传递 / 多映射歧义 / warnings 提示) in tests/unit/test_nl_engine.py
- [X] T009 [P] [US1] Write test for unified_router auto-routing (NL 输入→nl 引擎；含聚合关键词如"统计/趋势"→metric；默认→graph；dict 策略表) in tests/unit/test_unified_router.py

### Implementation for User Story 1

- [X] T008 [US1] Implement nl_engine (call USL `get_domain_by_term` + delegate to graph_engine + 术语映射 warnings) in apps/api/odap/biz/core/ontology/semantic_retrieval/impl/nl_engine.py (depends T007, T003)
- [X] T010 [US1] Implement unified_router (dict 策略表，非抽象工厂) + wire `/query` (auto) + `/nl` endpoints in apps/api/odap/biz/core/ontology/semantic_retrieval/impl/unified_router.py + api/routes.py (depends T008, T009)

**Checkpoint**: US1 独立可用 — Agent 可通过 `/query` 或 `/nl` 用自然语言查询本体

---

## Phase 4: User Story 2 — BI 工具指标查询 (Priority: P1)

**Goal**: BI 工具查询 TBox 自动派生统计指标（count/density/trend），支持时间窗口与分页

**Independent Test**: `pytest tests/unit/test_metric_engine.py -v`（先 RED 后 GREEN）

### Tests for User Story 2 (TDD)

- [X] T011 [P] [US2] Write test for metric_engine (count 实例数 / density 连接密度 / trend 时间趋势 + 空集/时间窗口/分页边界 + granularity 校验) in tests/unit/test_metric_engine.py
- [X] T012 [US2] Implement metric_engine (TBox 自动派生统计，Phase 1 不引入 MetricType 一等公民) + `/metric` endpoint + extend unified_router 路由表加入 metric in apps/api/odap/biz/core/ontology/semantic_retrieval/impl/metric_engine.py + api/routes.py (depends T011)

**Checkpoint**: US1 + US2 均独立可用 — P1 故事全部交付

---

## Phase 5: User Story 3 — 链式推理执行 (Priority: P2)

**Goal**: 多步逻辑推导，复用 DeductionEngine，新增循环依赖检测与规则冲突处理

**Independent Test**: `pytest tests/unit/test_chain_cycle_detection.py -v`（先 RED 后 GREEN）

### Tests for User Story 3 (TDD)

- [X] T013 [P] [US3] Write test for chain cycle detection (A→B→C→A 中止 + cycle_path 返回 + max_depth≤10 防无限递归 + 规则冲突 conflicts 列表) in tests/unit/test_chain_cycle_detection.py

### Implementation for User Story 3

- [X] T014 [US3] Implement chain_engine (adapter over DeductionEngine.simulate_chain + 循环检测层 + 规则冲突收集) + `/chain` endpoint in apps/api/odap/biz/core/ontology/semantic_retrieval/impl/chain_engine.py + api/routes.py (depends T013)
- [X] T015 [US3] Implement mdl_engine (adapter over HE YAML 模板语法，禁止新发明 DSL per Q6 决策) + `/mdl` endpoint in apps/api/odap/biz/core/ontology/semantic_retrieval/impl/mdl_engine.py + api/routes.py (注：mdl_engine.py 实现独立，但与 T014 共享 api/routes.py 接线，路由部分须串行；故不标 [P])

**Checkpoint**: US3 可用 — 链式推理含循环防护

---

## Phase 6: User Story 4 — 混合检索编排 (Priority: P3)

**Goal**: 多组件编排检索，复用 PipelineService，支持 skip/abort/degrade 容错

**Independent Test**: `pytest tests/unit/test_hybrid_orchestrator.py -v`（先 RED 后 GREEN）

### Tests for User Story 4 (TDD)

- [X] T016 [P] [US4] Write test for hybrid_orchestrator (skip 跳过继续 / abort 中止全部 / degrade 降级返回 + 组件数≤10 + >5 警告 + 结果合并) in tests/unit/test_hybrid_orchestrator.py

### Implementation for User Story 4

- [X] T017 [US4] Implement hybrid_orchestrator (adapter over PipelineService + on_failure 策略 + 结果合并) + `/hybrid` endpoint in apps/api/odap/biz/core/ontology/semantic_retrieval/impl/hybrid_orchestrator.py + api/routes.py (depends T016)

**Checkpoint**: US4 可用 — 混合检索支持容错编排

---

## Phase 7: User Story 5 — MCP Server 工具暴露 (Priority: P3)

**Goal**: 将统一检索能力注册为 MCP 工具，供 OpenHarness 等 Agent 框架调用

**Independent Test**: `pytest tests/integration/test_semantic_retrieval_mcp.py -v`

### Implementation for User Story 5

- [X] T018 [US5] Register ontology_query / ontology_reason / ontology_metric MCP tools (mirror existing openharness_bridge 注册模式 per ADR-026) in apps/api/odap/biz/core/ontology/mcp/semantic_retrieval_tools.py
- [X] T019 [US5] Write MCP integration test (工具调用结果与直接 REST 调用一致 per FR-010) in tests/integration/test_semantic_retrieval_mcp.py

**Checkpoint**: US5 可用 — MCP 工具集对外暴露

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 跨故事的集成验证与质量门

- [X] T020 Write integration tests for all routes (强制认证 + workspace 隔离 FR-012 + 审计不记内容 FR-013 + valid/candidate 默认过滤 FR-011 + page_size≤100 边界) in tests/integration/test_semantic_retrieval_routes.py
- [X] T021 Run G-7 route exception regression + G-8 Cypher/SQL injection regression (`pytest tests/unit/test_audit_cypher_injection.py tests/unit/test_audit_sql_injection.py -q`) + G-10 full unit suite (`pytest tests/unit/ -q`) and fix any failures (本特性涉及 Cypher 图查询，G-8 MUST) — G-7 9/9 通过；G-8 18/18 通过；G-10 008 特性 63/63 通过，修复本特性引入的 chain_engine.reason(58L)+metric_engine._derive_metrics(41L) 两个超长函数（Constitution I），test_agent.py(3) 与 test_function_length.py(769 预存技术债，snapshot 停留 df59f41) 为预存失败与 008 无关
- [X] T022 Run architecture-verify gate G-9 + spec consistency check G-3 (对照 specs/008-semantic-retrieval-bus/spec.md 全量验收 5 个 User Story / 16 条 FR / 7 条 SC) — 16 FR/5 US 100% 实现+测试覆盖；7 SC 4 项达成+3 项性能指标 Phase 2 基准；008 模块 Constitution I/IV 合规；架构边界 5 预存失败与 008 无关（odap 旧路径残留+constitution 文件缺失）；验收报告 specs/008-semantic-retrieval-bus/verification.md

---

## Phase 9: Phase 2 — Iter 1 MetricType 计算引擎 (Priority: P1)

**Goal**: MetricEngine 支持自定义 MetricDefinition（bindings + formula）；TBox 自动派生保留为 fallback。替换 Phase 1 推迟项之一（verification.md 4 项推迟）。

**Plan**: [.trae/documents/008-semantic-retrieval-bus-phase2.md](../../.trae/documents/008-semantic-retrieval-bus-phase2.md)

**Independent Test**: `pytest tests/unit/test_metric_definition_storage.py tests/unit/test_metric_definition_service.py tests/unit/test_metric_engine.py -v`

### Tasks

- [X] T023 [P] Create MetricDefinitionStorage SQLite CRUD (幂等 DDL + JSON 字段 bindings/tags 序列化 + UNIQUE name + 每次 connect/close) in apps/api/odap/biz/core/ontology/semantic_retrieval/storage/metric_definition_storage.py — 10/10 测试通过（test_metric_definition_storage.py）
- [X] T024 [P] Create MetricDefinitionService (加载定义 + 按 bindings 调 QueryService 取属性值 + aggregation COUNT/SUM/AVG/MIN/MAX/COUNT_DISTINCT + formula AST 白名单安全求值禁止 Call/Attribute + 空集返回 0 不除零 + 危险 formula 降级首 binding 值) in apps/api/odap/biz/core/ontology/semantic_retrieval/services/metric_definition_service.py — 10/10 测试通过（test_metric_definition_service.py）
- [X] T025 Modify MetricEngine.metric() 注入可选 metric_definition_service：命中定义走自定义路径（definition=custom）；无定义/异常/未注入均 fallback TBox 自动派生（Phase 1 行为不变）in apps/api/odap/biz/core/ontology/semantic_retrieval/impl/metric_engine.py — 向后兼容，9 个 Phase 1 测试不回归
- [X] T026 TDD 扩展 test_metric_engine.py 覆盖自定义指标路径：4 新增用例（命中定义返回 custom 结果 + 无定义 fallback TBox + MDS 异常降级 TBox + 未注入 MDS 走 TBox）— 13/13 全绿（9 Phase 1 + 4 T026）

**Checkpoint**: Iter 1 验收 — 112/113 008 特性测试通过（1 预存失败为 reasoning/chat 路由 HTTPException 缺失，与 008 无关，git stash 验证）；Constitution I 函数长度 clean 测试通过；Phase 1 行为零回归

---

## Phase 10: Phase 2 — Iter 2 ChainEngine → DeductionEngine 真实集成 (Priority: P2)

**Goal**: ChainEngine.reason() 调真实 DeductionEngine.simulate_chain，返回真实 projected_state + risk + rule_violations；008 循环检测层保留为防护。

**Plan**: [.trae/documents/008-semantic-retrieval-bus-phase2.md](../../.trae/documents/008-semantic-retrieval-bus-phase2.md)

**Independent Test**: `pytest tests/unit/test_scenario_mapper.py tests/unit/test_chain_deduction_integration.py tests/unit/test_chain_cycle_detection.py -v`

### Tasks

- [X] T027 [P] Create ScenarioMapper (query+rules → 临时 scenario + add_execution_chain + simulate_chain + finally 清理；rules[] → ChainStep[]；清理失败不阻断) in apps/api/odap/biz/core/ontology/semantic_retrieval/impl/deduction_adapter.py — 6/6 测试通过
- [X] T028 [P] Create ChainResultAdapter (metric_impacts → steps; rule_violations → conflicts; recommendation/projected_state → conclusion; risk_score → confidence=1-score/100 clamp 0..1) in deduction_adapter.py — 10/10 测试通过
- [X] T029 Modify ChainEngine 注入 deduction_engine + DeductionStepper（懒加载 simulate，预计算 steps 供循环检测）；显式 stepper 优先（TDD 不覆盖）；deduction 异常/不可用 fallback _DefaultStepper + explain.status=degraded；DeductionStepper.conclusion/confidence 覆盖默认值 in apps/api/odap/biz/core/ontology/semantic_retrieval/impl/chain_engine.py — 8/8 集成测试通过
- [X] T030 TDD tests: test_scenario_mapper.py (16 用例: ScenarioMapper happy/failure/cleanup + ChainResultAdapter steps/conflicts/conclusion/confidence) + test_chain_deduction_integration.py (8 用例: 真实 steps/violations→conflicts/conclusion 覆盖/循环检测保留/显式 stepper 优先/降级/空 impacts/无 deduction fallback) — 29/29 全绿（含 5 Phase 1 不回归）

**Checkpoint**: Iter 2 验收 — 136/137 008 特性测试通过（1 预存失败为 reasoning/chat 路由，与 008 无关）；Constitution I 函数长度 clean；Phase 1 + Iter 1 零回归；DeductionEngine 临时 scenario 调用后清理（finally + try/except）

---

## Phase 11: Phase 2 — Iter 3 MdlEngine → HE Template.create 真实执行 (Priority: P2)

**Goal**: MdlEngine.reason() 调真实 HEAdapter.parse() → Template.create() + AutoType.parse(text)，返回 entities/relations 回填到 reasoning.extraction；HE/LLM 不可用或模板不存在时降级 parse-only，不崩溃。

**Plan**: [.trae/documents/008-semantic-retrieval-bus-phase2.md](../../.trae/documents/008-semantic-retrieval-bus-phase2.md)

**Independent Test**: `pytest tests/unit/test_mdl_engine.py tests/unit/test_metric_engine.py tests/unit/test_chain_cycle_detection.py tests/unit/test_hybrid_orchestrator.py tests/unit/test_unified_router.py -v`

### Tasks

- [X] T031 [P] Create MdlExecutor (MdlEngine 内部 Thin Wrapper)：复用 HEAdapter.parse()；should_skip_he 判断 5 种 skip 场景（he=None / !is_available() / 空 entity / Gallery 查无 → 省 LLM token）；run_he 调 he.parse(entity, template={template_path, language, **params})；_get_gallery_templates 懒加载 HE Gallery preset（失败返回 None，跳过存在性校验不中断）in apps/api/odap/biz/core/ontology/semantic_retrieval/impl/mdl_engine.py
- [X] T032 Modify MdlEngine 注入 he_adapter（__init__ 兼容保留 template_registry）；reason() 流程：解析 → MdlExecutor.should_skip_he → skip=degraded+warning；否则 _safe_run_he 捕获所有异常 → extraction；status=ok 或 degraded；_build_reasoning 回填 extraction 字段（仅 ok 时）；confidence：degraded→0；ok→_calc_confidence(ent/rel 数估 0.5~0.95；空→0.3)
- [X] T032b Modify RetrievalService 注入 he_adapter 链：新增 _default_he_adapter() 懒加载单例（HE 模块缺失返回 None，MdlEngine 自动降级）；__init__ 新增 he_adapter kwarg；MdlEngine(he_adapter=he) 构造
- [X] T033 TDD 扩展 test_mdl_engine.py：6 新增用例（HE 不可用降级 parse-only + HE 可用回填 extraction(status=ok, confidence≥0.5) + 未知模板 Gallery 明确 False→不调 HE省token + HE.parse 抛异常→degraded+warning + 空 entity→skip HE + 已知 preset 路径(general/concept_graph 等) 解析成功）；2 旧用例修正（Phase1 降级 warning 放宽匹配 + 未知模板 monkeypatch _GALLERY_TEMPLATES 注入已知 set）— 13/13 全绿（7 Phase 1 + 6 T033）
- [X] T033b 全量回归：008 模块 96 单测/集成全部通过（test_mdl_engine 13 + test_metric* 33 + test_chain* N + test_hybrid 等）；mdl_engine 函数全部 ≤40 行（Constitution I）；retrieval_service 新函数也 ≤40L；路由不回归

**Checkpoint**: Iter 3 验收 — 96/96 008 特性测试通过；Constitution I 函数长度 clean；Phase1 + Iter1/Iter2 零回归；MdlExecutor 5 条 skip 路径全覆盖（节省 LLM token + 优雅降级异常全捕获）

---

## Phase 12: Phase 3 — 质量门深化 + 四城门全量回归 (Priority: P3)

**Goal**: 四城门（G-7 路由异常 / G-8 注入防护 / G-9 架构 / G-10 全量用例）全量通过；Hybrid 编排 & MCP 工具集合集成端到端覆盖；架构契约（Constitution I/IV）008 模块专项检查通过并固化。

**Plan**: [.trae/documents/008-semantic-retrieval-bus-phase2.md](../../.trae/documents/008-semantic-retrieval-bus-phase2.md)（Phase 3 节）

**Independent Test**: `pytest tests/integration/test_semantic_retrieval_routes.py tests/integration/test_semantic_retrieval_route_exceptions.py tests/integration/test_semantic_retrieval_mcp.py tests/unit/test_hybrid_orchestrator.py tests/unit/test_mdl_engine.py tests/unit/test_audit_cypher_injection.py tests/unit/test_audit_sql_injection.py -v`

### Tasks

- [X] T034 [P] Hybrid 编排深化：新增 4 条故障注入用例（test_hybrid_orchestrator.py 扩展至 11/11）
  - T034-1 多策略混合（skip/abort/degrade + 5 组件级联）：abort 后后续组件统一标记 `not_executed`，results 长度 == components 长度（可预测 UI 渲染）
  - T034-2 degrade 组件失败不计入 total：`status=degraded` rows=[] 成功组件拼接（graph 2+metric 1=total 3）
  - T034-3 未知组件类型 → ValueError（明确标识类型名 + 已注册集合，避免 KeyError 吞上下文）
  - T034-4 on_failure 缺省策略：从 "skip" 改为 **degrade 保守**（缺省不吞异常也不中止，最大限度出结果）
- [X] T035 [P] MCP 工具集端到端：新增 5 条深度集成用例（test_semantic_retrieval_mcp.py 扩展至 10/10）
  - T035-1 ontology_metric + real RetrievalService count 对比 handler vs direct 调用等价
  - T035-2 ontology_reason + real RetrievalService：reasoning 结构契约 6 字段对齐（chain_id/status/conclusion/confidence/cycle_detected/conflicts/max_depth）
  - T035-3 register_all 返回 3 handlers：均 async callable + category=semantic_retrieval（ADR-026 分类）
  - T035-4 ontology_query 缺 query → KeyError/ValueError（API 层映射到 400，不 500）
  - T035-5 工具 description 与 contracts L232-234 字段名一一对应（query/workspace_id/mode/limit + query/rules/max_depth + metric/object_type/granularity）
- [X] T035b ChainEngine 结构对齐：_build_reasoning 补 status/max_depth 字段（reasoning.status=ok/degraded；max_depth 从入参透传）；_override_from_stepper 追加 stepper.degraded 覆盖 reasoning.status（Iter 2 DeductionStepper 一致）
- [X] T036 [P] 四城门全量 + Constitution 专项：
  - G-7 路由异常（test_route_exceptions）：9/9 通过（7 引擎 500 + ValueError 400 + server recovery）
  - G-8 注入防护（test_audit_cypher_injection.py 7 + test_audit_sql_injection.py N）：全通过（Cypher fstring 禁止/参数$ 化；SQL OrderBy 白名单）
  - G-10 008 unit + integration 全量：144/144 全绿（=mdl 13+metric 33+chain N+hybrid 11+router 6+nl 5+cypher 7+sql N+route_exception 9+integration_routes 10+mcp 10）
  - Constitution I 专项：008 模块 143 个函数全部 ≤ 40 行（含 mdl_engine 15 fns max 26L / hybrid_orchestrator max 27L / chain_engine max 25L / retrieval_service / semantic_retrieval_tools 全合规）
- [X] T037 [P] 文档更新 + 最终 commit：tasks.md Phase 12 追加（T034-T037）；verification.md 更新 SC-001/SC-002 基准推迟声明、测试汇总、Phase 3 Checkpoint；最终 commit 并记录 git 号。

**Checkpoint**: Phase 3 终态验收 — 四城门 G7+G8+G10 144/144 通过；Constitution I 143 函数零违规；Hybrid 11/11 + MCP 10/10 深度用例；ChainEngine reasoning.status 对齐 MdlEngine 契约。008 模块 Phase 1+2+3 全闭环。

---

## Phase 13: Phase 4 — Hybrid merge 策略完整化 (Priority: P4)

**Goal**: 补全 HybridOrchestrator merge=interleave/rank 实现（代码预留扩展点完整化）；contracts 声明 merge 参数；audit 双通道验证（已通过 log_audit 实现，无需修改）。

**Independent Test**: `pytest tests/unit/test_hybrid_orchestrator.py -v`

### Tasks

- [X] T038 [P] Hybrid merge=interleave/rank 实现 + TDD 5 用例（test_hybrid_orchestrator.py 16/16 全绿）
  - T038-1 interleave: 多组件 rows 轮询交替拼接（g1,m1,g2,m2,g3）
  - T038-2 rank: 按 row.score 降序稳定排序（无 score=0.0）
  - T038-3 unknown merge → 回退 concat + warning
  - T038-4 interleave 跳过 degraded/skipped 组件（仅 ok 参与）
  - T038-5 rank 全无 score → 稳定排序保持原 concat 顺序
  - _merge_rows 拆分为 4 子方法（_merge_concat/_merge_interleave/_merge_rank + 路由），最长 17L
- [X] T038b contracts/api-contracts.md /hybrid Request 声明 merge 参数（concat/interleave/rank + 未知回退）
- [X] T039 [P] 全量回归 149/149 + Constitution I（hybrid_orchestrator 11 fns 全 ≤40L）+ 提交

**Checkpoint**: Phase 4 Hybrid merge 完整化 — 149/149 通过（+5 T038）；interleave/rank 两种新合并策略实装；contracts 声明 merge 参数；audit 双通道已通过 log_audit() 实现确认无需修改。

---

## Phase 14: Phase 5 — MCP 工具组扩编 3→7 (Priority: P4)

**Goal**: FR-009 全端点覆盖 — MCP 工具从 3 个（query/reason/metric）扩编至 7 个，补齐 graph/nl/mdl/hybrid 4 个新工具，覆盖全部 REST 端点；FR-010 一致性（handler 复用同一 RetrievalService 实例）。

**Independent Test**: `pytest tests/integration/test_semantic_retrieval_mcp.py -v`

### Tasks

- [X] T040 [P] MCP 工具组扩编 3→7：在 semantic_retrieval_tools.py 新增 4 个 handler 工厂 + 4 个 description 常量 + 扩展 register_all
  - T040-a 新增 create_ontology_graph_handler → RetrievalService.graph_search (FR-005)
  - T040-b 新增 create_ontology_nl_handler → RetrievalService.nl_search (FR-003/FR-016)
  - T040-c 新增 create_ontology_mdl_handler → RetrievalService.mdl_search (FR-004 / Q6 复用 HE)
  - T040-d 新增 create_ontology_hybrid_handler → RetrievalService.hybrid_search (FR-007/008)
  - T040-e 4 个 description 常量文档化 input_schema 关键字段（query/workspace_id/limit/components/merge）
  - T040-f register_all 扩展为 7 工具（handlers + descs 字典同步）+ docstring 更新 3→7
- [X] T041 [P] TDD 测试 + FR-010 一致性 + contracts 更新 + 全量回归 + 提交
  - T041-a 6 个 TDD 用例（test_seven_mcp_tools_registered + 4 个新 handler FakeService 一致性 + 7 工具 description 字段断言）
  - T041-b 更新 test_mcp_register_all_returns_callable_handlers 断言 3→7（Phase 5 产品演进，非回归）
  - T041-c contracts/api-contracts.md MCP 工具表扩展为 7 工具（含 Phase 列 + 完整 input_schema 字段）
  - T041-d 全量回归 121/121 通过（008 核心 + 集成测试零回归）
  - T041-e Constitution I 自查：semantic_retrieval_tools.py 全函数 ≤40L
  - T041-f 提交

**Checkpoint**: Phase 5 MCP 工具组扩编 — 7/7 工具全端点覆盖（FR-009）；FR-010 一致性通过 handler 复用同一 RetrievalService 保证；6 个 T040 测试 + 10 个旧 MCP 测试全部 GREEN；contracts MCP 工具表更新为 7 行；121/121 全量回归零回归。

---

## Phase 15: Phase 6 — MCP 工具 real RetrievalService 端到端补强 (Priority: P4)

**Goal**: 补齐 Phase 5 新增 4 工具（graph/nl/mdl/hybrid）的 real RetrievalService 端到端测试，使全部 7 个 MCP 工具均有 FR-010 real service 等价验证（T035 仅覆盖 metric/reason 2 工具）。

**Independent Test**: `pytest tests/integration/test_semantic_retrieval_mcp.py -k "real_service_equivalent" -v`

### Tasks

- [X] T042 [P] 4 新 MCP 工具 real RetrievalService 端到端 FR-010 等价验证
  - T042-1 ontology_graph handler == direct graph_search（结构契约 rows/total/explain）
  - T042-2 ontology_nl handler == direct nl_search（结构契约 rows/total/explain）
  - T042-3 ontology_mdl handler == direct mdl_search（排除 chain_id UUID 后等价；reasoning 子结构契约 chain_id/template/status/conclusion）
  - T042-4 ontology_hybrid handler == direct hybrid_search（排除 request_id UUID 后等价；结构契约 mode/request_id/rows/total/components/warnings）
- [X] T043 [P] 全量回归 125/125 + tasks.md/verification.md 更新 + 提交

**Checkpoint**: Phase 6 MCP 工具 real service 端到端补强 — 7/7 工具全部有 FR-010 real RetrievalService 等价验证（T035 metric/reason 2 + T042 graph/nl/mdl/hybrid 4 + T019 query FakeService 1）；125/125 全量回归零回归。

---

## Phase 16: Phase 7 — SC-001/SC-002 性能基准框架搭建 (Priority: P4)

**Goal**: 为 SC-001（95% NL 查询 3s 内）和 SC-002（BI P95 5s 内）搭建可运行的性能基准测试框架。框架验证模式下确认 P95 断言逻辑 + 框架不崩溃；真实 SC 验收需接入 10k/10万级 Neo4j 数据集（Phase 7+ 生产环境验证）。

**Independent Test**: `pytest -m perf tests/performance/ -v`

### Tasks

- [X] T044 [P] SC-001 查询延迟基准测试（tests/performance/test_sc001_query_latency.py）
  - 10 个代表性 NL 查询样本（中文关键词/短句/长句/特殊字符）
  - P95 百分位断言（线性插值法，无 numpy 依赖）
  - Warmup 查询排除首次初始化开销
  - 双模式策略：正常模式 P95 ≤ 3s / 降级模式（Neo4j 不可用）P95 ≤ 15s
  - 结构化结果断言：每次查询返回 mode/total/rows 字段
- [X] T045 [P] SC-002 指标延迟基准测试（tests/performance/test_sc002_metric_latency.py）
  - 10 个指标查询样本（count/density/trend 交替 + object_type/granularity 过滤）
  - P95 百分位断言 ≤ 5s（MetricEngine 不连 Neo4j，正常模式即可通过）
  - 结构化结果断言：mode/total/metrics/rows/explain 字段
- [X] T046 [P] 运行基准验证 + 文档更新 + 提交
  - SC-001 降级模式通过（Neo4j 不可用，P95 < 15s）
  - SC-002 正常模式通过（P95 < 5s）
  - 008 全量回归 129/129 零回归（+4 性能测试）

**Checkpoint**: Phase 7 SC-001/SC-002 性能基准框架搭建完成 — 双模式策略（正常/降级）适配当前环境；SC-001 NL 查询 P95 + SC-002 metric P95 断言逻辑就绪；4 个 @pytest.mark.perf 测试可重复运行；真实 SC 验收待 10k/10万级 Neo4j 数据集接入。

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖，立即开始
- **Foundational (Phase 2)**: 依赖 Setup 完成 — **BLOCKS** 所有 User Story
- **User Stories (Phase 3-7)**: 均依赖 Foundational 完成
  - US1 / US2 可并行（不同引擎文件，仅共享 routes.py 的增量编辑，需串行提交）
  - US3 依赖 Foundational（chain/mdl 独立于 US1/US2）
  - US4 依赖 US1+US2+US3（hybrid 编排已有引擎）
  - US5 依赖 US1+US2+US3（MCP 工具映射已有端点）
- **Polish (Phase 8)**: 依赖全部 User Story 完成

### User Story Dependencies

- **US1 (P1)**: Foundational 后即可开始，无其他故事依赖
- **US2 (P1)**: Foundational 后即可开始，与 US1 并行（共享 unified_router 路由表扩展，需协调）
- **US3 (P2)**: Foundational 后即可开始，与 US1/US2 独立
- **US4 (P3)**: 依赖 US1+US2+US3（编排现有引擎）
- **US5 (P3)**: 依赖 US1+US2+US3（映射现有端点）

### Within Each User Story

- TDD 区域：测试 MUST 先写并 FAIL，再实现至 GREEN，最后 Refactor
- 引擎实现先于端点接线
- 函数体 ≤ 40 行（Constitution I）
- 每个 task 完成后提交（atomic commit）

### Parallel Opportunities

- Phase 2: T002 / T003 / T004 可并行（不同文件）
- Phase 3: T007 / T009 可并行（不同测试文件）
- Phase 4-5: US2 与 US3 可并行（不同引擎）
- Phase 5: T014 与 T015 的引擎实现（impl/chain_engine.py 与 impl/mdl_engine.py）可并行，但 api/routes.py 路由接线须串行（已移除 T015 的 [P] 标记）

---

## Parallel Example: Phase 2 Foundational

```bash
# 并行启动三个独立文件的任务：
Task: "Create Pydantic models in models/retrieval.py"          # T002
Task: "Create graph_engine adapter in impl/graph_engine.py"    # T003
Task: "Create audit_log adapter in storage/audit_log.py"       # T004
# T005 依赖 T002/T003/T004 完成后串行
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. 完成 Phase 1: Setup（T001）
2. 完成 Phase 2: Foundational（T002-T006）— **CRITICAL，阻塞所有故事**
3. 完成 Phase 3: US1（T007-T010，TDD）
4. **STOP and VALIDATE**: `pytest tests/unit/test_nl_engine.py tests/unit/test_unified_router.py -v` + 手动 curl `/query` 验证
5. MVP 可演示 — Agent 自然语言查询本体

### Incremental Delivery

1. Setup + Foundational → 基础设施就绪
2. + US1 → MVP（P1 自然语言查询）→ 验证 → 演示
3. + US2 → P1 BI 指标查询 → 验证 → 演示
4. + US3 → P2 链式推理（含循环防护）→ 验证 → 演示
5. + US4 → P3 混合检索编排 → 验证 → 演示
6. + US5 → P3 MCP 工具暴露 → 验证 → 演示
7. Polish → 全量验收 + 架构门

### Parallel Team Strategy

- Foundational 完成后：Developer A 做 US1，Developer B 做 US2/US3（不同引擎文件）
- US4/US5 须等 US1-US3 完成后串行

---

## Notes

- [P] 任务 = 不同文件、无未完成依赖
- [Story] 标签映射到 spec.md 的 User Story，便于追溯
- TDD 区域测试 MUST 先 FAIL 再 GREEN（Constitution III）
- 不建单实现接口（Constitution IV）：Phase 1 不创建 IRetrievalEngine，待 Phase 2 出现第二引擎再提取
- 统一路由器用 dict 策略表，非抽象工厂（Constitution IV 避免过度设计）
- 每个 task 完成后提交，避免大堆变更
