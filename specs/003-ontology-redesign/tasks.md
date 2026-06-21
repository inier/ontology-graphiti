# Tasks: 本体设计器彻底重构

**Input**: Design documents from `specs/003-ontology-redesign/`
**Prerequisites**: plan.md (required), spec.md (required for user stories)

## Task Format

```
[ID] [markers] [Story] Description
```

**Markers**:
- **[P]**: Can run in parallel (different files, no dependencies)
- **[TDD]**: Must follow RED-GREEN-REFACTOR (write test → fail → implement → pass → refactor)
- **[REVIEW]**: Requires code review before proceeding to next task
- **[SUBAGENT]**: Can be delegated to a subagent for parallel execution

**Story labels**: `[US1]`, `[US2]`, etc. map tasks to user stories for traceability.

## Path Conventions

- **Backend**: `odap/biz/core/ontology/`, `odap/biz/management/business/`
- **Frontend**: `frontend/src/modules/ontology/`, `frontend/src/modules/business/`
- **Tests**: `tests/unit/`
- **Web entry**: `odap/web/app.py`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 新增依赖、创建模块目录结构、统一 Schema 层模型定义

- [x] T001 Add sqlalchemy>=2.0.0, psycopg2-binary>=2.9.0, pymysql>=1.1.0 to requirements.txt
- [x] T002 Create ontology_api module structure: odap/biz/core/ontology/ontology_api/__init__.py, api/__init__.py, services/__init__.py, storage/__init__.py
- [x] T003 [P] Create extraction module structure: odap/biz/core/ontology/extraction/__init__.py, api/__init__.py, services/__init__.py, models/__init__.py
- [x] T004 [P] Enhance OMS schemas with missing type definitions (ProcessTypeDefinition, RuleTypeDefinition, FunctionTypeDefinition, IndicatorTypeDefinition) in odap/biz/core/ontology/application/oms/schemas.py
- [x] T005 [P] Create extraction request/response Pydantic models in odap/biz/core/ontology/extraction/models/schemas.py

**Execution notes**: T001 must complete before any SQLAlchemy-dependent code. T004 and T005 can run in parallel as they define different model classes.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 本体 CRUD 存储、Schema 版本管理、统一 API 路由注册——所有 User Story 的前置基础

**CRITICAL**: No user story work can begin until this phase is complete.

- [x] T006 [TDD] Implement SQLiteOntologyStorage with ontologies, ontology_schema_versions, object_type_definitions, link_type_definitions, action_type_definitions, process_type_definitions, rule_type_definitions, function_type_definitions, indicator_type_definitions, database_connections, extraction_sessions tables in odap/biz/core/ontology/ontology_api/storage/sqlite_ontology_storage.py
- [x] T007 [TDD] Implement OntologyService (CRUD + schema version commit/diff/rollback) in odap/biz/core/ontology/ontology_api/services/ontology_service.py
- [x] T008 [P] Implement ObjectTypeDefinition/LinkDefinition/ActionTypeDefinition CRUD in OntologyService (extends T007) in odap/biz/core/ontology/ontology_api/services/ontology_service.py
- [x] T009 [P] Implement business type definition CRUD (ProcessType/RuleType/FunctionType/IndicatorType) in OntologyService in odap/biz/core/ontology/ontology_api/services/ontology_service.py
- [x] T010 Implement unified ontology API routes (CRUD + version + object-types + graph) in odap/biz/core/ontology/ontology_api/api/routes.py
- [x] T011 Register ontology_api routes in odap/web/app.py with include_router()
- [x] T012 [REVIEW] Add schema_type_id column to business_processes, business_rules, business_logics, business_indicators tables via migration in odap/biz/management/business/storage/sqlite_storage.py
- [x] T013 [P] Add business type definition query endpoints (list schema types for dropdown) to existing business routes in odap/biz/management/business/api/routes.py

**Execution notes**: T006-T009 follow TDD — write tests first in tests/unit/test_ontology_storage.py and tests/unit/test_ontology_service.py. T012 is a REVIEW gate — verify migration is backward-compatible before proceeding.

