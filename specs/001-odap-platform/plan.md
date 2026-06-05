# Implementation Plan: ODAP 本体驱动分析决策平台

**Branch**: `001-odap-platform` | **Date**: 2026-05-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-odap-platform/spec.md`

## Summary

ODAP（本体驱动分析决策平台）基于 OntoFlow 六层架构，以 Graphiti 双时态知识图谱为核心，提供本体管理、智能体编排、决策推演与模拟仿真能力。平台采用模块化单体架构（FastAPI + React 19），3 阶段交付：P1 基础层（本体+工作空间+数据摄入）→ P2 核心层（Agent+策略+认知+查询）→ P3 增强层（推演+问答+反馈+MCP）。OpenHarness 以进程内集成方式作为 Agent 编排核心，本体拆分为模型层（借鉴 Palantir AIP 核心概念）和管理引擎，存储采用 SQLite+Neo4j+Redis+MinIO 四引擎组合，前端完整重构为 5 级组件体系+移动优先响应式+中英双语 i18n。

## Technical Context

**Language/Version**: Python 3.10+（容器基准 3.10，本地开发兼容 3.10-3.13）, TypeScript 5.x

**Primary Dependencies**: FastAPI, Pydantic v2, React 19, Ant Design 6, OpenHarness (in-process), Graphiti, Neo4j, OPA, Zustand 5, AntV G6 5, @xyflow/react, ECharts 6

**Storage**: SQLite（关系型：工作空间/角色/策略/审计等）+ Neo4j（图谱：本体实例/关系/时序数据）+ Redis（缓存+会话）+ MinIO（对象存储：文档/图片/二进制，新增）

**Testing**: pytest（后端单元/集成/E2E）, vitest + @testing-library/react（前端）

**Target Platform**: Linux server (Docker Compose / Podman Compose)

**Project Type**: Web application（模块化单体）

**Performance Goals**: API P95 < 500ms, QA P95 < 3s, 推演 < 30s, Agent 意图识别 > 90%, OPA 策略热更新 < 30s, Data Health 增量扫描 < 60s/100K 实例

**Constraints**: 移动优先响应式（6 断点）, OpenHarness 独立性（不 fork 核心代码）, 不重复引入存储引擎, 5 级组件体系+组件库可替代性设计, 本体设计采用 Palantir 范式 (Branch&Merge + Action Type + Object View), 本体演化采用 OntoFlow 范式 (goal-driven)

**Scale/Scope**: 37 个 FR (30 原版 + 7 brainstorm 增量), 50+ API 路由 (含新增 35+ 端点), 13+ 前端页面模块, 7 大业务领域

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 状态 | 说明 |
|------|------|------|
| I. 简单 | ✅ 通过 | 每个 FR 有明确边界，不预先设计未需求的功能；函数体 > 40 行拆分（CI 守卫 R-P3-001 生效）；命名语义明确 |
| II. 可维护 | ⚠️ 需注意 | 模块化单体架构，领域模块独立 routes/services/impl/storage；配置集中管理；前端统一 apiClient **尚未完全落地**（SkillManager.tsx、knowledgeStore.ts 存在绕过 apiClient 的调用，需在 Phase 3 前修复） |
| III. 测试优先 | ✅ 通过 | 测试金字塔 80/15/5，质量门禁（覆盖率 > 80%，Lint 0 error，类型检查 0 error）；Bug 修复先写复现测试；新增模块必须同步新增测试（AGENTS.md 规则 9） |
| IV. 避免过度设计 | ✅ 通过 | 借鉴 Palantir AIP 核心概念（Object Type/Property/Action/Rule），不严格对齐完整体系；仅实现当前 FR 需要的子集；Phase 4 仅引入 Branch&Merge/Action Type/Object View 等高价值子集，不引入 Palantir 完整功能集 |
| **V. SDD 质量门 (v2.1.0, BMAD 2026-06-05)** | ✅ 通过 | G-1..G-12 已纳入 constitution v2.1.0 并由 [test_constitution_compliance.py](file:///e:/DEMO/AI/ontology-graphiti/tests/unit/test_constitution_compliance.py) 验证 |

**复杂度跟踪**:

| 违规项 | 为何需要 | 被拒绝的更简方案及原因 |
|--------|----------|----------------------|
| 5 级组件体系 | spec 明确要求全项目统一组件库+可替代性设计 | 3 级组件体系无法满足可替代性隔离层要求，L4 模板层和 L5 页面层是可替代性设计的关键；**但当前仅有一个 AntDesignAdapter 实现，隔离层在出现第二个适配器前保持轻量** |
| MinIO 对象存储 | FR-004 多模态数据接入需要非结构化存储 | SQLite BLOB 存储大文件性能差且不符合"不重复引入"原则（需独立存储引擎） |
| 前端统一 apiClient | 宪法 II 要求前端 API 调用 MUST 通过统一 API 客户端 | 当前部分组件绕过 apiClient 直接 fetch，需逐步迁移 |

## Project Structure

### Documentation (this feature)

```text
specs/001-odap-platform/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── README.md        #   API 契约索引（21 个模块，320+ 端点）
├── checklists/
│   └── requirements.md  #   需求检查清单
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
ontology-graphiti/
├── odap/
│   ├── biz/
│   │   ├── core/
│   │   │   ├── ontology/
│   │   │   │   ├── model/
│   │   │   │   │   ├── api/
│   │   │   │   │   │   ├── routes.py
│   │   │   │   │   │   └── schemas.py
│   │   │   │   │   ├── models/
│   │   │   │   │   │   ├── entity_type.py
│   │   │   │   │   │   ├── property.py
│   │   │   │   │   │   ├── relation.py
│   │   │   │   │   │   ├── constraint.py
│   │   │   │   │   │   └── ontology_document.py
│   │   │   │   │   ├── interfaces/
│   │   │   │   │   │   └── model_repository.py
│   │   │   │   │   ├── impl/
│   │   │   │   │   │   └── model_repository_impl.py
│   │   │   │   │   ├── services/
│   │   │   │   │   │   └── model_service.py
│   │   │   │   │   └── storage/
│   │   │   │   │       ├── __init__.py
│   │   │   │   │       └── sqlite_model_storage.py
│   │   │   │   ├── engine/
│   │   │   │   │   ├── api/
│   │   │   │   │   │   ├── routes.py
│   │   │   │   │   │   └── schemas.py
│   │   │   │   │   ├── models/
│   │   │   │   │   │   ├── version.py
│   │   │   │   │   │   ├── audit.py
│   │   │   │   │   │   └── validation.py
│   │   │   │   │   ├── interfaces/
│   │   │   │   │   │   ├── version_manager.py
│   │   │   │   │   │   ├── audit_recorder.py
│   │   │   │   │   │   └── validation_engine.py
│   │   │   │   │   ├── impl/
│   │   │   │   │   │   ├── version_manager_impl.py
│   │   │   │   │   │   ├── audit_recorder_impl.py
│   │   │   │   │   │   └── validation_engine_impl.py
│   │   │   │   │   ├── services/
│   │   │   │   │   │   └── engine_service.py
│   │   │   │   │   └── storage/
│   │   │   │   │       ├── __init__.py
│   │   │   │   │       └── sqlite_engine_storage.py
│   │   │   │   ├── ingestion/
│   │   │   │   │   ├── api/
│   │   │   │   │   │   ├── routes.py
│   │   │   │   │   │   └── schemas.py
│   │   │   │   │   ├── impl/
│   │   │   │   │   │   ├── pdf_processor.py
│   │   │   │   │   │   ├── word_processor.py
│   │   │   │   │   │   ├── ocr_processor.py
│   │   │   │   │   │   └── batch_importer.py
│   │   │   │   │   ├── services/
│   │   │   │   │   │   └── ingest_service.py
│   │   │   │   │   └── storage/
│   │   │   │   │       ├── __init__.py
│   │   │   │   │       └── sqlite_ingest_storage.py
│   │   │   │   ├── harness/
│   │   │   │   ├── runtime/
│   │   │   │   ├── schema/
│   │   │   │   ├── servitization/
│   │   │   │   ├── abution_graph/
│   │   │   │   ├── team_agent/
│   │   │   │   ├── oms/
│   │   │   │   └── __init__.py
│   │   │   ├── agent/
│   │   │   │   ├── api/
│   │   │   │   │   ├── routes.py
│   │   │   │   │   └── schemas.py
│   │   │   │   ├── models/
│   │   │   │   ├── interfaces/
│   │   │   │   ├── impl/
│   │   │   │   │   ├── swarm_orchestrator.py
│   │   │   │   │   ├── intent_router.py
│   │   │   │   │   └── ooda_loop.py
│   │   │   │   ├── services/
│   │   │   │   ├── storage/
│   │   │   │   └── __init__.py
│   │   │   └── cognition/
│   │   │       ├── api/
│   │   │       ├── models/
│   │   │       ├── interfaces/
│   │   │       ├── impl/
│   │   │       │   ├── intent_recognizer.py
│   │   │       │   ├── knowledge_navigator.py
│   │   │       │   ├── explanation_engine.py
│   │   │       │   └── role_view_manager.py
│   │   │       ├── services/
│   │   │       ├── thought_graph/
│   │   │       └── __init__.py
│   │   ├── decision/
│   │   │   ├── action_service/
│   │   │   ├── decision_pipeline/
│   │   │   ├── decision_recommendation/
│   │   │   │   ├── api/
│   │   │   │   │   ├── routes.py
│   │   │   │   │   └── schemas.py
│   │   │   │   ├── models/
│   │   │   │   ├── impl/
│   │   │   │   │   └── recommendation_engine.py
│   │   │   │   ├── services/
│   │   │   │   └── __init__.py
│   │   │   └── __init__.py
│   │   ├── integration/
│   │   │   ├── openharness_agent/
│   │   │   │   ├── api/
│   │   │   │   └── __init__.py
│   │   │   ├── hook_system/
│   │   │   │   ├── api/
│   │   │   │   ├── models/
│   │   │   │   ├── interfaces/
│   │   │   │   ├── impl/
│   │   │   │   │   └── hook_manager.py
│   │   │   │   ├── services/
│   │   │   │   └── __init__.py
│   │   │   ├── mcp_adapter/
│   │   │   │   ├── api/
│   │   │   │   ├── models/
│   │   │   │   ├── interfaces/
│   │   │   │   ├── impl/
│   │   │   │   │   ├── server_manager.py
│   │   │   │   │   └── connection_pool.py
│   │   │   │   ├── services/
│   │   │   │   └── __init__.py
│   │   │   ├── frontend_compat/
│   │   │   └── __init__.py
│   │   ├── platform/
│   │   │   ├── workspace/
│   │   │   │   ├── api/
│   │   │   │   ├── models/
│   │   │   │   ├── interfaces/
│   │   │   │   ├── impl/
│   │   │   │   ├── services/
│   │   │   │   ├── storage/
│   │   │   │   └── __init__.py
│   │   │   ├── roles/
│   │   │   │   ├── api/
│   │   │   │   ├── models/
│   │   │   │   ├── services/
│   │   │   │   ├── storage/
│   │   │   │   └── __init__.py
│   │   │   ├── skill_system/
│   │   │   │   ├── api/
│   │   │   │   ├── models/
│   │   │   │   ├── interfaces/
│   │   │   │   ├── impl/
│   │   │   │   ├── services/
│   │   │   │   └── __init__.py
│   │   │   ├── session_memory/
│   │   │   │   ├── api/
│   │   │   │   ├── models/
│   │   │   │   ├── impl/
│   │   │   │   │   ├── short_term_memory.py
│   │   │   │   │   ├── working_memory.py
│   │   │   │   │   └── long_term_memory.py
│   │   │   │   ├── services/
│   │   │   │   └── __init__.py
│   │   │   ├── tool_registry/
│   │   │   │   ├── api/
│   │   │   │   ├── models/
│   │   │   │   ├── impl/
│   │   │   │   │   ├── registry.py
│   │   │   │   │   └── semantic_discovery.py
│   │   │   │   ├── services/
│   │   │   │   └── __init__.py
│   │   │   ├── ontology_memory/
│   │   │   └── __init__.py
│   │   ├── data/
│   │   │   ├── qa/
│   │   │   │   ├── api/
│   │   │   │   │   ├── routes.py
│   │   │   │   │   └── schemas.py
│   │   │   │   ├── models/
│   │   │   │   ├── impl/
│   │   │   │   │   ├── qa_engine.py
│   │   │   │   │   ├── temporal_reasoner.py
│   │   │   │   │   └── chart_renderer.py
│   │   │   │   ├── services/
│   │   │   │   └── __init__.py
│   │   │   ├── knowledge_base/
│   │   │   ├── data_warehouse/
│   │   │   ├── perception/
│   │   │   ├── semantic_map/
│   │   │   └── __init__.py
│   │   ├── simulation/
│   │   │   ├── event_simulator/
│   │   │   │   ├── api/
│   │   │   │   ├── models/
│   │   │   │   ├── impl/
│   │   │   │   │   ├── event_generator.py
│   │   │   │   │   ├── timeline_engine.py
│   │   │   │   │   └── scenario_template.py
│   │   │   │   ├── services/
│   │   │   │   └── __init__.py
│   │   │   ├── simulation_sandbox/
│   │   │   │   ├── api/
│   │   │   │   ├── models/
│   │   │   │   ├── impl/
│   │   │   │   │   ├── sandbox_manager.py
│   │   │   │   │   └── parallel_runner.py
│   │   │   │   ├── services/
│   │   │   │   └── __init__.py
│   │   │   ├── simulation_deduction/
│   │   │   ├── feedback/
│   │   │   │   ├── api/
│   │   │   │   ├── models/
│   │   │   │   ├── impl/
│   │   │   │   │   ├── collector.py
│   │   │   │   │   ├── analyzer.py
│   │   │   │   │   └── aggregator.py
│   │   │   │   ├── services/
│   │   │   │   └── __init__.py
│   │   │   ├── visualization/
│   │   │   └── __init__.py
│   │   ├── management/
│   │   │   ├── agent_management/
│   │   │   ├── business/
│   │   │   └── __init__.py
│   │   └── __init__.py
│   ├── infra/
│   │   ├── graph/
│   │   │   ├── graph_service.py
│   │   │   └── __init__.py
│   │   ├── query/
│   │   │   ├── sources/
│   │   │   │   ├── schema_source.py
│   │   │   │   ├── entity_source.py
│   │   │   │   ├── topo_source.py
│   │   │   │   └── temporal_source.py
│   │   │   ├── service.py
│   │   │   ├── parser.py
│   │   │   ├── protocols.py
│   │   │   ├── routes.py
│   │   │   └── __init__.py
│   │   ├── opa/
│   │   │   ├── opa_service.py
│   │   │   ├── routes.py
│   │   │   ├── policies/
│   │   │   ├── bundles/
│   │   │   └── __init__.py
│   │   ├── security/
│   │   │   ├── auth_service.py
│   │   │   ├── auth_routes.py
│   │   │   ├── jwt_service.py
│   │   │   ├── jwt_auth.py
│   │   │   ├── oauth2_providers.py
│   │   │   ├── unified_audit.py
│   │   │   ├── audit_api.py
│   │   │   ├── audit_models.py
│   │   │   ├── security_audit.py
│   │   │   ├── data_classification.py
│   │   │   ├── encryption.py
│   │   │   └── __init__.py
│   │   ├── openharness/
│   │   │   ├── v2_adapter.py
│   │   │   ├── swarm_adapter.py
│   │   │   ├── skill_adapter.py
│   │   │   ├── hook_adapter.py
│   │   │   ├── decision_engine.py
│   │   │   ├── llm_client.py
│   │   │   ├── memory_adapter.py
│   │   │   ├── permission_backend.py
│   │   │   ├── query_guard_hook.py
│   │   │   ├── tool_adapter.py
│   │   │   └── __init__.py
│   │   ├── storage/
│   │   │   ├── minio_client.py
│   │   │   └── __init__.py
│   │   ├── llm/
│   │   ├── data_pipeline/
│   │   │   ├── adapters/
│   │   │   ├── multimodal_processor.py
│   │   │   └── __init__.py
│   │   ├── query/
│   │   ├── middleware/
│   │   ├── monitoring/
│   │   ├── resilience/
│   │   ├── logging/
│   │   ├── config/
│   │   ├── utils/
│   │   ├── events/
│   │   ├── object_service/
│   │   └── __init__.py
│   ├── tools/
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── agent_tools/
│   │   ├── analysis/
│   │   ├── computation/
│   │   ├── intelligence/
│   │   ├── operations/
│   │   ├── planning/
│   │   ├── policy/
│   │   ├── recommendation/
│   │   ├── task_management/
│   │   ├── visualization/
│   │   └── __init__.py
│   ├── web/
│   │   ├── app.py
│   │   ├── api/
│   │   │   └── app.py
│   │   ├── gateway/
│   │   ├── ws/
│   │   │   └── event_bus.py
│   │   └── __init__.py
│   ├── common/
│   │   ├── constants.py
│   │   └── __init__.py
│   └── __init__.py
├── frontend/
│   ├── src/
│   │   ├── modules/
│   │   │   ├── shared/
│   │   │   │   ├── components/
│   │   │   │   │   ├── atoms/
│   │   │   │   │   │   ├── Button.tsx
│   │   │   │   │   │   ├── Input.tsx
│   │   │   │   │   │   ├── Badge.tsx
│   │   │   │   │   │   ├── Tooltip.tsx
│   │   │   │   │   │   └── index.ts
│   │   │   │   │   ├── molecules/
│   │   │   │   │   │   ├── FormField.tsx
│   │   │   │   │   │   ├── SearchBar.tsx
│   │   │   │   │   │   ├── Card.tsx
│   │   │   │   │   │   ├── Modal.tsx
│   │   │   │   │   │   └── index.ts
│   │   │   │   │   ├── organisms/
│   │   │   │   │   │   ├── DataTable.tsx
│   │   │   │   │   │   ├── FormPanel.tsx
│   │   │   │   │   │   ├── GraphView.tsx
│   │   │   │   │   │   ├── ChatPanel.tsx
│   │   │   │   │   │   └── index.ts
│   │   │   │   │   ├── templates/
│   │   │   │   │   │   ├── MasterDetail.tsx
│   │   │   │   │   │   ├── SplitView.tsx
│   │   │   │   │   │   ├── FullScreen.tsx
│   │   │   │   │   │   └── index.ts
│   │   │   │   │   └── adapter/
│   │   │   │   │       ├── UIAdapter.ts
│   │   │   │   │       ├── AntDesignAdapter.ts
│   │   │   │   │       └── index.ts
│   │   │   │   ├── locales/
│   │   │   │   │   ├── zh-CN/
│   │   │   │   │   │   ├── common.json
│   │   │   │   │   │   └── shared.json
│   │   │   │   │   └── en-US/
│   │   │   │   │       ├── common.json
│   │   │   │   │       └── shared.json
│   │   │   │   ├── pages/
│   │   │   │   │   └── LoginPage.tsx
│   │   │   │   ├── services/
│   │   │   │   │   ├── apiClient.ts
│   │   │   │   │   └── api.ts
│   │   │   │   ├── stores/
│   │   │   │   │   ├── authStore.ts
│   │   │   │   │   └── i18nStore.ts
│   │   │   │   ├── styles/
│   │   │   │   │   ├── global.css
│   │   │   │   │   ├── colors.ts
│   │   │   │   │   ├── breakpoints.ts
│   │   │   │   │   └── index.ts
│   │   │   │   ├── hooks/
│   │   │   │   │   ├── useResponsive.ts
│   │   │   │   │   ├── useI18n.ts
│   │   │   │   │   └── useAuth.ts
│   │   │   │   ├── utils/
│   │   │   │   │   └── responsive.ts
│   │   │   │   └── index.ts
│   │   │   ├── ontology/
│   │   │   │   ├── components/
│   │   │   │   │   ├── blueprint/
│   │   │   │   │   ├── OntologySemanticNetwork.tsx
│   │   │   │   │   ├── GraphCanvas.tsx
│   │   │   │   │   └── ...
│   │   │   │   ├── pages/
│   │   │   │   ├── services/
│   │   │   │   ├── stores/
│   │   │   │   ├── locales/
│   │   │   │   │   ├── zh-CN/
│   │   │   │   │   │   └── ontology.json
│   │   │   │   │   └── en-US/
│   │   │   │   │       └── ontology.json
│   │   │   │   └── index.ts
│   │   │   ├── agent/
│   │   │   ├── audit/
│   │   │   ├── business/
│   │   │   ├── config/
│   │   │   ├── ingest/
│   │   │   ├── knowledge/
│   │   │   ├── qa/
│   │   │   ├── roles/
│   │   │   ├── simulation/
│   │   │   ├── system/
│   │   │   ├── version/
│   │   │   ├── workspace/
│   │   │   └── i18n-admin/
│   │   │       ├── pages/
│   │   │       │   └── I18nAdminPage.tsx
│   │   │       ├── services/
│   │   │       │   └── i18nApi.ts
│   │   │       └── index.ts
│   │   ├── App.tsx
│   │   ├── AppRoutes.tsx
│   │   ├── config.ts
│   │   ├── main.tsx
│   │   └── index.css
│   ├── public/
│   ├── test/
│   ├── package.json
│   ├── vite.config.ts
│   ├── vitest.config.ts
│   ├── tsconfig.json
│   └── eslint.config.js
├── openharness/
├── docker/
│   ├── Dockerfile
│   ├── Dockerfile.dev
│   └── docker-compose.yml
├── tests/
│   ├── unit/
│   │   ├── test_ontology_model.py
│   │   ├── test_ontology_engine.py
│   │   ├── test_workspace.py
│   │   ├── test_agent.py
│   │   ├── test_opa.py
│   │   ├── test_cognition.py
│   │   ├── test_query.py
│   │   ├── test_session_memory.py
│   │   ├── test_tool_registry.py
│   │   ├── test_semantic_layer.py
│   │   ├── test_hook_system.py
│   │   ├── test_mcp_adapter.py
│   │   ├── test_simulation.py
│   │   ├── test_qa.py
│   │   ├── test_decision_recommendation.py
│   │   ├── test_event_simulator.py
│   │   ├── test_feedback.py
│   │   ├── test_auth.py
│   │   ├── test_data_classification.py
│   │   └── test_i18n.py
│   ├── integration/
│   │   ├── test_ontology_graphiti.py
│   │   ├── test_agent_openharness.py
│   │   ├── test_opa_integration.py
│   │   └── test_mcp_integration.py
│   └── e2e/
│       ├── test_ontology_workflow.py
│       ├── test_agent_workflow.py
│       └── test_simulation_workflow.py
├── docs/
├── bootstep.py
├── main.py
├── requirements.txt
└── .env.example
```

**Structure Decision**: 采用 Web application 结构（Option 2），后端 odap/ + 前端 frontend/ 分离。后端按 7 大业务领域（core/decision/integration/platform/data/simulation/management）组织，每个模块严格遵循 routes→services→impl→storage 调用链。前端按功能模块组织，shared/ 下放置 5 级组件体系（atoms→molecules→organisms→templates→pages）和 adapter 隔离层。

## Spec-Docs 差异清单

| # | 差异项 | Spec 立场 | Docs/ADR 立场 | 处理方式 |
|---|--------|-----------|---------------|----------|
| 1 | OpenHarness 集成时机 | 当前阶段必须集成（FR-005/014/016/017/018/022/024/025） | ADR-030 推迟到 Phase 4 | 以 spec 为准，立即集成；ADR-030 状态修正为 Superseded |
| 2 | 推演沙箱隔离方式 | 进程级隔离（基于 OpenHarness 沙箱） | 需求定稿 FR-601 Docker 容器隔离 | 以 spec 为准，进程级隔离；FR-601 覆盖 |
| 3 | 前端响应式策略 | 移动优先（ADR-037），6 断点 | Assumptions 桌面优先 | 以 spec 为准，移动优先；Assumptions 修正 |
| 4 | Skill 热插拔注册 | 通过 OpenHarness Skill 管理功能注册 | ADR-030 推迟决策 | 以 spec 为准，OpenHarness 注册；ADR-030 Superseded |
| 5 | 本体管理拆分 | 拆分为本体模型层+本体管理引擎 | ADR-038/048 未明确拆分 | 以 spec 为准，严格拆分；ADR-048 补充拆分说明 |
| 6 | 用户认知引擎 | 纳入当前阶段（FR-016），基于 OpenHarness | ADR-049 独立设计 | 以 spec 为准，基于 OpenHarness；ADR-049 补充 OpenHarness 依赖 |
| 7 | MCP 协议集成 | 纳入当前阶段（FR-017），基于 OpenHarness | ADR-026 独立设计 | 以 spec 为准，基于 OpenHarness；ADR-026 补充 OpenHarness 依赖 |
| 8 | Hook 系统 | 基于 OpenHarness 生命周期钩子（FR-018） | ADR-027 独立设计 | 以 spec 为准，基于 OpenHarness 钩子；ADR-027 补充 OpenHarness 依赖 |
| 9 | 闭环反馈机制 | 纳入当前阶段（FR-022），基于 OpenHarness | ADR-051 独立设计 | 以 spec 为准，OpenHarness 外层封装；ADR-051 补充 OpenHarness 依赖 |
| 10 | 统一查询服务 | 纳入当前阶段（FR-023），4 种查询源 | ADR-055 已设计 | 一致，ADR-055 保持 Accepted |
| 11 | 会话记忆管理 | 基于 OpenHarness Memory Plugin（FR-024） | 现有 session_memory 独立实现 | 以 spec 为准，迁移到 OpenHarness Memory Plugin |
| 12 | 工具注册表 | 基于 OpenHarness Tool 接口（FR-025） | ADR-029/047 独立设计 | 以 spec 为准，基于 OpenHarness Tool 接口；ADR-047 补充 |
| 13 | 结构化语义层 | 纳入当前阶段（FR-026），含前端扩展 | ADR-056 已设计 | 一致，ADR-056 保持 Accepted |
| 14 | 数据分类与加密 | 4 级分类+传输加密+存储加密（FR-027） | SECURITY.md 未细化分类 | 以 spec 为准，4 级分类+AES-256-GCM+TLS 1.3 当前交付；KMS 推迟到下一阶段（spec 已授权） |
| 15 | 测试策略 | 测试金字塔+质量门禁（FR-028） | ADR-044 已设计 | 一致，ADR-044 保持 Accepted |
| 16 | OntologyDocument JSON | 统一原子格式，参考 Palantir AIP 核心概念（FR-029） | ADR-032 已设计 | 一致，ADR-032 保持 Accepted |
| 17 | 国际化 | 中英双语+后台管理+LLM 翻译（FR-030） | ADR-037 部分覆盖 | 以 spec 为准，完整实现 FR-030；ADR-037 补充 |
| 18 | 决策推荐引擎 | 基于 Graphiti RAG 增强推理（FR-019） | decision_recommendation 现有基础 | 增强现有实现，增加 Graphiti RAG 集成 |
| 19 | 事件模拟器 | 基于本体定义生成事件（FR-020） | event_simulator 现有基础 | 增强现有实现，增加本体关联约束 |
| 20 | Agent 编排架构 | DomainSwarm OODA 循环+混合路由 | ADR-005/043 已设计 | 以 spec 为准，DomainSwarm OODA；ADR-043 补充混合路由 |
| 21 | 认证方式 | OAuth2/OIDC+本地账号（FR-021） | auth_service 现有 JWT | 增加 OAuth2/OIDC 支持 |
| 22 | Palantir 本体参考 | 借鉴 Palantir AIP 核心概念 | ADR-036 已参考 | 以 spec 为准，借鉴核心概念；ADR-036 补充借鉴说明 |
| 23 | Graphiti 双时态 | 全面利用（版本/问答/推演） | ADR-002 已决策 | 一致，ADR-002 保持 Accepted |
| 24 | 前端组件体系 | 5 级组件+统一组件库+可替代性设计 | COMPONENT_SPEC.md 3 级体系 | 以 spec 为准，升级为 5 级+隔离层 |

## Phase 1: 基础层（P1 优先级）

**目标**: 构建平台核心基础——本体模型层+管理引擎+工作空间+数据摄入+i18n

**预计工期**: 8-10 周

### FR-001: 本体设计器（本体模型层+本体管理引擎拆分）

**技术方案**:

将现有 `odap/biz/core/ontology/` 拆分为两个子系统：

**本体模型层** (`ontology/model/`):
- 参考 Palantir AIP 核心概念：ObjectType → Property → Action → Rule
- `models/entity_type.py`: EntityType(BaseModel)，包含 name、properties、primary_key、constraints
- `models/property.py`: Property(BaseModel)，包含 name、data_type、required、default_value、classification_level
- `models/relation.py`: Relation(BaseModel)，包含 source_type、target_type、relation_type、cardinality
- `models/constraint.py`: Constraint(BaseModel)，包含 constraint_type、expression、error_message
- `models/ontology_document.py`: OntologyDocument(BaseModel)，统一原子格式，参考 Palantir AIP 核心概念设计
- 负责实例 CRUD（FR-003 的 CRUD 部分）
- 实例唯一性基于主键属性组合判定
- API: `POST /api/ontology/model/entity-types`, `GET /api/ontology/model/entity-types/{id}`, `PUT /api/ontology/model/entity-types/{id}`, `DELETE /api/ontology/model/entity-types/{id}`
- API: `POST /api/ontology/model/instances`, `GET /api/ontology/model/instances/{id}`, `PUT /api/ontology/model/instances/{id}`, `DELETE /api/ontology/model/instances/{id}`

**本体管理引擎** (`ontology/engine/`):
- 版本管理：基于 Graphiti 双时态（valid_time + transaction_time），每次变更生成版本记录
- 验证引擎：属性完整性检查、一致性验证、约束校验
- 审计记录：数据摄入审计（FR-015）
- API: `POST /api/ontology/engine/versions`, `GET /api/ontology/engine/versions/{id}`, `POST /api/ontology/engine/versions/{id}/rollback`
- API: `POST /api/ontology/engine/validate`, `GET /api/ontology/engine/audit`

**前端**:
- 重构 `ontology/` 模块，拆分为 OntologyModelDesigner + OntologyEnginePanel
- 本体设计器：左侧实体类型列表 + 中间属性编辑面板 + 右侧关系图预览
- 版本管理：版本时间线 + 变更对比 + 一键回滚

**存储**:
- SQLite: 实体类型定义、属性定义、关系定义、约束定义、版本元数据
- Neo4j: 本体实例数据、关系实例、时序版本快照

### FR-002: 本体版本管理（Graphiti 双时态）

**技术方案**:

- 利用 Graphiti 的 `valid_time`（业务时间）和 `transaction_time`（系统时间）双时态能力
- `impl/version_manager_impl.py`:
  - `create_version(ontology_id, change_desc, valid_time)`: 创建新版本，Graphiti 记录 valid_time + transaction_time
  - `get_version(ontology_id, version_id)`: 获取指定版本快照
  - `rollback_version(ontology_id, target_version_id)`: 回滚到指定版本，创建新版本记录回滚操作
  - `compare_versions(ontology_id, v1_id, v2_id)`: 双版本差异对比
  - `query_at_time(ontology_id, timestamp)`: 查询指定时间点的本体状态（时序查询）
- 版本冲突检测：乐观锁，基于 transaction_time 判断并发修改
- 回滚时通知相关 Agent 刷新知识缓存（通过 Hook 系统广播）

**API**:
- `POST /api/ontology/engine/versions` — 创建版本
- `GET /api/ontology/engine/versions?ontology_id={id}` — 版本列表
- `GET /api/ontology/engine/versions/{version_id}` — 版本详情
- `POST /api/ontology/engine/versions/{version_id}/rollback` — 回滚
- `GET /api/ontology/engine/versions/compare?v1={id}&v2={id}` — 版本对比
- `GET /api/ontology/engine/versions/temporal-query?ontology_id={id}&timestamp={ts}` — 时序查询

### FR-003: 本体实例 CRUD+批量导入

**技术方案**:

- CRUD 由本体模型层负责：
  - `create_instance(entity_type_id, properties)`: 创建实例，验证属性完整性
  - `get_instance(instance_id)`: 获取实例
  - `update_instance(instance_id, properties)`: 更新实例
  - `delete_instance(instance_id)`: 删除实例
  - `list_instances(entity_type_id, filters, page, page_size)`: 分页列表
- 批量导入由本体管理引擎负责：
  - `batch_import(entity_type_id, data, format)`: 支持 CSV/JSON 批量导入
  - 导入时自动验证属性完整性，无效数据标记并跳过
  - 返回导入结果摘要：成功数、失败数、失败详情
- 实例唯一性基于主键属性组合判定（用户在实体类型中指定哪些属性构成唯一标识）

**API**:
- `POST /api/ontology/model/instances` — 创建实例
- `GET /api/ontology/model/instances/{id}` — 获取实例
- `PUT /api/ontology/model/instances/{id}` — 更新实例
- `DELETE /api/ontology/model/instances/{id}` — 删除实例
- `POST /api/ontology/model/instances/batch` — 批量导入
- `GET /api/ontology/model/instances?entity_type_id={id}` — 实例列表

### FR-004: 多模态数据接入（PDF/Word+OCR，MinIO 存储）

**技术方案**:

- 新增 `odap/infra/storage/minio_client.py`: MinIO 客户端封装
  - `upload_object(bucket, key, data, content_type)`: 上传对象
  - `download_object(bucket, key)`: 下载对象
  - `get_presigned_url(bucket, key, expires)`: 获取预签名 URL
  - `delete_object(bucket, key)`: 删除对象
- 新增 `odap/biz/core/ontology/ingestion/`:
  - `impl/pdf_processor.py`: PDF 文本提取（PyPDF2/pdfplumber）
  - `impl/word_processor.py`: Word 文档解析（python-docx）
  - `impl/ocr_processor.py`: 图片 OCR（Tesseract/PaddleOCR）
  - `impl/batch_importer.py`: 批量导入处理器
- 处理流程：文件上传 → MinIO 存储 → 文本/OCR 提取 → LLM 实体抽取 → 本体实例更新
- Docker Compose 新增 MinIO 服务

**API**:
- `POST /api/ontology/ingestion/upload` — 文件上传（multipart/form-data）
- `GET /api/ontology/ingestion/tasks/{task_id}` — 导入任务状态
- `POST /api/ontology/ingestion/extract` — 触发实体抽取

### FR-012: 工作空间管理（增强隔离）

**技术方案**:

- 增强现有 `odap/biz/platform/workspace/`:
  - 4 级隔离（low/standard/high/strict），strict 级别强制校验资源归属
  - 工作空间之间数据完全隔离：SQLite 按工作空间分表或 workspace_id 过滤
  - Neo4j 按工作空间分图或 workspace_id 标签隔离
  - Redis 按 workspace_id 前缀隔离
  - MinIO 按工作空间分 bucket
- 增强场景管理：场景切换后本体、技能、配置、策略自动切换
- 工作空间导入导出：支持 JSON 格式的完整工作空间导出和导入

**API**:
- `POST /api/workspaces` — 创建工作空间
- `GET /api/workspaces` — 工作空间列表
- `GET /api/workspaces/{id}` — 工作空间详情
- `PUT /api/workspaces/{id}` — 更新工作空间
- `DELETE /api/workspaces/{id}` — 删除工作空间（需 OPA 策略校验）
- `POST /api/workspaces/{id}/export` — 导出
- `POST /api/workspaces/{id}/import` — 导入

### FR-013: 场景切换

**技术方案**:

- 增强现有 `odap/biz/platform/workspace/services/scenario_service.py`:
  - 场景切换时自动加载关联本体列表、技能配置、OPA 策略、Agent 配置
  - 切换事件通过 Hook 系统广播，各模块监听切换事件刷新缓存
  - 场景与本体 N:M 关联，解绑需检查依赖
- 前端：场景切换器组件（WorkspaceSwitcher 增强），切换后全局状态更新

**API**:
- `POST /api/workspaces/{ws_id}/scenarios` — 创建场景
- `GET /api/workspaces/{ws_id}/scenarios` — 场景列表
- `PUT /api/workspaces/{ws_id}/scenarios/{id}` — 更新场景
- `POST /api/workspaces/{ws_id}/scenarios/{id}/activate` — 激活场景
- `POST /api/workspaces/{ws_id}/scenarios/{id}/ontologies` — 绑定本体

### FR-015: 数据摄入审计

**技术方案**:

- 由本体管理引擎的审计模块负责：
  - 记录数据来源（上传文件/批量导入/API 调用/Agent 操作）
  - 记录处理过程（抽取步骤、转换规则、验证结果）
  - 记录转换规则（字段映射、类型转换、默认值填充）
- 审计记录写入 SQLite + 统一审计通道（unified_audit.py）
- 前端：审计时间线组件展示

**API**:
- `GET /api/ontology/engine/audit?entity_type_id={id}&page={n}` — 审计记录列表
- `GET /api/ontology/engine/audit/{audit_id}` — 审计详情

### FR-029: OntologyDocument JSON 统一格式

**技术方案**:

- 定义 `OntologyDocument` JSON Schema，参考 Palantir AIP 核心概念设计：
  ```json
  {
    "id": "uuid",
    "name": "本体名称",
    "version": "1.0.0",
    "object_types": [
      {
        "id": "uuid",
        "name": "实体类型名",
        "properties": [...],
        "primary_key": ["prop1", "prop2"],
        "actions": [...],
        "rules": [...]
      }
    ],
    "relations": [...],
    "metadata": {...}
  }
  ```
- 所有数据摄入、导入导出、模块间数据交换必须使用此格式
- `odap/biz/core/ontology/model/models/ontology_document.py`: Pydantic 模型定义
- `odap/biz/core/ontology/schema/document.py`: 现有 schema 迁移到 OntologyDocument 格式
- 提供 `to_owl()` / `to_rdf()` 导出方法；`from_palantir()` 仅在需要导入 Palantir 数据时实现

**API**:
- `GET /api/ontology/model/documents/{ontology_id}` — 获取 OntologyDocument
- `POST /api/ontology/model/documents` — 创建/导入 OntologyDocument
- `PUT /api/ontology/model/documents/{ontology_id}` — 更新 OntologyDocument
- `POST /api/ontology/model/documents/{ontology_id}/export?format=owl|rdf` — 格式导出

### FR-027: 数据分类标记+传输加密（部分）

**技术方案**:

- 新增 `odap/infra/security/data_classification.py`:
  - 4 级分类枚举：`DataClassification(str, Enum)` — TS/S/C/U
  - Property 模型增加 `classification_level` 字段
  - 数据写入时自动标记分类级别
- 新增 `odap/infra/security/encryption.py`:
  - 传输加密：强制 TLS 1.3（FastAPI HTTPS 配置）
  - 存储加密：TS/S 级数据 AES-256-GCM 加密存储（推迟 KMS 集成，初期使用配置文件密钥）
  - C 级数据仅传输加密
  - U 级数据标准安全措施
- OPA 策略：基于数据分类级别的访问控制规则
- 存储加密在 Phase 1 实现（AES-256-GCM + 配置文件密钥）；KMS 集成推迟到下一阶段（当前 feature 不实现）

**API**:
- 数据分类标记嵌入在实体类型/属性的 CRUD 操作中
- `GET /api/security/classification-levels` — 分类级别列表

### FR-030: 国际化（中英双语+后台管理+LLM 翻译）

**技术方案**:

**后端**:
- 新增 `odap/biz/platform/i18n/`:
  - `api/routes.py`: 翻译条目 CRUD + LLM 翻译接口
  - `api/schemas.py`: 请求/响应模型
  - `models/translation.py`: Translation(BaseModel)，key/module/locale/value
  - `services/i18n_service.py`: 翻译管理+LLM 翻译调用
  - `storage/sqlite_i18n_storage.py`: 翻译条目持久化
- 翻译文件按模块拆分：每个前端模块有独立的 locales/{locale}/xxx.json
- LLM 翻译：调用 OpenAI API 批量翻译未翻译条目，人工审核后入库

**前端**:
- 新增 `frontend/src/modules/i18n-admin/`: 后台翻译管理界面
  - 翻译条目列表（按模块/语言筛选）
  - 在线编辑翻译
  - LLM 自动翻译按钮+人工审核
- 使用 react-i18next 作为 i18n 框架（research.md 课题3 决策）
- 每个模块独立维护翻译文件：`modules/{name}/locales/{locale}/{name}.json`
- 共享翻译：`modules/shared/locales/{locale}/common.json`

**API**:
- `GET /api/i18n/translations?module={name}&locale={locale}` — 获取翻译
- `POST /api/i18n/translations` — 创建/更新翻译条目
- `POST /api/i18n/translations/auto-translate` — LLM 自动翻译
- `GET /api/i18n/modules` — 模块列表
- `GET /api/i18n/locales` — 支持的语言列表

### Phase 1 交付物

- [ ] 本体模型层完整 CRUD + OntologyDocument JSON 格式
- [ ] 本体管理引擎版本管理+验证+审计
- [ ] 多模态数据接入（PDF/Word/OCR）+ MinIO 集成
- [ ] 工作空间 4 级隔离 + 场景切换
- [ ] 数据分类标记 + 传输加密
- [ ] i18n 中英双语 + 后台管理 + LLM 翻译
- [ ] 前端 5 级组件体系基础设施 + 移动优先响应式框架
- [ ] Phase 1 全部单元测试（覆盖率 > 80%）

---

## Phase 2: 核心层（P2 优先级）

**目标**: 构建智能体编排+策略治理+认知引擎+查询服务核心能力

**预计工期**: 10-12 周

### FR-005: 多 Agent 协同调度（OpenHarness Swarm 集成）

**技术方案**:

- 基于 OpenHarness Swarm 实现 DomainSwarm OODA 循环编排
- `odap/biz/core/agent/impl/swarm_orchestrator.py`:
  - `DomainSwarm`: 继承/封装 OpenHarness Swarm，实现 OODA 循环（Observe→Orient→Decide→Act）
  - `IntentRouter`: 混合路由策略（规则优先 + LLM 兜底）
    - 规则路由：基于本体事实的意图-角色映射表
    - LLM 路由：不确定时调用 LLM 分类意图
    - 默认路由：不确定时路由到 Intelligence Agent
  - `SubAgentPlanner`: 按意图自动规划 subAgent 任务分解
- Agent 角色模型：Commander/Intelligence/Operations（可扩展）
- 意图识别准确率目标 > 90%
- 路由规则及置信度必须基于本体事实

**API**:
- `POST /api/agent/dispatch` — 意图分发
- `GET /api/agent/tasks/{task_id}` — 任务状态
- `GET /api/agent/tasks/{task_id}/chain` — 决策链路
- `POST /api/agent/swarm/configure` — Swarm 配置

### FR-006: Agent 决策过程可视化

**技术方案**:

- 决策过程数据结构：`DecisionChain` 包含 steps（OODA 各阶段）、reasoning（推理过程）、evidence（依据）
- 后端：Agent 执行时通过 Hook 系统记录每个 OODA 步骤
- 前端：决策链路可视化组件
  - 时间线视图：按时间顺序展示决策步骤
  - 思维链视图：展示推理过程和依据
  - 交互式：点击步骤查看详细信息
- WebSocket 实时推送决策过程

**API**:
- `GET /api/agent/decisions/{decision_id}` — 决策详情
- `GET /api/agent/decisions/{decision_id}/chain` — 决策链路
- `WS /ws/agent/decisions` — 决策过程实时推送

### FR-007: OPA 策略 Markdown 编写+热更新

**技术方案**:

- 增强现有 `odap/infra/opa/`:
  - `opa_service.py` 增加 Markdown→Rego 编译器
    - Markdown 策略语法：`## 规则名\n当 [条件] 时 [允许/拒绝]`
    - 编译为 Rego 策略文件
    - 编译失败时保持旧策略运行（fail-close）
    - 不暴露 Rego 编译错误细节给非管理员用户
  - 热更新：编译后通过 OPA API 加载策略，30 秒内生效
  - 策略版本管理：SQLite 存储策略版本历史
