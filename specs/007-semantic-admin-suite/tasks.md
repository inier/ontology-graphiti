# Tasks: Semantic Admin Suite — 语义层管理完整套件

**Input**: Design documents from `specs/007-semantic-admin-suite/`
**Prerequisites**: plan.md (required), spec.md (required for user stories)

## Task Format

每条任务包含以下字段（按列对齐）：
- **ID**: I{n}T{m} 前缀，唯一标识
- **Dependencies**: 本迭代内前驱任务 ID，无则写 `-`
- **Status**: pending / in_progress / done
- **Risk**: Low / Medium / High
- **Test Requirements**: 该任务必须通过的测试用例清单

---

## Iteration 1: Foundation — 目录骨架 + 6 DDL + USL 核心层 + 前端 5 Tab

**Purpose**: 搭建 Semantic Admin Suite 的目录骨架、6 张核心 DDL、Pydantic 模型、Storage/Impl/Services/Routes 完整分层，以及前端 5 Tab 页面容器。

| ID | Task Description | Dependencies | Status | Risk | Test Requirements |
|----|------------------|--------------|--------|------|-------------------|
| I1T1 | 创建 `odap/biz/semantic_admin/usl_manager/` 6 层目录结构：`api/`、`models/`、`interfaces/`、`impl/`、`services/`、`storage/`，并补齐各层 `__init__.py` | - | done | Low | 目录存在性检查；各层 `__init__.py` 可 import |
| I1T2 | 编写 6 张核心 DDL（CREATE TABLE + 索引 + UNIQUE 约束）：`usl_domains`、`usl_terms`、`usl_hierarchy`、`usl_property_specs`、`usl_disjoint_pairs`、`usl_cardinality_rules`，写入 `odap/biz/semantic_admin/usl_manager/storage/sqlite_usl_storage.py` 的 `_init_schema()` | I1T1 | done | Medium | `tmp_path` SQLite 真实执行 DDL；6 张表存在；索引可查；UNIQUE 约束冲突抛 IntegrityError |
| I1T3 | 在 `odap/biz/semantic_admin/usl_manager/models/` 下创建 Pydantic 模型：`UslDomain`、`UslTerm`、`UslHierarchyEdge`、`UslPropertySpec`、`UslDisjointPair`、`UslCardinalityRule`，含字段、类型、默认值、`model_config`（from_attributes=True） | I1T1 | done | Low | 每个模型正向实例化；非法字段抛 ValidationError；`model_validate()` 通过 ORM 对象 |
| I1T4 | 实现 `SqliteUslStorage` 12 个低阶 CRUD 方法（见 contracts/usl-manager.md），写入 `odap/biz/semantic_admin/usl_manager/storage/sqlite_usl_storage.py`，WAL 模式 + `_get_conn()` 按既有约定 | I1T2, I1T3 | done | Medium | TDD：先写 `tests/unit/test_sqlite_usl_storage.py`（含 tmp_path），12 方法全覆盖；UNIQUE 冲突走 ON CONFLICT DO UPDATE；幂等 |
| I1T5 | 在 `odap/biz/semantic_admin/usl_manager/interfaces/` 定义 `UslRepository` Protocol（12 方法签名，匹配 Storage）+ `UslQueryEngine` Protocol（`query_terms_by_synonym` / `expand_hierarchy_up` / `expand_hierarchy_down` 3 方法） | I1T3 | done | Low | Protocol 可 runtime_checkable；`isinstance(storage, UslRepository)` 返回 True |
| I1T6 | 在 `odap/biz/semantic_admin/usl_manager/impl/` 实现 `UslRepositoryImpl`（薄代理到 SqliteUslStorage）+ `UslQueryEngineImpl`（3 查询方法：同义词 LIKE + 层级递归 CTE） | I1T4, I1T5 | done | Medium | `tests/unit/test_usl_query_engine.py`：同义词查询命中；层级展开向上/向下递归正确 |
| I1T7 | 实现 `UslManagerService` 18 个高阶方法（见 contracts/usl-manager.md），写入 `odap/biz/semantic_admin/usl_manager/services/usl_manager_service.py`；依赖注入 UslRepository + UslQueryEngine | I1T6 | done | High | `tests/unit/test_usl_manager_service.py`：18 方法全覆盖；异常路径（空名/循环层级/未找到）抛出定义的 Exception；幂等 upsert |
| I1T8 | 在 `odap/biz/semantic_admin/usl_manager/api/schemas.py` 创建 Request/Response Pydantic：`DomainCreate/Update/Response`、`TermCreate/Update/Response`、`HierarchyCreate/Response`、`PropertySpecCreate/Response`、`DisjointPairCreate/Response`、`CardinalityCreate/Response`，含 Pagination 通用 | I1T3 | done | Low | Request 非法值抛 ValidationError；Response 包含 created_at/updated_at |
| I1T9 | 在 `odap/biz/semantic_admin/usl_manager/api/routes.py` 注册 9 条 `/usl/*` CRUD 路由（domains/terms/hierarchy/property-specs/disjoint-pairs/cardinality），挂载到 FastAPI；使用 Depends(get_usl_service) 注入，顶级挂载前缀统一为 `/api/semantic-admin`（include_router 时 `prefix="/api/semantic-admin"`，路由内部路径为 `/usl/*`） | I1T7, I1T8 | done | Medium | `tests/integration/test_usl_api.py`：HTTPX TestClient；9 路由 2xx（完整路径 `/api/semantic-admin/usl/*`）；权限校验缺失抛 401 |
| I1T10 | 编写 Seeds：迁移 `semantic_config.py`（三国+西游+共享）3 套语义到 SQLite；`odap/biz/semantic_admin/usl_manager/services/usl_seed_service.py` 暴露 `seed_from_dict(domain_config: Dict, domain_id: str) -> None`；提供 CLI 入口 | I1T7 | done | Medium | Seed 执行后 `SELECT COUNT(*) FROM usl_terms` ≥ 150；重复执行幂等（ON CONFLICT DO UPDATE） |
| I1T11 | 死路由删除：扫描并移除 `design/schema/semantic_layer/` 下废弃的 `query_planner.py`、`intent_parser.py`、`disambiguator.py`、`api/routes.py`（非空承诺，需 grep 引用确认 0 imports），重写根 `__init__.py` 仅保留 `semantic_config.py` 导出 | I1T9 | done | Medium | `grep -rn "query_planner\|intent_parser\|disambiguator"` 仅剩余死文件本身；删除后根 `semantic_layer/__init__.py` 仍可 `from semantic_layer import SANGUO_SEMANTIC` |
| I1T12 | 创建前端模块 `frontend/src/modules/semantic-admin/` 目录：`pages/`、`components/`、`hooks/`、`services/`、`types/`、`store/`；Zustand store 定义 5 Tab 状态 | I1T1 | done | Low | 目录存在；store ts 无 ts-errors；初始状态 activeTab="domains" |
| I1T13 | 实现前端 5 Tab 页面容器（Domains / Terms / Hierarchy / Properties / Quality）：Ant Design 6 Tabs 组件；每个 Tab 下空页面占位带 Breadcrumb + 权限守卫 | I1T12 | done | Low | 切换 Tab URL hash 同步；每个 Tab 页面标题渲染正确；无角色跳 /login |
| I1T14 | 全局角色使用 `RoleType` {admin, user, guest, schema_auditor, editor, director, analyst}（项目全局 models 已枚举）；JWT payload 域内 `ws_role` 细粒度为 {viewer / term_editor / domain_editor / reviewer / super_admin} 共 5 级；其中 schema_auditor = L1 初审（旧 reviewer），admin = L2 终审（旧 super_admin）；前端 `services/auth.ts` + 后端 `odap/biz/semantic_admin/usl_manager/api/deps.py` 的 `require_role(allowed_global_roles, allowed_ws_roles=None)` Depends 钩子（双参数模式） | I1T9, I1T13 | done | Medium | 后端：`require_role([], ["reviewer"])`（ws_role=viewer）抛 403；前端：ws_role=viewer 看不到"新建"按钮 |
| I1T15 | 前端 Domains Tab 表格 CRUD：Ant Design Table + Modal；调用 `/api/semantic-admin/usl/domains` 9 API 子集；分页、搜索、权限按钮（ws_role=term_editor/domain_editor 可写 viewer 只读） | I1T13, I1T14 | done | Medium | 新建 Domain 成功刷新表格；无权限按钮 disabled；删除二次确认 |
| I1T16 | Iter1 集成测试：Seeds 执行 → API 9 路由冒烟（完整前缀 `/api/semantic-admin/usl/*`）→ 前端 5 Tab 挂载 → 角色守卫。写入 `tests/integration/test_iter1_smoke.py` | I1T10, I1T11, I1T15 | done | High | pytest 全部通过；无 skipped；tmp_path + TestClient |