**Checkpoint**: Foundation ready. Verify: (1) ontology CRUD works via API, (2) schema version commit/diff works, (3) business tables have schema_type_id column, (4) type definition list API returns data. Get human approval before starting user stories.

---

## Phase 3: User Story 1 - 手工定义本体结构 (Priority: P1) MVP

**Goal**: 用户可手工定义对象类型、关系类型、动作类型、业务过程、逻辑函数、规则和指标，且结构与子菜单页面共享数据源
**Independent Test**: 在设计器中创建本体→添加各类型定义→在子菜单页面验证结构可见→创建实例数据

### Implementation for User Story 1

- [x] T014 [US1] Create OntologySelector component (Modal with ontology list + create new) in frontend/src/modules/ontology/components/OntologySelector.tsx
- [x] T015 [US1] Create DesignMethodSelector component (3 design method cards) in frontend/src/modules/ontology/components/DesignMethodSelector.tsx
- [x] T016 [US1] Refactor OntologyDesignerPage to integrate OntologySelector + DesignMethodSelector + remove hardcoded documentId='default' in frontend/src/modules/ontology/pages/OntologyDesignerPage.tsx
- [x] T017 [P] [US1] Add ontology CRUD + object-types + type-definitions API methods to ontologyApi.ts in frontend/src/modules/ontology/services/ontologyApi.ts
- [x] T018 [P] [US1] Refactor ontologyStore to support ontology selection, type definition CRUD, and schema version state in frontend/src/modules/ontology/stores/ontologyStore.ts
- [x] T019 [US1] Implement ObjectTypeDefinition editor (create/edit/delete with properties, links, actions) in frontend/src/modules/ontology/pages/OntologyDesignerPage.tsx
- [x] T020 [P] [US1] Implement LinkTypeDefinition editor (source/target type selector, cardinality, link_type) as sub-component in frontend/src/modules/ontology/pages/OntologyDesignerPage.tsx
- [x] T021 [P] [US1] Implement ActionTypeDefinition editor (name, target type, parameters) as sub-component in frontend/src/modules/ontology/pages/OntologyDesignerPage.tsx
- [x] T022 [US1] Implement business type definition editors (ProcessType/RuleType/FunctionType/IndicatorType) as tabs in OntologyDesignerPage in frontend/src/modules/ontology/pages/OntologyDesignerPage.tsx
- [x] T023 [US1] Update frontend business types.ts to add ontology_id, version_id, schema_type_id fields in frontend/src/modules/business/types.ts
- [x] T024 [US1] Update businessApi.ts to add schema type definition list endpoints for dropdown population in frontend/src/modules/business/services/businessApi.ts
- [x] T025 [US1] Update business pages (Process/Rule/Logic/Indicator) to populate schema_type_id dropdown from type definitions and link instances to schema types in frontend/src/modules/business/pages/

**Execution notes**: T014-T015 can start in parallel with backend (T017 uses mock data initially). T019-T022 are the core editing UI tasks. T023-T025 connect the business sub-menus to the unified type system.

**Checkpoint**: User Story 1 fully functional. Verify: create ontology → add object types → add business process type → switch to business sub-menu → see type definition → create instance. Get human approval.

---

## Phase 4: User Story 4 - 本体版本管理 (Priority: P1)

**Goal**: 用户可查看版本历史、对比差异、回滚到历史版本、手动提交版本快照
**Independent Test**: 创建本体→多次修改→提交版本→查看历史→对比差异→回滚→验证数据恢复

### Implementation for User Story 4

- [x] T026 [US4] Implement schema version history panel (list versions with changelog, timestamps) in frontend/src/modules/ontology/components/VersionHistoryPanel.tsx
- [x] T027 [US4] Implement version diff view (compare two schema snapshots, highlight added/modified/deleted type definitions) in frontend/src/modules/ontology/components/VersionDiffView.tsx
- [x] T028 [US4] Implement version commit action (button + changelog input dialog) in OntologyDesignerPage toolbar in frontend/src/modules/ontology/pages/OntologyDesignerPage.tsx
- [x] T029 [US4] Implement version rollback action (select version → confirm dialog → restore schema) in frontend/src/modules/ontology/pages/OntologyDesignerPage.tsx
- [x] T030 [US4] Add version API methods (list, commit, diff, rollback) to ontologyApi.ts in frontend/src/modules/ontology/services/ontologyApi.ts

