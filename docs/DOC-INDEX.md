# 文档索引（DOC-INDEX）

> **本文件由脚本生成，请勿手改。** 重新生成：`python scripts/doc_governance.py index`
> 真相源：各文档自身的 YAML front-matter（ADR-097 第 2 条）。
> 规则：`docs/DOC-GOVERNANCE-POLICY.yaml`。校验：`python scripts/doc_governance.py audit --ci`。

纳管文档 **288** 份，产物文件 **10** 份。

治理校验：error **0** / warn **17**

## 1. 状态图例

| status | 含义 |
|--------|------|
| authoritative | 该关注点的唯一权威，冲突时以此为准 |
| active | 现行有效，但非唯一权威 |
| proposed | 已提议未接受（ADR） |
| reference | 参考资料，不作实施依据 |
| superseded | 已被取代，保留作历史可追溯 |
| archived | 已归档，不再维护 |
| vendor | 第三方/导出内容，不纳入本项目治理 |

## L0 需求层（10）

| 文档 | 状态 | 归属 | 关注点 | 版本 | 取代/被取代 |
|------|------|------|--------|------|-------------|
| `PRD-v2.md` | authoritative | pm | product-requirements | 2.0.0 |  |
| `README.md` | active | pm | requirements | — |  |
| `SPEC-KB-DOC-MGMT.md` | active | pm | kb-doc-mgmt | — |  |
| `SPEC-v2.md` | authoritative | pm | dev-spec | 2.0.0 |  |
| `archive/req-alpha.md` | archived | pm | requirements | — |  |
| `archive/req-beta.md` | archived | pm | requirements | — |  |
| `backlog/待优化清单_2026-05-03.md` | reference | pm | requirements | — |  |
| `documents/前端功能实现与设计对比报告.md` | reference | pm | requirements | — |  |
| `documents/前端功能实现计划.md` | reference | pm | requirements | — |  |
| `req-ok.md` | authoritative | pm | requirements-scope | — |  |

## L1 产品设计层（4）

| 文档 | 状态 | 归属 | 关注点 | 版本 | 取代/被取代 |
|------|------|------|--------|------|-------------|
| `ODAP综合优化设计文档.md` | active | pm | product-design-optimization | — |  |
| `OPERATION_GUIDE.md` | active | pm | operation-guide | — |  |
| `README.md` | active | pm | product-design | — |  |
| `webui-enhancement-design.md` | reference | pm | webui-enhancement | — |  |

## L2 架构层（37）