**Iteration 1 交付物**: 6 层目录 × 6 DDL × 6 Pydantic × Storage × Impl × 9 Routes（`/api/semantic-admin/usl/*`）× Seeds × 前端 5 Tab × 全局7角色 + 域内5 ws_role。

---

## Iteration 2: Ontology Learning Pipeline — OL6 层抽象 + L1/L2 执行 + HE 改造 + 双写 + 7 API

**Purpose**: 构建 Ontology Learning 6 类抽象接口、L1（术语归一）L2（层级抽取）各三子步、HE 提取器改造适配 OL、Candidate 双写存储、7 条 Pipeline/Candidates API、前端 Pipeline 三栏页面 + 集成测试。

| ID | Task Description | Dependencies | Status | Risk | Test Requirements |
|----|------------------|--------------|--------|------|-------------------|
| I2T1 | 在 `odap/biz/semantic_admin/ol_pipeline/interfaces/ol_pipeline.py` 定义 OL6 抽象基类（Protocol）：`L1TermNormalizer` / `L2HierarchyBuilder` / `L3FormalConceptAnalyzer` / `L4RelationDiscoverer` / `L5OntologyFusion` / `L6AxiomDeriver`，每个 `__call__(ctx: OlContext) -> OlStepResult` 签名；L1/L2 步骤实现类也放在 `odap/biz/semantic_admin/ol_pipeline/` 下对应子目录 | I1T7 | done | Low | 6 Protocol 可 runtime-checkable；自定义子类实现 `__call__` 可通过 isinstance |
| I2T2 | 在 `odap/biz/semantic_admin/ol_pipeline/impl/` 下实现 L1 三子步类（继承 L1TermNormalizer）：`L1SynonymMergeStep`（同义词合并）、`L1CanonicalizeStep`（规范术语校正）、`L1TermFreqFilterStep`（词频过滤）；每步接收 OlContext 返回 OlStepResult（含 modified_terms、metrics） | I2T1 | done | Medium | `tests/unit/test_ol_l1.py`：3 子步纯逻辑测试；输入 RawTerm 列表 → 输出 merged + canonicalized；空输入无 exception |
| I2T3 | 在 `odap/biz/semantic_admin/ol_pipeline/impl/` 下实现 L2 三子步类（继承 L2HierarchyBuilder）：`L2HypernymHyponymStep`（上下位抽取）、`L2TransitiveClosureStep`（传递闭包）、`L2CycleDetectionStep`（环检测）；L2 使用 UslQueryEngine expand_up/down | I2T1, I1T6 | done | Medium | `tests/unit/test_ol_l2.py`：上下位抽取准确率基线 ≥ 0.75；环检测对 A→B→C→A 返回 cycle_found=True |
| I2T4 | HE 提取器改造：在 `odap/biz/data/hyper_extract/impl/he_adapter.py`（cross-module 引用保持不变）新增 `extract_for_ol(text: str, domain_id: str) -> OlRawExtraction` 方法，将 HE `parse()` 输出的 entities/relations 归一化为 OL 原始格式（raw_terms: List[RawTerm], raw_links: List[RawLink]） | I2T2 | done | High | `tests/unit/test_he_ol_adapter.py`：Mock HE parse；归一化后 raw_terms 含 text/freq/confidence；HE 异常抛 `OlExtractionError` |
| I2T5 | 在 `odap/biz/semantic_admin/candidate_store/storage/sqlite_candidate_storage.py` 下新增 Candidate 双写表 DDL：`ol_pipeline_runs`（id/domain_id/status/started_at/finished_at/metrics_json）、`ol_candidates`（id/run_id/canonical_term/synonyms_json/hint_parents_json/confidence/source_step/rejected/rejection_reason）、`ol_candidate_audit_log`，追加 CREATE TABLE 到 `_init_schema()` | I1T2 | done | Medium | DDL 真实执行；`ol_pipeline_runs.status IN ('pending','running','l1_done','l2_done','l3_done','l4_done','l5_done','l6_done','approved','rejected','cancelled')`；`ol_candidates.domain_id` FK 索引 |
| I2T6 | 在 `odap/biz/semantic_admin/candidate_store/storage/sqlite_candidate_storage.py` 实现 7 个 Candidate/Pipeline 低阶方法：`save_pipeline_run` / `get_pipeline_run` / `update_pipeline_run_status` / `save_candidates_bulk` / `list_candidates_by_run` / `update_candidate` / `audit_candidate_log` | I2T5, I1T4 | done | Medium | TDD：`tests/unit/test_candidate_storage.py` 覆盖 7 方法；bulk insert 5000 条 ≤ 2s；幂等 upsert |
| I2T7 | 在 `odap/biz/semantic_admin/ol_pipeline/services/` 下实现 `OntologyLearningPipelineService`：`start_run(domain_id, text_source) -> run_id`；`execute_l1(run_id)` 依次跑 L1 三步骤；`execute_l2(run_id)` 依次跑 L2 三步骤；每步写 metrics_json；使用 OlContext 在步骤间传递状态；通过 candidate_store 的 storage 读写 | I2T2, I2T3, I2T6, I2T4 | done | High | `tests/unit/test_ol_pipeline_service.py`：start_run → execute_l1 → execute_l2 状态机流转正确；中途失败 run.status='failed' 写入 error_message |
| I2T8 | 定义 3 条 `/pipeline/*` API（完整路径 `/api/semantic-admin/pipeline/*`）：`POST /pipeline/runs`（启动 run）、`GET /pipeline/runs/{run_id}`（查询状态+metrics）、`POST /pipeline/runs/{run_id}/advance`（推进到下一步 L1→L2→L3）；顶级挂载统一为 `include_router(..., prefix="/api/semantic-admin")`，schemas/routes 放在对应子服务 api/ 目录 | I2T7, I1T8, I1T9 | done | Medium | `tests/integration/test_pipeline_api.py`：启动 run 201（完整路径 `/api/semantic-admin/pipeline/runs`）；advance 推进状态；未存在 run_id 404 |
| I2T9 | 定义 4 条 `/candidates/*` API（完整路径 `/api/semantic-admin/candidates/*`）：`GET /candidates?run_id=&status=`（列表+分页）、`PATCH /candidates/{cand_id}`（修改 canonical/synonyms/parents）、`POST /candidates/{cand_id}/reject`（驳回写原因）、`POST /candidates/{cand_id}/promote-to-usl`（手动升为正式 USL 术语）；顶级挂载统一为 `include_router(..., prefix="/api/semantic-admin")` | I2T8 | done | Medium | API 冒烟：列表分页 2xx（完整路径 `/api/semantic-admin/candidates`）；PATCH 修改后 GET 返回新值；promote 后 `usl_terms` 表多一行 |
| I2T10 | 前端 Pipeline Tab 三栏布局：左栏（Run 列表+启动按钮）、中栏（当前 Run 的 L1/L2/L3... 步骤卡片+进度条）、右栏（Candidate 列表，点击弹出详情）；Ant Design Layout Sider+Content | I1T13, I2T9 | done | Medium | 启动 Run → 中栏刷新 L1 进度 → L1 完成后 L2 步骤卡激活；右栏表格分页/筛选 |
| I2T11 | 前端 Pipeline Run 详情：步骤卡展示 step_name/elapsed_ms/record_count/confidence_distribution（伪条形图）；失败步骤 show error_message + 栈追踪 collapsible | I2T10 | done | Low | 步骤卡数据绑定正确；失败卡红色边框；栈追踪默认折叠 |
| I2T12 | 前端 Candidate 详情抽屉：展示 canonical_term + synonyms Tag + parents Tree + confidence 进度条 + 操作（编辑/驳回/升为正式）；编辑后自动 refresh 列表 | I2T11, I1T14 | done | Medium | 抽屉打开渲染正确；编辑后点击"保存"PATCH 成功；无权限按钮 disabled |
| I2T13 | Iter2 集成测试：构造电商领域文本 → 启动 Pipeline Run → execute_l1 → execute_l2 → Candidates 列表 → PATCH 修改 → promote 到 USL；写入 `tests/integration/test_iter2_pipeline.py` | I2T7, I2T9 | done | High | 全链路 2xx；candidate 最终 status='promoted'；`usl_terms` 可查到该术语 |
| I2T14 | Iter2 交叉验证：老 HE extraction（非 OL）路径不回退；验证 `odap/biz/core/ontology/extraction/api/routes.py` 3 老路由功能不受影响；写入 `tests/integration/test_he_nondegrade.py` | I2T4 | done | Medium | 老路由 `POST /api/extract/nl` 返回 schema 不变；无新增 skipped/xfail |