**Execution notes**: T026-T027 can run in parallel. T028-T029 depend on T030 for API calls. Backend version management already implemented in Phase 2 (T007).

**Checkpoint**: User Stories 1 AND 4 both work independently. Verify: create ontology → add types → commit version → add more types → commit → view history → diff → rollback → verify data restored. Get human approval.

---

## Phase 5: User Story 5 - 本体图谱展示与交互 (Priority: P1)

**Goal**: 图谱可视化展示对象类型和关系类型，支持缩放/平移/节点编辑/边编辑，恢复语义图谱菜单
**Independent Test**: 创建含多个对象类型和关系类型的本体→图谱正确渲染→缩放平移流畅→点击节点/边显示详情→编辑生效

### Implementation for User Story 5

- [x] T031 [US5] Implement graph data adapter (ObjectTypeDefinition→GraphNode, LinkTypeDefinition→GraphEdge) in frontend/src/modules/ontology/services/ontologyApi.ts
- [x] T032 [US5] Create NodeEdgeEditor component (side panel with type definition details + edit form) in frontend/src/modules/ontology/components/NodeEdgeEditor.tsx
- [x] T033 [US5] Enhance GraphCanvas onNodeClick/onEdgeClick callbacks to open NodeEdgeEditor panel in frontend/src/modules/ontology/components/GraphCanvas.tsx
- [x] T034 [US5] Integrate graph view as tab in OntologyDesignerPage with live data from type definitions in frontend/src/modules/ontology/pages/OntologyDesignerPage.tsx
- [x] T035 [US5] Restore semantic graph menu entry in AppLayout.tsx sidebar + add /ontology/graph route in AppRoutes.tsx in frontend/src/modules/shared/components/AppLayout.tsx and frontend/src/AppRoutes.tsx
- [x] T036 [P] [US5] Create OntologyGraphPage (standalone graph page using GraphCanvas) in frontend/src/modules/ontology/pages/OntologyGraphPage.tsx

**Execution notes**: T031-T032 can run in parallel. T033 depends on T032. T035-T036 can run in parallel with T033-T034.

**Checkpoint**: User Stories 1, 4, AND 5 all work independently. Verify: graph renders → zoom/pan works → click node shows editor → edit saves → semantic graph menu visible → standalone graph page works. Get human approval.

---

## Phase 6: User Story 2 - 通过外部数据库抽取本体 (Priority: P2)

**Goal**: 用户可配置外部数据库连接，系统读取 Schema 并映射为本体定义，预览编辑后确认导入
**Independent Test**: 连接 SQLite 示例数据库→执行抽取→验证对象类型/关系类型/动作类型映射正确

### Implementation for User Story 2

- [x] T037 [TDD] [US2] Implement DatabaseSchemaExtractor (SQLAlchemy Inspector + mapping rules) in odap/biz/core/ontology/design/ingestion_split/db_schema_ingester.py
- [x] T038 [US2] Implement ExtractionService (session lifecycle + conflict detection + merge strategy) in odap/biz/core/ontology/extraction/services/extraction_service.py
- [x] T039 [US2] Implement extraction API routes (test-connection, extract/database, extract/natural-language, sessions, confirm) in odap/biz/core/ontology/extraction/api/routes.py
- [x] T040 [US2] Register extraction routes in odap/web/app.py with include_router()
- [x] T041 [P] [US2] Create DatabaseExtractor component (connection form + test button + table filter + start extraction) in frontend/src/modules/ontology/components/DatabaseExtractor.tsx
- [x] T042 [P] [US2] Create ExtractionPreview component (editable type definition list with add/modify/delete before confirm) in frontend/src/modules/ontology/components/ExtractionPreview.tsx
- [x] T043 [US2] Integrate DatabaseExtractor + ExtractionPreview into OntologyDesignerPage design method flow in frontend/src/modules/ontology/pages/OntologyDesignerPage.tsx
- [x] T044 [US2] Add extraction API methods to ontologyApi.ts in frontend/src/modules/ontology/services/ontologyApi.ts

