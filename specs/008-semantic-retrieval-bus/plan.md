# Implementation Plan: Semantic Retrieval Service Bus (语义检索服务总线)

**Branch**: `009-semantic-retrieval-bus` | **Date**: 2026-07-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/008-semantic-retrieval-bus/spec.md`
**Related ADR**: ADR-073 (基于本体的数据服务四步落地架构)

## Summary

为"用本体"阶段构建统一的语义检索服务总线，作为 AI Agent 和 BI 工具访问本体数据的统一入口。采用 **Facade + 薄适配器** 架构：新建 `biz/core/ontology/semantic_retrieval` 6 层 biz 模块，通过薄适配器复用现有 `QueryService`、`DeductionEngine`、`USL 术语映射`、`PipelineService`、`storage_audit` 等资产，对外暴露 `/api/semantic-retrieval/*` RESTful 路由组（三层：统一检索 / 分项检索 / 混合检索）和 MCP 工具集。

核心设计原则：**不重复造轮子**。新模块是编排层而非实现层——所有检索能力均通过适配现有服务实现，新模块只负责路由分发、请求归一化、结果合并、审计埋点。

## Technical Context

**Language/Version**: Python 3.11 (后端); 复用现有 FastAPI 应用，无前端改动
**Primary Dependencies**: FastAPI, Pydantic v2, neo4j-driver, SQLite (现有，无新增依赖)
**Storage**: Neo4j (ABox 图数据) + SQLite (元数据/审计) — 复用现有存储，不新建
**Testing**: pytest (现有 test 框架，含 `tests/unit/`、`tests/integration/`)
**Target Platform**: 现有 ODAP 模块化单体应用（ADR-046），Linux/Windows 容器部署
**Project Type**: web-service (modular monolith 新增 biz 模块)
**Performance Goals**: NL 查询 P95 ≤ 3s；BI 指标 P95 ≤ 5s（10 万级实例）；链式推理正确率 ≥ 90%
**Constraints**:
- MUST 复用现有 6 层 biz 模块结构（AGENTS.md L800-816）
- MUST NOT 引入新 DSL（复用 HE YAML + UModel 语法）
- MUST NOT 替换现有 `/api/reasoning/retrieve`（按 ADR-073 并存）
- 所有端点 MUST 强制认证 + workspace 隔离 + 审计（不记录查询内容）
- 默认过滤 `valid=false` 推演态 + `USL__Candidate` 候选态（FR-011）

## Constitution Check

*GATE: Must pass before proceeding. Re-check after design phase.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. 简单 | PASS | Facade + 薄适配器，每层函数单一职责。统一检索路由器用简单 strategy 选择器（按输入特征选引擎），不引入 ML 路由。函数体 ≤ 40 行约束。 |
| II. 可维护 | PASS | 6 层 biz 模块分层（api/services/impl/interfaces/models/storage）；依赖单向（infra ← biz ← api）；复用 `storage_audit` 统一审计；路由按领域模块注册。 |
| III. 测试优先 | PASS | TDD 应用于：路由分发逻辑、NL→术语映射、metric 聚合、chain 循环检测、hybrid 容错。新增端点配套集成测试（G-7/G-10）。 |
| IV. 避免过度设计 | NEEDS ATTENTION | ⚠️ 关键约束：MUST NOT 一次性建 5 个重引擎。分 3 Phase 交付，Phase 1 只建 P1 故事所需（NL + graph + metric）。不建单实现接口；统一路由器用 dict 查找而非抽象类工厂。 |

**NEEDS ATTENTION 缓解措施**：在任务拆解中强制 Phase 边界——Phase 1 仅实现 P1 故事（NL/BI），Phase 2 加 chain/mdl，Phase 3 加 hybrid/MCP。每个 Phase 独立可交付。

## Project Structure

### Documentation (this feature)

```text
specs/008-semantic-retrieval-bus/
├── spec.md                  # Feature specification
├── plan.md                  # This file
├── research.md              # Phase 0 研究结论
├── data-model.md            # 6 个核心实体
├── quickstart.md            # 运行/测试指南
├── checklists/
│   └── requirements.md      # 质量检查清单
└── contracts/
    └── api-contracts.md     # /api/semantic-retrieval/* REST 契约
```

### Source Code (repository root)

```text
apps/api/odap/biz/core/ontology/semantic_retrieval/   # 新增 biz 模块（6 层）
├── api/
│   └── routes.py            # /api/semantic-retrieval/* 路由组（强制认证）
├── models/
│   └── retrieval.py         # SearchRequest/SearchResult/SearchComponent 等 Pydantic 模型
├── interfaces/
│   └── i_retrieval_engine.py  # 检索引擎接口（仅当 >1 实现时才提取）
├── impl/
│   ├── unified_router.py    # 统一检索：按输入特征选择引擎（dict 策略表）
│   ├── graph_engine.py      # 图检索适配器 → 复用 QueryService.search_entities
│   ├── metric_engine.py     # 指标查询：TBox 自动派生统计（Phase 1）
│   ├── nl_engine.py         # NL 检索：USL 术语映射 + 图检索（Phase 1）
│   ├── chain_engine.py      # 链式推理适配器 → 复用 DeductionEngine（Phase 2）
│   ├── mdl_engine.py        # MDL/DSL 适配器 → 复用 HE YAML 模板（Phase 2）
│   └── hybrid_orchestrator.py  # 混合编排适配器 → 复用 PipelineService（Phase 3）
├── services/
│   └── retrieval_service.py  # 应用服务：编排引擎 + 审计 + workspace 过滤
└── storage/
    └── audit_log.py          # 检索审计（复用 storage_audit，仅统计不记内容）

apps/api/odap/biz/core/ontology/mcp/                 # MCP 工具注册（Phase 3，复用现有 bridge）
└── semantic_retrieval_tools.py  # ontology_query/ontology_reason/ontology_metric 工具

tests/
├── unit/
│   ├── test_unified_router.py
│   ├── test_graph_engine.py
│   ├── test_metric_engine.py
│   ├── test_nl_engine.py
│   ├── test_chain_cycle_detection.py
│   └── test_hybrid_orchestrator.py
└── integration/
    └── test_semantic_retrieval_routes.py
```

**Structure Decision**: 采用标准 6 层 biz 模块结构（AGENTS.md 规范）。`interfaces/` 层在 Phase 1 暂不创建（Constitution IV：不建单实现接口）；当 Phase 2 出现第二个引擎实现时再提取 `IRetrievalEngine` 接口。MCP 工具注册放在 `ontology/mcp/` 而非 `semantic_retrieval/` 内，因为 MCP 注册是平台级横切关注点，不属于单一 biz 模块。

## Execution Strategy

### TDD Requirements

- [x] **unified_router**: 路由分发逻辑有多种输入特征分支，需 TDD 锁定路由决策表
- [x] **nl_engine**: NL→术语映射有歧义和边界（无映射、多映射），需 TDD
- [x] **metric_engine**: 聚合统计有边界（空集、时间窗口、分页），需 TDD
- [x] **chain_engine 循环检测**: A→B→C→A 循环防护是安全关键逻辑，必须 TDD
- [x] **hybrid_orchestrator 容错**: 跳过/中止/降级策略需 TDD 覆盖三种失败模式

### Parallel Execution Opportunities

- [x] **graph_engine** 与 **metric_engine** 无共享文件，可并行开发（Phase 1）
- [x] **chain_engine** 与 **mdl_engine** 无共享文件，可并行开发（Phase 2）
- [x] **MCP 工具注册** 依赖 services 层稳定，须在 Phase 3 串行

### Human Checkpoints

1. Phase 1 完成后 — 验证 NL + BI 指标查询满足 P1 故事验收场景
2. Phase 2 完成后 — 验证链式推理循环检测和规则冲突处理
3. Phase 3 完成后 — 运行全套测试 + MCP 集成验证，对照 spec 全量验收
4. 合并前 — 最终 spec 对照审查（G-3 一致性、G-9 架构门）

### Review Gates

- [x] **api-contracts.md**: REST 契约须评审后再实现消费方
- [x] **audit_log 实现**: 审计不记录查询内容的安全约束须评审（FR-013）
- [x] **chain 循环检测**: 安全关键逻辑须评审

## Complexity Tracking

> Constitution Check 仅 1 项 NEEDS ATTENTION（非 VIOLATION），无需填表。缓解措施已写入 Execution Strategy 的 Phase 边界约束。

## Phasing (交付路线)

| Phase | 交付内容 | 对应 User Story | 依赖 |
|-------|---------|----------------|------|
| **Phase 1 (MVP)** | 模块骨架 + 统一检索 + graph/nl/metric 三引擎 | US1 (P1) + US2 (P1) | 无（复用现有 QueryService/USL） |
| **Phase 2** | chain 引擎 + mdl 引擎 | US3 (P2) | Phase 1；复用 DeductionEngine/HE 模板 |
| **Phase 3** | hybrid 编排 + MCP 工具注册 | US4 (P3) + US5 (P3) | Phase 1+2；复用 PipelineService/MCP bridge |