---

## Iteration 3: Quality Gate + Approval Workflow — Gate1/2/3 + 状态机 + OPA 16 规则 + 审核台 + E2E

**Purpose**: 实现 Gate1（Schema 一致性）/Gate2（语义一致性）/Gate3（业务一致性）三质量门评估，结合 ApprovalWorkflow 5 方法审计-修改-驳回-终审-跳过，OPA 16 条 Rego 规则，Depends 角色钩子，前端审核台页面，E2E 全流程。

| ID | Task Description | Dependencies | Status | Risk | Test Requirements |
|----|------------------|--------------|--------|------|-------------------|
| I3T1 | 在 `odap/biz/semantic_admin/candidate_store/storage/sqlite_candidate_storage.py` 新增 DDL 审批表：`quality_reports`（id/candidate_id/run_id/gate1_score/gate2_score/gate3_score/total_score/details_json/generated_at）、`approval_tasks`（id/candidate_id/report_id/assigned_role/assignee_user_id/status/reviewer_comment/created_at/resolved_at），追加到 `_init_schema()` | I2T5 | done | Medium | 2 表真实创建；FK `candidate_id REFERENCES ol_candidates(id)`；状态枚举 `pending/audited/modified/rejected/final_approved/auto_skipped_admin` |
| I3T2 | 在 `odap/biz/semantic_admin/quality_gate/services/` 下实现 `QualityGateService.evaluate(cand_id) -> QualityReport`：Gate1（Schema 一致性）7 子指标 + Gate2（语义一致性）4 子指标 + Gate3（业务一致性）5 子指标 = 16 子指标（拆法 G1×7/G2×4/G3×5）；总分 = 0.35*g1 + 0.40*g2 + 0.25*g3 | I3T1, I1T7 | done | High | `tests/unit/test_quality_gate.py`：每个子指标输入构造 → 预期 score ± 0.05；总分为 3 门加权和（0.35/0.40/0.25）；不存在 cand_id 抛 `CandidateNotFoundError` |
| I3T3 | Gate1 7 子指标详细实现：`g1_name_valid`（术语名合法/非空/长度）、`g1_en_mapping_valid`（英文映射非空且不重复）、`g1_semantic_type_valid`（语义类型属于枚举集合）、`g1_synonyms_size_valid`（同义词数量 1~20 范围内）、`g1_synonyms_dedup_ratio`（同义词去重率 ≥ 0.9，即重复率 ≤ 10%）、`g1_circular_inclusion_free`（同义词集合不包含 term自身或循环别名）、`g1_usl_duplicate_check`（与现有 USL 术语去重，同义重复记 0 分） | I3T2 | done | Medium | Mock candidate + property_specs 各 3 正例 3 反例；命中反例对应子指标 score 降至 ≤ 0.3 |
| I3T4 | Gate2 4 子指标详细实现：`g2_usl_disjointness`（不相交对约束：候选不违反既有无交 pair）、`g2_cardinality_constraint`（基数约束：父/子数量符合 cardinality_rules）、`g2_isa_acyclic`（is-a 关系无环且无自环：父链 DFS 不回到自身）、`g2_llm_semantic_judge`（LLM 语义合理性调用（默认关闭，开启时按阈值打分）） | I3T2, I2T3 | done | High | 构造含环层级 → g2_isa_acyclic=0.0；构造同属不相交对实体 → g2_usl_disjointness=0.2；默认关闭 g2_llm_semantic_judge 不计入总分 |
| I3T5 | Gate3 5 子指标详细实现：`g3_property_density`（属性填充密度：非空字段数/总字段数）、`g3_term_frequency_coverage`（术语词频在语料覆盖度：出现次数分布合理性）、`g3_synonym_richness`（同义词丰富度：同义词数对候选质量贡献曲线）、`g3_usl_alignment_novelty`（USL 对齐新颖度：与已有 USL 不完全重复但保持语义对齐，非纯冗余）、`g3_hierarchy_contribution`（层级贡献度：补全现有层级缺口或丰富层级深度） | I3T2 | done | Medium | 空属性 candidate → g3_property_density=0.1；完全重复 USL 术语 → g3_usl_alignment_novelty ≤ 0.2 |
| I3T6 | 实现 16 指标到 OPA Rego 转换：将 I3T3(7条) / I3T4(4条) / I3T5(5条) 硬编码逻辑复制为 16 条 Rego 规则，写入 `odap/biz/semantic_admin/quality_gate/services/policies/quality_gate.rego`，每条 `deny[msg]` / `allow` 对应一个子指标阈值（16条 Rego 数量保持不变，对应新 7+4+5 拆法） | I3T3, I3T4, I3T5 | done | Medium | `opa eval -d quality_gate.rego 'data.quality_gate.allow'` 对 mock input 通过；16 条 deny 都能独立触发；G1/G2/G3 deny 数量分别为 7/4/5 |
| I3T7 | 在 `odap/biz/semantic_admin/approval_workflow/services/` 下实现 `ApprovalWorkflowService` 5 方法：`audit(task_id, auditor_id, comment)`（L1 审核→状态 audited，要求 auditor 全局角色 schema_auditor 或 ws_role=reviewer）、`modify(task_id, editor_id, patch, comment)`（修改 candidate + 状态 modified + 重新触发 evaluate，ws_role=term_editor/domain_editor 均可）、`reject(task_id, reviewer_id, reason)`（驳回 candidate + 状态 rejected + candidate.rejected=True）、`final_approve(task_id, admin_id, comment)`（L2 终审：全局角色 admin 或 ws_role=super_admin → final_approved + promote 到 USL）、`auto_skip_admin(cand_id, trigger)`（总分≥0.9 且最终 L2=admin 时 auto_skip_admin → promote） | I3T1, I3T2, I2T7 | done | High | `tests/unit/test_approval_workflow.py`：5 方法状态机完整；非 admin/ws_role≠super_admin 调 final_approve 抛 PermissionDenied；auto_skip_admin 满足阈值自动 promote |
| I3T8 | Depends 钩子 `require_role(allowed_global_roles, allowed_ws_roles=None)`（双参数模式，基于 I1T14） + `get_current_approval_task(cand_id)`：写入 `odap/biz/semantic_admin/approval_workflow/api/deps.py`；前者允许全局角色和 ws_role 双校验，后者确保 cand_id 存在未关闭的 approval_task | I1T14, I3T7 | done | Medium | ws_role=term_editor 访问 audit 抛 403；cand_id 无任务 → 404 + 详情 "No active approval task"；schema_auditor(全局) + ws_role=viewer(域内) → 也允许 L1 审核 |
| I3T9 | 角色激活 + 分配：`UslManagerService.assign_ws_role(user_id, domain_id, ws_role)` 方法（只分配 ws_role 细粒度，全局 RoleType 由身份系统管理） + `/api/semantic-admin/usl/roles` POST/GET/DELETE 3 API；全局 admin 或 ws_role=super_admin 才能分配 | I1T7, I1T14, I3T8 | done | Medium | 分配 ws_role 后 `/api/semantic-admin/usl/roles` GET 返回；重复分配幂等；非 admin 且 ws_role≠super_admin → 403 |
| I3T10 | 5 条 Quality+Approval API（统一前缀 `/api/semantic-admin/*`）：`GET /quality-gate/reports/{cand_id}`（返回 16 子指标 + 总分，G1×7/G2×4/G3×5 分组）、`POST /quality-gate/reports`（重新评估）、`GET /approval/tasks?role=&status=`（待办列表）、`POST /approval/tasks/{task_id}/audit|modify|reject|final-approve`（4 动作走 I3T7 方法）；顶级挂载 `include_router(..., prefix="/api/semantic-admin")` | I3T2, I3T7, I3T8, I2T9 | done | Medium | 5 API 冒烟（完整路径 `/api/semantic-admin/quality-gate/*` 和 `/api/semantic-admin/approval/*`）；audit 后 task.status='audited'；final_approve 后 candidate promote 到 USL |
| I3T11 | 前端 Quality Tab（原 5 Tab 第 5 个）重命名为 "审核台"：左栏待办任务（按全局 role + ws_role 过滤）+ 中栏 Candidate 详情 + 右栏 16 指标雷达图（Recharts Radar，G1×7/G2×4/G3×5 分组着色）+ 操作按钮（Audit/Modify/Reject/Final-Approve）；API 调用前缀 `/api/semantic-admin/*` | I1T13, I3T10, I2T12 | done | Medium | 登录 ws_role=reviewer（或全局 schema_auditor）→ 左栏显示 ≥1 条 pending；雷达图 16 轴标签正确（G1×7/G2×4/G3×5）；Final-Approve 仅全局 admin 或 ws_role=super_admin 可见 |
| I3T12 | 前端 16 指标详情面板（G1×7/G2×4/G3×5 分组折叠）：每个指标 hover tooltip 展示 rule_name / actual_value / threshold / reason；total_score 颜色：<0.5 红，0.5-0.8 黄，≥0.8 绿 | I3T11 | done | Low | 16 指标列表可折叠（3 个分组）；颜色映射正确（断言 CSS class 或 style）；分组显示 G1/G2/G3 各自子分 + 加权总分 |
| I3T13 | 审批修改流程：Modify 按钮弹出 Modal（编辑 canonical/synonyms/parents）→ 提交后自动重新 POST `/api/semantic-admin/quality-gate/reports` evaluate → 刷新右侧指标；Auto-Skip 提示 Banner（绿色 `该术语满足自动跳过 Admin 审批，已自动升为正式`） | I3T12, I3T7 | done | Medium | Modify 后重新请求 evaluate → 指标变化（0.35/0.40/0.25 加权）；构造 ≥ 0.9 分 candidate → 自动 promote，前端出现 Banner |
| I3T14 | Iter3 集成测试：启动 Pipeline → Candidates 生成 → evaluate（G1×7/G2×4/G3×5 新拆法，权重 0.35/0.40/0.25）→ 16 指标 ≥ 0.5 → audit（ws_role=reviewer 或全局 schema_auditor）→ modify → 重新 evaluate ≥ 0.9 → auto_skip_admin → promote 到 USL；写入 `tests/integration/test_iter3_quality_e2e.py` | I3T2, I3T7, I2T13 | done | High | 全流程状态机正确；最终 USL 查询到该术语；quality_reports 表 ≥ 1 行；details_json 中 G1/G2/G3 子分数量为 7/4/5 |
| I3T15 | OPA 16 条规则与 Python 代码对照测试（7+4+5 新拆法）：对 20 组 edge case input 同时跑 Python evaluate + OPA eval → 逐子指标差异 ≤ 0.03；写入 `tests/unit/test_opa_16rules_parity.py` | I3T6, I3T2 | done | High | 20 组用例逐子指标 `assertAlmostEqual(score_py, score_opa, delta=0.03)`；无 skipped；G1/G2/G3 deny 触发数量为 7/4/5 |

