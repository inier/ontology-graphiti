---
id: odap.l15.specs-2026-10-28-semantic-layer-workbench-design
status: reference
owner: architect
version: ''
layer: L15
concern: design-spec-record
lifecycle: frozen
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
governance_reason: superpowers 设计规格存档，结论已落 ADR 或代码，规格本身冻结
governance_evidence: docs/07-adr/README.md 各 ADR 的 specs 引用（如 ADR-087 引用 2026-10-07-semantic-drift-detection-design）
---

# 统一语义层工作台设计（USL 发布生命周期 + 本体单一写入通道）

- **状态**：待复审（设计基线；复审通过后由 `superpowers:writing-plans` 拆实施计划）
- **日期**：2026-10-28
- **范围**：统一语义层工作台；USL 草案/变更集/审核/发布生命周期；本体模型单一写入通道；四工作区（定义/审核/发布/探查）；AI 提案式写入；RDF 导入导出边界；消费方版本固定
- **关联**：[ADR-091](../../07-adr/ADR-091_语义发布生命周期与本体单一写入通道.md)（本设计决策记录）；[ADR-068](../../07-adr/ADR-068_本体模块四层分层架构.md)、[ADR-073](../../07-adr/ADR-073_基于本体的数据服务四步落地架构.md)、[ADR-079](../../07-adr/ADR-079_本体论与LLM结合边界.md)、[ADR-080](../../07-adr/ADR-080_ontology门面封装与分层契约.md)、[ADR-083](../../07-adr/ADR-083_图谱实体软删除语义.md)、[ADR-084](../../07-adr/ADR-084_open_typed双层事实模型与写路径不变量.md)、[ADR-085](../../07-adr/ADR-085_SHACL形状持久化与写路径校验不变量.md)、[ADR-086](../../07-adr/ADR-086_概念缺口回路.md)、[ADR-090](../../07-adr/ADR-090_子项目D_promote按attribution_layer路由_类型化编辑.md)
- **规格衔接**：`specs/003-ontology-redesign/spec.md` US5/FR-035/Assumptions；`specs/007-semantic-admin-suite/spec.md` FR-059/FR-060；`docs/02-architecture/ARCHITECTURE_FOUR_STEPS.md` §1.1/§3
- **硬性规则**：AGENTS.md 规则 1（路由注册）、规则 2（服务层返回 dict）、规则 3（路由透传 HTTPException）、规则 6（routes→services→storage）、规则 9（新模块零测试不提交）、规则 12（架构决策 ADR + 文档同步）、规则 13（临时文件目录化）、规则 14（失败显式、兜底可观测、禁止幻影调用/hasattr 探测式降级/测试必须执行真实函数体）

---

## 0. 结论摘要

1. **一条业务语义主线**：USL 草案 → 变更集 → 人工审核（AI 预审标注存疑项）→ 发布版本 → 被本体构建、数据标准、数据提取门控、QA/SHACL 消费。发布版本不可变，消费方按版本固定。
2. **一个本体写入通道**：`OntologyWriteGateway` 是唯一写入实现。HTTP 编辑器、AI 助手、USL 投影、抽取链路、感知链路全部收敛为「产提案 → 网关校验并应用」；AI 在任何权限下都不直接写入。
3. **一个工作台**：`/semantic-admin/workbench` 四工作区（定义/审核/发布/探查）+ 三视图（图谱/卡片墙/表格）。探查与编辑是**模式 + 服务端权限**，不是两套页面，也不是两套后端。
4. **三层保存**：自动保存写草案；变更集聚合逻辑单元并保证复合操作原子；版本发布是独立人工门。即时保存与变更集不冲突（C2）。
5. **RDF 是序列化格式，不是审批通道**：只导出已发布版本；导入落草案并生成变更集，永不直发（C3）。
6. **兼容策略**：现有 USL CRUD 保留为「写草案」；现有语义管理页保留为高级工具；迁移脚本把现有域快照为 `v1` 已发布版本；消费切换有显式配置开关与启动告警。

---

## 1. 背景与现状

### 1.1 目标

业务语义需要被统一定义、统一管理、统一发布，并成为本体构建、数据标准与数据提取的前置约束。当前系统已有 USL（域/术语/层级/属性/不相交/基数）、OL 6 层流水线、候选库、质量闸、两级审批、USL 写回、概念缺口回路，但缺少三样东西：

1. **发布态**：USL 没有「草案 vs 已发布」的边界，任何直接 CRUD 都立即成为消费方可读的事实。
2. **单一写入通道**：本体 TBox 至少有五条写入路径，权限、审计、版本、校验各自为政。
3. **统一工作面**：图谱、卡片、USL 管理、候选、审批、版本分散在多个页面，没有一个地方能同时完成「看、改、审、发」。

### 1.2 代码证据

| # | 事实 | 证据 | 影响 |
|---|------|------|------|
| E1 | USL 六张表没有 `status`/`version`/`revision` 列 | `apps/api/odap/biz/semantic_admin/usl_manager/storage/sqlite_usl_storage.py:91-207` | 无法区分草案与已发布；无法乐观锁；无法回滚 |
| E2 | `UslTerm`/`UslDomain` 模型没有状态与版本字段 | `apps/api/odap/biz/semantic_admin/usl_manager/models/usl_term.py`、`usl_domain.py` | 服务层无法表达生命周期 |
| E3 | USL 直接 CRUD 写入即生效，无审批/发布门 | `apps/api/odap/biz/semantic_admin/usl_manager/api/routes.py`（terms/domains/hierarchies 等写接口） | 草案内容会立刻被 QA/SHACL/写回消费 |
| E4 | QA 读 USL 只按 `domain_code` 取域，不校验发布态 | `apps/api/odap/biz/data/qa/pipeline/query_pipeline.py:58-88` | 未发布内容参与问答 |
| E5 | SHACL 形状生成直接读 `usl_cardinalities`/`usl_disjoint_pairs` | `apps/api/odap/biz/core/ontology/design/engine/shacl/shape_generator.py` | 未发布约束进入校验 |
| E6 | 本体 HTTP 类型写入已经过 `TypeRegistry`，但只做 OMS 同步，不做权限/版本/提案 | `apps/api/odap/biz/core/ontology/ontology_api/api/routes.py:236-300, 402-430`；`registry/type_registry.py` | 有统一入口的雏形，但没有治理职责 |
| E7 | 本体写路由只依赖 `get_current_user`，无角色/OPA 校验 | 同上文件第 39-915 行的全部写路由 | 「没有权限不能编辑」尚未在服务端成立 |
| E8 | AI 助手写工具直接 `OntologyService.create/update/delete_*` | `apps/api/odap/biz/core/assistant/plugins/ai_assistant/tools/write_tools.py:146-598` | AI 可绕过审批、审计、版本直接改 TBox |
| E9 | USL 写回直接写 TBox，并会按 `USL__{code}` 命名自动建本体 | `apps/api/odap/biz/semantic_admin/usl_writeback/impl/graphiti_writeback_adapter.py:112-136, 152-153, 434-435, 478-479, 493-495` | 双写不可控；命名反推违反 ADR-079 §7 |
| E10 | 写回在关系缺 source/target 时静默降级为 ObjectType | 同上 `442-479` | 规则 14 禁止的静默降级；根因被掩盖 |
| E11 | HE 导入直接写本体，逐项异常仅 warning 后继续 | `apps/api/odap/biz/data/hyper_extract/services/extract_service.py:1276-1305` | 部分失败不可见；规则 14 违规 |
| E12 | 感知链路无 `ontology_id` 时回退到 `oms.create_object_type`，异常仅 warning | `apps/api/odap/biz/data/perception/hub.py:209-263`（回退在 254-263） | 未绑定本体的类型静默写入 OMS |
| E13 | 语义地图「查看图谱」渲染原始 JSON | `apps/web/src/modules/ontology/pages/SemanticMapPage.tsx` | 不是可探查的图谱 |
| E14 | 语义地图后端无分页/过滤/邻居扩展 | `apps/api/odap/biz/data/semantic_map/api/routes.py:66-177` | 大图不可用 |
| E15 | 图谱组件已是 Sigma.js，具备布局/搜索/路径/社区等能力，但选中态内部自持 | `apps/web/src/modules/shared/modules/graph/components/GraphView.tsx`、`GraphCanvas.tsx` | 无法与卡片墙共享选中态 |
| E16 | FR-060（RDF/OWL 导入导出）未实现，无 `rdflib` 依赖与路由 | `specs/007-semantic-admin-suite/spec.md:353-354, 430`；`apps/api/pyproject.toml` | 规格悬空 |
| E17 | 撤销服务只支持 `workspace/scenario/agent/ontology_version` | `apps/api/odap/biz/platform/undo/services/undo_service.py` | USL/本体类型编辑无法复用 |
| E18 | spec 003 写「即时保存」「单用户」「复用 G6」 | `specs/003-ontology-redesign/spec.md:108-109, 219, 222` | 与现状和本次设计冲突，需回写 |

### 1.3 五条本体写入路径

| # | 来源 | 当前入口 | 当前行为 | 目标形态 |
|---|------|---------|---------|---------|
| W1 | 人工设计器 | `POST/PUT/DELETE /api/ontologies/...` → `TypeRegistry` → `OntologyService` | 直接写；无角色校验 | 网关应用，`origin=human` |
| W2 | AI 助手 | `/api/assistant/tools/execute` → `write_tools.py` → `OntologyService` | 直接写；无审批 | 只产 `OntologyChangeProposal`，人工确认后网关应用 |
| W3 | USL 写回 | `usl_writeback` → `OntologyService` | 直接写；自动建 `USL__` 本体；静默降级 | 显式投影到**本体草案**，网关应用，`origin=usl` |
| W4 | HE 导入 | `extract_service._write_to_ontology` → `OntologyService` | 直接写；异常吞掉 | HITL 预览后由网关应用，`origin=extract` |
| W5 | 感知链路 | `perception/hub.py` → `TypeRegistry` 或 `oms.create_object_type` | 有 `ontology_id` 走注册表，否则回退 OMS | 必须绑定本体；否则产提案/显式拒绝，`origin=perception` |