- 前端：策略编辑器（Markdown 编辑+预览+编译状态）

**API**:
- `POST /api/policy/markdown` — 提交 Markdown 策略
- `GET /api/policy/markdown/{id}` — 获取策略
- `PUT /api/policy/markdown/{id}` — 更新策略
- `POST /api/policy/markdown/{id}/compile` — 编译策略
- `GET /api/policy/markdown/{id}/status` — 编译状态

### FR-008: ABAC 权限校验+审计日志

**技术方案**:

- ABAC 模型：Subject（用户/Agent 角色）+ Action（操作类型）+ Resource（资源+工作空间）+ Environment（时间/IP 等）
- `odap/infra/opa/opa_service.py`:
  - `check_permission(subject, action, resource, env)`: OPA 策略校验
  - 返回 allow/deny + 原因
- 审计日志：所有写操作通过 `unified_audit.py` 记录
  - actor（用户/Agent）、action、resource、result、timestamp
  - 写入 SQLite + Graphiti 审计通道
- 前端：审计日志时间线展示

**API**:
- `POST /api/policy/check` — 权限校验
- `GET /api/audit/logs?page={n}&actor={id}&action={type}` — 审计日志查询
- `GET /api/audit/timeline?resource={id}` — 审计时间线

### FR-016: 用户认知引擎（意图识别+知识导航+解释引擎）