**Execution notes**: T037 follows TDD — write tests in tests/unit/test_db_schema_ingester.py first. T041-T042 can run in parallel with T037-T040 (use mock API initially). T043 integrates everything.

**Checkpoint**: User Stories 1, 4, 5, AND 2 all work. Verify: connect SQLite DB → extract schema → preview → edit → confirm → types appear in designer and graph. Get human approval.

---

## Phase 7: User Story 3 - 自然语言输入提取本体 (Priority: P2)

**Goal**: 用户输入自然语言描述，系统提取对象类型/关系类型/规则/动作类型，支持联网检索补充
**Independent Test**: 输入"电商系统需要管理用户、商品和订单"→验证提取的对象类型/关系类型/规则合理

### Implementation for User Story 3

- [x] T045 [TDD] [US3] Implement SchemaLevelExtractor (LLM + ONTOLOGY_SCHEMA_EXTRACT_PROMPT + JSON parsing) in odap/biz/core/ontology/extraction/services/schema_extractor.py
- [x] T046 [US3] Implement web search integration for NL extraction (reuse NewsIngester search chain with user-controlled auto_search flag) in odap/biz/core/ontology/extraction/services/schema_extractor.py
- [x] T047 [US3] Add NL extraction endpoint to extraction API routes in odap/biz/core/ontology/extraction/api/routes.py
- [x] T048 [P] [US3] Create NLExtractor component (text input + auto_search toggle + start extraction) in frontend/src/modules/ontology/components/NLExtractor.tsx
- [x] T049 [US3] Integrate NLExtractor into OntologyDesignerPage design method flow (reuse ExtractionPreview from US2) in frontend/src/modules/ontology/pages/OntologyDesignerPage.tsx
- [x] T050 [US3] Add NL extraction API methods to ontologyApi.ts in frontend/src/modules/ontology/services/ontologyApi.ts

**Execution notes**: T045 follows TDD — write tests in tests/unit/test_schema_extractor.py first. T048 can run in parallel with T045-T047. T049 reuses ExtractionPreview from US2 (T042).

**Checkpoint**: All 5 user stories work. Verify: input NL text → extract types → preview → edit → confirm → types appear in designer. Get human approval.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 边界情况处理、安全加固、测试补全

- [x] T051 [P] Add conflict detection and merge UI for extraction results that overlap with existing type definitions in frontend/src/modules/ontology/components/ExtractionPreview.tsx
- [x] T052 [P] Add empty state guidance for graph view (when no object types defined) in frontend/src/modules/ontology/components/GraphCanvas.tsx
- [x] T053 [P] Add database connection password encryption (AES-256) in odap/biz/core/ontology/ontology_api/storage/sqlite_ontology_storage.py
- [x] T054 [P] Add route exception handling tests for all new routes (except HTTPException: raise pattern) in tests/unit/test_ontology_api_routes.py
- [x] T055 Run full test suite (pytest tests/unit/ -v) — all tests must pass
- [x] T056 Run frontend type check (cd frontend && npm run typecheck) — no errors

**Execution notes**: T051-T054 can all run in parallel. T055-T056 are final validation gates.

---

## Phase 9: AI 辅助基础设施 (US6 前置)

**Purpose**: 本地规则引擎、AI 助手后端模块、AG-UI 生产化——所有 AI 辅助 User Story 的前置基础

**CRITICAL**: No AI user story work can begin until this phase is complete.