| 文档 | 状态 | 归属 | 关注点 | 版本 | 取代/被取代 |
|------|------|------|--------|------|-------------|
| `ARCHITECTURE-v2.md` | authoritative | architect | architecture | 2.0 |  |
| `ARCHITECTURE.md` | superseded | architect | architecture | — | → `ARCHITECTURE-v2.md` |
| `ARCHITECTURE_ANALYSIS_REPORT.md` | reference | architect | architecture-analysis | — |  |
| `ARCHITECTURE_BIZ.md` | active | architect | architecture-biz | — |  |
| `ARCHITECTURE_EVOLVE.md` | reference | architect | architecture-evolution | — |  |
| `ARCHITECTURE_FOUR_STEPS.md` | reference | architect | four-steps-mapping | — |  |
| `ARCHITECTURE_FULL_CHAIN.md` | active | architect | architecture-full-chain | — |  |
| `ARCHITECTURE_INFRA.md` | active | architect | architecture-infra | — |  |
| `ARCHITECTURE_OPS.md` | active | architect | architecture-ops | — |  |
| `ARCHITECTURE_TARGET_PLAN.md` | reference | architect | architecture-target-plan | — |  |
| `ARCHITECTURE_TOOLS.md` | active | architect | architecture-tools | — |  |
| `ARCHITECTURE_WEB.md` | active | architect | architecture-web | — |  |
| `DEEP_REVIEW_REPORT_20260505.md` | reference | architect | architecture-review | — |  |
| `PHASE4_5_PLAN.md` | reference | architect | architecture-rollout-plan | — |  |
| `README.md` | active | architect | architecture | — |  |
| `REVIEW_REPORT_20260505.md` | superseded | architect | architecture-review | — | → `DEEP_REVIEW_REPORT_20260505.md` |
| `SCALABLE_ARCHITECTURE_2026.md` | active | architect | scalability | — |  |
| `SCALABLE_ARCHITECTURE_OVERVIEW.md` | reference | architect | scalability | — |  |
| `reports/ADR-065_BULKHEAD_AUDIT.md` | reference | architect | architecture | — |  |
| `reports/ANOMALY_REPORT.md` | reference | architect | architecture | — |  |
| `reports/ARCHITECTURE_PLAN_v4.0_归档.md` | reference | architect | architecture | — |  |
| `reports/ARCHITECTURE_REVIEW_20260423.md` | reference | architect | architecture | — |  |
| `reports/AUDIT_REPORT.md` | reference | architect | architecture | — |  |
| `reports/COMPLETENESS_REPORT.md` | reference | architect | architecture | — |  |
| `reports/RESEARCH_SEMANTICA_COMPARISON_2026-08-14.md` | reference | architect | architecture | — |  |
| `reports/RESEARCH_SEMANTICA_SOURCES_2026-10-28.md` | reference | architect | architecture | — |  |
| `reports/RESEARCH_TRUSTGRAPH_SEMANTICA_FIT_2026-10-28.md` | reference | architect | architecture | — |  |
| `reports/RESEARCH_TRUSTGRAPH_SOURCES_2026-10-28.md` | reference | architect | architecture | — |  |
| `reports/RESTRUCTURE_PLAN.md` | reference | architect | architecture | — |  |
| `reports/REVIEW_ONTOLOGY_PIPELINE_2026-10-03.md` | reference | architect | architecture | — |  |
| `reports/TEST_REPORT.md` | reference | architect | architecture | — |  |
| `reports/spike_engine_2026-08-16/REPORT.md` | reference | architect | architecture | — |  |
| `subsystems/AI_ASSISTANT_OPERATIONS_MANUAL_SCHEMA.md` | active | architect | architecture-subsystem | — |  |
| `subsystems/AI_ASSISTANT_PLATFORM_ONTOLOGY.md` | active | architect | architecture-subsystem | — |  |
| `subsystems/AI_ASSISTANT_STANDALONE.md` | active | architect | architecture-subsystem | — |  |
| `subsystems/AI_ASSISTANT_UNIFIED.md` | active | architect | architecture-subsystem | — |  |
| `subsystems/ONTOLOGY_SUBSYSTEM_BOUNDARY.md` | active | architect | architecture-subsystem | — |  |

## L3 模块设计层（32）