**技术方案**:

- 基于 OpenHarness 设计，增强现有 `odap/biz/core/cognition/`:
  - `impl/intent_recognizer.py`: 意图识别器
    - 基于 LLM + 本体事实的意图分类
    - 支持角色上下文（不同角色不同意图映射）
    - 输出：intent_type + confidence + parameters
  - `impl/knowledge_navigator.py`: 知识导航器
    - 基于本体的知识图谱导航
    - 推理路径可视化（高亮路径+逐步回溯）
  - `impl/explanation_engine.py`: 解释引擎
    - AI 决策过程可解释性
    - 推理链路展示（"为什么"问题的回答）
  - `impl/role_view_manager.py`: 角色视图管理器
    - 不同角色（Commander/Intelligence/Operations）定制化视图
    - 角色切换后界面自动适配

**API**:
- `POST /api/cognition/recognize-intent` — 意图识别
- `POST /api/cognition/navigate` — 知识导航
- `POST /api/cognition/explain` — 解释请求
- `GET /api/cognition/role-view?role={role}` — 角色视图
- `PUT /api/cognition/role-view` — 更新角色视图配置

### FR-014: Skill 热插拔（OpenHarness 注册）

**技术方案**:

- 增强现有 `odap/biz/platform/skill_system/`:
  - 通过 OpenHarness Skill 管理功能注册和发现
  - `impl/hotplug.py`: 热插拔实现
    - `register_skill(skill_def)`: 注册 Skill 到 OpenHarness
    - `unregister_skill(skill_id)`: 注销 Skill
    - `discover_skills(query)`: 发现可用 Skill
  - 无需重启服务即可生效
  - Skill 生命周期管理：draft→active→deprecated→archived