- [x] T057 [TDD] [US6] Implement TypeInferenceEngine (exact match + prefix/suffix/contains + 50+ mapping table) in odap/biz/core/ontology/assistant/rules/type_inference.py
- [x] T058 [TDD] [P] [US6] Implement ConstraintSuggester (property name pattern → constraint mapping) in odap/biz/core/ontology/assistant/rules/constraint_suggester.py
- [x] T059 [TDD] [US6] Implement SQLiteAssistantStorage (ai_suggestions + ai_assistant_sessions tables) in odap/biz/core/ontology/assistant/storage/sqlite_assistant_storage.py
- [x] T060 [TDD] [US6] Implement SuggestionService (lifecycle: pending→accepted/rejected, audit log integration) in odap/biz/core/ontology/assistant/services/suggestion_service.py
- [x] T061 [TDD] [US6] Implement AssistantService (AG-UI protocol: run/resume, tool_call dispatch, HITL confirm flow) in odap/biz/core/ontology/assistant/services/assistant_service.py
- [x] T062 [US6] Implement 5 AG-UI tool_call handlers (add_property, add_link_type, add_action_type, suggest_properties, validate_constraint) in odap/biz/core/ontology/assistant/tools/
- [x] T063 [US6] Implement AI assistant API routes (AG-UI run/resume, infer-type, suggest-constraints, suggestions CRUD, health) in odap/biz/core/ontology/assistant/api/routes.py
- [x] T064 [US6] Register assistant routes in odap/web/app.py with include_router()
- [x] T065 [US6] Implement AI assistant Pydantic models (AISuggestion, AIAssistantSession, request/response schemas) in odap/biz/core/ontology/assistant/models/schemas.py
- [x] T066 [P] [US6] Add OPA policy for AI assistant endpoints (role-based access control) in odap/infra/opa/policies/ontology_assistant.rego
- [x] T067 [US6] AG-UI production hardening: ErrorBoundary, reconnect (2 retries), heartbeat 120s, namespace isolation in frontend/src/modules/qa/agui/AGUIProvider.tsx

**Execution notes**: T057-T058 can run in parallel (different rule engines). T059 must complete before T060. T061 depends on T060 and T062. T063 depends on T061 and T065. T066-T067 can run in parallel with backend tasks.

**Checkpoint**: AI infrastructure ready. Verify: (1) type inference accuracy 100% on 50 test property names, (2) AG-UI run/resume flow works end-to-end, (3) suggestions CRUD works, (4) OPA policy blocks unauthorized access. Get human approval.

---

## Phase 10: User Story 6 & 7 - AI 辅助配置对象类型/关系类型/动作类型 (Priority: P1)

**Goal**: 用户可通过行内补全、对话式、浮动面板三种方式获得 AI 辅助，加速对象类型属性、关系类型、动作类型的配置
**Independent Test**: 创建"用户"对象类型→输入"email"触发行内补全→对话框输入"添加手机号"→点击AI按钮获取属性推荐→创建"订单"类型→AI建议"下单"关系→输入"订单可以被取消"创建动作

### Implementation for User Story 6 & 7

- [x] T068 [US6] Create useTypeInference hook (debounce 300ms, call /api/ontology-assistant/infer-type, return type+constraints) in frontend/src/modules/ontology/hooks/useTypeInference.ts
- [x] T069 [P] [US6] Create useOntologyAssistant hook (AG-UI protocol client for ontology designer, SSE stream, tool_call handling, HITL confirm) in frontend/src/modules/ontology/hooks/useOntologyAssistant.ts
- [x] T070 [US6] Create AIInlineCompletion component (dropdown below property name input, shows inferred type + constraints, Tab/Enter to accept) in frontend/src/modules/ontology/components/AIInlineCompletion.tsx
- [x] T071 [P] [US6] Create AIChatInput component (embedded chat input beside property list, sends natural language commands, shows AI responses with pending suggestions) in frontend/src/modules/ontology/components/AIChatInput.tsx
- [x] T072 [P] [US6] Create AIAssistantPanel component (floating panel with batch operations, suggest properties for type, completeness check) in frontend/src/modules/ontology/components/AIAssistantPanel.tsx
- [x] T073 [P] [US6] Create AISuggestionList component (list of pending/accepted/rejected suggestions with accept/reject/edit actions) in frontend/src/modules/ontology/components/AISuggestionList.tsx
- [x] T074 [US6] Integrate AIInlineCompletion into ObjectTypeEditor property name input in frontend/src/modules/ontology/pages/OntologyDesignerPage.tsx
- [x] T075 [US6] Integrate AIChatInput + AISuggestionList into ObjectTypeEditor property list area in frontend/src/modules/ontology/pages/OntologyDesignerPage.tsx
- [x] T076 [US6] Integrate AIAssistantPanel as floating panel triggered by AI button in OntologyDesignerPage toolbar in frontend/src/modules/ontology/pages/OntologyDesignerPage.tsx
- [x] T077 [US6] Add AI assistant API methods (run, resume, infer-type, suggest-constraints, suggestions CRUD, health) to frontend/src/modules/ontology/services/ontologyApi.ts
- [x] T078 [US6] Add AI suggestion state management to ontologyStore (pending suggestions, accept/reject actions, AI availability status) in frontend/src/modules/ontology/stores/ontologyStore.ts
- [x] T079 [US7] Extend AIAssistantPanel with link type suggestions (when object types A and B exist, suggest relationships) in frontend/src/modules/ontology/components/AIAssistantPanel.tsx
- [x] T080 [US7] Extend AIAssistantPanel with action type suggestions (suggest actions for object types based on existing relationships) in frontend/src/modules/ontology/components/AIAssistantPanel.tsx
- [x] T081 [US7] Integrate AIChatInput into LinkTypeEditor and ActionTypeEditor tabs for natural language creation in frontend/src/modules/ontology/pages/OntologyDesignerPage.tsx
- [x] T082 [US7] Add conflict detection for AI-suggested links/actions that overlap with existing definitions in frontend/src/modules/ontology/components/AIAssistantPanel.tsx