| 文档 | 状态 | 归属 | 关注点 | 版本 | 取代/被取代 |
|------|------|------|--------|------|-------------|
| `README.md` | active | module-owner | module-design | — |  |
| `agent/DESIGN.md` | active | module-owner | module-design | — |  |
| `api_gateway/DESIGN.md` | active | module-owner | module-design | — |  |
| `audit_log/DESIGN.md` | active | module-owner | module-design | — |  |
| `audit_log/GRAPHITI_INTEGRATION.md` | active | module-owner | module-design | — |  |
| `auth/DESIGN.md` | active | module-owner | module-design | — |  |
| `decision_recommendation/DESIGN.md` | active | module-owner | module-design | — |  |
| `event_simulator/DESIGN.md` | active | module-owner | module-design | — |  |
| `graphiti_client/DESIGN.md` | active | module-owner | module-design | — |  |
| `hook_system/DESIGN.md` | active | module-owner | module-design | — |  |
| `infra/DESIGN.md` | active | module-owner | module-design | — |  |
| `mcp_protocol/DESIGN.md` | active | module-owner | module-design | — |  |
| `ontology/DESIGN.md` | active | module-owner | module-design | — |  |
| `ontology_management_engine/DESIGN.md` | active | module-owner | module-design | — |  |
| `opa_policy/DESIGN.md` | active | module-owner | module-design | — |  |
| `openharness_bridge/DESIGN.md` | active | module-owner | module-design | — |  |
| `qa_engine/API.md` | active | module-owner | module-design | — |  |
| `qa_engine/DESIGN.md` | active | module-owner | module-design | — |  |
| `qa_engine/INTEGRATION.md` | active | module-owner | module-design | — |  |
| `semantic_admin/DESIGN.md` | active | module-owner | module-design | — |  |
| `semantic_admin/SEMANTIC_ASSET_DESIGN.md` | active | module-owner | module-design | — |  |
| `session_memory/DESIGN.md` | active | module-owner | module-design | — |  |
| `simulator/DESIGN.md` | active | module-owner | module-design | — |  |
| `skills/DESIGN.md` | active | module-owner | module-design | — |  |
| `swarm_orchestrator/DESIGN.md` | active | module-owner | module-design | — |  |
| `test/DESIGN.md` | active | module-owner | module-design | — |  |
| `tool_registry/DESIGN.md` | active | module-owner | module-design | — |  |
| `user_cognition_engine/DESIGN.md` | active | module-owner | module-design | — |  |
| `visualization/DESIGN.md` | active | module-owner | module-design | — |  |
| `visualization/DESIGN_GRAPH_OPTIMIZATION.md` | active | module-owner | module-design | — |  |
| `web_frontend/DESIGN.md` | active | module-owner | module-design | — |  |
| `workspace/DESIGN.md` | active | module-owner | module-design | — |  |

## L4 UI/UX 层（11）

| 文档 | 状态 | 归属 | 关注点 | 版本 | 取代/被取代 |
|------|------|------|--------|------|-------------|
| `05-ODAP-V2-DESIGN-SYSTEM.md` | superseded | designer | ui-design | — | → `UIUX-DESIGN-v2.md` |
| `COMPONENT_HIERARCHY.md` | reference | designer | component-hierarchy | — |  |
| `COMPONENT_SPEC.md` | active | designer | ontology-build-component-spec | — |  |
| `FRONTEND_COMPONENT_DESIGN.md` | active | designer | frontend-architecture | — |  |
| `I18N_DEV_GUIDE.md` | active | designer | i18n | — |  |
| `MOBILE_FIRST_DESIGN.md` | active | designer | mobile-first | — |  |
| `ONTOLOGY_BUILD_UI.md` | active | designer | ontology-build-ui | — |  |
| `README.md` | active | designer | ui-design | — |  |
| `TOKEN-MIGRATION-MAP.md` | active | designer | token-migration | — |  |
| `UIUX-DESIGN-v2.md` | authoritative | designer | ui-design | 2.0.0 |  |
| `UI_DESIGN.md` | superseded | designer | ui-design | — | → `UIUX-DESIGN-v2.md` |

## L5 安全层（2）

| 文档 | 状态 | 归属 | 关注点 | 版本 | 取代/被取代 |
|------|------|------|--------|------|-------------|
| `README.md` | active | architect | security | — |  |
| `SECURITY.md` | authoritative | architect | security | — |  |

## L6 DFX 层（4）

| 文档 | 状态 | 归属 | 关注点 | 版本 | 取代/被取代 |
|------|------|------|--------|------|-------------|
| `DFX_DESIGN.md` | authoritative | qa | dfx | — |  |
| `README.md` | active | qa | dfx | — |  |
| `TDD_BEHAVIOR_LIST.md` | active | qa | tdd-behavior | — |  |
| `TEST_DESIGN.md` | authoritative | qa | test-design | — |  |

## L7 决策记录层（100）