### 1.4 与既有规格的对齐结论

| 冲突点 | 原表述 | 本次结论 | 处理 |
|--------|--------|---------|------|
| **C1 两态分离** | `ARCHITECTURE_FOUR_STEPS.md:17,99`「编辑态/探查态强制分离」 | 分离的是**读写通道**，不是产品页面。操作上提供探查/编辑模式，服务端按权限强制 | 工作台一个页面两种模式；改文档措辞为「读写通道分离 + 模式/权限门」 |
| **C2 即时保存 vs 变更集** | spec 003 US5/FR-035「修改即时保存」 | 不冲突。即时保存写草案；变更集聚合逻辑单元；版本发布是独立门 | 三层保存模型（§4.3） |
| **C3 RDF vs USL 审批** | spec 007 FR-060 导入导出 | 不冲突。RDF 是序列化/传输格式，审批归属仍在 USL 变更集 | 只导出已发布版；导入落草案（§4.9） |
| **C4 USL 审批归属** | US6：USL 正式表变更走 Candidate → QG → 审批 → 写回 | 不是归属冲突，是**发布态缺失**：审批通过后直接写活表，消费方立即读到 | 新增 domain 级发布版本；候选审批写草案，发布另走版本门（§4.2） |
| **C5 AI 直接写入** | `write_tools.py` 直写 TBox | 真实缺陷。AI 在任何权限下都不直接写入 | AI 只产提案；网关是唯一写入通道（§4.5/§4.6） |

### 1.5 设计边界（用户已确认）

1. USL 直接 CRUD **保留**，语义收敛为「编辑草案」；发布必须走审核。
2. USL **不纳入**本体特有构造（Action/Process/Rule/Function/Indicator）；USL 治理业务语义（对象/关系/属性 + 约束），本体治理结构。
3. 现有语义管理页不删除，降级为高级工具；工作台成为主入口。

---

## 2. 已锁定决策

| # | 决策 | 理由 |
|---|------|------|
| D1 | USL 是业务语义的唯一权威源 | 避免「术语一份、本体一份、文档一份」三份真值 |
| D2 | `usl_*` 工作表 = 草案；发布版本 = 不可变快照；消费方只读已发布版本 | 草案与发布物理分层，消费方无需逐表过滤状态 |
| D3 | 生命周期 `draft → pending_review → published → deprecated`；驳回回 `draft` | 与现有两级审批语义兼容，状态机可测试 |
| D4 | 直接 CRUD 保留，写草案，不触发发布 | 不打断现有运营习惯；发布门单独加 |
| D5 | 保存/变更集/版本三层分离 | 即时保存与变更集不冲突；各自有明确触发条件 |
| D6 | 变更集是审核与发布的最小单元；复合操作原子 | 避免「关系建了、端点没建」的半成品进入审核 |
| D7 | 发布必须人工审核；AI 只做预审与存疑标注 | 延续 ADR-086/090「采不采永远人决定」 |
| D8 | 单向流：USL 发布版 → 本体草案 → 本体稳定版 → 消费；反向只出提案 | 本体只有一条建设/更新通道；不允许本体反写 USL |
| D9 | `OntologyWriteGateway` 是唯一写入通道；所有来源产提案 | 权限、审计、版本、校验、OMS 同步只实现一次 |
| D10 | AI 无直接写入；只产提案，继承调用者身份与权限 | 回答 C5；避免 AI 提权与不可审计变更 |
| D11 | 一个工作台、四工作区、三视图；探查/编辑是模式 + 服务端权限 | 回答「不存在只读与编辑两个工作台」 |
| D12 | USL 不含本体特有构造 | 业务语义与结构建模分离，避免 USL 变成第二个本体 |
| D13 | RDF 只导出已发布版；导入落草案并生成变更集 | RDF 不是审批通道；防止绕过审核 |
| D14 | 消费方固定版本；升级是显式动作 | 防止发布瞬间改变问答/抽取/校验行为 |
| D15 | 并发用 `revision` + 409 乐观锁；撤销用操作日志；发布版不可回卷 | 替代 spec 003 的单用户假设；发布版不可变 |
| D16 | 迁移把现有域快照为 `v1` 已发布；消费切换有显式开关与启动告警 | 兼容既有数据；开关可回退，不是静默兜底 |
| D17 | 新增 import-linter 契约 C5 守住单一写入通道 | 契约比约定可靠；债账只减不增（ADR-080 纪律） |

---

## 3. 关键事实（决定实现方式）

- **工作表即草案**：`usl_domains`/`usl_terms`/`usl_hierarchies`/`usl_property_specs`/`usl_disjoint_pairs`/`usl_cardinalities` 继续作为当前草案存储。这样现有 CRUD、候选写回、质量闸全部无需改表即可继续工作，只是消费方改读发布快照。
- **发布快照不需要复制六张表**：一条 `usl_domain_versions.snapshot_json` 保存整个 domain package，结构上保证不可变，避免六套 `*_published` 表与双份真值。
- **本体版本已有稳定态语义**：`ontology_schema_versions.is_stable` + `schema_snapshot` + `commit_schema_version` 已实现「把当前工作版本标 stable、再建新工作版本」；可直接作为「本体稳定版」。
- **候选审批状态机已完整**：`DRAFT → QUALITY_GATED → PENDING_REVIEW → AUDITOR_APPROVED → ADMIN_PENDING → APPROVED`；最终审批写回失败会停在 `APPROVED` 可重试。USL 发布门接在「候选审批之后、消费之前」，不重造审批。
- **权限依赖已存在**：读 `get_current_user`；写 `verify_semantic_writer`；终审 `verify_semantic_admin_only`。新生命周期加 `verify_semantic_reviewer` / `verify_semantic_publisher`；本体写加 `verify_ontology_writer`。
- **图谱组件已具备大部分能力**：Sigma.js 布局切换、搜索、类型过滤、审计过滤、小地图、路径搜索、社区检测、全屏、快捷键；缺的是受控选中态与外部高亮。
- **撤销服务可扩展**：现有 `resource_types` 是白名单；新增 `usl_change_item` / `ontology_type` 需要扩展白名单与逆操作构造，不复用 `ontology_version` 语义。
- **菜单是 seed 驱动**：新增菜单必须改 `seed_four_steps.py`；已有 DB 需迁移脚本（seed 幂等 skip 陷阱）。

---

## 4. 设计