- 现有 `odap/tools/` 下的 9 个技能包迁移为 OpenHarness Skill 格式

**API**:
- `POST /api/skill/register` — 注册 Skill
- `DELETE /api/skill/{id}` — 注销 Skill
- `GET /api/skill/discover?q={query}` — 发现 Skill
- `GET /api/skill/{id}/status` — Skill 状态

### FR-021: OAuth2/OIDC+本地账号认证

**技术方案**:

- 增强现有 `odap/infra/security/`:
  - `oauth2_providers.py`: OAuth2/OIDC Provider 集成
    - 支持企业 SSO（Keycloak/Auth0/Okta）
    - Authorization Code Flow + PKCE
    - Token 交换：OAuth2 Token → JWT Token
  - `auth_service.py`: 增加本地账号密码认证
    - bcrypt 密码哈希
    - JWT 双 Token（Access 15min / Refresh 7d）
  - API Key 认证推迟到下一阶段
- 前端：LoginPage 增加 SSO 登录按钮

**API**:
- `POST /api/auth/login` — 本地账号登录
- `POST /api/auth/sso/{provider}` — SSO 登录
- `POST /api/auth/refresh` — 刷新 Token
- `POST /api/auth/logout` — 登出

### FR-023: 统一查询服务（4 种查询源）