| 文档 | 状态 | 归属 | 关注点 | 版本 | 取代/被取代 |
|------|------|------|--------|------|-------------|
| `ADR-001_agent_基础设施openharness_langgraph.md` | active | architect | adr | — |  |
| `ADR-002_graphiti_作为双时态知识图谱.md` | active | architect | adr | — |  |
| `ADR-003_opa_策略治理引擎mvp_生产化.md` | active | architect | adr | — |  |
| `ADR-004_统一_skill_体系架构.md` | active | architect | adr | — |  |
| `ADR-005_分层_agent_架构openharness_原生_领域扩展.md` | active | architect | adr | — |  |
| `ADR-006_openharness_复用策略完全复用_适配复用_独立扩展.md` | active | architect | adr | — |  |
| `ADR-007_前端采用_react_ant_design_技术栈.md` | active | architect | adr | — |  |
| `ADR-008_审计日志完整记录.md` | active | architect | adr | — |  |
| `ADR-009_markdown_编写_opa_策略.md` | active | architect | adr | — |  |
| `ADR-010_多模态文档处理可配置.md` | active | architect | adr | — |  |
| `ADR-011_角色配置热生效.md` | active | architect | adr | — |  |
| `ADR-012_配置组合引擎.md` | active | architect | adr | — |  |
| `ADR-013_多数据源统一接入.md` | active | architect | adr | — |  |
| `ADR-014_技能热插拔架构.md` | active | architect | adr | — |  |
| `ADR-015_可扩展图表系统.md` | active | architect | adr | — |  |
| `ADR-016_完备文档体系.md` | active | architect | adr | — |  |
| `ADR-017_原子提交规范.md` | active | architect | adr | — |  |
| `ADR-018_domain_simulator_engine.md` | active | architect | adr | — |  |
| `ADR-019_多模态文档处理流水线.md` | active | architect | adr | — |  |
| `ADR-020_管理员控制台统一界面.md` | active | architect | adr | — |  |
| `ADR-021_qa_driven_ontology_building.md` | active | architect | adr | — |  |
| `ADR-022_模拟数仓与统一查询服务.md` | active | architect | adr | — |  |
| `ADR-023_多工作空间隔离架构.md` | active | architect | adr | — |  |
| `ADR-024_本体驱动分析核心架构.md` | active | architect | adr | — |  |
| `ADR-025_openharness_integration.md` | active | architect | adr | — |  |
| `ADR-026_mcp_protocol_integration.md` | active | architect | adr | — |  |
| `ADR-027_hook_system_architecture.md` | active | architect | adr | — |  |
| `ADR-028_permission_checker_opa_integration.md` | active | architect | adr | — |  |
| `ADR-029_tool_registry_architecture.md` | active | architect | adr | — |  |
| `ADR-030_phase1_推迟引入openharness_保留现有编排器.md` | active | architect | adr | — |  |
| `ADR-031_simulator_web_visualization_realtime_ontology.md` | active | architect | adr | — |  |
| `ADR-032_standard_ontology_document_format.md` | active | architect | adr | — |  |
| `ADR-033_项目目录结构重构.md` | superseded | architect | adr | — | → `ADR-066-monorepo-restructure.md` |
| `ADR-036_palantir_ontology_reference.md` | active | architect | adr | — |  |
| `ADR-037_frontend_mobile_first_i18n.md` | active | architect | adr | — |  |
| `ADR-038_本体管理引擎与用户认知引擎架构.md` | superseded | architect | adr | — | → `ADR-068_本体模块四层分层架构.md` |
| `ADR-039_qa_engine_architecture.md` | active | architect | adr | — |  |
| `ADR-040_api_gateway_unified_entry.md` | active | architect | adr | — |  |
| `ADR-041_workspace_resource_isolation.md` | active | architect | adr | — |  |
| `ADR-042_audit_log_storage_query.md` | active | architect | adr | — |  |
| `ADR-043_agent_router_semantic_routing.md` | active | architect | adr | — |  |
| `ADR-044_test_strategy_framework.md` | active | architect | adr | — |  |
| `ADR-045_frontend_visualization_g6_leaflet.md` | active | architect | adr | — |  |
| `ADR-046_modular_monolith_deployment.md` | active | architect | adr | — |  |
| `ADR-047_tool_registry_p0_phased_implementation.md` | active | architect | adr | — |  |
| `ADR-048_本体管理引擎架构决策.md` | superseded | architect | adr | — | → `ADR-068_本体模块四层分层架构.md` |
| `ADR-049_用户认知引擎架构决策.md` | superseded | architect | adr | — | → `ADR-068_本体模块四层分层架构.md` |
| `ADR-050_OADP业务语义体系架构.md` | active | architect | adr | — |  |
| `ADR-051_闭环反馈机制设计.md` | proposed | architect | adr | — |  |
| `ADR-052_webui_opensource_selection.md` | active | architect | adr | — |  |
| `ADR-053_skill_management_selection.md` | active | architect | adr | — |  |
| `ADR-054_规格与架构文档瘦身.md` | active | architect | adr | — |  |
| `ADR-055-统一查询服务.md` | active | architect | adr | — |  |
| `ADR-056-语义层修正.md` | superseded | architect | adr | — | → `ADR-061-semantic-admin-suite-architecture.md` |
| `ADR-057-domain-ontology-semantic-layer.md` | superseded | architect | adr | — | → `ADR-061-semantic-admin-suite-architecture.md` |
| `ADR-058-rbac-menu-management.md` | active | architect | adr | — |  |
| `ADR-059-dev-prod-environment-isolation.md` | active | architect | adr | — |  |
| `ADR-060-knowledge-base-document-storage.md` | active | architect | adr | — |  |
| `ADR-061-semantic-admin-suite-architecture.md` | active | architect | adr | — |  |
| `ADR-061_skill_plugin_packaging.md` | active | architect | adr | — |  |
| `ADR-062_graph_cqrs_tiering.md` | active | architect | adr | — |  |
| `ADR-063_tenant_aware_isolation.md` | active | architect | adr | — |  |
| `ADR-064_observability_baseline.md` | active | architect | adr | — |  |
| `ADR-065_microservice_extraction_playbook.md` | active | architect | adr | — |  |
| `ADR-066-monorepo-restructure.md` | active | architect | adr | — |  |
| `ADR-067_biz_shared_relocation.md` | active | architect | adr | — |  |
| `ADR-068_本体模块四层分层架构.md` | active | architect | adr | — |  |
| `ADR-069_统一AI助手与智能问答服务.md` | active | architect | adr | — |  |
| `ADR-070_基于OpenHarness全能力的AI助手架构.md` | active | architect | adr | — |  |
| `ADR-071_BuildResultContract_构建产物契约.md` | active | architect | adr | — |  |
| `ADR-072_ReasoningServiceContract_推理服务契约.md` | active | architect | adr | — |  |
| `ADR-073_基于本体的数据服务四步落地架构.md` | active | architect | adr | — |  |
| `ADR-074_情报驱动架构_HE与Graphiti正确定位及分层审计.md` | proposed | architect | adr | — |  |
| `ADR-075_确定性推理引擎引入.md` | active | architect | adr | — |  |
| `ADR-076_决策智能架构_决策作为一等公民对象.md` | active | architect | adr | — |  |
| `ADR-077_SHACL_OWL本体治理.md` | active | architect | adr | — |  |
| `ADR-078_图分析服务.md` | proposed | architect | adr | — |  |
| `ADR-079_本体论与LLM结合边界.md` | active | architect | adr | — |  |
| `ADR-080_ontology门面封装与分层契约.md` | active | architect | adr | — |  |
| `ADR-081_infra依赖倒置provider注册表.md` | active | architect | adr | — |  |
| `ADR-082_事件源与BI指标语义抽取入口.md` | active | architect | adr | — |  |
| `ADR-083_图谱实体软删除语义.md` | active | architect | adr | — |  |
| `ADR-084_open_typed双层事实模型与写路径不变量.md` | proposed | architect | adr | — |  |
| `ADR-085_SHACL形状持久化与写路径校验不变量.md` | active | architect | adr | — |  |
| `ADR-086_概念缺口回路.md` | active | architect | adr | — |  |
| `ADR-088_EvoOntology借鉴采纳_归因分层与配对回放门控.md` | active | architect | adr | — |  |
| `ADR-089_子项目C_ontology_semantics MCP工具_按需查询替代全量注入.md` | active | architect | adr | — |  |
| `ADR-090_子项目D_promote按attribution_layer路由_类型化编辑.md` | active | architect | adr | — |  |
| `ADR-091_语义发布生命周期与本体单一写入通道.md` | proposed | architect | adr | — |  |
| `ADR-092_icon-library-lock.md` | active | architect | adr | — |  |
| `ADR-093_design-token-theming.md` | active | architect | adr | — |  |
| `ADR-094_ontology-constraint-orchestration.md` | active | architect | adr | — |  |
| `ADR-095_intent-recognition-generalization.md` | active | architect | adr | — |  |
| `ADR-096_llm-wiki-storage-sync.md` | active | architect | adr | — |  |
| `ADR-097_docs-governance-provenance.md` | active | architect | adr | — |  |
| `ADR-098_frontend-compat-convergence.md` | active | architect | adr | — |  |
| `ADR-099_frontend-agent-protocol-agui.md` | active | architect | adr | — |  |
| `ADR-100_graph-render-stack-consolidation.md` | active | architect | adr | — |  |
| `ADR-101_决策主线贯通_决策台账与待决策队列.md` | active | architect | adr | — |  |
| `README.md` | active | architect | adr | — |  |