### 4.1 总体架构

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          统一语义层工作台（前端）                          │
│  定义 workspace │ 审核 workspace │ 发布 workspace │ 探查 workspace          │
│  三视图：图谱 / 卡片墙 / 表格；共享选中态；URL 深链；能力驱动按钮            │
└───────────────┬──────────────────────────────────────────────┬───────────┘
                │ /api/semantic-admin/workbench/*               │ /api/ontologies/*
                ▼                                              ▼
┌───────────────────────────────┐              ┌───────────────────────────────┐
│  usl_manager（草案 CRUD）      │              │  OntologyWriteGateway         │
│  usl_publish（版本/变更集/审核）│              │  （唯一 TBox 写入口）          │
│  candidate_store（候选）        │              │  权限/校验/版本/审计/OMS 同步  │
│  quality_gate（质量闸）         │              │  proposal 应用/幂等/冲突检测   │
└───────────────┬───────────────┘              └───────────────┬───────────────┘
                │ SQLite                                        │ SQLite + Neo4j
                ▼                                              ▼
┌───────────────────────────────┐              ┌───────────────────────────────┐
│ usl_* 草案表                   │              │ ontology_* / TBox / ABox      │
│ usl_domain_versions（快照）    │              │ ontology_schema_versions       │
│ usl_change_requests/items      │              │ ontology_change_proposals      │
└───────────────┬───────────────┘              └───────────────┬───────────────┘
                │ PublishedUslView（只读、按版本固定）           │
                ▼                                              ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ 消费方：本体构建投影 / 数据标准 / 数据提取门控 / QA / SHACL / 语义检索      │
│ 每条消费记录 usl_version_id；版本升级是显式动作；未发布域显式报错           │
└──────────────────────────────────────────────────────────────────────────┘

反向通道（只出提案，不反写）：
  本体侧缺口 / 漂移 / AI 建议 ──→ gap_pool / change proposal ──→ USL 草案变更集
```

### 4.2 USL 发布生命周期与版本模型

#### 4.2.1 状态机

```
                 submit                  approve (reviewer+)
   draft ─────────────────→ pending_review ─────────────────→ published
     ↑                            │                              │
     │ reject / request_changes  │                              │ deprecate
     └────────────────────────────┘                              ▼
                                                              deprecated
   published ──(rollback)──→ 新建 draft 变更集（不移动 published 指针）
```

- `draft`：工作表可编辑；不进入消费。
- `pending_review`：变更集冻结；工作表仍可被同一变更集外的写入影响，但**审核基于提交时的 diff 快照**，不基于活的草案表。审核期间若草案继续变化，提交的 diff 不变；批准时若 `base_content_hash` 与当前草案不一致，返回 409 要求 rebase。
- `published`：不可变快照；`usl_domains.published_version_id` 指向它。
- `deprecated`：不再允许新本体/新抽取会话选择；已固定的消费者继续可用，直到显式升级。
- 一个 domain 同时最多一个 `published` 版本；旧版本标 `SUPERSEDED`。

#### 4.2.2 版本对象

`usl_domain_versions`：

| 字段 | 说明 |
|------|------|
| `version_id` | UUID |
| `domain_id` | 所属域 |
| `version_no` | 单调递增整数，展示为 `v{n}` |
| `status` | `PUBLISHED` / `SUPERSEDED` / `DEPRECATED`（版本只在发布时创建，不存在草稿版本） |
| `schema_version` | 快照格式版本，首版 `usl-package-v1` |
| `snapshot_json` | 完整 domain package（见 §4.11.1） |
| `content_hash` | `sha256:` + snapshot 规范化 JSON 的哈希 |
| `changelog` | 发布说明 |
| `parent_version_id` | 上一发布版本 |
| `source_change_request_id` | 产生该版本的变更集 |
| `created_by` / `created_at` / `published_by` / `published_at` | 审计 |

#### 4.2.3 发布事务

发布不是「改一个状态字段」，而是一个原子事务：

1. 校验草案：引用完整性（hierarchy/cardinality 两端存在）、无环、canonical 唯一、属性类型合法、基数上下界合法、不相交对不重复。
2. 构建快照 + `content_hash`；若与当前 `published_version_id` 的快照一致，返回 `USL_NO_CHANGES_409`（不产生空版本）。
3. 插入新版本 `PUBLISHED`。
4. 原 `PUBLISHED` 版本改 `SUPERSEDED`（若存在）。
5. 更新 `usl_domains.published_version_id`。
6. 追加 `usl_publication_events`（`published`）。
7. 事务提交后发布 `usl.version.published` 事件；`PublishedUslView` 以 `version_id` 为缓存键，每次解析先读 `usl_domains.published_version_id`（单行索引查询），指针变化自然换键，不依赖跨进程缓存失效广播（4 worker 部署安全）。
8. 任一步失败 → 整体回滚，`published_version_id` 不变。

#### 4.2.4 候选审批、写回与发布的关系

- 现有 OL 候选审批链（`candidate_store` → `quality_gate` → 两级审批 → `usl_writeback`）保持不变；审批通过后的写回目标仍是 `usl_*` 工作表，即**草案**。
- 候选写回必须同时生成 `usl_change_items`（`origin=ol_pipeline`），使草案变化可审核、可追溯；不再出现「审批通过即被消费」的隐式发布。
- 草案进入发布态仍需 domain 级变更集审核 + 发布；候选审批只完成「草案接受」，不完成「语义发布」。
- USL → 本体的写回改名为「投影」，是独立的显式动作（§4.8.2），不随候选审批自动执行。

#### 4.2.5 回滚

- **不允许**把 `published_version_id` 直接指回旧版本（那会让已固定的消费者在不知情下换语义）。
- `POST /usl/domains/{id}/rollback` 的语义是：以目标版本快照为内容，创建一个新的 draft 变更集，走正常审核发布，产生 `v{n+1}`。
- 发布事件记录 `rollback_of_version_id`，审计可追溯。

#### 4.2.6 废弃

- `deprecate` 只允许对当前 `published` 版本执行，需要 `semantic.publish` 权限。
- 废弃同时设置版本 `status=DEPRECATED` 与域 `lifecycle=deprecated`：前者标记快照不再推荐，后者阻止新投影/新抽取会话选择该域。已有固定版本的消费者继续读到快照；工作台显式提示「已废弃」。
- `lifecycle=active` 为默认；`archived` 仅用于无任何发布版本的空域，归档后不可编辑。
- 域删除（`DELETE /usl/domains/{id}`）走 `verify_semantic_admin_only`，且必须满足：无 `PUBLISHED` 版本，或已显式废弃。删除只移除**工作表与域记录**；`usl_domain_versions` 中已发布快照与 `usl_publication_events` **不物理删除**，转为 `status=DEPRECATED` + `domain_lifecycle=archived` 保留审计（消费者若仍固定该 `version_id` 继续可读，直至其自行升级）。删除动作记录 `usl.domain.deleted` 事件并保留 `deleted_at`，不做物理级联。

### 4.3 三层保存模型（回答 C2）

| 层 | 触发 | 写入对象 | 是否审核 | 是否影响消费 | UI 反馈 |
|----|------|---------|---------|-------------|---------|
| **L1 自动保存** | 字段编辑后 600ms 防抖 / 失焦 / 显式 Ctrl+S | 草案表对应行（原子 UPDATE，带 `revision`） | 否 | 否 | 「已保存到草稿」+ 未发布徽标 |
| **L2 变更集** | 进入编辑会话自动开一个；或用户「新建变更集」 | `usl_change_requests` + `usl_change_items` | 否（草稿态） | 否 | 变更集面板：N 项变更、可撤销 |
| **L3 版本发布** | 「提交审核」→ 审核通过 → 发布 | `usl_domain_versions` + `published_version_id` | 是 | 是 | 版本时间线 + 发布说明 |

**L1 的校验边界**：自动保存只做**单行级校验**（字段类型、长度、枚举合法性、canonical 字符集、必填非空），通过即落库；跨行/跨实体约束（层级无环、基数两端存在、不相交对互斥）不在 L1 执行——它们要么依赖尚未保存的对端行，要么需要全量扫描。跨行校验放在三个显式时点：① 变更集提交审核时全量校验；② 发布事务内再校验一次（防止审核后草案被并发改动）；③ 用户在 UI 主动触发「校验」按钮时即时反馈。L1 校验失败时不写入，返回 `USL_FIELD_INVALID_422` + 字段定位，前端就地标红；不静默保留非法值，也不把非法值写进草案。

**变更项合并（coalescing）**：连续编辑同一行同一字段时，不产生 N 条 `usl_change_items`。规则：同一 `(change_request_id, entity_kind, entity_id, field_path)` 在 **5 分钟窗口**内且尚未提交时，更新最后一条 item 的 `after_json`、累加 `edit_count`、保留最早的 `before_json`；撤销时按 `before_json` 恢复，与是否合并无关。窗口与字段范围写入配置（`usl.change_item_coalesce_window_seconds`），不硬编码。跨越窗口、跨字段、跨实体不合并，保证 diff 可读且可审计。

**变更项不是暂存区**：变更项在写入时即落草案表（同一 SQLite 事务），`usl_change_items` 是已应用变更的审计/差异日志，不是「待应用的草稿」。`draft` 状态的变更集可继续追加 items；提交时冻结为 diff 快照（`submitted_content_hash`）。这样自动保存、撤销、审核看到的是同一份事实，不需要第四层「暂存/已应用」状态。

**复合操作示例**：新建关系「下单」+ 创建两端对象类型 + 设置基数，是一个 `atomic=true` 的变更集。客户端通过一次批量请求提交全部 items；服务端在**同一个 SQLite 事务**里校验并应用全部 items，任一失败全部不落。自动保存只保存单个字段，不承担复合语义；复合操作期间前端暂停逐字段自动保存，改为整组提交。

**撤销**：
- 前端保留最近 50 个操作（会话级）；每个 `usl_change_item` 服务端存 `inverse_json`，撤销时按逆操作 + 当前 `revision` 校验应用。
- 跨变更集撤销：只允许撤销**未提交**（draft）变更集；已提交/已发布不可撤销。
- 发布后的「撤销」= 新建回滚变更集（§4.2.5），不是时间倒流。
- 50 级是 UI 上限；服务端操作历史不截断，供审计。

**并发**：
- 每行 `revision INTEGER NOT NULL DEFAULT 1`；更新必须带 `expected_revision`，不匹配返回 409 + 当前行。
- 变更集记录 `base_content_hash`；审核批准时若草案已变，返回 409 要求 rebase（重新生成 diff），不自动合并。
- 不做 CRDT/实时协同；多标签页通过 revision 冲突显式提示。

### 4.4 变更集与审核

#### 4.4.1 变更集状态

```
draft ──submit──→ pending_review ──approve──→ approved ──publish──→ merged
  │                    │
  │                    ├──reject──→ rejected
  │                    └──request_changes──→ draft
  └──abandon──→ abandoned
```

- `draft`：可继续加 items；可放弃。
- `pending_review`：冻结 diff 快照；可被审核人批准/驳回/要求修改。
- `approved`：审核通过、尚未发布；发布失败可重试（与候选 APPROVED 可重试语义一致）。
- `merged`：已生成发布版本。
- 一个 domain 同时最多一个 `pending_review` 变更集，避免审核队列分叉。

#### 4.4.2 变更项

`usl_change_items`：

| 字段 | 说明 |
|------|------|
| `id` / `change_request_id` / `seq` | 主键、所属、顺序 |
| `op` | `add` / `update` / `delete` / `rename` |
| `entity_type` | `domain` / `term` / `hierarchy` / `property_spec` / `disjoint_pair` / `cardinality` |
| `entity_id` | 目标行 ID（add 时为空，服务端生成） |
| `before_json` / `after_json` | 变更前后完整快照 |
| `inverse_json` | 逆操作，用于撤销 |
| `edit_count` | 合并计数（同字段连续编辑，默认 1） |
| `origin` | `human` / `ai` / `ol_pipeline` / `import`，用于审计与 AI 预审 |
| `created_at` / `created_by` | 审计 |

`diff_json` 不单独存储，由 items 聚合生成；审核页按 `entity_type` 分组展示。

#### 4.4.3 AI 预审（辅助，不决策）

提交审核时同步执行一次预审（也可手动重跑），结果写 `usl_change_requests.ai_review_json`：

```json
{
  "model": "…",
  "prompt_version": "usl-review-v1",
  "generated_at": "…",
  "summary": "12 项变更，3 项存疑",
  "doubtful": [
    {"item_id": "…", "severity": "high", "reason": "术语与既有 canonical 语义冲突", "suggestion": "合并或改名"},
    {"item_id": "…", "severity": "medium", "reason": "缺少定义", "suggestion": "补充 definition"}
  ],
  "checks": [
    {"name": "canonical_unique", "status": "pass"},
    {"name": "hierarchy_acyclic", "status": "pass"},
    {"name": "type_consistency", "status": "warn", "detail": "…"}
  ]
}
```

- 确定性检查（唯一性、环、类型、基数、引用完整性）由代码执行，**不交给 LLM**。
- LLM 只做语义层建议（命名冲突、定义缺失、同义词歧义），输出必须带 `item_id` 与证据；解析失败则该次预审标 `failed`，不阻塞人工审核。
- 人工审核默认只看 `doubtful` 项；「全部通过」需要显式展开全部 diff。
- AI **不能**自动批准、自动发布、自动合并；`ai_review_json` 只是证据。

#### 4.4.4 审核动作与四眼原则

| 动作 | 权限 | 前置状态 | 结果 |
|------|------|---------|------|
| `submit` | `semantic.draft.write` | draft | pending_review |
| `approve` | `semantic.review` | pending_review | approved |
| `reject` | `semantic.review` | pending_review | rejected |
| `request_changes` | `semantic.review` | pending_review | draft |
| `publish` | `semantic.publish` | approved | merged + 新版本 |
| `abandon` | 创建者或 `semantic.admin` | draft | abandoned |

- `created_by == reviewer` 时禁止批准（四眼原则），返回 `USL_SELF_APPROVAL_FORBIDDEN_403`；管理员也不能自批。
- 审核人可修改单个 item 后批准（`modify_then_approve`），修改本身作为新 item 记入 diff，审计保留。
- 发布可由「最终批准」自动触发（配置 `usl.auto_publish_on_approve=true`，默认 true），也可拆成两步；拆两步时 `approved` 状态可见。

### 4.5 单一写入通道 `OntologyWriteGateway`

#### 4.5.1 定位

`TypeRegistry` 已经是对象/关系/动作/过程/规则/函数/指标的类型写入入口，并负责 OMS 同步；但它只做「转发 + 同步」，没有权限、版本、提案、审计。设计把它升级为 `OntologyWriteGateway`：

```
外部来源（HTTP / AI / USL / HE / 感知）
        │
        ▼
OntologyChangeProposal（统一提案模型）
        │  apply(proposal, actor, origin)
        ▼
OntologyWriteGateway
  ├─ 权限校验（actor + role + workspace + origin）
  ├─ 输入校验（schema / 引用 / 命名 / 密级）
  ├─ 幂等键（proposal_id / idempotency_key）
  ├─ 乐观锁（ontology_revision / type_revision）
  ├─ 应用（内部调用 TypeRegistry → OntologyService → OMS 同步）
  ├─ 版本标记（写入当前工作版本；稳定版仍由 commit 产生）
  └─ 审计（origin / actor / proposal_id / before / after / trace_id）
```

`OntologyService` 退居为**读 + 低层写实现**；`public.py` 对写只暴露网关，读继续暴露查询服务。迁移期内保留 `OntologyService` 导出，但写方法加必填 `origin` 参数（见 §4.5.4）。

#### 4.5.2 提案模型

`ontology_change_proposals`：

| 字段 | 说明 |
|------|------|
| `proposal_id` | UUID |
| `ontology_id` | 目标本体 |
| `origin` | `human` / `ai` / `usl` / `extract` / `perception` |
| `status` | `pending` / `applied` / `rejected` / `superseded` / `failed` |
| `title` / `summary` | 人读 |
| `operations_json` | 有序操作列表（create/update/delete type/property/link） |
| `diff_json` | 归一化 diff，供 UI 展示 |
| `evidence_json` | AI/抽取/感知证据：模型、prompt hash、文档、span、置信度 |
| `idempotency_key` | 来源幂等键 |
| `base_ontology_revision` | 乐观锁基线 |
| `created_by` / `created_at` / `applied_by` / `applied_at` / `reject_reason` | 审计 |

操作应用语义：
- 全部操作在一个逻辑事务中；任一失败 → 提案 `failed`，记录失败项；已应用部分不静默保留。
- `apply` 需要 `ontology.draft.write`；AI 来源的提案额外要求调用者确认（前端显式按钮），不因 `origin=ai` 自动提权。
- 应用后写入本体**当前工作版本**；不自动 `commit_schema_version`。稳定版仍由人工提交。

#### 4.5.3 来源矩阵

| 来源 | 谁创建提案 | 谁应用 | 默认行为 | 审计字段 |
|------|-----------|-------|---------|---------|
| `human` | 工作台/设计器 | 同一有权限用户 | 保存即应用（L1 自动保存） | actor、type_revision |
| `ai` | AI 工具 | 人工在提案面板点击应用 | 只创建提案；不自动应用 | model、prompt_hash、confidence、evidence |
| `usl` | 用户显式「投影到本体」 | 同一有权限用户 | 预览 → 应用；不自动跟随发布 | usl_domain_code、usl_version_id、content_hash |
| `extract` | HE 抽取会话 | 预览确认后应用；`auto_apply` 需显式开启 | 默认 HITL；失败逐项报告 | session_id、document_id、span |
| `perception` | 感知链路 | 配置了绑定本体且有写权限时应用；否则只产提案 | 无绑定 → `proposal`，不再回退 OMS | event_id、extractor、ontology_id |

#### 4.5.4 架构强制

1. **import-linter 新契约 C5**：契约名为 `C5-ontology-single-write-channel`，`type=forbidden`，`source_modules` 逐项列出 `odap.biz` 下除 `odap.biz.core.ontology` 外的所有子域 + `odap.infra` / `odap.tools` / `odap.web`（与 C3 的 source 清单一致，不能只写 `odap.biz`，否则会把 ontology 内部网关自身也判违规），`forbidden_modules=["odap.biz.core.ontology.ontology_api.services.ontology_service"]`，`allow_indirect_imports=true`（防止经 `public.py` 以外的中转绕行；`public.py` 属于 ontology 包自身，不在 source 中）。
   - 写方法不得对外暴露：`public.py` 的 `_PUBLIC_MAP` 只导出 `OntologyWriteGateway` 与读服务（`OntologyReadService`/现有读方法），不导出 `OntologyService` 的 `create_*`/`update_*`/`delete_*`/`commit_schema_version`。
   - 迁移期以 `ignore_imports` 逐条登记现有 W1–W5 调用点与对应移除任务号；**只减不增**（与 ADR-080 C4 同一纪律），每条 ignore 上线即关联一个 P 期退出条件。
2. **写方法 `origin` 必填**：`OntologyService.create/update/delete_*` 增加 keyword-only `origin`；迁移期默认 `legacy` 并每次调用 `logger.warning` + metric `ontology_legacy_write_total{caller}`；C5 清零后改为必填、删除默认值。
3. **public 门面只暴露网关**：`public.py` 的 `_PUBLIC_MAP` 写入口改为 `OntologyWriteGateway`；`OntologyService` 仅保留读方法导出。外部模块（assistant/USL/HE/perception）只能通过 `public` 拿到网关。
4. **回归守卫**：新增架构测试，断言外部模块不 import `OntologyService` 写方法；`lint-imports` 4→5 contracts。

#### 4.5.5 五条路径迁移

- **W1 人工**：路由从 `_get_type_registry()` 改为 `gateway.apply()`；权限从 `get_current_user` 改为 `verify_ontology_writer`；行为不变（保存即应用），但增加 revision/审计。
- **W2 AI**：删除 `write_tools.py` 的直写工具，替换为 `propose_ontology_change`；注册表中移除直写工具，避免模型误用；前端提案面板展示 diff + 应用按钮。
- **W3 USL**：`usl_writeback` 重命名语义为 `usl_projection`；必须显式指定 `ontology_id`，删除 `USL__` 自动建本体；缺 source/target 返回错误，不再降级；调用 `gateway.apply(origin="usl")`。
- **W4 HE**：`_write_to_ontology` 改为生成提案/预览结果；异常逐项收集并返回 `{"status":"error","items":[...]}`，不再 `warning + return`；应用阶段走网关。
- **W5 感知**：`PerceptionHub` 必须拿到绑定本体（事件字段或 workspace 默认绑定）；无绑定 → 创建 `perception` 提案 + `status=proposed`；不再调用 `oms.create_object_type`。

### 4.6 AI 提案流（回答 C5）

**结论：不存在「AI 有权限就直接写」的场景。** AI 的唯一写能力是创建提案。

| 场景 | AI 能做什么 | AI 不能做什么 | 权限依据 |
|------|------------|--------------|---------|
| 本体设计对话 | 生成类型/属性/关系的提案、解释影响 | 直接创建/修改/删除类型；提交版本 | 调用者 `ontology.propose` |
| USL 定义 | 生成术语/同义词/属性/约束草案、预审标注 | 写入正式表；批准；发布 | 调用者 `semantic.draft.write` |
| 抽取/导入 | 生成候选与提案 | 直接写 TBox；绕过 HITL | 会话权限 + `auto_apply` 显式开启 |
| 缺口修复 | 生成变更提案/路由工单 | 自动晋升、自动发布 | 调用者写权限 |

约束：
- AI 继承调用者身份；不服务账户、不拓宽 scope。
- 提案记录 `origin=ai`、`model`、`prompt_version`、`confidence`、`evidence`。
- 前端应用 AI 提案时必须二次确认；确认动作记为 `applied_by=<user>`，审计同时保留 `origin=ai`。
- 配置 `ai.write_mode` 只有 `proposal` 一个合法值；出现其他值启动失败（显式），防止以后被改成 `direct`。

### 4.7 工作台信息架构

#### 4.7.1 路由与菜单

- 路由：`/semantic-admin/workbench`（主入口）。
- URL 状态：`?ws=define|review|publish|explore&mode=explore|edit&domain=<code>&ontology=<id>&version=<id>&view=graph|cards|table&node=<kind:id>&panel=detail`
- 嵌入：追加 `embed=1`，强制 `mode=explore` + `ws=explore`，隐藏全局导航与工作台侧栏，只渲染当前视图与详情面板；用于第三方系统 iframe 引用。`embed=1` 与服务端能力查询无关——**服务端仍按调用者权限返回数据**，嵌入不额外授权；无 `semantic.read` 时返回 403 而非空白框架。嵌入不提供第二套页面，只是同一工作台的布局开关（§9 第 9 条）。
- 菜单：`建本体 / 语义管理 / 统一语义工作台` 置顶；原「USL 配置 / USL 本体管理 / OL 流水线 / 候选管理 / 审批工作流 / 质量仪表盘 / 概念缺口 / 缺口统计」保留在「语义管理（高级）」子目录。
- 旧页不删除；工作台通过深链跳转到高级操作（如 OL 流水线运行详情）。

#### 4.7.2 四工作区

| 工作区 | 目标用户 | 核心能力 | 数据源 |
|--------|---------|---------|--------|
| **定义 Define** | 语义编辑者 | 草案 CRUD、AI 生成草案、变更集、自动保存、撤销、提交审核 | 草案表 + `usl_change_requests` |
| **审核 Review** | 审核人 | 待审队列、diff、AI 存疑项、逐项通过/修改/驳回、四眼校验 | `usl_change_requests` + `ai_review_json` |
| **发布 Publish** | 发布人 | 版本时间线、发布说明、发布/废弃、回滚变更集、导出 | `usl_domain_versions` |
| **探查 Explore** | 业务人员/全体 | 只读图谱/卡片/表格、搜索、详情、影响面、版本切换 | `PublishedUslView` + 本体/实例图谱 |

**定义区的 AI 生成草案流**（与人工编辑共用同一份草案事实，不产生旁路）：

1. 用户在 Define 区发起「AI 生成草案」，提供范围（域 + 业务描述/文档片段）与意图（新增术语、补同义词、补属性、补层级）。
2. 服务端以**调用者身份**调用 LLM，产出结构化候选 `{terms, properties, hierarchies}`；先做确定性校验（canonical 冲突、重复、非法字段），再落 `usl_change_items`（`origin=ai`），并即时写入草案表，与人工编辑一样受 revision 与撤销约束。
3. 前端以 **diff 预置视图**展示：逐条可接受/修改/丢弃；接受即保留该 item，丢弃则按 `inverse_json` 撤销该项。默认不全选。
4. 提交审核时与人工变更合并为同一变更集；`ai_review_json` 会额外标注 AI 生成项，审核人可一键筛选「仅看 AI 项」。
5. AI 生成失败或候选为空时，显式返回 `USL_AI_DRAFT_EMPTY_422`/`USL_AI_DRAFT_FAILED_502`，不写入空变更集、不静默回退为人工空白表单。

#### 4.7.3 三视图与共享状态

- **图谱**：复用 `GraphView`/`GraphCanvas`（Sigma.js）。新增受控属性：`selectedNodeId`、`onSelectNode`、`highlightIds`。USL 视图节点=术语，边=层级/基数/属性归属；本体视图节点=对象类型，边=关系类型；实例视图节点=实体，边=事实。
- **卡片墙**：新增 `SemanticCardWall`。卡片字段：canonical、display_name、semantic_type、definition 摘要、同义词数、属性数、层级父/子数、热度（gap heat）、状态徽标（草案/待审/已发布/废弃）、置信度、来源版本。支持按类型分组、搜索、筛选、批量选择。
- **表格**：复用 `AdvancedTable`/AntD Table，列可配置、导出当前筛选。
- **共享选中态**：Zustand `workbenchStore` 保存 `scope/domain/ontology/version/view/selectedNodeId/filters/search`；图谱选中 ↔ 卡片高亮 ↔ 详情面板三者同步；URL 为可分享的真源。
- **详情面板**：统一 DTO（§4.12.3），包含定义、同义词、属性、约束、层级、引用它的本体类型、最近缺口信号、变更历史、权限能力。

#### 4.7.4 模式与权限

- `mode=explore`：只读；默认。所有编辑控件不渲染（不是禁用后仍可点）。
- `mode=edit`：进入前调 `GET /workbench/capabilities`；无 `semantic.draft.write` → 显示明确拒绝原因，不切换。
- 审核/发布工作区按 `semantic.review`/`semantic.publish` 显示；无权限则不显示入口。
- 服务端每个写接口独立鉴权；前端能力查询只是 UX，不作为安全边界。

#### 4.7.5 空态/加载/错误

- 未选择域：引导选择或创建；不默认加载全量。
- 域未发布：探查区显示「尚未发布」+ 发布入口（有权限时）；不展示草案内容给无草案读权限的用户。
- 图过大：服务端 `truncated=true` + 建议筛选；前端显示「已截断，请缩小范围」，不静默画部分图。
- 409 冲突：弹出「他人已修改」+ 当前值/我的值，提供刷新/覆盖（覆盖需重新提交变更集）。
- 403：显示所需角色，不伪装成空数据。
- 失败：错误码 + 可操作建议；不吞异常、不返回假成功。

### 4.8 消费与门控

#### 4.8.1 版本固定

所有消费入口必须显式携带或解析 `usl_version_id`：

| 消费方 | 固定方式 | 未发布/无版本时 |
|--------|---------|----------------|
| 本体构建投影 | 用户在投影向导选择 `domain_code + version_id` | 明确报错 `USL_NOT_PUBLISHED_409`，不静默用草案 |
| 数据提取门控 | 抽取会话开始时解析并写入 `usl_version_id` | `gate=block` 时失败；`gate=off` 需显式理由并审计 |
| QA | 请求解析域的最新发布版本，响应记录 `usl_version_id` | 不做语义增强，响应元数据标 `usl_status=unpublished` |
| SHACL | 形状生成时固定版本，缓存键含 `version_id` | 不生成 USL 派生形状；日志记录原因 |
| 语义检索/MCP | 检索请求携带 `domain_code`，服务解析发布版本 | 返回 `usl_unpublished` 标记，不读草案 |

#### 4.8.2 本体构建投影

- 输入：`ontology_id` + `domain_code` + `version_id`。
- 预览：把发布包映射为 `object_type/link_type/property/cardinality/disjointness` 的候选操作，生成 `origin=usl` 提案；展示新增/修改/跳过。
- 应用：走网关写入**本体草案**；不自动提交稳定版。
- 溯源：每个类型记录 `source_usl_domain`、`source_usl_version_id`、`source_term_id`、`content_hash`。
- 漂移：本体详情显示「上游有更新版本」；用户可生成升级提案；不自动改已发布本体。
- 不做：USL 不生成 Action/Process/Rule/Function/Indicator；这些由本体设计器单独维护。

#### 4.8.3 数据标准

- `GET /usl/published/{domain_code}/standards` 输出：术语表（canonical/synonyms/definition/semantic_type）、属性规格（data_type/unit/required）、层级、基数、不相交对、版本与 hash。
- 导出 CSV/JSON/YAML；供数据治理、指标口径、外部系统对接。
- 标准包带 `version_id + content_hash`；下游引用必须记录版本，不能只记域名。

#### 4.8.4 数据提取门控

- 抽取会话字段：`usl_domain_code`、`usl_version_id`（开始时解析）、`usl_gate_mode ∈ {block, warn, off}`。
- 默认 `block`：有绑定域时必须通过发布包校验；无发布版本 → 会话创建失败（提示先发布）。
- `warn`：违规记录但继续，结果标 `usl_gate_status=warn`；需 `semantic.review` 或显式会话配置。
- `off`：必须填写 `reason`，审计记录；用于历史数据回灌/实验。
- 校验项：术语是否存在（canonical/synonym/alias）、语义类型是否允许、属性名/类型/单位、基数、不相交、必填。
- 未知术语：不静默接受；产生 `concept_gap` 信号 + 候选提案（复用 gap_pool），并按 `gate_mode` 阻断或告警。
- 结果记录 `violations[]`（term、rule、expected、actual、severity），可导出。

#### 4.8.5 QA 与 SHACL

- QA 只读发布包；响应元数据带 `usl_domain_code/version_id/content_hash`，便于答案追溯。
- SHACL 形状缓存键从 `domain_code` 改为 `(domain_code, version_id, content_hash)`；发布新版本不污染旧形状。
- 未发布域：QA 仍可基于本体/图谱回答，但明确标记未应用 USL 约束；不把草案当发布。

### 4.9 RDF 导入导出（回答 C3）

- **格式**：`json`、`yaml`（HE 模板兼容）、`turtle`、`rdfxml`。首版用 `rdflib`；映射规则版本 `usl-rdf-mapping-v1`。
- **导出**：只允许 `published` 版本；URL 必须带 `version_id` 或解析最新发布版；响应头 `X-USL-Version` / `X-USL-Content-Hash`。草案导出需显式 `?draft=true` 且需要 `semantic.draft.write`，并在文件头标注 `DRAFT`。
- **导入**：解析 → 结构校验 → 与当前草案 diff → 生成 `draft` 变更集；**永不直接发布**。冲突项标记 `doubtful`，人工决策。导入结果返回 `change_request_id`。
- **范围**：只映射 USL 治理对象（term/hierarchy/property_spec/cardinality/disjoint_pair）；不导入本体特有构造、审批记录、角色分配、版本历史。
- **失败**：解析错误 422 + 行列/节点定位；不支持的三元组收集为 `unsupported[]`，不静默丢弃。
- **不承诺**：RDF 往返不保证保留 ODAP 内部 ID、审计字段、审批状态；以 `canonical + domain_code` 作为业务键。

### 4.10 权限矩阵

| 能力 | 全局角色 | 工作空间角色 | 说明 |
|------|---------|-------------|------|
| `semantic.read` | 所有已认证 | 任意成员 | 读已发布包；草案读需额外权限 |
| `semantic.draft.read` | admin / schema_auditor / editor | term_editor / domain_editor / reviewer / owner / super_admin | 工作台编辑模式、草案预览 |
| `semantic.draft.write` | admin / schema_auditor / editor | term_editor / domain_editor / reviewer / owner / super_admin | 与现有 `verify_semantic_writer` 一致；reviewer 可写草案但不能自批 |
| `semantic.review` | admin / schema_auditor | reviewer / schema_auditor / owner / super_admin | 审核、驳回、要求修改；不能自批 |
| `semantic.publish` | admin | owner / super_admin | 发布/废弃；全局 admin 与域 owner/super_admin |
| `semantic.admin` | admin | — | 删除域、恢复、强制操作 |
| `ontology.read` | 所有已认证 | 任意成员 | 读本体/图谱 |
| `ontology.draft.write` | admin / schema_auditor / editor | schema_auditor / owner / super_admin | 本体编辑、应用提案 |
| `ontology.version.commit` | admin / schema_auditor | schema_auditor / owner / super_admin | 提交稳定版本 |
| `ontology.propose` | 有 `ontology.draft.write` 或 `semantic.draft.write` | 同上 | AI 提案入口；不能应用 |
| `ai.propose` | 继承调用者 | 继承调用者 | 不存在 `ai.write` |

实现：
- 新增 `verify_semantic_reviewer`、`verify_semantic_publisher`、`verify_ontology_writer`、`verify_ontology_committer` 依赖；统一走 `get_current_user` 便于测试 override。
- 现有 `verify_semantic_writer` 不改语义，避免打断现有页面与测试。
- 本体写路由全部替换为 `verify_ontology_writer`；提交版本为 `verify_ontology_committer`。
- 审核四眼：`created_by != reviewer`；管理员也不例外。
- 前端只渲染能力；服务端每个写接口独立校验。

### 4.11 数据模型与迁移

#### 4.11.1 发布快照格式（`usl-package-v1`）

```json
{
  "schema_version": "usl-package-v1",
  "domain": {
    "id": "…",
    "code": "ecommerce",
    "display_name": "电商",
    "description": "…",
    "en_mapping": {}
  },
  "terms": [
    {
      "id": "…",
      "canonical": "订单",
      "semantic_type": "对象类型",
      "synonyms": [],
      "near_synonyms": [],
      "aliases": [],
      "stoplist_flag": false,
      "definition": "…",
      "provenance": {}
    }
  ],
  "hierarchies": [],
  "property_specs": [],
  "disjoint_pairs": [],
  "cardinalities": [],
  "generated_at": "2026-10-28T00:00:00+00:00"
}
```

规范化：哈希只覆盖语义内容（`schema_version`、`domain`、`terms`、`hierarchies`、`property_specs`、`disjoint_pairs`、`cardinalities`），**排除 `generated_at` 等易变字段**；按实体类型 + `id` 排序后 `json.dumps(..., sort_keys=True, ensure_ascii=False, separators=(",", ":"))` 计算 SHA-256。快照不包含角色分配、审批记录、操作日志。`USL_NO_CHANGES_409` 与消费方固定版本均使用该语义哈希，不使用整包 JSON 的字节哈希。

#### 4.11.2 新表

| 表 | 关键列 | 说明 |
|----|--------|------|
| `usl_domain_versions` | `version_id` PK、`domain_id`、`version_no`、`status`、`schema_version`、`snapshot_json`、`content_hash`、`changelog`、`parent_version_id`、`source_change_request_id`、`created_by/at`、`published_by/at` | 发布快照；`UNIQUE(domain_id, version_no)`；`INDEX(domain_id, status)` |
| `usl_change_requests` | `id` PK、`domain_id`、`base_version_id`、`base_content_hash`、`submitted_content_hash`、`title`、`summary`、`status`、`origin`、`diff_json`、`ai_review_json`、`atomic INTEGER NOT NULL DEFAULT 1`、`created_by/at`、`submitted_by/at`、`reviewed_by/at`、`decision_note`、`merged_version_id` | 变更集；`base_content_hash` = 开启时发布版 hash，`submitted_content_hash` = 提交时草案语义 hash |
| `usl_change_items` | `id` PK、`change_request_id`、`seq`、`op`、`entity_type`、`entity_id`、`field_path`、`before_json`、`after_json`、`inverse_json`、`edit_count`、`origin`、`created_by/at` | 变更项；`field_path` 是合并键（§4.3），`INDEX(change_request_id, seq)` + `INDEX(change_request_id, entity_type, entity_id, field_path)` |
| `usl_term_versions` | `id` PK、`table_name`、`row_id`、`old_value_json`、`new_value_json`、`changed_by`、`changed_at`、`change_request_id` | FR-059 不可变历史 |
| `usl_publication_events` | `id` PK、`domain_id`、`version_id`、`event`、`actor`、`at`、`note`、`rollback_of_version_id` | 发布/废弃/回滚审计 |

#### 4.11.3 既有表增量

| 表 | 新增列 | 默认/迁移 |
|----|--------|----------|
| `usl_domains` | `published_version_id TEXT`、`revision INTEGER NOT NULL DEFAULT 1`、`lifecycle TEXT NOT NULL DEFAULT 'active'` | 迁移脚本回填 |
| `usl_terms` | `revision INTEGER NOT NULL DEFAULT 1`、`updated_by TEXT`、`change_request_id TEXT` | 现有行回填 1 |
| `usl_hierarchies` | 同上 | 同上 |
| `usl_property_specs` | 同上 | 同上 |
| `usl_disjoint_pairs` | 同上 | 同上 |
| `usl_cardinalities` | 同上 | 同上 |
| `ontologies` | `published_version_id TEXT` | `is_stable` 仍是稳定版唯一真源；`published_version_id` 是 `commit_schema_version` 事务内同步的冗余指针，便于消费方单行解析，禁止单独修改 |
| `ontology_schema_versions` | `source_usl_version_id TEXT`、`published_by TEXT`、`published_at TEXT`、`content_hash TEXT` | 稳定版回填 hash |
| `ontology_type_definitions`（及各类型表） | `revision INTEGER NOT NULL DEFAULT 1`、`source_usl_term_id TEXT`、`source_usl_version_id TEXT` | 现有行回填 |
| 抽取会话表 | `usl_domain_code TEXT`、`usl_version_id TEXT`、`usl_gate_mode TEXT`、`usl_gate_status TEXT`、`usl_violations_json TEXT` | 现有会话回填空并在读取时显式标记 `legacy` |

#### 4.11.4 迁移脚本

`scripts/migrate_usl_publish_v1.py`：

1. `--dry-run` 输出将创建的表/列、将发布的域、预计版本号。
2. 建表/加列（幂等，`ALTER TABLE ADD COLUMN` 前检查 `PRAGMA table_info`）。
3. 回填 `revision=1`。
4. 对每个 `published_version_id IS NULL` 的域：构建 `usl-package-v1` 快照，插入 `v1` `PUBLISHED`，设置指针，写 `bootstrap_publish` 事件。
5. 校验：域数、术语数、hash、引用完整性；失败列出明细并以非 0 退出。
6. 不自动切换消费模式；切换由部署配置 `USL_CONSUMPTION_MODE` 决定。
7. 所有临时输出写 `apps/api/data/migrations/`（规则 13），不写项目根目录。

#### 4.11.5 消费模式开关

- `USL_CONSUMPTION_MODE=published|draft`，默认 `published`（新部署）。
- `draft` 仅用于迁移期回退：启动时 `logger.warning("USL_CONSUMPTION_MODE=draft: 发布门已关闭，消费方读取草案")`，并在 `/health` 与指标暴露 `usl_consumption_mode=mode`。
- 开关不是静默兜底：必须显式配置；未设置时用 `published`；非法值启动失败。
- 迁移完成后设 `published`，并在下一个版本删除 `draft` 选项（单独 ADR/变更）。

### 4.12 API 契约

所有响应遵循规则 2：服务层返回 `{"status":"ok"|"error","code":...,"message":...,...}`；路由层翻译 HTTP；`except HTTPException: raise`。

#### 4.12.1 USL 发布与审核

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/semantic-admin/usl/domains/{domain_id}/versions` | `semantic.read` | 版本列表（不含完整快照） |
| GET | `/api/semantic-admin/usl/domains/{domain_id}/versions/{version_id}` | `semantic.read` | 版本详情；`?include=snapshot,diff` |
| POST | `/api/semantic-admin/usl/domains/{domain_id}/rollback` | `semantic.draft.write` | 以目标版本建回滚变更集 |
| POST | `/api/semantic-admin/usl/change-requests/{id}/publish` | `semantic.publish` | 发布 `approved` 变更集并生成新版本 |
| POST | `/api/semantic-admin/usl/domains/{domain_id}/versions/{version_id}/deprecate` | `semantic.publish` | 废弃当前发布版本 |
| POST | `/api/semantic-admin/usl/domains/{domain_id}/change-requests` | `semantic.draft.write` | 创建变更集（可带 items） |
| GET | `/api/semantic-admin/usl/change-requests` | `semantic.draft.read` / `semantic.review` | 队列；按 status/domain 过滤 |
| GET | `/api/semantic-admin/usl/change-requests/{id}` | 同上 | diff + AI 预审 + 能力 |
| POST | `/api/semantic-admin/usl/change-requests/{id}/items` | `semantic.draft.write` | 追加变更项（原子校验） |
| POST | `/api/semantic-admin/usl/change-requests/{id}/items/{item_id}/undo` | `semantic.draft.write` | 按 `inverse_json` 逆操作撤销单个未提交项（revision 校验） |
| POST | `/api/semantic-admin/usl/change-requests/{id}/submit` | `semantic.draft.write` | 提交审核 |
| POST | `/api/semantic-admin/usl/change-requests/{id}/approve` | `semantic.review` | 批准（四眼） |
| POST | `/api/semantic-admin/usl/change-requests/{id}/reject` | `semantic.review` | 驳回 + 理由 |
| POST | `/api/semantic-admin/usl/change-requests/{id}/request-changes` | `semantic.review` | 退回 draft |
| POST | `/api/semantic-admin/usl/change-requests/{id}/ai-review` | `semantic.review` | 重跑预审 |
| POST | `/api/semantic-admin/usl/domains/{domain_id}/ai-draft` | `semantic.draft.write` | 生成 AI 草案 items 并写入草案（`origin=ai`），返回逐条 diff 供接受/丢弃 |
| POST | `/api/semantic-admin/usl/change-requests/{id}/abandon` | 创建者/`semantic.admin` | 放弃 |

#### 4.12.2 已发布视图与导出

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/semantic-admin/usl/published/{domain_code}` | `semantic.read` | 发布包元数据（版本/hash/时间） |
| GET | `/api/semantic-admin/usl/published/{domain_code}/terms` | `semantic.read` | 术语列表（分页/过滤） |
| GET | `/api/semantic-admin/usl/published/{domain_code}/graph` | `semantic.read` | USL 图数据（分页/过滤/截断标记） |
| GET | `/api/semantic-admin/usl/published/{domain_code}/standards` | `semantic.read` | 数据标准包 |
| GET | `/api/semantic-admin/usl/published/{domain_code}/export` | `semantic.read` | `format=json|yaml|turtle|rdfxml` |
| POST | `/api/semantic-admin/usl/published/{domain_code}/validate` | `semantic.read` | 批量校验（抽取门控/外部系统） |
| POST | `/api/semantic-admin/usl/import` | `semantic.draft.write` | 导入为 draft 变更集 |

#### 4.12.3 工作台聚合

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/semantic-admin/workbench/overview` | `semantic.read` | 域/版本/待审/缺口/权限摘要 |
| GET | `/api/semantic-admin/workbench/capabilities` | 已认证 | 当前用户在当前域的 `can_*` 与服务端原因 |
| GET | `/api/semantic-admin/workbench/graph` | `semantic.read` | `scope=usl|ontology|instance`、`domain_code`、`ontology_id`、`version_id`、`filters`、`cursor`、`limit` |
| GET | `/api/semantic-admin/workbench/cards` | `semantic.read` | 卡片墙分页数据 |
| GET | `/api/semantic-admin/workbench/detail/{kind}/{id}` | `semantic.read` | 统一详情 DTO |
| GET | `/api/semantic-admin/workbench/neighbors` | `semantic.read` | 图扩展（按 node + depth + edge types） |
| GET | `/api/semantic-admin/workbench/search` | `semantic.read` | 跨 USL/本体/实例搜索 |
| GET | `/api/semantic-admin/workbench/history` | `semantic.draft.read` | 操作历史（撤销栈服务端依据） |

`graph` 响应：

```json
{
  "status": "ok",
  "scope": "usl",
  "version_id": "…",
  "content_hash": "sha256:…",
  "nodes": [{"id": "term:…", "kind": "term", "label": "订单", "semantic_type": "对象类型", "status": "published", "badges": ["hot"], "metrics": {"heat": 12, "properties": 6}}],
  "edges": [{"id": "hier:…", "source": "term:…", "target": "term:…", "kind": "IS_A", "label": "IS_A"}],
  "truncated": false,
  "next_cursor": null,
  "meta": {"node_limit": 2000, "filters_applied": {}}
}
```

#### 4.12.4 本体提案与投影

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | `/api/ontologies/{ontology_id}/proposals` | `ontology.propose` | 创建提案（AI/抽取/感知/人工批量） |
| GET | `/api/ontologies/{ontology_id}/proposals` | `ontology.read` | 提案列表 |
| GET | `/api/ontologies/{ontology_id}/proposals/{proposal_id}` | `ontology.read` | 提案详情 + diff + 证据 |
| POST | `/api/ontologies/{ontology_id}/proposals/{proposal_id}/apply` | `ontology.draft.write` | 网关应用（幂等） |
| POST | `/api/ontologies/{ontology_id}/proposals/{proposal_id}/reject` | `ontology.draft.write` | 拒绝 + 理由 |
| POST | `/api/ontologies/{ontology_id}/usl-projections` | `ontology.draft.write` | 预览/应用已发布 USL 投影 |
| GET | `/api/ontologies/{ontology_id}/usl-drift` | `ontology.read` | 上游新版本/内容漂移 |

#### 4.12.5 错误码

| 错误码 | HTTP | 触发 |
|--------|------|------|
| `USL_DOMAIN_NOT_FOUND_404` | 404 | 域不存在 |
| `USL_VERSION_NOT_FOUND_404` | 404 | 版本不存在 |
| `USL_NOT_PUBLISHED_409` | 409 | 消费方要求发布版但域未发布 |
| `USL_NO_CHANGES_409` | 409 | 发布内容与当前发布版一致 |
| `USL_REVISION_CONFLICT_409` | 409 | 草案行 revision 不匹配 |
| `USL_REVIEW_BASE_MISMATCH_409` | 409 | 审核期间草案变化，需 rebase |
| `USL_CHANGE_SET_STATE_409` | 409 | 变更集状态不允许该动作 |
| `USL_FIELD_INVALID_422` | 422 | L1 单行校验失败（字段定位） |
| `USL_AI_DRAFT_EMPTY_422` | 422 | AI 草案无有效候选 |
| `USL_AI_DRAFT_FAILED_502` | 502 | LLM 调用失败或无结构化输出 |
| `USL_SELF_APPROVAL_FORBIDDEN_403` | 403 | 创建者自批 |
| `USL_PERMISSION_DENIED_403` | 403 | 缺角色/工作空间权限 |
| `ONTOLOGY_PROPOSAL_REQUIRED_409` | 409 | 非网关来源尝试直写 |
| `ONTOLOGY_REVISION_CONFLICT_409` | 409 | 本体/类型 revision 不匹配 |
| `ONTOLOGY_WRITE_FORBIDDEN_403` | 403 | 缺 `ontology.draft.write` |
| `EXTRACTION_GATE_BLOCKED_422` | 422 | 抽取结果违反发布包 |
| `RDF_PARSE_ERROR_422` | 422 | RDF/JSON/YAML 解析失败 |
| `RDF_VERSION_IMMUTABLE_409` | 409 | 尝试改已发布版本 |

### 4.13 审计与可观测

- **审计事件**：`usl.change_request.created/submitted/approved/rejected/published/deprecated/rollback_requested`、`usl.version.published`、`usl.draft.updated`、`ontology.proposal.created/applied/rejected`、`ontology.write`（含 `origin`）、`ontology.version.committed`、`extraction.gate.blocked/warned`。
- **日志**：所有发布/审核/网关应用 INFO；权限拒绝 WARNING；发布失败 ERROR 并带 `domain_id/version_id/change_request_id`。
- **指标**：`usl_publish_total{domain,status}`、`usl_change_request_age_seconds{status}`、`usl_revision_conflict_total`、`usl_ai_review_doubtful_ratio`、`ontology_write_total{origin,status}`、`ontology_legacy_write_total{caller}`、`extraction_gate_violation_total{rule}`。
- **追踪**：`trace_id` 从请求头注入，贯穿变更集/发布/网关应用；审计记录可反查。
- **健康**：`/health` 暴露 `usl_consumption_mode`、`usl_unpublished_domains`（计数）、`ontology_legacy_write_total`（迁移进度）。

---

## 5. 测试策略

### 5.1 分层

| 层 | 内容 | 工具/约束 |
|----|------|----------|
| 单元 | 版本号/hash、快照序列化、状态机、四眼、revision、逆操作、AI 预审解析、错误码映射 | pytest；纯函数优先 |
| 存储 | `tmp_path` 真实 SQLite；建表/迁移幂等；并发 revision；部分唯一索引；事务回滚 | 禁止 MagicMock 模拟 DB |
| 服务 | 返回 `{"status","code","message"}`；不抛 HTTPException；发布失败不改指针；变更集原子 | 真实服务体，禁止 patch 掉待测函数 |
| 路由 | 200/201/400/403/404/409/422；`except HTTPException: raise`；权限依赖 override | FastAPI TestClient |
| 契约 | 已发布视图只读；消费方固定版本；导出只含发布版；导入不发布 | 集成测试 |
| 架构 | `lint-imports` C1–C5；外部模块不直写 `OntologyService`；`public.py` 写入口只有网关 | `lint-imports` + AST/grimp 测试 |
| 前端 | 工作台 store、能力门、图谱/卡片选中同步、URL 深链、自动保存防抖、409 提示、i18n | Vitest + Testing Library |
| E2E | 建域 → 加术语 → 提交 → AI 预审 → 批准 → 发布 → 消费读到；发布后改草案 → 消费仍读旧版；AI 提案 → 人工应用 → 审计 | pytest e2e / Playwright（如可用） |

### 5.2 关键用例

1. 发布事务中途失败（版本插入成功、指针更新失败）→ 回滚，指针不变。
2. 发布内容与当前发布版一致 → `USL_NO_CHANGES_409`，不产生空版本。
3. 审核期间草案被改 → 批准返回 `USL_REVIEW_BASE_MISMATCH_409`，变更集回 draft 可 rebase。
4. 创建者自批 → 403。
5. 同一域两个 `pending_review` → 第二个提交 409。
6. 撤销复合变更集 → 全部 items 逆序回滚，任一 revision 冲突则整体不落。
7. 发布后撤销 → 生成回滚变更集，不移动指针。
8. 未发布域被 QA/抽取/SHACL 消费 → 显式 `USL_NOT_PUBLISHED_409` 或 `usl_status=unpublished` 元数据；不读草案。
9. AI 工具调用 `propose_ontology_change` → 生成提案；不存在直写工具；尝试直写被 C5/网关拒绝。
10. USL 写回缺 source/target → 显式错误，不降级 ObjectType。
11. 感知无 `ontology_id` → 提案 + `status=proposed`，不写 OMS。
12. HE 导入部分失败 → 返回逐项错误，不返回整体成功。
13. RDF 导入 → 只产生 draft 变更集；导入已发布版本 ID 不被接受。
14. 工作台无 `semantic.draft.write` 进入 edit → 服务端 403，前端显示原因。
15. 图超过 2000 节点 → `truncated=true`；前端提示筛选。
16. 卡片墙与图谱选中同步；URL 深链恢复选中。
17. 迁移脚本 dry-run/apply 幂等；重复执行不产生重复版本。
18. 同一行同一字段 5 分钟内连续编辑 3 次 → 只保留 1 条 item，`before_json` 为首次值、`after_json` 为末次值、`edit_count=3`；跨窗口或跨字段产生新 item。
19. L1 自动保存非法值（空 canonical、非法枚举、超长）→ 422 + 字段定位，草案行保持原值；跨行约束在 L1 允许多行暂不满足，但在提交审核与发布时被拦截。

### 5.3 回归基线

- 后端单测必须离线跑；离线全量有 ~206 个环境依赖型失败基线，新增失败必须与 stashed-HEAD 基线逐 node ID 对比。
- `lint-imports` 从 `apps/api` 执行，期望 `5 kept, 0 broken`（新增 C5 后）。
- 前端 `npx vitest run`；`tsc -b --noEmit` 有 ~159–161 个存量错误，不新增。
- 既有 gap/candidate/ontology CRUD 测试零回归。

---

## 6. 文档同步清单

| 文档 | 变更 |
|------|------|
| `docs/02-architecture/ARCHITECTURE_FOUR_STEPS.md` | §1.1/§3 改「编辑态/探查态分离」为「读写通道分离 + 模式/权限门」；工作台归入见本体/建本体 |
| `specs/003-ontology-redesign/spec.md` | US5/FR-035 注明「即时保存=写草案」；Assumptions 单用户改为乐观锁；G6 改为 Sigma.js |
| `specs/007-semantic-admin-suite/spec.md` | FR-059/FR-060 标注实现状态与本次边界（FR-060 分阶段） |
| `docs/03-modules/README.md` | 新增 `semantic_admin/usl_publish` 后端模块、`semantic-workbench` 前端模块 |
| `docs/03-modules/semantic_admin/DESIGN.md` | 生命周期、新表、端点、权限、发布事务、迁移 |
| `docs/03-modules/ontology/DESIGN.md` | `OntologyWriteGateway`、提案模型、五路径迁移、C5 |
| `docs/03-modules/web_frontend/DESIGN.md` / `docs/04-ui/*` | 工作台 IA、四工作区、三视图、能力门、深链 |
| `docs/07-adr/README.md` | ADR-091 索引行 + 时间线 |
| `agents.md` | API 路径表、`USL_CONSUMPTION_MODE` 环境变量、规则/陷阱补充（如适用） |
| `docs/09-checklists/DOC_SYNC_CHECKLIST.md` | 增加 USL 发布/网关/权限同步项 |
| 菜单 seed | `seed_four_steps.py` 新增工作台菜单 + 既有 DB 迁移脚本 |
| 死链检查 | 本设计不删除文档；若后续归档旧页，执行 `python scripts/check_dangling_doc_links.py` |

---

## 7. 风险与回滚

| 风险 | 影响 | 缓解 |
|------|------|------|
| 草案不再对消费方可见 | 现有 QA/抽取行为变化 | 迁移脚本先发布 `v1`；`USL_CONSUMPTION_MODE=draft` 可回退；工作台显式「未发布」提示 |
| 发布快照过大 | SQLite 读放大/内存 | 单域规模上限（NFR-008 10 万术语）；v1 存 JSON，监控体积，后续压缩；`PublishedUslView` 只缓存当前版本 |
| 图数据过大 | 浏览器卡顿 | 服务端 2000 节点上限 + `truncated` + 过滤/邻居扩展；前端虚拟化卡片 |
| 权限收紧打断现有客户端 | 403 增多 | 迁移期能力端点 + 明确错误；测试 fixture override；发布说明 |
| 网关改造面大 | 回归风险 | 分阶段：先加提案/审计，再切来源，最后 C5 强制；C5 债账棘轮 |
| AI 提案质量不稳 | 人工负担 | 确定性检查 + 存疑标注 + 证据；AI 不自动通过 |
| 版本固定导致语义滞后 | 上游更新不生效 | 漂移面板 + 显式升级提案；不自动改已发布本体 |
| RDF 映射不完整 | 外部系统误解 | 明确只映射 USL 治理对象；`unsupported[]` 报告；不承诺内部 ID 往返 |
| 迁移脚本误发布 | 错误内容成为 v1 | dry-run + 校验 + 备份；失败非 0 退出；不自动执行 |

回滚：
- 新增表/列是加法；旧代码路径不受影响。
- `USL_CONSUMPTION_MODE=draft` 立即恢复旧读取行为（显式告警）。
- 网关按来源分阶段切换，可单独回退某来源。
- 发布版本不可删；错误发布用新版本修正，不物理回滚。

---

## 8. 实施分期

> 详细任务由 `superpowers:writing-plans` 拆分；本节只定阶段与退出标准。

| 阶段 | 内容 | 退出标准 |
|------|------|---------|
| **P0 契约与存储** | ADR-091；新表/列；迁移脚本；`PublishedUslView`；快照/hash；单测 | 迁移 dry-run/apply 幂等；发布事务测试通过；旧路径零回归 |
| **P1 生命周期 API** | 变更集/items/状态机；审核/发布/废弃/回滚；AI 预审与 AI 草案生成；items 合并；L1 单行校验；权限依赖；错误码 | 状态机全路径测试；四眼/409/rebase 测试；合并与单行校验测试；路由契约测试 |
| **P2 工作台** | 路由/菜单；四工作区；图谱/卡片/表格；能力端点；共享选中；URL 深链；自动保存/撤销；`embed=1` 布局 | 前端 Vitest 全绿；无权限 403 路径；图截断/空态/错误态；嵌入只读且无越权 |
| **P3 消费切换** | QA/SHACL/语义检索/抽取门控读发布版；版本固定；`USL_CONSUMPTION_MODE` 默认 published | 未发布显式错误；固定版本集成测试；迁移部署演练 |
| **P4 单一写入通道** | `OntologyWriteGateway`；提案模型；W1–W5 迁移；C5 契约；legacy 告警 | 五路径全部走网关；C5 5 kept/0 broken；AI 直写工具删除；HE/感知失败显式 |
| **P5 投影与 RDF** | USL→本体投影/漂移；RDF 导入导出；数据标准导出 | 投影只写草案；RDF 只导出发布版；导入不发布；往返测试 |

依赖：P1 依赖 P0；P2 依赖 P1（能力/版本 API）；P3 依赖 P1；P4 可与 P3 并行但 C5 收口在 P4 末；P5 依赖 P3/P4。

---

## 9. 明确不做

1. 不做 AI 自动批准/自动发布/自动合并；`ai_review_json` 只作证据。
2. 不做实时协同编辑/CRDT；并发用乐观锁 + 409。
3. 不把 Action/Process/Rule/Function/Indicator 纳入 USL。
4. 不做 RDF 对本体特有构造、内部 ID、审批状态的往返保真。
5. 不做跨租户物理隔离；沿用现有 workspace 隔离。
6. 本期不删除现有语义管理页；工作台是主入口，旧页保留为高级工具。
7. 不做 USL → 已发布本体的自动实时同步；升级是显式提案。
8. 不做发布版本的物理删除/时间倒流；回滚=新版本。
9. 不做第二套「嵌入版工作台」：`embed=1` 只是同一工作台的布局开关，不新建页面、不新建 API。
10. 不做拖拽即改模型与画布布局持久化（拖拽在本期只用于视图内重排/分组，不产生语义变更；节点坐标不入库）。
11. 不做独立的 NL2Ontology 向导：自然语言入口只作为 Define 区「AI 生成草案」的一种输入（§4.7.2），不另开流程。
12. 不做课程/教学内容。
13. 不做 USL 草案的实时多人协同光标/在线状态。

---

## 10. 设计自审记录

- **占位符**：无 TBD/TODO；所有未实现项均给出阶段与退出标准。
- **内部一致性**：D1–D17 与 §4 各节一一对应；C1–C5 均有结论与落地章节；版本只在发布时创建（无 DRAFT 版本）与 §4.2.1/§4.2.2/§4.11.2 一致；发布接口统一为 `change-requests/{id}/publish`。
- **范围**：单一实施计划可覆盖 P0–P2；P3–P5 作为后续切片，依赖关系明确。
- **歧义**：明确「草案=工作表」「发布=快照」「即时保存=写草案」「撤销≠回滚发布版」「AI 只提案」；L1 只做单行校验，跨行约束在提交/发布/手动校验三时点执行；同字段窗口内合并变更项，跨窗口/跨字段不合并。
- **本轮补充**：`embed=1` 明确为同一工作台的布局开关（不授权、不新建页面/API）；Define 区 AI 生成草案有独立端点与失败码，不写空变更集；域删除保留已发布快照与发布事件；C5 契约给出精确的 `source/forbidden/allow_indirect_imports` 语义与 `public.py` 导出边界；§9 明确排除拖拽改模型/坐标持久化、独立 NL2Ontology 向导、课程与第二套嵌入页面。
- **规则核对**：路由注册（规则 1）、服务层 dict（规则 2）、HTTPException 透传（规则 3）、调用链（规则 6）、测试（规则 9）、ADR+文档同步（规则 12）、临时文件（规则 13）、失败显式（规则 14）均在对应章节落地。