**技术方案**:

- 增强现有 `odap/infra/query/`:
  - `service.py`: QueryService 统一接口
    - `query(source, params)`: 统一查询入口
    - 4 种查询源：
      - `schema_source.py`: 本体 Schema 查询（实体类型/属性/关系定义）
      - `entity_source.py`: 实体实例查询（CRUD+过滤+分页）
      - `topo_source.py`: 拓扑查询（路径/邻居/子图）
      - `temporal_source.py`: 时序查询（基于 Graphiti 双时态）
  - 通过 OpenHarness Tool 接口注册，Agent Safe 默认只读
  - 架构守卫：pytest 测试用例验证 Agent 代码中没有直接调用 graph_manager 的写方法

**API**:
- `POST /api/query` — 统一查询
- `GET /api/query/sources` — 查询源列表
- `POST /api/query/validate` — 查询验证

### FR-024: 会话记忆管理

**技术方案**:

- 基于 OpenHarness Memory Plugin 实现，迁移现有 `odap/biz/platform/session_memory/`:
  - `impl/short_term_memory.py`: 短期记忆（对话上下文，Redis 存储，TTL 30min）
  - `impl/working_memory.py`: 工作记忆（当前任务状态，Redis 存储，TTL 2h）
  - `impl/long_term_memory.py`: 长期记忆（持久化到 Graphiti，无 TTL）
  - 记忆检索：基于语义相似度 + 时间衰减
  - 多轮对话和 Agent 协同必须基于记忆上下文

**API**:
- `GET /api/memory/session/{session_id}` — 获取会话记忆
- `POST /api/memory/session/{session_id}/clear` — 清除短期记忆
- `GET /api/memory/long-term?query={q}` — 长期记忆检索

### FR-025: 统一工具注册表

**技术方案**:

- 增强现有 `odap/biz/platform/tool_registry/`:
  - 基于 OpenHarness Tool 接口实现
  - `impl/registry.py`: ToolRegistry
    - `register_tool(tool_def)`: 注册工具（Skill/QueryService/MCP Server 统一注册为 Tool）
    - `unregister_tool(tool_id)`: 注销工具
    - `invoke_tool(tool_id, params)`: 调用工具
    - `list_tools(category)`: 按分类列出工具
  - `impl/semantic_discovery.py`: 语义发现
    - 基于自然语言描述匹配工具
  - 统一管理生命周期、权限和调用

**API**:
- `POST /api/tools/register` — 注册工具
- `DELETE /api/tools/{id}` — 注销工具
- `POST /api/tools/{id}/invoke` — 调用工具
- `GET /api/tools?category={cat}` — 工具列表
- `POST /api/tools/discover` — 语义发现

### FR-026: 结构化语义层

**技术方案**:

- 基于 ADR-056 设计，新增 `odap/biz/core/semantic_layer/`:
  - Intent → StructuredQuery → Agent Task 的结构化映射
  - `intent_parser.py`: 自然语言意图解析为 StructuredQuery
  - `query_planner.py`: StructuredQuery 规划为 Agent Task 序列
  - `disambiguator.py`: 歧义消除
    - 同义词/近似词映射（用户可配置）
    - 扩写规则（用户可配置）
  - 前端扩展功能：用户配置同义词/近似词映射和扩写规则的界面

**API**:
- `POST /api/semantic/parse-intent` — 意图解析
- `POST /api/semantic/plan-tasks` — 任务规划
- `GET /api/semantic/synonyms` — 同义词映射列表
- `POST /api/semantic/synonyms` — 添加同义词映射
- `GET /api/semantic/expansion-rules` — 扩写规则列表
- `POST /api/semantic/expansion-rules` — 添加扩写规则

### FR-018: Hook 系统

**技术方案**:

- 增强现有 `odap/biz/integration/hook_system/`:
  - 基于 OpenHarness 生命周期钩子
  - `impl/hook_manager.py`:
    - Pre-Hook: Agent 执行前拦截（OPA 策略注入、参数校验）
    - Post-Hook: Agent 执行后增强（审计日志、性能监控）
    - Hook 注册表：管理优先级和依赖
  - OPA 策略注入通过 Pre-Hook 实现
  - 审计日志通过 Post-Hook 实现
  - Hook 注册/注销支持热更新

**API**:
- `POST /api/hooks/register` — 注册 Hook
- `DELETE /api/hooks/{id}` — 注销 Hook
- `GET /api/hooks` — Hook 列表
- `POST /api/hooks/{id}/enable` — 启用 Hook
- `POST /api/hooks/{id}/disable` — 禁用 Hook

### FR-022: 闭环反馈机制

**技术方案**:

- 基于 OpenHarness 实现，增强现有 `odap/biz/simulation/feedback/`:
  - Feedback Collector/Analyzer/Aggregator 作为 OpenHarness 的外层封装
  - 部署在同一进程内，通过 OpenHarness 的 Hook 机制触发
  - `collector.py`: 执行结果收集（感知层输入）
  - `analyzer.py`: 决策效果分析（量化评估）
  - `aggregator.py`: 历史经验聚合（沉淀到知识图谱）
  - 完成"感知-理解-决策-执行-追踪"完整闭环
  - 执行结果反馈到感知层，决策效果可量化评估

**API**:
- `POST /api/feedback/collect` — 收集反馈
- `GET /api/feedback/analysis/{task_id}` — 反馈分析
- `GET /api/feedback/aggregate?ontology_id={id}` — 经验聚合
- `POST /api/feedback/close-loop` — 闭环触发

### Phase 2 交付物

- [ ] DomainSwarm OODA 循环编排 + 混合路由
- [ ] Agent 决策过程可视化
- [ ] OPA Markdown 策略编写+热更新
- [ ] ABAC 权限校验+审计日志
- [ ] 用户认知引擎（意图识别+知识导航+解释引擎+角色视图）
- [ ] Skill 热插拔（OpenHarness 注册）
- [ ] OAuth2/OIDC+本地账号认证
- [ ] 统一查询服务（4 种查询源）
- [ ] 会话记忆管理（短期/工作/长期）
- [ ] 统一工具注册表
- [ ] 结构化语义层（含前端扩展）
- [ ] Hook 系统（基于 OpenHarness 钩子）
- [ ] 闭环反馈机制
- [ ] Phase 2 全部单元测试（覆盖率 > 80%）

---

## Phase 3: 增强层（P3 优先级）

**目标**: 构建推演+问答+MCP+决策推荐高价值增强能力

**预计工期**: 8-10 周

### FR-009: 沙箱推演环境

**技术方案**:

- 增强现有 `odap/biz/simulation/simulation_sandbox/`:
  - 基于 OpenHarness 的沙箱机制实现进程级隔离
  - `impl/sandbox_manager.py`:
    - `create_sandbox(config)`: 创建隔离沙箱环境
    - `run_simulation(sandbox_id, params)`: 在沙箱中运行推演
    - `get_sandbox_status(sandbox_id)`: 沙箱状态
    - `destroy_sandbox(sandbox_id)`: 销毁沙箱
  - 推演数据与生产环境完全隔离
  - 资源限制：内存/时间超限自动终止，返回部分结果和超时提示
  - 沙箱内推演结果可导出到生产环境（需审批）

**API**:
- `POST /api/simulation/sandbox` — 创建沙箱
- `POST /api/simulation/sandbox/{id}/run` — 运行推演
- `GET /api/simulation/sandbox/{id}/status` — 沙箱状态
- `GET /api/simulation/sandbox/{id}/results` — 推演结果
- `DELETE /api/simulation/sandbox/{id}` — 销毁沙箱

### FR-010: 多方案并行推演+What-if

**技术方案**:

- 新增 `odap/biz/simulation/simulation_sandbox/impl/parallel_runner.py`:
  - `run_parallel(scenarios)`: 多方案并行推演
  - `run_what_if(base_scenario, param_variations)`: What-if 参数敏感性分析
  - 并行度控制：最多 10 个方案并行
  - 结果以并排对比视图展示，高亮关键指标差异
- WebSocket 实时推送推演进度
- 推演历史基于 Graphiti 双时态存储，支持历史对比

**API**:
- `POST /api/simulation/parallel` — 并行推演
- `POST /api/simulation/what-if` — What-if 分析
- `WS /ws/simulation/progress` — 推演进度推送
- `GET /api/simulation/comparison?ids={id1,id2}` — 结果对比

### FR-011: 自然语言问答+图谱检索

**技术方案**:

- 增强现有 `odap/biz/data/qa/`:
  - `impl/qa_engine.py`: 问答引擎
    - 融合本体知识 + 图谱检索 + LLM 生成
    - 多轮对话上下文理解（基于会话记忆）
    - 利用 Graphiti 双时态支持时序推理（"当时发生了什么"类问题）
  - `impl/temporal_reasoner.py`: 时序推理器
    - 基于 Graphiti valid_time 的时序查询
    - "在 X 时间点，Y 的状态是什么"类问题
  - `impl/chart_renderer.py`: 图表渲染
    - 混合渲染模式：轻量交互型前端渲染（G6+Leaflet+ECharts）
    - 计算密集型后端渲染
    - 支持 8 种以上图表类型
  - 用户可一键将当前视图信息添加到问答上下文

**API**:
- `POST /api/qa/ask` — 问答
- `POST /api/qa/ask/temporal` — 时序问答
- `GET /api/qa/sessions/{id}` — 会话历史
- `POST /api/qa/chart` — 图表渲染请求

### FR-017: MCP 协议集成

**技术方案**:

- 增强现有 `odap/biz/integration/mcp_adapter/`:
  - 基于 OpenHarness 实现 MCP v1.0 协议集成
  - `impl/server_manager.py`:
    - `register_server(server_config)`: 注册 MCP Server
    - `unregister_server(server_id)`: 注销 MCP Server
    - `call_tool(server_id, tool_name, params)`: 调用 MCP 工具
  - 支持外部领域仿真系统接入（雷达模拟器、气象数据源、卫星影像等）
  - 运行时动态添加/移除 MCP Server
  - MCP Server 在独立沙箱进程中运行
  - 通过统一工具注册表注册为 Tool

**API**:
- `POST /api/mcp/servers` — 注册 MCP Server
- `DELETE /api/mcp/servers/{id}` — 注销 MCP Server
- `GET /api/mcp/servers` — Server 列表
- `POST /api/mcp/servers/{id}/tools/{tool_name}` — 调用工具
- `GET /api/mcp/servers/{id}/status` — Server 状态

### FR-019: 决策推荐引擎

**技术方案**:

- 增强现有 `odap/biz/decision/decision_recommendation/`:
  - 基于 Graphiti RAG 增强推理
  - `impl/recommendation_engine.py`:
    - `generate_recommendations(simulation_results)`: 方案推荐
    - `assess_risks(recommendation)`: 多维度风险评估
    - `rank_recommendations(recommendations)`: 方案排序
    - `explain_recommendation(recommendation_id)`: 决策理由可解释性
  - 与推演结果集成，为推演结果提供方案推荐
  - 历史推荐经验沉淀到知识图谱

**API**:
- `POST /api/decision/recommend` — 生成推荐
- `POST /api/decision/risk-assessment` — 风险评估
- `GET /api/decision/recommendations/{id}/explain` — 推荐解释
- `GET /api/decision/history?ontology_id={id}` — 历史推荐

### FR-020: 事件模拟器

**技术方案**:

- 增强现有 `odap/biz/simulation/event_simulator/`:
  - `impl/event_generator.py`: 事件生成器
    - 按剧本/模板自动生成事件序列
    - 事件必须基于当前工作空间的本体定义展开
    - 生成的事件必须与本体具有相关性（间接关联可接受，不能文不对题）
  - `impl/timeline_engine.py`: 时间线引擎
    - 模拟时钟独立控制（加速/减速/暂停）
    - 事件按时间线顺序注入
  - `impl/scenario_template.py`: 剧本模板
    - 预定义事件模板库
    - 支持自定义模板
  - 手动注入关键事件
  - 事件注入驱动本体状态演化

**API**:
- `POST /api/event-simulator/generate` — 生成事件序列
- `POST /api/event-simulator/inject` — 手动注入事件
- `GET /api/event-simulator/timeline/{id}` — 时间线
- `POST /api/event-simulator/clock/control` — 时钟控制（加速/减速/暂停）
- `GET /api/event-simulator/templates` — 模板列表

### FR-028: 测试金字塔+质量门禁（贯穿所有阶段）

**技术方案**:

- 测试金字塔：80% 单元测试 / 15% 集成测试 / 5% E2E 测试
- 质量门禁：
  - PR 合并前：单元测试覆盖率 > 80%、集成测试 0 失败、Lint 0 error、类型检查 0 error
  - 发版前：E2E 核心流程测试、性能测试、安全扫描
- CI/CD 集成：
  - GitHub Actions / GitLab CI
  - 自动运行 lint + typecheck + test
  - 覆盖率报告自动生成
- 测试基础设施：
  - 后端：pytest + pytest-asyncio + pytest-mock
  - 前端：vitest + @testing-library/react
  - 集成测试：需要 Neo4j 运行，否则 skip
  - E2E 测试：Playwright（新增）

**门禁脚本**:
- `scripts/quality-gate.sh`: 统一质量门禁脚本
  - 后端：`ruff check .` + `pytest tests/unit/ -v --cov=odap --cov-fail-under=80`
  - 前端：`npm run lint` + `npm run typecheck` + `npm test`

### Phase 3 交付物

- [ ] 沙箱推演环境（进程级隔离）
- [ ] 多方案并行推演+What-if 分析
- [ ] 自然语言问答+图谱检索+时序推理
- [ ] MCP 协议集成（动态添加/移除 Server）
- [ ] 决策推荐引擎（Graphiti RAG 增强推理）
- [ ] 事件模拟器（本体关联+时间线+剧本模板）
- [ ] 测试金字塔+质量门禁（全阶段覆盖）
- [ ] Phase 3 全部单元测试（覆盖率 > 80%）

---

## Phase 4: Palantir/OntoFlow 增强层（P4 优先级，2026-06-05 brainstorm 增量）

**目标**: 借鉴 Palantir Foundry 与 OntoFlow 的核心范式，把 ODAP 的「本体设计」与「本体应用」推到企业级。包含 7 个新 FR（FR-031..FR-037），重点解决：本体多团队并行开发、数据质量闭环、Agent 强类型护栏、跨角色视图隔离。

**预计工期**: 12-15 周（按 4 个里程碑分批交付）

**设计原则**:
- **零结构破坏**：不替换现有 FR-001 本体模型层，而是在其上叠加 Palantir 范式
- **职责分离**：Data Health 与 OPA 严格分工（OPA 写时，Data Health 写后）
- **分层架构**：Action Type（业务接口，本体层）→ Skill（工程实现，能力层）
- **演化为先**：每个 FR 都支持 OntoFlow goal-driven 演化模式

### FR-031: Data Health 数据健康引擎

**技术方案**:

- 新增 `odap/biz/core/ontology/health/`:
  - `models/rule.py`: HealthRule(BaseModel) — 包含 `target_type`、`check_expression`（声明式 JSON/YAML）、`severity`、`notification_channel`、`schedule`
  - `models/report.py`: HealthReport(BaseModel) — 包含 `instance_id`、`rule_id`、`status` (pass/warn/fail)、`details`
  - `interfaces/scanner.py`: HealthScanner(ABC) — `scan(rule) -> Iterator[HealthReport]`
  - `impl/scanner.py`: DeclarativeHealthScanner — 解析 JSON/YAML 规则并执行
  - `impl/notification.py`: NotificationDispatcher — 支持 Email/Webhook/IM
  - `services/health_service.py`: HealthService — CRUD 规则、触发扫描、查询报告
  - `storage/sqlite_health_storage.py`: HealthRule + HealthReport 持久化
- 调度：基于 `apscheduler` 或 `celery beat`，支持 cron 表达式
- 增量扫描：基于 `last_scan_at` 时间戳，扫描新增/变更数据
- 全量扫描：异步执行，不阻塞主流程（通过 BackgroundTasks）
- 大数据规模：> 100K 实例时使用分批扫描 + 进度上报

**API**:
- `POST /api/ontology/health/rules` — 创建健康规则
- `GET /api/ontology/health/rules?target_type={type}` — 规则列表
- `PUT /api/ontology/health/rules/{id}` — 更新规则
- `DELETE /api/ontology/health/rules/{id}` — 删除规则
- `POST /api/ontology/health/scan` — 触发扫描（同步/异步）
- `GET /api/ontology/health/scan/{scan_id}/status` — 扫描状态
- `GET /api/ontology/health/reports?rule_id={id}&page={n}` — 报告列表
- `GET /api/ontology/health/summary` — 总体健康摘要

**与 OPA 分工**:
| 场景 | 用 OPA | 用 Data Health |
|------|--------|----------------|
| 写入时权限校验 | ✅ | ❌ |
| 防止脏数据写入 | ✅ | ⚠️ (事后检测) |
| 发现历史数据漂移 | ❌ | ✅ |
| 合规审计 (Sox/HIPAA) | ❌ | ✅ |
| 实时告警 | ❌ | ✅ |

### FR-032: 本体分支与合并（Branch & Merge, Palantir 范式）

**技术方案**:

- 升级现有 `odap/biz/core/ontology/engine/`:
  - `models/branch.py`: OntologyBranch(BaseModel) — 包含 `id`、`name` (e.g., `main`, `feature/team-x`)、`base_version_id`、`head_version_id`、`protected`、`merge_strategy` (auto/manual/3-way)
  - `models/merge_request.py`: MergeRequest(BaseModel) — 包含 `source_branch_id`、`target_branch_id`、`diff`、`conflicts[]`、`status` (open/merged/conflicted)、`reviewers[]`、`approvals[]`
  - `models/conflict.py`: Conflict(BaseModel) — 包含 `object_type_id`、`field_path`、`base_value`、`ours_value`、`theirs_value`、`resolution` (ours/theirs/manual)
  - `impl/branch_manager.py`: BranchManager — `create_branch`、`list_branches`、`protect_branch`、`delete_branch`
  - `impl/merge_engine.py`: MergeEngine — 3-way merge 算法（基于 ontology_document.json 的 JSON Patch）
  - `impl/diff_engine.py`: DiffEngine — 计算版本差异，输出 JSON Patch
  - `services/branch_service.py`: 编排 + 通知评审人
- 冲突解决 UI：可视化 diff + 三方对比 + 选择保留版本
- 主分支保护：main 分支必须经过 PR/MR 评审，禁止直接 push
- Git-like 语义：HEAD/main/commit，但底层是 SQLite + Neo4j

**API**:
- `POST /api/ontology/branches` — 创建分支
- `GET /api/ontology/branches?ontology_id={id}` — 分支列表
- `GET /api/ontology/branches/{id}` — 分支详情
- `PUT /api/ontology/branches/{id}/protect` — 保护分支
- `POST /api/ontology/branches/{id}/merge` — 合并分支
- `POST /api/ontology/merge-requests` — 创建 MR
- `GET /api/ontology/merge-requests?status={status}` — MR 列表
- `POST /api/ontology/merge-requests/{id}/approve` — 批准 MR
- `POST /api/ontology/merge-requests/{id}/resolve-conflict` — 解决冲突

### FR-033: Object Type 继承 + 组合 (inherits + mixins)

**技术方案**:

- 升级 `odap/biz/core/ontology/model/models/entity_type.py`:
  - `EntityType(BaseModel)` 扩展字段：
    - `inherits: List[str] = Field(default_factory=list)` — 父类引用（支持多继承，但深度 ≤ 5）
    - `mixins: List[str] = Field(default_factory=list)` — Mixin 引用列表
  - 验证规则：
    - 继承链深度 ≤ 5（避免"继承地狱"）
    - Mixin 冲突检测：重名字段 MUST 显式 override，不允许 silent shadow
    - 循环继承检测（DAG 验证）
  - 解析流程：扁平化继承链 → 应用 mixin → 字段去重 → 冲突解决
  - 解析后的 `EntityType` 暴露 `effective_properties` (含继承+组合)
- 新增 `odap/biz/core/ontology/model/models/mixin.py`: Mixin(BaseModel)
  - `name`、`properties[]`、`actions[]`
  - 不支持嵌套继承（避免循环）

**API**:
- 现有 CRUD 端点扩展 `inherits` / `mixins` 字段
- `GET /api/ontology/model/entity-types/{id}/effective-properties` — 解析后的完整属性
- `GET /api/ontology/model/entity-types/{id}/inheritance-graph` — 继承关系图
- `POST /api/ontology/model/validate-inheritance` — 验证继承链

### FR-034: Action Type 一等公民 + Skill 分层

**技术方案**:

- 新增 `odap/biz/core/ontology/action_type/`:
  - `models/action_type.py`: ActionType(BaseModel)
    - `id`, `name`, `description`, `parameters: List[ActionParam]`
    - `return_type: ActionReturn` (可引用 ObjectType 实例)
    - `implementation: List[str]` — Skill 引用列表 (1:N)
    - `preconditions: List[str]` — 引用 OPA 策略
    - `postconditions: List[str]`
  - `models/skill_binding.py`: SkillBinding — 映射 Action 步骤到 Skill
  - `impl/action_executor.py`: ActionExecutor
    - 接收 Agent 调用 → 参数 OPA 校验 → 按 Skill 顺序执行 → 错误回滚
  - `services/action_service.py`: ActionService
- 升级 `odap/biz/platform/tool_registry/`:
  - 现有 ToolRegistry 扩展为 `SkillRegistry`
  - 每个 Skill 必须通过 OPA 授权 + Action Type 引用才能被 Agent 调用
- Agent 调用流程：
  1. Agent 决定调用 Action Type
  2. 平台校验 Action 是否存在
  3. 参数按 ObjectType 强类型校验
  4. OPA 二次校验权限
  5. 按 Skill 列表顺序执行
  6. 任一失败 → 全部回滚（事务语义）

**API**:
- `POST /api/ontology/action-types` — 创建 Action Type
- `GET /api/ontology/action-types?entity_type_id={id}` — 列表
- `GET /api/ontology/action-types/{id}` — 详情
- `PUT /api/ontology/action-types/{id}` — 更新
- `POST /api/ontology/action-types/{id}/execute` — Agent 调用
- `GET /api/ontology/action-types/{id}/executions` — 执行历史
- `POST /api/skill/bind-action` — 绑定 Skill 到 Action

### FR-035: 计算属性 (Computed Properties)

**技术方案**:

- 升级 `odap/biz/core/ontology/model/models/property.py`:
  - `Property(BaseModel)` 扩展：
    - `is_computed: bool = False`
    - `depends_on: List[str] = Field(default_factory=list)` — 依赖其他属性
    - `cache_strategy: Literal["none", "lazy", "eager", "hybrid"]`
    - `materialize_view: Optional[str]` — 物化视图名称
- 新增 `odap/biz/core/ontology/materialization/`:
  - `models/view.py`: MaterializedView(BaseModel)
  - `impl/view_manager.py`: ViewManager — 增量重算、定时全量、查询路由
  - `services/compute_service.py`: ComputeService
- 重算触发：
  - 实体变更时：基于 `depends_on` 反向索引找到下游视图，增量重算
  - 定时全量：cron 表达式，默认每天一次
  - 手动触发：API 端点
- 查询路由：QueryService 优先查物化视图，未命中时实时计算
- Stale 警告：返回查询结果时附带 `is_stale: bool` 字段

**API**:
- 现有 Property CRUD 扩展计算相关字段
- `POST /api/ontology/materialization/views` — 创建物化视图
- `POST /api/ontology/materialization/views/{id}/recompute` — 触发重算
- `GET /api/ontology/materialization/views/{id}/status` — 视图状态
- `GET /api/ontology/computed/resolve?entity_id={id}&property={name}` — 查询计算属性

### FR-036: OntoFlow 目标导向演化 (Goal-driven Evolution)

**技术方案**:

- 升级 `odap/biz/core/ontology/engine/`:
  - `models/goal.py`: Goal(BaseModel)
    - `id`, `name`, `description`, `rationale`
    - `priority: Literal["low", "medium", "high", "critical"]`
    - `linked_requirements: List[str]` — 外部需求 ID
  - `models/change.py`: OntologyChange(BaseModel) 扩展：
    - `goal_id: str` — 关联目标
    - `rationale: str` — 变更理由
  - `services/change_service.py`: 强制要求 goal + rationale
- 前端：本体验证器 MUST 拒绝没有 `goal_id` 的变更
- 审计追踪：所有版本变更 MUST 可追溯到 `goal_id` → `linked_requirements`
- Goal 形式类似 ADR (Architecture Decision Record)

**API**:
- `POST /api/ontology/goals` — 创建 Goal
- `GET /api/ontology/goals?status={status}` — Goal 列表
- `PUT /api/ontology/goals/{id}` — 更新 Goal
- `GET /api/ontology/changes?goal_id={id}` — 按 Goal 查变更
- `GET /api/ontology/goals/{id}/impact` — 评估 Goal 影响的实例/规则

### FR-037: 对象视图 (Object View, Palantir 范式)

**技术方案**:

- 新增 `odap/biz/core/ontology/view/`:
  - `models/view.py`: ObjectView(BaseModel)
    - `id`, `name` (e.g., `commander-view`, `operator-view`)
    - `target_type_id: str` — 适用 Object Type
    - `included_properties: List[str]` — 暴露的属性白名单
    - `included_actions: List[str]` — 暴露的动作
    - `role_binding: List[str]` — 绑定角色
    - `redaction_rules: List[RedactionRule]` — 脱敏规则
  - `models/redaction.py`: RedactionRule(BaseModel) — 字段 + 脱敏方式 (mask/hash/partial/remove)
  - `impl/view_resolver.py`: ViewResolver — 给定 user + entity 返回可见属性
  - `services/view_service.py`: ViewService
- 前端：Object Type 设计器增加 View 编辑标签页
- View 与 OPA 关系：View 决定"展示什么"，OPA 决定"能否访问"，职责分离

**API**:
- `POST /api/ontology/views` — 创建 View
- `GET /api/ontology/views?target_type_id={id}` — View 列表
- `PUT /api/ontology/views/{id}` — 更新 View
- `DELETE /api/ontology/views/{id}` — 删除 View
- `GET /api/ontology/views/{id}/resolve?entity_id={id}&user_id={id}` — 解析用户可见属性
- `POST /api/ontology/views/{id}/bind-role` — 绑定角色

### Phase 4 交付物

- [ ] Data Health 引擎（完整性+一致性+漂移检测）
- [ ] 本体 Branch & Merge (git-like 语义 + PR/MR 评审 + 冲突解决)
- [ ] Object Type inherits + mixins (继承深度 ≤ 5)
- [ ] Action Type 一等公民 + Skill 分层 (1:N 绑定)
- [ ] 计算属性 (depends_on 声明 + 物化视图)
- [ ] OntoFlow goal-driven 演化 (强制 goal_id + rationale)
- [ ] Object View (跨角色属性隔离 + 脱敏)
- [ ] Phase 4 全部单元测试 (覆盖率 > 80%)
- [ ] 新 FR 的 API 契约文档 (contracts/core-ontology-p4.md)
- [ ] 宪法合规 (G-1..G-12) 全过

### Phase 4 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| Branch & Merge 冲突解决 UI 复杂 | 实施工作量大 | 高 | MVP 阶段只支持 JSON Patch 文本 diff；3-way 可视化推后 |
| 计算属性依赖图过大 | 增量重算性能差 | 中 | 维护依赖图 + 物化视图 + 限制 depends_on 链深度 ≤ 10 |
| Action Type 与现有 ToolRegistry 冲突 | 数据不一致 | 中 | 实施时先把现有 Tool 标记为 legacy，逐步迁移 |
| OntoFlow Goal 强制导致用户抵触 | 本体变更流程变重 | 中 | 提供 Goal 模板 + 快捷创建（默认 Goal "功能改进"） |
| Object View 性能开销 | 每次查询都需 resolve | 中 | 缓存 (Redis) + OPA 批量校验 |

---

## 前端重构计划

### 5 级组件体系实施

| 级别 | 名称 | 职责 | 示例 |
|------|------|------|------|
| L1 | Atoms（原子） | 最小不可拆分 UI 单元 | Button, Input, Badge, Tooltip, Icon |
| L2 | Molecules（分子） | 原子组合，有明确功能 | FormField, SearchBar, Card, Modal, Dropdown |
| L3 | Organisms（组织） | 分子组合，独立功能区块 | DataTable, FormPanel, GraphView, ChatPanel, MapView |
| L4 | Templates（模板） | 组织组合，页面布局骨架 | MasterDetail, SplitView, FullScreen, Dashboard |
| L5 | Pages（页面） | 模板+数据，完整页面 | OntologyDesigner, AgentChat, SimulationDeduction |