## L8 任务层（5）

| 文档 | 状态 | 归属 | 关注点 | 版本 | 取代/被取代 |
|------|------|------|--------|------|-------------|
| `MENU_DEDUP_PLAN.md` | reference | pm | menu-refactor | — |  |
| `MENU_REFACTOR_PLAN.md` | reference | pm | menu-refactor | — |  |
| `README.md` | active | pm | task-breakdown | — |  |
| `SCALABLE_TASK_BREAKDOWN.md` | active | pm | scalability-tasks | — |  |
| `TASK_BREAKDOWN.md` | authoritative | pm | task-breakdown | — |  |

## L9 检查层（5）

| 文档 | 状态 | 归属 | 关注点 | 版本 | 取代/被取代 |
|------|------|------|--------|------|-------------|
| `CHECKLIST_v2.md` | authoritative | qa | checklist | 2.0.0 |  |
| `DOC_SYNC_CHECKLIST.md` | active | qa | doc-sync | — |  |
| `README.md` | active | qa | checklist | — |  |
| `api-contract-matrix.md` | active | qa | api-contract-matrix | — |  |
| `contract-rulings.md` | authoritative | qa | contract-rulings | — |  |

## L10 契约层（5）

| 文档 | 状态 | 归属 | 关注点 | 版本 | 取代/被取代 |
|------|------|------|--------|------|-------------|
| `API_SPEC.md` | active | backend | ontology-build-api | — |  |
| `BACKEND_API_DESIGN.md` | active | backend | backend-api-design | — |  |
| `DATABASE_DESIGN.md` | active | backend | database-design | — |  |
| `INGEST_API_SPEC.md` | active | backend | ingest-api | — |  |
| `README.md` | active | backend | api-contract | — |  |

