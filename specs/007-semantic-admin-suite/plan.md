# Implementation Plan: 语义层管理后台 (Semantic Admin Suite)

**Branch**: `007-semantic-admin-suite` | **Date**: 2026-07-11 | **Spec**: [spec.md](file:///e:/DEMO/AI/ontology-graphiti/specs/007-semantic-admin-suite/spec.md)
**Input**: Feature specification from `specs/007-semantic-admin-suite/spec.md`

## Summary

构建语义层管理后台完整套件（**顶级 biz 域独立新模块，不嵌套在 core/ontology 内部**）：6 个子服务松耦合 —— 🧠 usl_manager（USL 统一语义层 6 张核心表 CRUD）、⚙️ ol_pipeline（L1~L6 流水线编排 3 张运行表）、🗃️ candidate_store（候选持久化 SQLite+Neo4j 双写）、🔐 approval_workflow（2 级审批 schema_auditor+admin，含 OPA Rego 策略）、🛡️ quality_gate（3 关 × 16 子指标：句法/语义/领域密度，含质量报告 2 张表）、♻️ usl_writeback（HITL 飞轮：已批准→USL+Ontology TBox 双写 + 回写状态推进）。配套 Neo4j 双写命名空间 `USL__Candidate` 节点与层级边、10 状态 Candidate 状态机、质量闸 4 档分层（HIGH/MEDIUM/LOW/VERY_LOW）、审批加速通道（Auditor 通过 + 总分 ≥ 0.7 跳过 Admin）。后端每个子服务内部严格遵循 AGENTS.md 7 层目录规范（api/models/interfaces/impl/services/storage）；前端 modules/semantic-admin 4 个顶级路由页（/usl /pipeline /candidates /quality）。

**总表数 = 11 张 SQLite 表**（6 USL + 3 Pipeline/Candidate + 2 Approval/Quality），无独立 Dashboard 快照表（质量面板查询直接从 quality_reports + approval_records 实时聚合，避免物化滞后）。

**Constraints（强制执行）**:
1. **不硬编码术语**：三国/西游等示例术语必须通过 seed migration 脚本写入，禁止在 Python 代码中直接写死字符串常量
2. **SQLite 存储层每次 connect/close**：storage 层每个方法独立 `sqlite3.connect()` → 执行 → `close()`，禁止跨方法复用连接，禁止全局单例连接
3. **服务层不抛 HTTPException**：services 层仅抛业务域异常（如 `DomainNotFoundError`、`InvalidTransitionError`），HTTPException 仅限 api/routes.py 层捕获后转换
4. **单元测试用 tmp_path 真实 DB 禁止 MagicMock**：所有涉及 DB 的单元测试必须使用 pytest `tmp_path` fixture 创建真实 SQLite 文件执行，禁止 `MagicMock` 替代 storage 层
5. **不允许空桩方法**：所有类方法（包括 interfaces/ 抽象基类的默认实现）必须有实际逻辑体，禁止 `pass` 或 `raise NotImplementedError` 留待后续

## Technical Context

**Language/Version**: Python 3.11 (Docker `python:3.11-slim`)
**Primary Dependencies**: FastAPI, Pydantic v2 (严格模式 `model_config = ConfigDict(strict=True)`), Neo4j Driver 5.x, SQLite3 (stdlib)
**Storage**: SQLite (11 张业务表 + seed migrations), Neo4j (`USL__*` 命名空间双写：`USL__Candidate` 节点 / `USL__L2_MEMBER_OF` 边 / `USL__IS_A_DRAFT` 边), MinIO (文档引用)
**Testing**: pytest 7+ (单元 + 集成), 要求 tmp_path 真实 DB、禁止 MagicMock 存储层
**Target Platform**: Docker 容器 (Podman 运行)，Linux 服务器部署
**Project Type**: web-service (FastAPI 后端 + React 19 前端，REST API + Ant Design Pro 组件)
**Performance Goals**: Candidate 列表查询分页 100 条 ≤ 100ms；质量闸 16 子指标计算 ≤ 500ms/候选；Dashboard 日快照物化 ≤ 2s/日
**Constraints**: 见上方 5 条强制执行约束；生产级实现无伪代码/空桩；术语 seed 化；SQLite 连接短命化；异常分层明确

## Constitution Check

*GATE: Must pass before proceeding. Re-check after design phase.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. 简单 | PASS | 6 个子服务**松耦合独立部署单元**（usl_manager/ol_pipeline/candidate_store/approval_workflow/quality_gate/usl_writeback），每个子服务只做一件事；状态机用纯函数 `next_status(current, event) → new` 实现；质量闸 16 子指标公式独立函数；无嵌套循环依赖 |
| II. 可维护 | PASS | 模块依赖单向：usl_manager ← ol_pipeline ← candidate_store ← quality_gate ← approval_workflow ← usl_writeback；每个子服务内部严格 7 层（storage←impl←interfaces←services←api）；无跨子服务直接 import storage 层 |
| III. 测试优先 | PASS | 8 个必须 TDD 单元（见下）；每个 storage 层全部 tmp_path 真实 SQLite；approval_workflow 的 OPA 策略用真实 opa eval CLI 验证（不 mock OPA）；状态机全路径 10 状态 × 事件矩阵覆盖 |
| IV. 避免过度设计 | PASS (post-design) | 11 张表全部追溯到 FR（6 USL→FR1-2；3 Pipeline→FR3；2 Approval/Quality→FR4-5）；10 状态机为三级审批 + 驳回重试 + 加速跳过最小必要；16 子指标每一项可单独 disable 且有权重可热更新 |

### 6 子服务 API 路径前缀映射（后端 routes.py 注册规范）

| # | 子服务 | 模块路径 | API 前缀 | 主要路由（示例） | 说明 |
|---|--------|----------|----------|----------------|------|
| 1 | 🧠 **usl_manager** | `odap/biz/semantic_admin/usl_manager/` | `/api/semantic-admin/usl/*` | `GET/POST /domains` · `GET/POST /terms` · `POST /hierarchy-edges` · `POST /property-specs` · `POST /cross-domain-mappings` | USL 6 张核心表 CRUD，含同义词/层级/属性/跨域映射 |
| 2 | ⚙️ **ol_pipeline** | `odap/biz/semantic_admin/ol_pipeline/` | `/api/semantic-admin/pipeline/*` | `POST /runs` · `GET /runs` · `GET /runs/{id}` · `POST /runs/{id}/retry` · `POST /runs/{id}/cancel` | OL L1~L6 流水线编排，3 张运行表；支持手动/定时/ingest_hook 触发 |
| 3 | 🗃️ **candidate_store** | `odap/biz/semantic_admin/candidate_store/` | `/api/semantic-admin/candidates/*` | `GET /`（列表+分页+筛选） · `GET /{id}` · `GET /{id}/graph-preview` · `GET /{id}/evidence` | 候选读服务（SQLite + Neo4j 双写由 ol_pipeline 内部触发，此处只查询） |
| 4 | 🛡️ **quality_gate** | `odap/biz/semantic_admin/quality_gate/` | `/api/semantic-admin/quality-gate/*` | `POST /evaluate` · `GET /candidates/{id}/report` · `GET /dashboard/metrics` · `GET /weights-config` | 3 关 ×16 子指标评估，质量报告存储，Dashboard 实时只读聚合层 |
| 5 | 🔐 **approval_workflow** | `odap/biz/semantic_admin/approval_workflow/` | `/api/semantic-admin/approvals/*` | `POST /candidates/{id}/audit` · `POST /candidates/{id}/final-approve` · `GET /candidates/{id}/history` · `POST /candidates/{id}/return-to-l2` | 2 级审批（schema_auditor + admin）+ 加速通道 + OPA Rego 权限策略 5 规则 |
| 6 | ♻️ **usl_writeback** | `odap/biz/semantic_admin/usl_writeback/` | `/api/semantic-admin/writeback/*`（内部路由，仅 approval 工作流调用） | `POST /candidates/{id}/write-approved` · `POST /candidates/{id}/write-rejected` · `GET /status` · `POST /retry/{id}` | HITL 飞轮写回：APPROVED → USL + Ontology TBox 双写，幂等 + 重试队列 |

> **路由注册约束（对齐 AGENTS.md 规则 1）**：以上 6 组路由必须全部在 `odap/web/app.py` 中通过各自子服务 `api/routes.py` 以 `include_router(prefix="/api/semantic-admin/xxx")` 方式独立注册；禁止合并到一个大 router 文件。

### Post-Design Re-evaluation

设计产物完成后（data-model.md + contracts/），重新评估宪法合规：
- **I. 简单**: 每个 service ≤ 12 个公共方法，单函数 ≤ 40 行；质量闸 `calculate_quality_score(candidate, reports)` 纯函数无副作用；状态机 `transition(curr, event, ctx)` 三参数纯函数 ✓
- **II. 可维护**: interfaces/ 层定义 `UslDomainRepository` 等抽象基类，storage/ 层做唯一实现，services 依赖接口不依赖实现；循环依赖扫描通过 ✓
- **III. 测试优先**: 8 个 TDD 文件清单已定义，每个文件 12+ 用例；storage 层 `test_*_storage.py` 全部 tmp_path 真实 SQLite；无 MagicMock 出现 ✓
- **IV. 避免过度设计**: Complexity Tracking 表证明 5 项复杂度每一项都有用户需求 + FR 编号支撑；无"未来可能用"的预留字段或接口 ✓

## Project Structure

### Documentation (this feature)

```text
specs/007-semantic-admin-suite/
├── spec.md              # Feature specification (用户故事 + 验收标准)
├── plan.md              # This file (实现计划 + 复杂度跟踪)
├── data-model.md        # Phase 1: 数据模型（11 张表 DDL + Neo4j Cypher + 10 状态机 + 质量闸公式）
├── quickstart.md        # Phase 1: 快速验证指南
├── research.md          # 调研资料
├── tasks.md             # Speckit 生成的任务清单
├── design/              # 🆕 可视化设计稿（浏览器直接打开，含 Mermaid + UI 原型）
│   ├── 01-architecture-planB.html          # 整体架构 + 4 Iter 总览 + 交付矩阵
│   ├── 02-iter1-usl-design.html            # Iter 1 详细设计（USL DDL/API/前端5Tab）
│   ├── 03-iter2-ol-pipeline-design.html    # Iter 2 详细设计（流水线/双写/7接口）
│   ├── 04-iter3-quality-approval-design.html # Iter 3 详细设计（质量闸/状态机/OPA/审核台UI）
│   └── 05-iter4-writeback-cleanup-design.html # Iter 4 详细设计（HITL写回/L3-L6/清理清单/质量面板）
├── checklists/
│   └── requirements.md    # 需求检查清单
└── contracts/           # 接口契约（供 TDD/代码生成/测试断言引用）
    ├── api-contracts.md         # REST API 完整契约
    ├── usl-manager.md           # usl_manager 服务 6 子服务契约
    └── quality-gate-approval.md # quality_gate + approval_workflow 契约
```

### Source Code (repository root — Backend 6 子服务松耦合 + 每个子服务内部 7 层)

```text
odap/biz/semantic_admin/             ← 顶级 biz 新域（与 core/decision/platform/data/simulation/management 并列，ODAP 第 8 大业务域）
├── __init__.py
│
├── 🧠 usl_manager/                  # 子服务 1: USL 规范术语管理 (6 张 USL 核心表 CRUD)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py                # /api/semantic-admin/usl/*  9 接口 (domains + terms + hierarchy + property-specs + disjoint-pairs + cardinality)
│   │   └── schemas.py               # CreateDomainReq / UpdateTermReq / etc.
│   ├── models/                      # Pydantic 领域模型
│   │   ├── usl_domain.py            # UslDomain (id/code/display_name/en_mapping_json)
│   │   ├── usl_term.py              # UslTerm (canonical/semantic_type/synonyms_json/near_syn_json/aliases_json/stoplist_flag)
│   │   ├── usl_hierarchy.py         # UslHierarchy (rel_type/parent_term/child_term/confidence)
│   │   ├── usl_property_spec.py     # UslPropertySpec (for_term/prop_name/data_type/unit/required_flag)
│   │   ├── usl_disjoint_pair.py     # UslDisjointPair (term_a/term_b/reason)
│   │   └── usl_cardinality.py       # UslCardinality (rel_name/domain_term/range_term/min_card/max_card)
│   ├── interfaces/
│   │   └── usl_repositories.py      # 6 个 ABC: UslDomainRepo / UslTermRepo / UslHierarchyRepo / UslPropertyRepo / UslDisjointRepo / UslCardinalityRepo
│   ├── impl/
│   │   ├── seed_sanguo_xiyou.py     # seed 迁移脚本：读取 semantic_config.py dict（只读一次，写入后标记 deprecated）
│   │   └── usl_query_engine.py      # 同义词 B 树匹配 / en_mapping 回退补全 / domain 过滤
│   ├── services/
│   │   └── usl_manager_service.py   # 编排层: create_term / add_hierarchy / merge_synonym / etc. → Dict[str, Any]
│   └── storage/
│       ├── __init__.py              # Storage = SqliteUslStorage（别名导出）
│       └── sqlite_usl_storage.py    # 6 张表 DAO（每次 connect/close）
│
├── ⚙️ ol_pipeline/                  # 子服务 2: L1~L6 流水线编排 (3 张运行表)
│   ├── api/
│   │   ├── routes.py                # /api/semantic-admin/pipeline/runs (POST/GET/POST {id}/retry)
│   │   └── schemas.py
│   ├── models/
│   │   ├── pipeline_config.py       # OLPipelineConfig (enabled_layers/fca_min_extent/...)
│   │   ├── pipeline_run.py          # PipelineRun (status/stats_json/...)
│   │   └── pipeline_layer_snapshot.py
│   ├── interfaces/
│   │   └── ol_stage.py              # OLStage 抽象基类（run(input) → output），L1~L6 全部继承
│   ├── impl/
│   │   ├── l1_usl_align_stage.py    # L1-1 USL 对齐 + L1-2 规范化 + L1-3 词性筛选
│   │   ├── l2_embed_cluster_stage.py # L2-1 BGE Embedding + L2-2 HDBSCAN 余弦聚类 + L2-3 语义类型推断
│   │   ├── l3_fca_taxonomy_stage.py # L3 FCA 形式概念分析（Iter4 实现）
│   │   ├── l4_relation_extract_stage.py # L4 关系三元组抽取 + SchemaTypeFilter（Iter4）
│   │   ├── l5_schema_fusion_stage.py    # L5 Embedding+结构+规则三层判同（Iter4）
│   │   ├── l6_axiom_inductor_stage.py   # L6 Apriori 关联规则（Iter4，默认跳过）
│   │   └── pipeline_orchestrator.py # PipelineOrchestrator（asyncio.create_task 异步编排 + 幂等重试）
│   ├── services/
│   │   └── pipeline_service.py
│   └── storage/
│       ├── __init__.py
│       └── sqlite_pipeline_storage.py # 3 张表: usl_pipeline_runs / usl_schema_candidates / usl_pipeline_layer_snapshots
│
├── 🗃️ candidate_store/              # 子服务 3: Candidate 双写 (SQLite ↔ Neo4j，复用 ol_pipeline 之 SQLite 表)
│   ├── api/
│   │   ├── routes.py                # /api/semantic-admin/candidates (GET list/{id}/{id}/graph-preview)
│   │   └── schemas.py
│   ├── models/                      # 复用 ol_pipeline 中 SchemaCandidate/... 模型
│   ├── interfaces/
│   │   └── dual_writer.py           # DualWriter ABC (write_nodes/write_edges/fail_rollback)
│   ├── impl/
│   │   └── neo4j_schema_graph_writer.py # Neo4j 双写（USL__Candidate 节点 + USL__L2_MEMBER_OF/USL__IS_A_DRAFT 边）
│   ├── services/
│   │   └── candidate_service.py     # 搜索/分页/详情/Cytoscape JSON 图谱预览
│   └── storage/                     # 复用 ol_pipeline storage（SQLite 为主，Neo4j 为从，降级策略）
│
├── 🛡️ quality_gate/                 # 子服务 4: 3 关 × 16 子指标质量闸
│   ├── api/
│   │   ├── routes.py                # POST /quality-gate/evaluate + GET candidates/{id}/quality-report
│   │   └── schemas.py
│   ├── models/
│   │   └── quality_report.py        # QualityReport (gate1/2/3_score + details JSON + total_score + tier)
│   ├── interfaces/
│   │   └── gate.py                  # Gate ABC (evaluate(candidate, ctx) -> score, details)
│   ├── impl/
│   │   ├── gate1_syntactic_impl.py  # G1 × 7 子项: 名称合规/en_mapping可用/semantic_type枚举/同义词大小/去重率/环检测/USL冲突
│   │   ├── gate2_semantic_impl.py   # G2 × 4 子项: Disjoint不相交/基数约束/is_a无环/LLM语义一致性Judge(默认关)
│   │   ├── gate3_domain_impl.py     # G3 × 5 子项: 属性密度/词频覆盖率/同义词丰富度/USL对齐率(反向新颖度)/层级贡献度
│   │   ├── quality_calculator.py    # 线性加权 total = 0.35*G1 + 0.40*G2 + 0.25*G3 + 4 档 Tier 分层
│   │   └── weight_config.py         # Pydantic BaseSettings（权重可热更新，不从代码硬编码）
│   ├── services/
│   │   └── quality_report_service.py # 批量 evaluate + 写入 quality_reports 表（100ms/候选性能目标）
│   └── storage/
│       ├── __init__.py
│       └── sqlite_quality_storage.py # 1 张表: usl_quality_reports
│
├── 🔐 approval_workflow/            # 子服务 5: 2 级审批 + OPA 策略
│   ├── api/
│   │   ├── routes.py                # POST candidates/{id}/audit | POST candidates/{id}/final-approve | GET candidates/{id}/approval-history
│   │   └── schemas.py
│   ├── models/
│   │   └── approval_record.py       # ApprovalRecord (action/before_status/after_status/review_score/comment/changes_json)
│   ├── interfaces/
│   │   └── state_machine.py         # CandidateStateMachine ABC（next_status(current, event) → new, ValueError on illegal）
│   ├── impl/
│   │   ├── candidate_state_machine.py # 10 状态纯函数实现 (DRAFT→L1_DONE→L2_DONE→PENDING_REVIEW→AUDITOR_*→ADMIN_PENDING/APPROVED→REJECTED→WRITTEN_BACK/STOPLISTED)
│   │   ├── semantic_admin.rego      # OPA Rego 策略 5 大规则: audit_candidate/final_approve/auto_approve_skip_admin/read_quality_report + deny(MODIFY/REJECT无comment)
│   │   └── permissions.py           # FastAPI Depends 两个钩子: verify_schema_auditor / verify_final_approve（调用 OPA）
│   ├── services/
│   │   └── approval_service.py      # 推进状态 + 写 approval_records；触发加速通道(AUDITOR_APPROVED+total≥0.7 自动跳过 ADMIN_PENDING)
│   └── storage/
│       ├── __init__.py
│       └── sqlite_approval_storage.py # 1 张表: usl_approval_records
│
└── ♻️ usl_writeback/                # 子服务 6: HITL 飞轮写回（APPROVED → 双写 USL + Ontology TBox）
    ├── api/
    │   ├── routes.py                # 内部路由（由 approval Workflow 触发，一般不对外暴露）
    │   └── schemas.py
    ├── interfaces/
    │   └── writeback_handler.py     # WritebackHandler ABC (write_approved/write_rejected)
    ├── impl/
    │   ├── writeback_service_impl.py # 2 个幂等函数: write_approved(cand_id) + write_rejected(cand_id, reason)
    │   ├── ontology_tbox_writer.py    # 调用 biz/core/ontology/ API POST /ontologies/{oid}/object-types ...
    │   └── hook_event_emitter.py      # 通过 biz/integration/hook_system 广播 schema_candidate.written_back 事件
    ├── services/
    │   └── writeback_service.py    # 编排: 先写USL(成功)→再写Ontology(失败标记NOT_WRITTEN_BACK+重试)→回写candidate状态→更新面板
    └── storage/                     # 复用 usl_manager/approval_workflow 的 storage，不新起表
```


### Source Code (repository root — Frontend modules 目录)

```text
frontend/src/modules/semantic-admin/  (新增语义层管理后台前端模块)
├── pages/
│   ├── DomainManagement.tsx         # 域管理页（列表 + 新建 + 编辑抽屉）
│   ├── TermManagement.tsx           # 术语管理页（树状层级 + 搜索）
│   ├── HierarchyEditor.tsx          # 层级编辑器（拖拽 L1/L2 关系）
│   ├── PropertySpecPanel.tsx        # 属性规范面板
│   ├── DisjointCardinality.tsx      # 不相交对 + 基数配置
│   ├── CandidatePipeline.tsx        # 候选流水线（列表 + 详情 + 10 状态时间线）
│   ├── ApprovalCenter.tsx           # 审批中心（Auditor 视图 + Admin 视图 + 加速通道标识）
│   ├── QualityGateView.tsx          # 质量闸 3 关 16 子指标详情 + 得分雷达图
│   └── SemanticDashboard.tsx        # Dashboard 日快照物化指标趋势图
├── components/
│   ├── DomainFormDrawer.tsx
│   ├── TermTree.tsx
│   ├── HierarchyDnDPanel.tsx
│   ├── PropertySpecForm.tsx
│   ├── CandidateStatusTimeline.tsx  # 10 状态可视化
│   ├── QualityRadarChart.tsx        # 16 子指标雷达图
│   ├── ApprovalFlowDiagram.tsx      # 审批流程（加速通道高亮）
│   └── DashboardMetricCard.tsx
├── hooks/
│   ├── useCandidateStateMachine.ts  # 前端状态机校验（与后端同矩阵）
│   ├── useQualityCalculator.ts      # 前端预览质量得分（仅 UI 辅助，最终以后端为准）
│   └── useDualWriteStatus.ts        # Neo4j 双写状态轮询
├── services/
│   ├── semanticApi.ts               # 全部 REST API 封装（12 组端点）
│   └── semanticApi.test.ts          # Vitest + apiMock
├── stores/
│   ├── semanticStore.ts             # Zustand 全局状态（当前域/选中术语/候选筛选条件）
│   └── semanticStore.test.ts
├── types/
│   └── index.ts                     # TypeScript 类型（对齐后端 Pydantic 模型）
├── locales/
│   ├── zh-CN/semantic-admin.json
│   └── en-US/semantic-admin.json
└── index.ts
```

**Structure Decision**：语义管理后台作为**顶级 biz 域独立新模块 `odap/biz/semantic_admin/`**（与 `core/decision/platform/data/simulation/management` 并列，ODAP 第 8 大业务域），内部拆 6 个松耦合子服务（usl_manager / ol_pipeline / candidate_store / quality_gate / approval_workflow / usl_writeback）。不嵌套在 `core/ontology/design/schema/semantic_layer/` 里的三个理由：
1. **职责解耦**：AGENTS.md 定义 `biz/core/ontology/` 只管 Ontology 本体定义（TBox CRUD + 版本 + 图谱），而 USL（统一语义层）是跨领域的"语义规范总线"，不只服务于 ontology，还服务于 Hyper-Extract、QA 问答、数据校验等多模块，应独立为顶级域；
2. **依赖方向正确**：如果放在 ontology 内部，usl_manager 会被 `biz/data/hyper_extract/` / `biz/data/qa/` 等反向 import，形成 `data → core` 的反向依赖环（违反 onion 架构：`infra ← core ← biz/data`）。顶级独立域后，依赖方向变为 `ol_pipeline → hyper_extract(正向)`、`qa/nl_pipeline → usl_manager(正向)`，无环；
3. **与前端路由对齐**：前端 `/semantic-admin` 为顶级路由（4 个页面：/usl /pipeline /candidates /quality），后端模块路径与前端路由前缀一一对应，新人上手找代码零猜测。

## Execution Strategy

### TDD Requirements (8 个必须 TDD 单元)

- [ ] **SqliteUslStorage (Domain/Term/Hierarchy/Property/Disjoint/Cardinality)**: 6 张 USL 表 CRUD + UNIQUE 约束 + 分页查询，tmp_path 真实 SQLite，验证 connect/close 每调用独立（检查 `_conn_count` 递增）
- [ ] **CandidateStateMachine**: 10 状态 × 事件矩阵全路径覆盖，包括 AUDITOR_MODIFIED 回退、AUDITOR_REJECTED→REJECTED→STOPLISTED 链路、加速通道触发条件（AUDITOR_APPROVED + total≥0.7 跳过 ADMIN_PENDING）
- [ ] **QualityCalculator.16 子指标**: 每个子指标独立用例（含边界：null/空集合/除零），3 关加权公式 + 4 档分层阈值正确性验证（HIGH≥0.85 等）
- [ ] **ApprovalService**: 两级审批正常路径 + 加速通道触发 + 驳回回退 + 修改后重提，验证不抛 HTTPException（仅抛业务异常）
- [ ] **Neo4jDualWriter**: Mock Neo4j Driver（仅此处允许 Mock，因为外部依赖）验证 USL__Candidate 节点 MERGE + USL__L2_MEMBER_OF 边 + USL__IS_A_DRAFT 边的正确 Cypher
- [ ] **SqliteCandidateStorage (3 张表)**: PipelineRun 状态变更、SchemaCandidate 10 状态持久化、PipelineLayerSnapshot JSON 序列化/反序列化，tmp_path 真实 DB
- [ ] **SqliteQualityStorage + SqliteApprovalStorage (合计 2 张表)**: ApprovalRecord 多版本（同一 candidate_id 多次审批）查询；QualityReport G1/G2/G3 细节 JSON 存储 + 按关聚合查询；Dashboard 指标从 quality_reports + approval_records 实时聚合（不物化，用 SQLite 日期函数 + 覆盖索引保障 ≤ 1s），并在 quality_gate/services/dashboard_query_service.py 提供只读聚合层

### Parallel Execution Opportunities

- [ ] **6 个后端子服务**（usl_manager / ol_pipeline / candidate_store / quality_gate / approval_workflow / usl_writeback）之间通过接口层（interfaces/）做契约，无跨子服务直接 import storage，可 3-4 人并行（usl_manager + candidate_store 一人、ol_pipeline + quality_gate 一人、approval_workflow + usl_writeback 一人、前端独立一人）
- [ ] **QualityGate 3 关（Gate1/2/3）+ DashboardQueryService** 可并行（质量关写 quality_reports 表，DashboardQueryService 只读聚合，无循环）
- [ ] **Frontend semantic-admin 模块** 可在 API 契约（contracts/*.md）冻结后与后端并行开发，使用 Vitest + apiMock
- [ ] **Seed 迁移脚本**（`usl_manager/impl/seed_sanguo_xiyou.py`，不拆 4 个 .sql 文件——以 Python 读原 semantic_config.py dict 并通过 SqliteUslStorage 写入，保留所有 UNIQUE 冲突幂等）可与任何代码并行

### Human Checkpoints (5 项)

1. **术语 seed 化审查** — 全量 grep `三国\|西游\|刘备\|孙悟空` 等示例词，确认仅出现在 `semantic_admin/usl_manager/impl/seed_sanguo_xiyou.py`（只读 import 原 semantic_config.py dict 后写库），Python/TS 其他文件零出现（test/fixture 除外）
2. **SQLite connect/close 审查** — 静态检查 5 个 storage 实现（`sqlite_usl_storage.py` / `sqlite_pipeline_storage.py` / `sqlite_quality_storage.py` / `sqlite_approval_storage.py` / 复用层），每个方法首行 `connect()`、末行 `close()`，无 `self.conn` 成员变量；5 个文件都要过
3. **状态机全路径走查** — 对照 data-model.md 10 状态图，现场演示至少 5 条路径：正常通过全链路 / 加速通道 / Auditor 驳回后修改重提 / Auditor 拒绝后加入黑名单 / Admin 打回 L2
4. **质量闸阈值交叉验证** — 人工计算 3 组示例候选数据的 16 子指标得分与代码 TDD 结果比对，误差 ≤ 1e-6
5. **前后端类型对齐** — TypeScript `types/index.ts` 与后端 Pydantic 模型逐字段 diff（字段名、类型、可空性、枚举值），无偏差

## §4 Acceptance Checklist（验收清单 · P0 必打勾）

### §4.1 Backend Group 1: Interfaces + Storage 契约（12 项）

- [ ] **IF-01**：7 子服务（usl_manager / ol_pipeline / candidate_store / quality_gate / approval_workflow / usl_writeback / sa_config）均存在独立 `interfaces/` 目录且导出非空 `__all__`
- [ ] **IF-02**：跨子服务禁止直接 import `.storage.*` — 通过 `interfaces/` ABC 注入（grep `from odap.biz.semantic_admin.\w+\.storage` 除 `__init__.py` 顶层导出外应为 0）
- [ ] **IF-03**：`UslRepository` 6 实体 CRUD 全部实现 — 无未实现的 `raise NotImplementedError` 路径（仅 interfaces 层允许）
- [ ] **IF-04**：`CandidateRepository` Protocol 覆盖 4 核心方法（get_candidate / update_status / list_pending_review / count_by_status）
- [ ] **ST-01**：5 个 SQLite Storage 类（Usl / Candidate / Pipeline / Quality / Approval）每方法首 `connect()` 末 `close()`，无 `self.conn` 成员
- [ ] **ST-02**：JSON 字段（Dict/List）存 `TEXT` + `json.loads()` 异常容错（非法 JSON 回默认空）
- [ ] **ST-03**：Enum 存 `.value` 字符串；datetime 存 `.isoformat()`
- [ ] **ST-04**：分页查询返回 `(List[T], int)`；page/page_size ≤ 0 时 ValueError
- [ ] **ST-05**：删除不存在的对象返回 `False`，不抛异常
- [ ] **ST-06**：所有 USL UNIQUE 冲突（domain.code / (domain_id, canonical) / 不相交对 / 基数等）均为 upsert，不抛 IntegrityError
- [ ] **ST-07**：SqliteXxxStorage 测试均使用 `tmp_path` 真实 `.db` 文件，禁用 MagicMock DB
- [ ] **ST-08**：`storage/__init__.py` 均执行 `Storage = SQLiteXxxStorage` 别名导出

### §4.2 Backend Group 2: Services + State Machine（14 项）

- [ ] **SVC-01**：所有 `services/` 返回 `Dict[str, Any]`，错误返回 `{"status": "error", "message": "..."}`，禁止抛 HTTPException
- [ ] **SVC-02**：`routes.py` 所有 `except` 块首行 `except HTTPException: raise` 透传，防止 500 兜底
- [ ] **SVC-03**：所有 Enum 采用 `(str, Enum)` 双继承（grep `class.*\(Enum\):` 排除含 `str,` 应为 0）
- [ ] **SVC-04**：容器字段全部 `Field(default_factory=list|dict|set)`，零 `= []/{}`
- [ ] **SVC-05**：`CandidateStateMachine` 10 状态 × 事件矩阵全路径覆盖，非法事件抛 ValueError
- [ ] **SVC-06**：加速通道（AUDITOR_APPROVED + total≥0.7）正确跳过 ADMIN_PENDING
- [ ] **SVC-07**：QualityCalculator 16 子指标 4 档 TIER 分层阈值（A≥0.85/B≥0.70/C≥0.55）与加权 0.35/0.40/0.25 完全匹配 spec
- [ ] **SVC-08**：`except Exception` 全部带日志（logger.warning/error），零 `pass` 静默
- [ ] **SVC-09**：OPA 策略 5 大规则（audit_candidate/final_approve/auto_skip/quality_report + deny MODIFY/REJECT 无 comment）全部在 Rego 中落地
- [ ] **SVC-10**：WritebackService 双写通道（A: GraphWriteProxy + B: GraphManager）独立事务，B 失败不阻塞 A（记 warning）
- [ ] **SVC-11**：7 子服务 `services/` 均为模块级单例（`xxx_service = XxxService()`），非每次请求 new
- [ ] **SVC-12**：`odap/web/app.py` 已 include_router 所有 semantic_admin 7 子路由
- [ ] **SVC-13**：`odap/biz/semantic_admin/__init__.py` 顶层 __all__ ≥ 10 个公开类（7 Service + 2 Storage + 1 Dashboard）
- [ ] **SVC-14**：DashboardQueryService 聚合查询（summary/terms-trend/approvals-breakdown）单请求耗时 ≤ 1s（SQLite 覆盖索引验证）

### §4.3 Backend Group 3: Pipeline + API 契约（10 项）

- [ ] **API-01**：OL 6 层（L1~L6）每层独立 `execute_layer(context) -> LayerResult`，接口在 `ol_pipeline/interfaces/pipeline_steps.py`
- [ ] **API-02**：Pipeline 状态机 DRAFT → RUNNING → L1_DONE → L2_DONE → L3_DONE → L4_DONE → L5_DONE → L6_DONE → COMPLETED / FAILED 合法，非法转换 ValueError
- [ ] **API-03**：`/api/semantic-admin/pipeline/runs/{id}/advance` 和 `/execute-all` 正确推进 layer_status JSON
- [ ] **API-04**：候选 5 个 API（create / list / get / update-status / approve / reject / promote-to-usl）均走 CandidateRepository 抽象，无跨 storage import
- [ ] **API-05**：审批 5 方法（audit / modify / reject / final_approve / auto_skip_admin）全部在 `approval_service.py` 落地
- [ ] **API-06**：质量闸报告 `/quality-gate/reports/{cand_id}` 含 3 关 16 子指标，字段名与 types/index.ts 完全对齐
- [ ] **API-07**：USL 写回 `/writeback/candidates/{id}` + `/writeback/status/{id}` 返回 dual_write 状态（A/B 通道独立 OK/FAIL）
- [ ] **API-08**：sa_config `/{scope}/{key}` / `/domain/{domain_code}` / `/ensure-builtin` 三读一写 API 全部存在
- [ ] **API-09**：C1/C2/C3/C4/C5/C6/D 系列 API（AGENTS.md §附录 E 列出的全部 semantic_admin 路径）在 `odap/web/app.py` 注册且 OpenAPI 文档可见
- [ ] **API-10**：所有错误响应 Pydantic `ErrorResponse`（含 `detail` 字段），无裸露 traceback 返回给前端

### §4.4 Frontend（10 项）

- [ ] **FE-01**：6 个顶层 Tab（USL / Pipeline / Candidates / Quality / Dashboard / Approvals）均在 `constants.tsx` + `AppRoutes.tsx` 注册
- [ ] **FE-02**：AdminTopTab 类型 含 'approvals'；TOP_TAB_TO_PATH / PATH_TO_TOP_TAB 双向映射无缺
- [ ] **FE-03**：CandidatesPage 集成 approvalApi（listApprovalTasks / audit / modify / reject / final_approve），按钮按 level 分流（L1: schema_auditor / L2: final_approver）
- [ ] **FE-04**：QualityDashboardPage 调 Dashboard 3 API + 4 KPI 卡 + 4 ECharts，store 缓存 5 分钟
- [ ] **FE-05**：CandidatesComingSoon / PipelineComingSoon / QualityComingSoon 均不导出（index.ts 零 ComingSoon export）
- [ ] **FE-06**：跨 src 一级目录 import 全用 `@/modules/xxx`（grep `from '\.\./\.\./` 非本模块内应为 0）
- [ ] **FE-07**：`approvalApi.ts` / `uslApi.ts` / `pipelineApi.ts` / `qualityApi.ts` / `saConfigApi.ts` 5 个服务文件均非空
- [ ] **FE-08**：Zustand store `useSemanticAdminStore` 缓存 pipelineRuns / candidates / dashboardSummary 3 层
- [ ] **FE-09**：`ApprovalsPage` 组件（或 CandidatesPage 的 approvals 视图）存在且路由 `/semantic-admin/approvals` 可访问
- [ ] **FE-10**：`npm run lint` + `npm run typecheck` 在 semantic-admin 模块无新增 error

### §4.5 Ops（9 项）

- [ ] **OPS-01**：`python bootstep.py dev` 启动后 `graphiti-main-app` 容器状态为 `(healthy)`
- [ ] **OPS-02**：README.md 无 `python main.py --web` 或 `cd frontend && npm run dev` 直接命令（仅 bootstep.py）
- [ ] **OPS-03**：ADR README 索引 4 视图（核心基建 / 前端 / 安全 / 数据 / 平台 / WebUI 选型 / 扩展 / 演进 / 完整索引）+ 编号规则全覆盖 001~065，孤儿文件为 0
- [ ] **OPS-04**：架构冲突 ADR（049 双份 / 061 双份）以 `b` 后缀区分显示，非重命名文件防止外链失效
- [ ] **OPS-05**：`.env.docker` JWT_SECRET ≥ 32 字符且无 hardcode 的 `sk-*` / `OPENAI_API_KEY` 占位示例（留空行引导用户填）
- [ ] **OPS-06**：SQLite 数据文件挂容器 `app-data` 命名卷（prod）或 dev bind mount，宿主机 `data/` 目录存在
- [ ] **OPS-07**：`podman logs graphiti-main-app 2>&1 | grep ERROR | grep -v "semantic_admin.*404"` 在一次 dev 启动内 = 0 语义相关 ERROR
- [ ] **OPS-08**：文档链一致性 — req-beta.md → spec.md → plan.md → AGENTS.md Appendix E 的 semantic_admin API 路径一一对应无 dangling
- [ ] **OPS-09**：`docs/09-checklists/DOC_SYNC_CHECKLIST.md` 对照检查 — 7 子服务 ×（backend 模块表 + 路由注册）与 docs/03-modules/README.md 列表一致

### Review Gates

- [ ] **11 张表 DDL**: Review before 写任何 storage 代码 — 字段命名、约束、索引与 data-model.md 完全一致（6 USL + 3 Pipeline + 2 Approval/Quality = 11）
- [ ] **SchemaCandidate 状态机 + 审批流程接口**: Review before 写 approval_workflow/services/approval_service.py — contracts/quality-gate-approval.md + contracts/usl-manager.md 签名
- [ ] **质量闸 16 子指标(G1×7/G2×4/G3×5)公式 + 阈值**: Review before 写 quality_gate/impl/quality_calculator.py — contracts/quality-gate-approval.md 公式编号与权重(w1=0.35 w2=0.40 w3=0.25)
- [ ] **Neo4j 双写命名空间规范**: Review before 写 candidate_store/impl/neo4j_schema_graph_writer.py — Cypher 前缀 `USL__` 约定与索引创建
- [ ] **Frontend API 调用层**: Review before 合并 semantic-admin 模块 — services/semanticApi.ts 请求路径与后端 routes.py 一一对应（/api/semantic-admin/* 前缀）

## Complexity Tracking (5 项复杂度追踪)

> Constitution Check IV (避免过度设计) 每一项必须证明必要性，附 FR 编号

| # | 复杂度 | 为什么必要 (附 FR) | 更简单方案为什么被拒绝 |
|---|--------|---------------------|------------------------|
| 1 | **10 状态 Candidate 状态机**（而非 3-4 状态简化版） | FR4.3 要求 L1→L2→Auditor→Admin 四级角色分工 + 驳回重试 + 黑名单机制；FR5.2 加速通道依赖 AUDITOR_APPROVED 与 ADMIN_PENDING 的区分 | 简化 3 状态（DRAFT/REVIEWING/DONE）无法表达"Auditor 修改后回退到 L2 重做"、"REJECTED→STOPLISTED 加入黑名单不再抽取"等关键业务流程 |
| 2 | **3 关 × 16 子指标质量闸**（而非 1 关总评分） | FR5.1 要求质量分层治理：结构合规关 / 语义一致关 / 覆盖完整关各有专家负责；FR5.2 加速通道依赖各维度独立加权 | 单关总评分无法定位"候选不合格到底是属性缺还是关系漏还是语义冲突"，导致审批人无法针对性修改 |
| 3 | **11 张 SQLite 表分离**（而非 2-3 张大表 + JSON） | FR1-3 要求 USL 6 核心支持事务级 CRUD 与并发编辑锁；FR4 流水线 3 表需独立索引查询；FR5 审批表需多版本审计；无 Dashboard 物化表后减少 1 张冗余 → 合计 11 张 | 合并为大表 JSON 会导致：1) 属性规范 / 同义词 UNIQUE 对无法数据库级保障；2) 审批记录按 candidate_id 聚合查询全表扫；3) 质量面板聚合查询无法使用覆盖索引，p95 ≥ 3s |
| 4 | **Neo4j 双写命名空间（USL__Candidate 节点 + 两条边类型）**（而非仅 SQLite 存储） | FR4.4 要求语义抽取阶段可对候选做图查询预筛选；FR4.5 审批通过后 USL__IS_A_DRAFT 边删除与正式 USL 节点 MERGE 原子切换 | 仅 SQLite 存储无法支持"找出所有 DRAFT 状态候选与现有正式术语的 L2 相似度 > 0.8"这类图遍历查询，且审批通过后从候选到正式需批量回写而非边切换 |
| 5 | **Dashboard 实时聚合层 quality_gate/services/dashboard_query_service.py**（而非日快照物化表） | FR6 要求 Dashboard 可查"今日至今"实时数据（日物化有 24h 滞后）；SQLite 对 10 万行级别的分组聚合在有覆盖索引下 < 800ms | 实时聚合的主要问题是性能，但经评估：quality_reports 建复合索引 (created_date, candidate_id) + approval_records 建 (created_date, approver_role) 即可将 14 天窗口查询压到 500ms 内；且"实时数据"是产品经理明确提出的优先级（优于物化表的性能优势） |

## Phase Summary (4 个迭代 × 每迭代 10 个交付物)

### Phase 0: Research & Design Baseline (research.md + data-model.md + contracts/)

1. **research.md**: Neo4j `USL__*` 命名空间索引最佳实践、SQLite 短连接性能基准测试（1000 次 connect/close vs 单长连接耗时比）、Pydantic v2 strict 模式与 SQLite TEXT→INT 自动转换陷阱
2. **data-model.md** (本特性核心): **11 张**表完整 DDL（**已全部合并至 data-model.md §2 权威版**，来源 6 USL 核心表 + 3 Pipeline 运行表 + 2 Approval/Quality 表 = 11，含 CHECK/UNIQUE/FK/覆盖索引/COMMENT，对齐 design/*.html iter4-final；**不再维护独立 DDL 拆分文件**） + Neo4j Cypher `USL__*` 命名空间 + 10 状态机图 + 3 关 16 子指标公式(G1×7/G2×4/G3×5 权重 0.35/0.40/0.25) + 4 档分层阈值 + 审批加速通道权重 + 6 个 Pydantic 核心模型字段清单
3. **contracts/usl-manager.md**（合并原 usl-domain/term/hierarchy/property 4 个合约）: `UslManager` 统一聚合接口，含 domain(10) + term(12) + hierarchy(8,含 check_cycle) + property(8,含按域批量) 共 **38 方法**
4. **contracts/ol-pipeline-service.md**: `OlPipelineService` 6 方法（submit/schedule_run/cancel_run/get_run_status/list_runs/resume_from_failed_step）
5. **contracts/candidate-dual-writer.md**: `CandidateDualWriter` 8 方法（create_candidate/upsert_sqlite/write_neo4j_usl_candidate_node/write_neo4j_l2_edges/link_neo4j_draft_edge/count_sqlite_by_status/get_run_candidates/bulk_delete_duplicates）
6. **contracts/quality-gate-approval.md**（合并原 quality-gate + approval-service 两个合约）: **3 关 16 子指标(G1×7/G2×4/G3×5)** + 3 级审批(AUDITOR_MODIFIED/AUDITOR_REJECTED/ADMIN_REJECTED 回退/加速通道) + 18 方法签名
7. **contracts/schema-candidate-service.md**: `SchemaCandidateService` 14 方法签名（submit/promote_to_l1/promote_to_l2/submit_review + 各状态转换事件）
8. **contracts/usl-writeback-service.md**: `UslWritebackService` 9 方法（APPROVED→MERGED idempotent writeback、同义词写回、层级/属性/跨域映射写回、更新 pipeline_runs.writeback_*、删除 Neo4j DRAFT 边）
9. **contracts/neo4j-namespace.md**（新增）: `USL__*` 前缀命名规范、6 类节点/5 类边、索引/约束、从 DRAFT→正式 MERGE 的原子切换 Cypher 片段
10. **quickstart.md**: 重建镜像 → `python -c "from odap.biz.semantic_admin.usl_manager.impl.seed_sanguo_xiyou import seed_demo_all; seed_demo_all()"` → 调 `POST /api/semantic-admin/pipeline/runs` 提交示例抽取 → 走审批全链路 → 查看 /semantic-admin/quality Dashboard 40 步操作指南

### Phase 1: Backend Core (6 USL 子服务 + Storage + Seed)

1. **usl_manager/impl/seed_sanguo_xiyou.py**: **11 张表**完整 DDL（CREATE TABLE IF NOT EXISTS + 全部 CREATE INDEX IF NOT EXISTS，幂等；不再拆 seed/*.sql 四文件），随后通过 SqliteUslStorage 调用批量 UPSERT 三国 + 西游 6 域 + 60 术语 + 40 层级 + 20 属性 + 10 跨域映射
2. **usl_manager/impl/seed_sanguo_xiyou.py → _seed_domains()**: 三国（魏蜀吴）+ 西游（佛界/天庭/妖族）共 6 个示例域 INSERT（ON CONFLICT DO NOTHING，SqliteUslStorage 级 UNIQUE 冲突自动幂等）
3. **usl_manager/impl/seed_sanguo_xiyou.py → _seed_terms()**: 三国 30 术语 + 西游 30 术语 + 各自层级关系 INSERT
4. **usl_manager/impl/seed_sanguo_xiyou.py → _seed_properties_and_mappings()**: 属性规范 × 20 + 跨域映射 × 10 INSERT（不再写不相交对与基数单独表，统一放进 usl_cross_domain_mappings.mapping_type='related_match' + properties_json）
5. **interfaces/usl_repositories.py**: 6 个 Repository 抽象基类（无 NotImplementedError，默认 raise `RepositoryNotInitializedError` 带完整消息）
6. **storage/sqlite_usl_storage.py**: 6 张 USL 表 DAO 实现（60+ 方法，每方法独立 connect/close）+ 对应测试 `tests/unit/test_sqlite_usl_storage.py`（tmp_path）
7. **models/usl_models.py**: `UslDomain` / `UslTerm` / `UslHierarchy` / `UslPropertySpec` / `UslDisjointPair` / `UslCardinality` 6 个 Pydantic 严格模型
8. **services/domain_service.py** + **term_service.py** + **hierarchy_service.py**: 3 个 USL 子服务实现（不抛 HTTPException，业务异常 `DomainNotFoundError` 等）
9. **services/property_service.py** + **disjoint_service.py** + **cardinality_service.py**: 另 3 个 USL 子服务实现
10. **api/routes.py (USL 部分)** + **api/schemas.py (USL 部分)**: `/api/v1/semantic/domains` 等 6 组 REST 端点 + 请求/响应 Schema

### Phase 2: Backend Extended (Candidate 流水线 + 审批 + 质量 + Dashboard)

1. **interfaces/candidate_repository.py** + **interfaces/approval_repository.py** + **interfaces/dashboard_repository.py**: 3 个抽象基类（默认异常非 NotImplementedError）
2. **storage/sqlite_candidate_storage.py**: 3 张 Candidate/Pipeline 表 DAO + `tests/unit/test_sqlite_candidate_storage.py`（tmp_path 真实 DB）
3. **storage/sqlite_approval_storage.py**: 2 张审批/质量表 DAO + `tests/unit/test_sqlite_approval_storage.py`
4. **storage/sqlite_dashboard_storage.py**: 1 张日快照表 DAO + `tests/unit/test_sqlite_dashboard_storage.py`（幂等覆盖测试）
5. **models/candidate_models.py** + **models/approval_models.py** + **models/dashboard_models.py**: SchemaCandidate / PipelineRun / PipelineLayerSnapshot / ApprovalRecord / QualityReport / DashboardDailySnapshot
6. **impl/state_machine.py**: `CandidateStateMachine.transition(curr_status, event, context) → new_status` 纯函数 + `tests/unit/test_candidate_state_machine.py`（10 状态全路径 25+ 用例）
7. **impl/quality_calculator.py**: 16 子指标独立函数（`calc_s1_*` 结构关 5 个 / `calc_s2_*` 语义关 6 个 / `calc_s3_*` 覆盖关 5 个）+ 加权聚合 + 4 档阈值 + `tests/unit/test_quality_calculator.py`
8. **impl/neo4j_dual_writer.py**: Neo4jDualWriter（MERGE USL__Candidate + USL__L2_MEMBER_OF + USL__IS_A_DRAFT）+ `tests/unit/test_neo4j_dual_writer.py`（此处唯一允许 Mock Neo4j driver）
9. **services/candidate_service.py** + **services/approval_service.py** + **services/quality_service.py** + **services/dashboard_service.py**: 4 个扩展服务实现（仅抛业务异常）
10. **api/routes.py (补全)** + **impl/seed_migrator.py** + **impl/snapshot_builder.py**: 剩余 REST 端点 + seed 执行 CLI + 每日快照构建 Cron 入口

### Phase 3: Frontend + Integration + QA

1. **frontend/src/modules/semantic-admin/types/index.ts**: TypeScript 类型定义（200+ 行，对齐后端 6 Pydantic 核心模型 + 所有 Request/Response Schema）
2. **frontend/src/modules/semantic-admin/services/semanticApi.ts**: 12 组 REST 端点封装 + `semanticApi.test.ts`（Vitest + apiMock）
3. **frontend/src/modules/semantic-admin/stores/semanticStore.ts**: Zustand 全局状态（域选中、术语树、候选筛选、审批视图切换）+ `semanticStore.test.ts`
4. **frontend/src/modules/semantic-admin/pages/DomainManagement.tsx + TermManagement.tsx + HierarchyEditor.tsx + PropertySpecPanel.tsx + DisjointCardinality.tsx**: 5 个 USL 配置页（含 Form 校验）
5. **frontend/src/modules/semantic-admin/pages/CandidatePipeline.tsx + ApprovalCenter.tsx + QualityGateView.tsx**: 3 个流水线审批页（CandidateStatusTimeline + QualityRadarChart + ApprovalFlowDiagram 组件）
6. **frontend/src/modules/semantic-admin/pages/SemanticDashboard.tsx + components/DashboardMetricCard.tsx**: Dashboard 页 + 7 日趋势图（折线 + 柱状）
7. **frontend/src/modules/semantic-admin/hooks/useCandidateStateMachine.ts + useQualityCalculator.ts**: 两个前端业务 Hook（与后端同矩阵，辅助 UI 即时校验）
8. **frontend/src/modules/semantic-admin/locales/zh-CN/semantic-admin.json + en-US/semantic-admin.json + index.ts**: i18n 词条（中/英各 200+ 条）+ 模块注册
9. **tests/integration/test_semantic_admin_e2e.py**: 端到端集成测试（seed → 建域术语 → 提交流水 → 走审批 → 物化快照 → 验证 Dashboard 指标，需 Neo4j + tmp_path SQLite）
10. **docs/specs/007-semantic-admin-suite/tasks.md (by /speckit-tasks)**: 按 Phase 0-3 拆分为 80+ 可独立验证小任务 + 依赖顺序 DAG（speckit-diagram-dependencies 生成）
