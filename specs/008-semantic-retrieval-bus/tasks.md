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

- [ ] T018 [US5] Register ontology_query / ontology_reason / ontology_metric MCP tools (mirror existing openharness_bridge 注册模式 per ADR-026) in apps/api/odap/biz/core/ontology/mcp/semantic_retrieval_tools.py
- [ ] T019 [US5] Write MCP integration test (工具调用结果与直接 REST 调用一致 per FR-010) in tests/integration/test_semantic_retrieval_mcp.py

**Checkpoint**: US5 可用 — MCP 工具集对外暴露

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 跨故事的集成验证与质量门

- [ ] T020 Write integration tests for all routes (强制认证 + workspace 隔离 FR-012 + 审计不记内容 FR-013 + valid/candidate 默认过滤 FR-011 + page_size≤100 边界) in tests/integration/test_semantic_retrieval_routes.py
- [ ] T021 Run G-7 route exception regression + G-8 Cypher/SQL injection regression (`pytest tests/unit/test_audit_cypher_injection.py tests/unit/test_sql_injection.py -q`) + G-10 full unit suite (`pytest tests/unit/ -q`) and fix any failures (本特性涉及 Cypher 图查询，G-8 MUST)
- [ ] T022 Run architecture-verify gate G-9 + spec consistency check G-3 (对照 specs/008-semantic-retrieval-bus/spec.md 全量验收 5 个 User Story / 16 条 FR / 7 条 SC)

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