## L11 归档层（44）

| 文档 | 状态 | 归属 | 关注点 | 版本 | 取代/被取代 |
|------|------|------|--------|------|-------------|
| `ANTD_DEPRECATION_CLEANUP.md` | archived | archivist | archive | — |  |
| `ARCHITECTURE_PLAN_v4.md` | archived | archivist | archive | — |  |
| `CHECKLIST.md` | archived | archivist | archive | — |  |
| `CHECKLIST_v1.md` | archived | archivist | archive | — |  |
| `CODE_CLEANUP_LIST.md` | archived | archivist | archive | — |  |
| `README.md` | archived | archivist | archive | — |  |
| `VERIFICATION_REPORT.md` | archived | archivist | archive | — |  |
| `audit/ARCHITECTURE_AUDIT_2026-07-09.md` | archived | archivist | archive | — |  |
| `audit/REVIEW_REPORT_2026-07-08.md` | archived | archivist | archive | — |  |
| `audit/SLIMMING_REPORT_2026-07-08.md` | archived | archivist | archive | — |  |
| `feature-specs/2026-06-09-sanguo-ontology-and-agent-design.md` | archived | archivist | archive | — |  |
| `feature-specs/2026-06-15-nl-ontology-query-service-design.md` | archived | archivist | archive | — |  |
| `feature-specs/2026-06-15-ontology-semantic-extraction-unification-design.md` | archived | archivist | archive | — |  |
| `feature-specs/2026-06-16-hyper-extract-integration-design.md` | archived | archivist | archive | — |  |
| `feature-specs/2026-06-22-ohmo-channels-design.md` | archived | archivist | archive | — |  |
| `overview.md` | archived | archivist | archive | — |  |
| `specs/architecture-review-2026/checklist.md` | archived | archivist | archive | — |  |
| `specs/architecture-review-2026/spec.md` | archived | archivist | archive | — |  |
| `specs/architecture-review-2026/tasks.md` | archived | archivist | archive | — |  |
| `specs/battlefield-intelligence-system/checklist.md` | archived | archivist | archive | — |  |
| `specs/battlefield-intelligence-system/spec.md` | archived | archivist | archive | — |  |
| `specs/battlefield-intelligence-system/tasks.md` | archived | archivist | archive | — |  |
| `specs/checklist.md` | archived | archivist | archive | — |  |
| `specs/fix-web-interface/checklist.md` | archived | archivist | archive | — |  |
| `specs/fix-web-interface/spec.md` | archived | archivist | archive | — |  |
| `specs/fix-web-interface/tasks.md` | archived | archivist | archive | — |  |
| `specs/ontology-engine-by-qa/checklist.md` | archived | archivist | archive | — |  |
| `specs/ontology-engine-by-qa/spec.md` | archived | archivist | archive | — |  |
| `specs/ontology-engine-by-qa/tasks.md` | archived | archivist | archive | — |  |
| `specs/ontology-management-full链路/checklist.md` | archived | archivist | archive | — |  |
| `specs/ontology-management-full链路/spec.md` | archived | archivist | archive | — |  |
| `specs/ontology-management-full链路/tasks.md` | archived | archivist | archive | — |  |
| `specs/ontology-management-full链路/verification_checklist.md` | archived | archivist | archive | — |  |
| `specs/openharness-react-integration/checklist.md` | archived | archivist | archive | — |  |
| `specs/openharness-react-integration/spec.md` | archived | archivist | archive | — |  |
| `specs/openharness-react-integration/tasks.md` | archived | archivist | archive | — |  |
| `specs/spec.md` | archived | archivist | archive | — |  |
| `specs/storage-architecture-redesign/checklist.md` | archived | archivist | archive | — |  |
| `specs/storage-architecture-redesign/spec.md` | archived | archivist | archive | — |  |
| `specs/storage-architecture-redesign/tasks.md` | archived | archivist | archive | — |  |
| `specs/tasks.md` | archived | archivist | archive | — |  |
| `specs/update-battlefield-data-2026-us-iran-war/checklist.md` | archived | archivist | archive | — |  |
| `specs/update-battlefield-data-2026-us-iran-war/spec.md` | archived | archivist | archive | — |  |
| `specs/update-battlefield-data-2026-us-iran-war/tasks.md` | archived | archivist | archive | — |  |