**Execution notes**: T068-T069 can run in parallel (different hooks). T070-T073 can run in parallel (different components). T074-T076 depend on T070-T073. T077-T078 can run in parallel with component work. T079-T082 all modify AIAssistantPanel.tsx and must be executed sequentially or merged into a single commit.

**Checkpoint**: US6 & US7 fully functional. Verify: (1) type "email" → inline completion suggests STRING + email constraint, (2) chat "添加手机号" → property added to list, (3) AI button → suggests phone/address for User type, (4) AI suggests "下单" link between User and Order, (5) chat "订单可以被取消" → action created. Get human approval.

---

## Phase 11: User Story 8 - AI 模式发现与扩展建议 (Priority: P2)

**Goal**: AI 主动分析本体结构，发现共性属性模式、关系模式、完整性问题，提供扩展建议
**Independent Test**: 创建多个对象类型→AI发现共性属性→建议抽象为基类→发现外键属性→建议创建关系→发现缺失审计字段→建议补充

### Implementation for User Story 8

- [x] T083 [TDD] [US8] Implement pattern_discovery tool_call handler (common attributes detection, foreign key pattern detection) in odap/biz/core/ontology/assistant/tools/pattern_discovery.py
- [x] T084 [TDD] [P] [US8] Implement completeness_check tool_call handler (orphan types, missing audit fields, missing status) in odap/biz/core/ontology/assistant/tools/completeness_check.py
- [x] T085 [US8] Add pattern_discovery and completeness_check to AssistantService tool registry in odap/biz/core/ontology/assistant/services/assistant_service.py
- [x] T086 [US8] Extend AIAssistantPanel with "AI 分析" button that triggers pattern discovery + completeness check in frontend/src/modules/ontology/components/AIAssistantPanel.tsx
- [x] T087 [US8] Add pattern discovery result visualization (common attributes → suggest base type, foreign key → suggest relationship) in frontend/src/modules/ontology/components/AIAssistantPanel.tsx
- [x] T088 [US8] Add completeness check result visualization (missing fields, orphan types, improvement suggestions) in frontend/src/modules/ontology/components/AIAssistantPanel.tsx

**Execution notes**: T083-T084 can run in parallel (different tool handlers). T086-T088 extend existing AIAssistantPanel.

**Checkpoint**: US8 fully functional. Verify: (1) create User/Product/Order with created_at → AI suggests base type, (2) Order has order_id/product_id → AI suggests relationships, (3) Order missing status → AI suggests adding. Get human approval.

---

## Phase 12: AI 辅助 Polish & Cross-Cutting Concerns

**Purpose**: AI 辅助功能的边界情况处理、安全加固、测试补全