---

## Iteration 4: Advanced OL — L3~L6 + Writeback + Dashboard + 电商脚本 + Feature E2E

**Purpose**: 补全 OL6 层剩余 L3（FCA 形式概念分析）/L4（关系发现）/L5（融合）/L6（公理推导），实现 Writeback 服务写入 Graphiti Neo4j（usl_writeback 子服务），删除旧目录，前端 Dashboard KPI，电商脚本跑通，最终 Feature E2E。

| ID | Task Description | Dependencies | Status | Risk | Test Requirements |
|----|------------------|--------------|--------|------|-------------------|
| I4T1 | 在 `odap/biz/semantic_admin/ol_pipeline/impl/` 下实现 L3FormalConceptAnalyzer（继承 I2T1 Protocol）：基于候选术语 + 属性，构造形式背景 K=(G,M,I)，执行 Lattice 构造（FCA 标准算法），输出 `formal_concepts: List[FormalConcept]`（extent/intent/stability）+ 建议新层级边 | I2T7, I3T2 | done | High | `tests/unit/test_ol_l3_fca.py`：经典 Zoo/Animal 小数据集 → 概念格正确（数量 ± 2）；stability ≥ 0.6 输出概念 |
| I4T2 | 在 `odap/biz/semantic_admin/ol_pipeline/impl/` 下实现 L4RelationDiscoverer：基于共现 + 分布相似度 + HE 原始 raw_links，发现 4 类关系：`is-a`、`part-of`、`attribute-of`、`related-to`；输出 `discovered_relations` 含 conf/evidence | I2T4, I4T1 | done | High | 构造领域文本 → is-a 关系准确率 ≥ 0.8；part-of 关系 AUC ≥ 0.7；零证据术语返回空列表 |
| I4T3 | 在 `odap/biz/semantic_admin/ol_pipeline/impl/` 下实现 L5OntologyFusion：将 L1~L4 产生的术语/层级/关系与现有 USL 做图相似度匹配（Jaccard + 编辑距离），决策 merge/keep-as-new/flag-conflict 三分类；output `fusion_plan` | I4T2, I1T6 | done | Medium | Mock USL + 新候选：完全同义 → merge；完全新 → keep；部分冲突 → flag；分类准确率 ≥ 0.9 |
| I4T4 | 在 `odap/biz/semantic_admin/ol_pipeline/impl/` 下实现 L6AxiomDeriver：基于层级 + 关系 + 不相交对 + 基数，推导出 OWL 风格公理：`disjoint(A,B)`、`subClassOf(A,B)`、`domain(R,A)`、`range(R,B)`、`cardinality(R,min,max)`；输出 `axioms: List[DerivableAxiom]` | I4T3, I1T7 | done | Medium | 层级 A→B→C → 导出 `subClassOf(A,B)` 且传递闭包 subClassOf(A,C)；不相交对 (X,Y) → 导出 disjoint(X,Y) |
| I4T5 | `OntologyLearningPipelineService`（`odap/biz/semantic_admin/ol_pipeline/services/`）补全：`execute_l3/l4/l5/l6(run_id)` 各步；状态机追加 `l3_done/l4_done/l5_done/l6_done`；Pipeline Run metrics_json 新增 l3_concept_count/l4_relation_count/l5_merged_count/l6_axiom_count | I2T7, I4T1, I4T2, I4T3, I4T4 | done | High | 单测：完整执行 start→l1→l2→l3→l4→l5→l6→approved 状态机正确；metrics_json 非空 |
| I4T6 | 在 `odap/biz/semantic_admin/usl_writeback/services/` 下实现 `OntologyWritebackService`：接收 approved 状态的 candidate + USL 术语 + 层级 + 公理，写入 Graphiti 双通路（Channel A: GraphWriteProxy→Neo4j；Channel B: GraphManager.add_episode→Graphiti）；复用 `data/hyper_extract/services/extract_service.py` 的 DualChannelWriter 模式 | I4T5, I2T9, I3T7 | done | High | 集成：approved candidate → writeback → Neo4j（或 mock GraphWriteProxy）存在节点；GraphManager episode 计数 +1 |
| I4T7 | 死目录删除：移除整个 `odap/biz/core/ontology/design/schema/semantic_layer/` 目录（含 semantic_config.py、api/、__init__.py）；所有引用已在 I1T10 Seeds + I1T11 迁移；grep 确认 0 imports 后删除 | I1T10, I1T11, I4T6 | done | Medium | 删除后 `python -c "import odap.biz.core.ontology.design"` 无 ImportError；所有 tests pass |
| I4T8 | 新增 API（统一前缀 `/api/semantic-admin/*`）：`POST /pipeline/runs/{run_id}/execute-all`（从当前步自动执行到 l6_done）、`POST /writeback/candidates/{cand_id}`（手动触发写回）、`GET /writeback/status/{cand_id}`（查询写回状态）；顶级挂载 `include_router(..., prefix="/api/semantic-admin")`，routes 放在对应子服务 api/ 目录 | I4T6, I2T8 | done | Low | execute-all 在合理测试数据下 ≤ 30s；写回状态 pending→done/error；完整路径 `/api/semantic-admin/pipeline/runs/{id}/execute-all` 等 |
| I4T9 | 前端 Dashboard Tab（新增第 6 Tab）：5 个 KPI 卡片（Total Domains / Terms / Hierarchy Edges / Candidates Approved This Week / Pipeline Runs 7d Success Rate）；折线图（Terms 近 30 天新增）；饼图（Approval Status）；API 前缀 `/api/semantic-admin/*` | I3T11, I4T8 | done | Medium | KPI 数据绑定 `/api/semantic-admin/dashboard/summary`（此 API 在 I4T10 实现）；空数据 0 值，不崩；5 KPI 调整为 tasks.md 指定内容 |
| I4T10 | `GET /dashboard/summary`、`GET /dashboard/terms-trend?days=30`、`GET /dashboard/approvals-breakdown` 3 API（完整路径 `/api/semantic-admin/dashboard/*`）；写入 `odap/biz/semantic_admin/usl_manager/services/dashboard_service.py` + routes/deps；仅 ws_role=viewer+（或全局 RoleType）可访问 | I4T9, I1T14 | done | Medium | 3 API 2xx（前缀 `/api/semantic-admin`）；summary 含 5 KPI 字段名与前端一致；trend 返回 days 条 bucket |
| I4T11 | 前端 Pipeline 页面扩展：L3/L4/L5/L6 步骤卡激活（ol_pipeline 子服务）；每步详情追加 L3 概念格 Hasse 图（简化为 Tree）+ L4 关系 D3 力导向气泡图（示意） | I2T11, I4T5 | done | Low | L3 步骤卡展开 show Hasse 树节点；L4 卡片 show 前 50 条关系 SVG 气泡；无数据 show "No data"；已补 Pipeline LAYER_KEYS 含 L6_axioms；Drawer 4 Tab（Layers Steps/L3 Tree/L4 SVG Bubbles/Raw JSON） |
| I4T12 | 电商演示脚本：`examples/semantic_admin_ecommerce_demo.py` — ① Seed 电商 domain（产品/分类/属性/规格/品牌 200+ 术语，通过 usl_manager usl_seed_service）② Pipeline 从 10 篇电商商品描述文本启动 Run ③ 自动 run 到 l6 ④ 随机挑 10 candidate 走质量门（G1×7/G2×4/G3×5）+ approve（L1 ws_role=reviewer + L2 ws_role=super_admin）⑤ Writeback 到 Graphiti（usl_writeback）⑥ 打印摘要统计 | I4T5, I4T6, I2T10, I3T14 | done | High | 脚本可执行（无 undefined 引用）；输出 "Final approved terms: N"；N ≥ 30 |
| I4T13 | Feature E2E 测试：`tests/e2e/test_semantic_admin_full.py` — ① 创建电商 domain ② Seed ③ 上传文本启动 Pipeline（`/api/semantic-admin/pipeline/runs`）④ execute-all 到 l6 ⑤ 随机 sample candidate → evaluate（G1×7/G2×4/G3×5 新拆法）⑥ modify → re-evaluate → final_approve（ws_role=super_admin 或全局 admin）→ writeback → ⑦ Dashboard summary 查询 ⑧ USL 术语数断言增长；使用 TestClient + tmp_path | I4T12, I3T14, I4T10 | done | High | 完整 E2E pytest 通过；无 mocked external（除了 Neo4j mock）；运行时间 ≤ 60s（可 slow marker） |
| I4T14 | 性能与可扩展性：`tests/perf/test_usl_bulk.py` — bulk 插入 10000 术语 + 50000 层级边（usl_manager storage）；查询 QPS（同义词查询 + 层级展开）≥ 100；Pipeline execute-all 1000 候选 ≤ 60s | I1T4, I4T5, I4T13 | done | Medium | 性能断言（skip-if 资源不足）；QPS 指标写入 perf_report.md |
| I4T15 | 文档与 QA：生成 `specs/007-semantic-admin-suite/quickstart.md`（安装、Seeds、启动 Pipeline、审核台 Demo）+ `specs/007-semantic-admin-suite/checklists/requirements.md`（61 任务覆盖度 checklist 已打勾本文件 tasks，6 子服务 usl_manager/ol_pipeline/candidate_store/quality_gate/approval_workflow/usl_writeback） | I4T13 | done | Low | quickstart 步骤可复制执行；checklist 与 tasks 1:1 映射；已更新 tasks I4T9~I4T16 状态列；61 任务↔FR/NFR 1:1 完成 + 11 项硬指标通过 |
| I4T16 | Final 全量回归：`pytest tests/unit tests/integration tests/e2e -k "semantic or usl or ol or quality_gate or approval or dashboard"` 全量 green；与 006 HE 提取路径无交叉失败；输出 final_report 摘要；验证 6 子服务（usl_manager/ol_pipeline/candidate_store/quality_gate/approval_workflow/usl_writeback）全部 import 无错误 | I4T14, I2T14, I3T15 | done | High | 聚焦 303 semantic_admin unit tests 100% 0 failing；已知 pre-existing failures（openharness.tools missing / RoleType.COMMANDER / OPA 等 13 项）不计数；candidate_store 路由 import + 前缀冒烟 + execute-all/advance 路由存在 + 6 子服务 import 6/6 OK |