## L12 评估层（2）

| 文档 | 状态 | 归属 | 关注点 | 版本 | 取代/被取代 |
|------|------|------|--------|------|-------------|
| `ARCHITECTURE-EVALUATION.md` | authoritative | pm | evaluation-architecture | — |  |
| `PRODUCT-EVALUATION.md` | authoritative | pm | evaluation-product | — |  |

## L13 决策登记（1）

| 文档 | 状态 | 归属 | 关注点 | 版本 | 取代/被取代 |
|------|------|------|--------|------|-------------|
| `OPEN-DECISIONS.md` | authoritative | architect | open-decisions | — |  |

## L15 设计规格存档（18）

| 文档 | 状态 | 归属 | 关注点 | 版本 | 取代/被取代 |
|------|------|------|--------|------|-------------|
| `plans/2026-09-25-event-source-bi-indicator-ol-entries.md` | reference | architect | design-spec-record | — |  |
| `plans/2026-09-27-persist-records-dry-refactor.md` | reference | architect | design-spec-record | — |  |
| `plans/2026-09-28-soft-delete-entity.md` | reference | architect | design-spec-record | — |  |
| `plans/2026-10-07-concept-gap-loop.md` | reference | architect | design-spec-record | — |  |
| `plans/2026-10-07-semantic-drift-detection.md` | reference | architect | design-spec-record | — |  |
| `specs/2026-07-16-monorepo-restructure-design.md` | reference | architect | design-spec-record | — |  |
| `specs/2026-07-16-monorepo-restructure-plan.md` | reference | architect | design-spec-record | — |  |
| `specs/2026-09-28-soft-delete-entity-design.md` | reference | architect | design-spec-record | — |  |
| `specs/2026-10-07-concept-gap-loop-design.md` | reference | architect | design-spec-record | — |  |
| `specs/2026-10-07-semantic-drift-detection-design.md` | reference | architect | design-spec-record | — |  |
| `specs/2026-10-08-evoontology-adoption-design.md` | reference | architect | design-spec-record | — |  |
| `specs/2026-10-09-subproject-c-ontology-semantics-tool-design.md` | reference | architect | design-spec-record | — |  |
| `specs/2026-10-09-subproject-d-promote-routing-design.md` | reference | architect | design-spec-record | — |  |
| `specs/2026-10-24-decision-mainline/architecture.md` | reference | architect | design-spec-record | — |  |
| `specs/2026-10-24-decision-mainline/prd.md` | reference | architect | design-spec-record | — |  |
| `specs/2026-10-24-decision-mainline/spec.md` | reference | architect | design-spec-record | — |  |
| `specs/2026-10-24-decision-mainline/uiux.md` | reference | architect | design-spec-record | — |  |
| `specs/2026-10-28-semantic-layer-workbench-design.md` | reference | architect | design-spec-record | — |  |