**实施步骤**:
1. 创建 `shared/components/adapter/` 隔离层：UIAdapter 接口 + AntDesignAdapter 实现
2. 创建 `shared/components/atoms/`：从 Ant Design 6 封装基础原子组件
3. 创建 `shared/components/molecules/`：组合原子组件
4. 创建 `shared/components/organisms/`：组合分子组件
5. 创建 `shared/components/templates/`：页面布局模板
6. 逐步迁移现有页面到 L5 级别

### 统一组件库创建

- 位置：`frontend/src/modules/shared/components/`
- 命名规范：PascalCase，与组件名一致
- 导出规范：每级 `index.ts` 统一导出
- 类型规范：所有组件 Props 使用 TypeScript 接口定义
- 样式规范：使用 CSS Variables + Ant Design Token 系统

### 组件库可替代性设计（隔离层）

- `shared/components/adapter/UIAdapter.ts`: 抽象接口
  - `getButton()`, `getInput()`, `getTable()`, `getModal()` 等
- `shared/components/adapter/AntDesignAdapter.ts`: Ant Design 6 实现
- 所有 L2+ 组件通过 UIAdapter 获取 L1 原子组件，不直接引用 Ant Design
- 替换组件库只需实现新的 Adapter

### 移动优先响应式（6 断点）

| 断点 | 名称 | 宽度 | 典型设备 |
|------|------|------|----------|
| xs | 极小 | < 576px | 手机竖屏 |
| sm | 小 | ≥ 576px | 手机横屏 |
| md | 中 | ≥ 768px | 平板竖屏 |
| lg | 大 | ≥ 992px | 平板横屏/小笔记本 |
| xl | 超大 | ≥ 1200px | 桌面 |
| xxl | 极大 | ≥ 1600px | 大屏桌面 |

- `shared/styles/breakpoints.ts`: 断点常量 + useResponsive Hook
- `shared/hooks/useResponsive.ts`: 响应式 Hook，返回当前断点信息
- CSS: 移动优先，min-width 媒体查询递进增强
- 布局：xs 单列 → sm 双列 → md 侧栏 → lg+ 完整布局

### i18n 基础设施

- 框架：react-i18next（research.md 课题3 决策）
- 文件组织：`modules/{name}/locales/{locale}/{name}.json`
- 共享翻译：`modules/shared/locales/{locale}/common.json`
- 运行时切换：Zustand store 管理当前语言
- 后端 API：`/api/i18n/translations` 管理翻译条目
- LLM 翻译：`/api/i18n/translations/auto-translate` 批量翻译

---

## OpenHarness 集成策略

### 进程内集成方案

- OpenHarness 作为 Python 包通过 `pip install -e ./openharness` 安装
- FastAPI 启动时在 lifespan 中初始化 OpenHarness（v1 + v2）
- 所有 OpenHarness 调用在同一进程内完成，无 IPC 开销
- Docker Compose 中无需独立 OpenHarness 容器

### 接口适配层设计

- `odap/infra/openharness/` 适配层：
  - `v2_adapter.py`: OpenHarness v2 初始化和生命周期管理
  - `swarm_adapter.py`: DomainSwarm 适配（OODA 循环编排）
  - `skill_adapter.py`: Skill 注册/发现适配
  - `memory_adapter.py`: Memory Plugin 适配（短期/工作/长期记忆）
  - `hook_adapter.py`: 生命周期钩子适配
  - `tool_adapter.py`: Tool 接口适配
  - `decision_engine.py`: 决策引擎适配
  - `llm_client.py`: LLM 客户端适配
  - `permission_backend.py`: 权限后端适配
  - `query_guard_hook.py`: 查询守卫钩子

### 独立性保证措施

1. **不 fork 核心代码**: OpenHarness 作为 Git Submodule 独立维护
2. **适配层隔离**: 所有 OpenHarness 调用通过 `odap/infra/openharness/` 适配层，业务代码不直接引用 OpenHarness
3. **封装隔离**: 适配层提供具体封装类，业务代码通过适配器调用 OpenHarness，不直接引用；适配器公共 API 保持稳定，OpenHarness API 变更时仅需更新适配器
4. **版本锁定**: requirements.txt 中锁定 OpenHarness 版本
5. **升级路径**: OpenHarness 官方升级时，仅需更新适配层，业务代码无感知

---

## Graphiti 双时态利用计划

### 本体版本管理

- **valid_time**: 用户指定的业务生效时间（"这个本体定义从什么时候开始有效"）
- **transaction_time**: 系统记录的实际变更时间（"这个变更什么时候被记录到系统中"）
- 版本创建：同时记录 valid_time 和 transaction_time
- 版本回滚：创建新版本记录回滚操作，valid_time 设为回滚生效时间
- 时序查询：`query_at_time(ontology_id, timestamp)` 查询任意时间点的本体状态
- 版本对比：基于双时态的版本差异计算

### 问答时序推理

- "当时发生了什么"类问题：基于 valid_time 查询历史状态
- "什么时候变成这样的"类问题：基于 transaction_time 查询变更时间
- "在 X 时间点的 Y 是什么状态"类问题：valid_time + transaction_time 联合查询
- 时序推理器：`temporal_reasoner.py` 封装 Graphiti 双时态查询

### 推演历史对比

- 推演结果存储：每次推演结果附带 valid_time（推演场景时间）和 transaction_time（推演执行时间）
- 推演对比：不同时间点的推演结果对比
- 推演回溯：查询历史推演结果和参数
- 决策推荐：基于历史推演结果的 RAG 增强推理

---

## 存储架构

### SQLite: 关系型数据

**用途**: 工作空间、角色、策略、审计日志、版本元数据、翻译条目、配置等

**规则**:
- 每次操作 `sqlite3.connect()` → 用完 `conn.close()`（无连接池）
- 复杂字段（Dict/List）→ JSON TEXT 列
- Enum → `.value` 字符串存储
- datetime → ISO 字符串存储
- 工作空间隔离：workspace_id 过滤

### Neo4j: 图谱数据

**用途**: 本体实例、关系实例、时序版本快照、推演结果、知识图谱

**规则**:
- 容器环境 URI: `bolt://graphiti-neo4j:7687`
- 工作空间隔离：节点 `workspace_id` 属性
- Graphiti 双时态：valid_time + transaction_time 自动管理
- 查询通过 QueryService 统一接口

### Redis: 缓存+会话

**用途**: 会话记忆（短期/工作记忆）、查询缓存、策略缓存、热数据缓存

**规则**:
- Key 前缀：`odap:{workspace_id}:{module}:{key}`
- TTL 策略：短期记忆 30min、工作记忆 2h、缓存 5min
- 连接：连接池，最大 50 连接

### MinIO: 对象存储（新增）

**用途**: 文档（PDF/Word）、图片、OCR 结果、二进制数据、导入导出文件

**规则**:
- Bucket 策略：每个工作空间一个 bucket（`ws-{workspace_id}`）
- 对象 Key：`{module}/{entity_type}/{entity_id}/{filename}`
- 预签名 URL：临时访问，有效期 1h
- 版本控制：启用对象版本管理

**Docker Compose 配置**:
```yaml
minio:
  image: minio/minio:latest
  ports:
    - "9000:9000"
    - "9001:9001"
  environment:
    MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
    MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-minioadmin}
  command: server /data --console-address ":9001"
  volumes:
    - minio_data:/data
```

---

## ADR 状态修正清单

| ADR | 当前状态 | 修正后状态 | 修正原因 |
|-----|----------|-----------|----------|
| ADR-030 | Accepted | Superseded | Spec 要求立即集成 OpenHarness，覆盖推迟决策 |
| ADR-036 | Accepted | Amended | 补充"借鉴 Palantir AIP 核心概念"说明 |
| ADR-037 | Accepted | Amended | 补充完整 i18n 实现（后台管理+LLM 翻译） |
| ADR-038 | Accepted | Amended | 补充本体模型层+本体管理引擎拆分说明 |
| ADR-043 | Accepted | Amended | 补充混合路由策略（规则优先+LLM 兜底） |
| ADR-047 | Accepted | Amended | 补充基于 OpenHarness Tool 接口实现 |
| ADR-048 | Accepted | Amended | 补充本体模型层拆分和 Palantir 参考 |
| ADR-049 | Accepted | Amended | 补充基于 OpenHarness 设计的依赖说明 |
| ADR-026 | Accepted | Amended | 补充基于 OpenHarness 实现 MCP 的依赖说明 |
| ADR-027 | Accepted | Amended | 补充基于 OpenHarness 生命周期钩子的依赖说明 |
| ADR-051 | Accepted | Amended | 补充基于 OpenHarness 外层封装的依赖说明 |
| ADR-029 | Accepted | Amended | 补充统一工具注册表基于 OpenHarness Tool 接口 |

---

## 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| OpenHarness API 不稳定或缺失功能 | Agent/MCP/Hook/Skill 集成受阻 | 中 | 适配层封装隔离，缺失功能自行补充并贡献上游 |
| Palantir 借鉴范围控制 | 借鉴范围可能扩大 | 低 | 严格限制在 Object Type/Property/Action/Rule 四层结构，不引入 Palantir 特有概念 |
| Graphiti 双时态查询性能 | 时序查询和版本对比慢 | 低 | 建立时间索引，缓存常用查询结果 |
| 前端重构范围大 | Phase 1 工期延长 | 中 | 优先完成基础设施（5 级体系+隔离层），页面逐步迁移 |
| MinIO 运维复杂度 | 部署和备份增加工作量 | 低 | Docker Compose 统一管理，复用现有备份策略 |
| 多方案并行推演资源消耗 | 服务器资源不足 | 中 | 限制并行度（最多 10），资源超限自动终止 |

## Complexity Tracking

| 违规项 | 为何需要 | 被拒绝的更简方案及原因 |
|--------|----------|----------------------|
| 借鉴 Palantir AIP 核心概念 | FR-001 要求借鉴 Palantir AIP 核心概念（Object Type/Property/Action/Rule） | 扁平本体模型无法支撑实体类型/属性/关系/约束的形式化定义和 OntologyDocument JSON 统一格式；但不严格对齐完整体系，仅借鉴四层结构 |
| 5 级组件体系 | spec 明确要求全项目统一组件库+可替代性设计 | 3 级组件体系无法满足可替代性隔离层要求，L4 模板层和 L5 页面层是可替代性设计的关键 |
| MinIO 对象存储 | FR-004 多模态数据接入需要非结构化存储 | SQLite BLOB 存储大文件性能差且不符合"不重复引入"原则（需独立存储引擎） |
| OpenHarness 适配层 | FR-005/014/016/017/018/022/024/025 均要求基于 OpenHarness | 直接调用 OpenHarness API 会导致业务代码与 OpenHarness 强耦合，违反独立性保证 |