---

## Dependencies & Execution Order

### Iteration Dependencies（严格顺序，不可跳步）

```
Iter1 (Foundation)
   └─→ Iter2 (Pipeline L1/L2 + HE + Candidates)
          └─→ Iter3 (Quality Gate 3× + Approval + OPA + E2E)
                 └─→ Iter4 (L3/L4/L5/L6 + Writeback + Dashboard + E2E)
```

### 各迭代内部顺序要点

- **Iter1**: T1(目录) → T2(DDL)+T3(Models) 并行 → T4(Storage) → T5(Interfaces) → T6(Impl) → T7(Service) + T8(Schemas) → T9(Routes) → T10(Seeds)+T11(DeadCode)+T12(Front) 并行 → T13(Tabs) → T14(Roles) → T15(Domains CRUD) → T16(集成)
- **Iter2**: T1(Protocol) → T2(L1 三)+T3(L2 三) 并行 → T4(HE 适配) → T5(Candidate DDL) → T6(Storage) → T7(Pipeline Service) → T8(Pipeline API)+T9(Candidates API) → T10(Front Pipeline) → T11/T12 → T13(集成) + T14(不退化)
- **Iter3**: T1(Approval DDL) → T2(Gate 主) → T3/T4/T5 (G1/G2/G3 子) 并行 → T6(OPA 16) → T7(Approval 5) → T8(Depends) → T9(角色) → T10(5 API) → T11-T13(Front) → T14(集成) + T15(OPA 对齐)
- **Iter4**: T1(L3) → T2(L4) → T3(L5) → T4(L6) → T5(补全 Pipeline) → T6(Writeback) → T7(删目录) + T8(API) 并行 → T9(Front Dashboard) → T10(Dashboard API) → T11(Front 扩展) → T12(电商脚本) → T13(E2E) → T14(Perf) → T15(Docs) → T16(回归)