## L16 技能导出（2）

| 文档 | 状态 | 归属 | 关注点 | 版本 | 取代/被取代 |
|------|------|------|--------|------|-------------|
| `i18n-workflow/README.md` | vendor | vendor | vendor-skill | — |  |
| `i18n-workflow/SKILL.md` | vendor | vendor | vendor-skill | — |  |

## L14 文档中心（根）（6）

| 文档 | 状态 | 归属 | 关注点 | 版本 | 取代/被取代 |
|------|------|------|--------|------|-------------|
| `docs/ARCHITECTURE_AUDIT_FULL_2026-07-19.md` | reference | architect | architecture-analysis | — |  |
| `docs/ARCHITECTURE_AUDIT_ONTOLOGY_LAYERING_2026-07-18.md` | reference | architect | architecture-analysis | — |  |
| `docs/DOCUMENT_BASELINE_v1.0.0.md` | superseded | architect | doc-governance | — | → `DOCUMENT_MANAGEMENT.md` |
| `docs/DOCUMENT_MANAGEMENT.md` | authoritative | architect | doc-governance | 3.0.0 |  |
| `docs/DOCUMENT_RELATIONSHIP.md` | active | architect | doc-relationship | — |  |
| `docs/README.md` | reference | architect | doc-index | — |  |