- [ ] T089 [P] Add AI suggestion naming convention validation (snake_case, no reserved words) in backend suggestion acceptance flow in odap/biz/core/ontology/assistant/services/suggestion_service.py
- [ ] T090 [P] Add AI service degradation UI (show "AI 助手暂不可用" banner when health check fails, disable AI features but keep manual editing) in frontend/src/modules/ontology/components/AIAssistantPanel.tsx
- [ ] T091 [P] Add AI suggestion audit log integration (log accept/reject with reason to unified_audit.py) in odap/biz/core/ontology/assistant/services/suggestion_service.py
- [ ] T092 [P] Add AI assistant route exception handling tests (except HTTPException: raise pattern) in tests/unit/test_ontology_assistant_routes.py
- [ ] T093 [P] Add type inference accuracy test (40+ property name groups covering 90+ variants, verify 100% accuracy for rule engine) in tests/unit/test_type_inference.py
- [ ] T094 [P] Add constraint suggester test (10+ property name patterns, verify correct constraint output) in tests/unit/test_constraint_suggester.py
- [ ] T095 Run full test suite (pytest tests/unit/ -v) — all tests must pass
- [ ] T096 Run frontend type check (cd frontend && npm run typecheck) — no errors

**Execution notes**: T089-T094 can all run in parallel. T095-T096 are final validation gates.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational — MVP core
- **US4 (Phase 4)**: Depends on Foundational — can start in parallel with US1 (backend version mgmt already done in Phase 2)
- **US5 (Phase 5)**: Depends on US1 (needs type definitions to render graph)
- **US2 (Phase 6)**: Depends on US1 (extraction results write to type definitions)
- **US3 (Phase 7)**: Depends on US2 (reuses ExtractionPreview component)
- **Polish (Phase 8)**: Depends on US1-US5 being complete
- **AI Infrastructure (Phase 9)**: Depends on Phase 2 — BLOCKS US6/US7/US8
- **US6 & US7 (Phase 10)**: Depends on Phase 9 (AI infrastructure) + Phase 3 (object/link/action type editors exist)
- **US8 (Phase 11)**: Depends on Phase 10 (pattern discovery needs existing AI assistant framework)
- **AI Polish (Phase 12)**: Depends on all AI user stories being complete

### Within Each User Story

1. Backend storage → service → routes (strict order)
2. Frontend API methods → components → page integration (strict order)
3. [REVIEW] tasks pause for human review
4. Story complete before moving to next priority

### Parallel Opportunities

- T004 + T005 (different model files)
- T008 + T009 (different service methods)
- T014 + T015 + T017 (different frontend files)
- T019 + T020 + T021 (different editor sub-components)
- T026 + T027 (different version UI components)
- T031 + T032 (different frontend files)
- T035 + T036 (menu vs page)
- T037 backend + T041/T042 frontend (different stacks)
- T045 backend + T048 frontend (different stacks)
- T051 + T052 + T053 + T054 (all independent polish tasks)
- T057 + T058 (different rule engines)
- T066 + T067 (OPA policy vs AG-UI hardening)
- T068 + T069 (different hooks)
- T070 + T071 + T072 + T073 (different AI components)
- T077 + T078 (API methods vs store)
- T083 + T084 (different tool handlers)
- T089 + T090 + T091 + T092 + T093 + T094 (all independent AI polish tasks)

---

## Superpowers Execution

### Execution Discipline by Marker

- **[TDD]**: Follow RED-GREEN-REFACTOR. Write test → run (must fail) → implement → run (must pass) → refactor if needed.
- **[SUBAGENT]**: Dispatch to a subagent for parallel execution.
- **[REVIEW]**: Pause execution. Present completed work to user. Wait for explicit approval before continuing.
- **[P]**: Launch parallel tasks where possible using the Task tool.

### Checkpoint Protocol

At every phase boundary:
1. Summarize what was completed in this phase
2. Run applicable tests
3. Report test results
4. Ask user: "Phase [N] complete. Proceed to Phase [N+1]?"
5. Only continue after explicit user approval

---

## Notes

- [P] tasks = different files, no dependencies
- [TDD] tasks = strict RED-GREEN-REFACTOR discipline
- [REVIEW] tasks = human review gate
- [Story] label maps task to specific user story for traceability
- Commit after each task or logical group
- Stop at any checkpoint to validate independently