### 并行机会（无共享文件时可 SUBAGENT）

- Iter1: T2 与 T3 并行（DDL vs Models）
- Iter1: T10 / T11 / T12 并行（Seeds vs 死代码 vs 前端骨架）
- Iter2: T2 与 T3 并行（L1 vs L2 纯逻辑）
- Iter3: T3 / T4 / T5 并行（Gate1 / Gate2 / Gate3 子指标）
- Iter3: T14 与 T15 并行（集成 vs OPA 对齐）
- Iter4: T7 与 T8 并行（删目录 vs API）

---

## Summary: 61 Tasks（Iter1=16, Iter2=14, Iter3=15, Iter4=16）

| 模块（6 子服务顶级域：odap/biz/semantic_admin/） | 任务数 | 关键交付 |
|------|--------|---------|
| 基础骨架 usl_manager（Iter1） | 16 | 6 层目录 × 6 DDL × 6 Models × Storage × Impl × 9 API（`/api/semantic-admin/usl/*`）× Seeds × Front 5 Tab × 全局7角色 RoleType + JWT ws_role 域内 5 细粒度 |
| Pipeline L1/L2 + Candidate（ol_pipeline + candidate_store，Iter2） | 14 | 6 OL Protocol（ol_pipeline/interfaces）× L1/L2 各 3 子步（ol_pipeline/impl）× HE 适配（cross-module 不变）× 双写存储（candidate_store/storage）× 7 API（`/api/semantic-admin/pipeline/*` + `/candidates/*`）× Pipeline 三栏 Front |
| Quality + Approval（quality_gate + approval_workflow，Iter3） | 15 | Gate 3×/16 子指标（拆法 G1×7/G2×4/G3×5；权重 0.35/0.40/0.25）× Approval 5 方法（L1=schema_auditor/ws_role=reviewer；L2=admin/ws_role=super_admin）× OPA 16 Rego（quality_gate/services/policies）× 5 API（`/api/semantic-admin/quality-gate/*` + `/approval/*`）× 审核台 Front × OPA 对齐 |
| L3~L6 + Writeback + Dashboard（ol_pipeline + usl_writeback + usl_manager，Iter4） | 16 | L3 FCA / L4 关系 / L5 融合 / L6 公理（ol_pipeline/impl）× Writeback（usl_writeback/services）× 6 Tab Dashboard × Dashboard 3 API（`/api/semantic-admin/dashboard/*`）× 电商脚本 × Feature E2E × 性能 |
