# 语义资产管理（Semantic Asset Management）设计方案

> 目标：梳理并统一当前「语义抽取 + 语义资产定义（含同义词）+ 角色化审核」的混乱现状，形成**一条清晰的端到端 Pipeline**，让用户用同一套心智模型完成**结构化**与**非结构化**两类语义定义：
> **初始化本体（可选） → 选/建模板 → 数据源引入/文档接入抽取 → 生成候选语义资产 → 指定业务角色审核 → 通过后写入 USL 规范库**。

---

## 0. 核心问题回答（模板 vs 本体，及两条接入链路）

### 0.1 模板是否依赖本体？

**不强制依赖**。模板分三种来源，只有"本体生成模板"依赖本体：

| 模板来源 | 是否需本体已初始化 | 实现 |
|---------|:---:|------|
| **预设模板**（preset，如 `chinese_ontology_graph.yaml`） | ❌ 不需要 | `TemplateEngine.list_presets()` 动态枚举 HE 内置模板，自带实体/关系类型白名单，可开箱即用 |
| **本体生成模板** | ✅ 需要 | `generate_from_ontology()` 读本体 `object_types/link_types/action_types` 生成字段 |
| **自定义模板** | 可选（仅作 LLM 提示上下文） | `generate_custom()`，`ontology_schema` 可为空 |

### 0.2 本体如何初始化定义？

已存在完整链路，无需新建：

- 后端：`OntologyService.create_ontology()` + `create_object_type()`（`odap/biz/core/ontology/ontology_api/services/ontology_service.py`）。
- 前端：`OntologyDesignerPage.tsx` / `BlueprintDesignerPage.tsx` / `UnifiedManagementPage.tsx`。
- 契约约束：`UnifiedIngestFacade._validate_ingest_contract()` 已要求「本体存在且有类型定义」，否则返回 `"本体 X 尚无类型定义，请先定义对象类型或使用 exploratory 模式"`。

**结论**：本方案把「初始化本体」作为 Pipeline 的可选前置步骤（Step 0）。若用户尚无本体，走 `exploratory` 模式或直接使用预设模板，不阻塞抽取。

### 0.3 两条接入链路（结构化 vs 非结构化）——已存在但割裂

代码走查确认，两条链路**都已实现**，但未串成一条用户可见 Pipeline：

**链路 A — 结构化数据引入**（`POST /api/ingest/unified` + `UnifiedIngestFacade`）
- 文档驱动源（`url/news/tavily/manual/json/natural_language/random_events/database/kb_upload/ontology_document`）→ `IngestService`
- 事件驱动源（`webhook/sensor/mcp/file/api`）→ `PerceptionHub`
- 已有 `constrained`/`exploratory` 抽取契约、冲突扫描/修复、审计。

**链路 B — 文档接入抽取（非结构化）**（`POST /api/he/extract` + `HEAdapter`）
- 模板化 HE 抽取 → 本体映射 → 双通道写入。

**割裂点**：`ingest` 的 `natural_language` 触发的是 `ol_pipeline`（规则抽取，L1~L6），而 `hyper_extract` 是另一套模板抽取；二者 + 语义管理台审核流，三者没有统一入口，用户无法理解"我该走哪条、结果去了哪"。

**本方案目标**：用一条 `SemanticAssetPipeline` 统一编排三类能力（结构化引入 / 非结构化抽取 / 候选审核），前端一个「语义资产」入口即可完成全部流程。

---

## 1. 现状问题诊断（为什么"乱"）

通过代码走查，当前存在 **4 类割裂**，是"混乱"的根源：

### 1.1 两套抽取体系并行且未贯通

| 体系 | 位置 | 能力 | 现状 |
|------|------|------|------|
| Hyper-Extract（模板化抽取） | `odap/biz/data/hyper_extract` | `list_presets`（预设模板）、`assess`（模板评分）、`generate_custom`（LLM 生成自定义模板）、`generate_from_ontology`（从本体生成模板）、`trial_extract` | 能力齐全，但 `api/routes.py` 只暴露了 `POST /extract`、`GET /templates/{ontology_id}`，**没有**「模板列表 / 自定义模板 / 按模板抽取」的对外接口 |
| OL Pipeline（规则抽取） | `odap/biz/semantic_admin/ol_pipeline` | L1 术语抽取 → L2 概念合并 → L3 分类 → L4 关系 → L5 模式归纳 → L6 公理 | 无模板概念，纯规则，与 HE 模板能力**完全割裂** |

**后果**：用户无法"选一个模板 → 抽取 → 拿到候选"，也无法把 HE 模板的产出纳入语义资产审核流。

### 1.2 三套审批状态机并存（最严重）

| 层 | 状态枚举 |
|----|----------|
| 前端 `ApprovalsPage` | `AUDITOR_PENDING` / `ADMIN_PENDING` / `AUDITOR_APPROVED` / `APPROVED` / `REJECTED` / `STOPLISTED`（硬编码 fetch + 离线 mock） |
| 前端 `CandidatesPage` + `pipelineApi.ts` | `new` / `gated` / `approved` / `rejected` / `written` / `auditor_approved` / `admin_pending` / `written_back` / `stoplisted`（小写旧枚举） |
| 后端 `ApprovalService` | `DRAFT` / `PENDING_REVIEW` / `AUDITOR_APPROVED` / `ADMIN_PENDING` / `APPROVED` / `REVIEWER_REJECTED` / `ADMIN_REJECTED` / `WRITTEN_BACK` / `STOPLISTED`（大写新枚举） |
| 后端 `ol_pipeline`（quality gate） | `approved` / `gated` / `rejected`（A/B/C/D 档映射） |

**后果**：同一候选在不同页面显示不同状态名，前端无法可靠判断"谁该审、审什么、审完去哪"。

### 1.3 两个审批页面功能重叠

- `ApprovalsPage`：裸 `fetch` + `localStorage token`，有离线 mock，状态名与前文另一套不一致。
- `CandidatesPage`：走 `pipelineApi`，有质量雷达抽屉、批量操作。
- 两者**都**在语义管理台 Tab 栏中，功能大量重叠，用户无所适从。

### 1.4 同义词 / 定义入口分散

`canonical` / `synonyms` / `near_synonyms` / `aliases` / `definition` 字段在 **USL term 层、candidate 层、审核 patch 层** 三处都存在，前端没有一个统一的"语义资产（术语 + 同义词 + 定义）"视图，审核时"该改哪一层"不清晰。

---

## 2. 统一领域模型（Single Source of Truth）

提出一个**统一语义资产模型**，消除上述割裂。核心原则：**一条语义资产（术语）只有一个 canonical 名称，同义词/近义词/别名/定义是其属性；抽取只产生"候选"，审核通过才成为"正式资产"。**

### 2.1 核心实体

```
SemanticDomain（语义域）                — 资产的分组容器
└── SemanticTerm（语义资产/规范术语）    — 唯一 canonical 名称
    ├── synonyms[]       同义词（等价）
    ├── near_synonyms[]  近义词（近似）
    ├── aliases[]        别名
    ├── definition       定义
    ├── examples[]       示例
    ├── semantic_type    语义类型（对象/关系/属性/动作/过程/规则）
    └── stoplist_flag    停用词标记

ExtractionTemplate（抽取模板）          — 自动化抽取的"配方"
    ├── source: preset | custom | ontology
    ├── yaml / payload
    └── 关联 ontology_id

Candidate（候选资产）                   — 抽取的中间产物（未正式入库）
    ├── canonical + 同义词等字段（与 SemanticTerm 同构）
    ├── source_template_id             — 追溯：来自哪个模板
    ├── pipeline_run_id                — 追溯：来自哪次抽取
    ├── confidence / quality_report    — 质量评分
    └── status                         — 统一状态机（见 §3）

ApprovalTask（审核任务）               — 角色化审核的工作项
    ├── candidate_id
    ├── assigned_role                  — 业务角色（见 §5）
    └── status / level / deadline
```

### 2.2 关系

```
ExtractionTemplate ──抽取──▶ Candidate ──审核通过──▶ SemanticTerm
                                       └─驳回──▶ STOPLISTED（下次抽取自动跳过）
SemanticDomain ──包含──▶ SemanticTerm
```

---

## 2.5 统一 Pipeline（一条端到端链路）

把「结构化引入 + 非结构化抽取 + 候选审核」统一为**一条 `SemanticAssetPipeline`**，前端一个入口即可完成全部流程。核心编排器 `SemanticAssetPipeline` 仅做确定性路由（复用现有三个子系统），不引入 LLM 判断。

### 2.5.1 总流程

```
┌────────────────────────────────────────────────────────────────────┐
│ Step 0  初始化本体（可选）                                            │
│   已有本体 → 跳过；无本体 → 走 exploratory 模式 或 直接用预设模板      │
│   （前端引导跳转 OntologyDesignerPage / BlueprintDesignerPage）       │
├────────────────────────────────────────────────────────────────────┤
│ Step 1  选择数据源类型（二选一）                                      │
│   ① 结构化数据引入  ② 文档接入抽取（非结构化）                         │
├────────────────────────────────────────────────────────────────────┤
│ Step 2  选择/设计抽取模板                                             │
│   预设模板（list_presets） / 自定义模板（generate_custom）            │
│   / 本体生成模板（generate_from_ontology）                            │
├────────────────────────────────────────────────────────────────────┤
│ Step 3  执行抽取/引入（生成 Candidate，status=DRAFT）                 │
│   结构化 → UnifiedIngestFacade.ingest()                              │
│   非结构化 → HEAdapter.parse() / extract_and_write()                 │
├────────────────────────────────────────────────────────────────────┤
│ Step 4  提交审核（DRAFT → PENDING_REVIEW）                            │
│   生成 ApprovalTask，assigned_role 指向业务角色                       │
├────────────────────────────────────────────────────────────────────┤
│ Step 5  角色化审核（改同义词/定义 → 通过/驳回）                        │
├────────────────────────────────────────────────────────────────────┤
│ Step 6  通过 → 写入 USL 规范库（SemanticTerm）                       │
└────────────────────────────────────────────────────────────────────┘
```

### 2.5.2 链路 A：结构化数据引入处理链路

```
数据源（DB 表 / JSON / URL / 事件流 …）
   │  用户在前端选择 source_type（数据库/JSON/URL/webhook/file/api …）
   ▼
POST /api/ingest/unified
   │  UnifiedIngestFacade.ingest(source_type, ontology_id, extraction_mode, …)
   ▼
路由：
   ├─ constrained（约束性）  ── 校验契约：本体已初始化且有类型定义
   │                             entity_type 必须已在本体中定义
   │                             （UnifiedIngestFacade._validate_ingest_contract / validate_entity_type）
   ├─ exploratory（探索性）  ── 允许推断新类型结构，生成 draft 候选
   ▼
分支：
   ├─ 文档驱动源  → IngestService（ingest_from_database/json/manual/url/news/tavily …）
   └─ 事件驱动源  → PerceptionHub（ingest_webhook/sensor/… → process_event）
   ▼
产出：实体/关系记录 → 归集为 Candidate（DRAFT）→ 进入 Step 4 审核流
   （并支持 conflict scan/repair：scan_data_conflicts / repair_data_conflicts）
```

### 2.5.3 链路 B：文档接入抽取（非结构化）处理链路

```
文档 / 文本（PDF/Word/纯文本/网页 …）
   │  用户粘贴文本 或 上传文档（前端解析为 text）
   ▼
POST /api/he/extract（指定 template_path 或 template_override）
   │  ExtractService.extract_and_write(text, ontology_id, template_override, …)
   ▼
HEAdapter.parse(text, template)：
   ├─ 有 template_path → Template.create() 加载 YAML 模板
   ├─ 无 → 默认 chinese_ontology_graph.yaml
   └─ 兜底 → 硬编码 AutoGraph（chunk_size=4096，one_stage）
   ▼
LLM 抽取 → normalize → 后校验（实体短于 2 字过滤 / 未命中原文打 possible_hallucination / 关系端点校验）
   ▼
本体映射（entity_type 对齐本体 object_types）
   ▼
双通道写入 → 归集为 Candidate（DRAFT）→ 进入 Step 4 审核流
   （批量场景：POST /api/he/extract/batch；进度：SSE /api/he/progress/{session_id}）
```

### 2.5.4 Pipeline 编排接口（待新增）

| 接口 | 说明 |
|------|------|
| `GET /api/semantic-assets/pipeline/options` | 返回可选：数据源类型、模板列表（preset）、本体列表（供 Step 1/2 下拉） |
| `POST /api/semantic-assets/pipeline/run` | 统一编排入口：`{source_type, template_ref, ontology_id, extraction_mode, payload}`，内部路由到 A/B 链路，产出 `pipeline_run_id` |
| `GET /api/semantic-assets/pipeline/{run_id}` | 查询一次 pipeline 的产出 Candidate 列表与进度 |
| `POST /api/semantic-assets/pipeline/{run_id}/submit` | 将 DRAFT 候选提交审核（→ PENDING_REVIEW） |

> 实现要点：`run` 内部**复用** `UnifiedIngestFacade` 与 `ExtractService`，不重写抽取逻辑，只做统一编排与候选归集（把两条链路的产出统一 `status=DRAFT` 写入 Candidate Store，并打上 `source_template_id` / `pipeline_run_id` 追溯标记）。

---

## 3. 统一状态机（消除三套枚举）

**唯一权威状态机**（后端大写枚举为准，前端唯一映射一份）：

```
                     ┌──────────────────────────────────────────┐
 抽取完成 ─────────▶ │  DRAFT（草稿候选）                          │
                     └────────────────┬─────────────────────────┘
                                      │ 提交审核
                                      ▼
                     ┌──────────────────────────────────────────┐
                     │  PENDING_REVIEW（待业务角色 L1 审核）        │
                     └──────────┬──────────────┬────────────────┘
                                │ 通过          │ 驳回
                                ▼              ▼
                     ┌────────────────┐  REVIEWER_REJECTED ──▶ STOPLISTED
                     │ AUDITOR_APPROVED│
                     │ 或 ADMIN_PENDING │   ←（高价值/冲突项升级到管理员）
                     └───────┬────────┘
                             │ 终审通过
                             ▼
                     ┌────────────────┐
                     │   APPROVED      │ ──▶ 写入 USL（WRITTEN_BACK）
                     └────────────────┘
```

**统一后的状态全集**（唯一枚举，前后端共用）：

| 状态 | 含义 | 归属 |
|------|------|------|
| `DRAFT` | 抽取完成，尚未提交审核 | 候选 |
| `PENDING_REVIEW` | 待业务角色审核 | 候选 |
| `AUDITOR_APPROVED` | 业务角色 L1 已通过（低风险单级即可） | 候选 |
| `ADMIN_PENDING` | 升级待管理员终审（高风险/冲突） | 候选 |
| `APPROVED` | 终审通过 | 候选 |
| `WRITTEN_BACK` | 已写入 USL 正式库 | 候选（终态） |
| `REVIEWER_REJECTED` | 业务角色驳回 | 候选（终态） |
| `ADMIN_REJECTED` | 管理员驳回 | 候选（终态） |
| `STOPLISTED` | 停用词（驳回后再次命中自动跳过） | 候选（终态） |

> **迁移规则**：废弃 `new/gated/approved(rejected/written)/auditor_pending/admin_pending` 等旧小写枚举，以及 `AUDITOR_PENDING` 等前端自造枚举。后端 `_norm_status()` 已具备兼容映射，前端需在 `pipelineApi.ts` 的 `CandidateStatus` 类型和 `STATUS_COLOR` 常量上做一次收敛。

---

## 4. 模板化抽取（自动化抽取的"配方"）

复用现有 `TemplateEngine` 能力，补齐对外接口，形成「选模板/自建模板 → 抽取」闭环。

### 4.1 模板来源

1. **预设模板（preset）**：`TemplateEngine.list_presets()` 动态枚举 HE 内置模板（`general/graph` 等）。
2. **自定义模板（custom）**：`TemplateEngine.generate_custom()` 用 LLM 按本体 + 缺口生成 YAML。
3. **本体生成模板（ontology）**：`TemplateEngine.generate_from_ontology()` 从本体 object/link/action types 生成。

### 4.2 端到端抽取流程

```
用户操作                         后端
─────────                        ─────
1. 选择模板（预设/自定义/本体生成）
   GET /he/templates            → list_presets() / generate_from_ontology()
2. （可选）自定义模板
   POST /he/templates/custom    → generate_custom()，返回 yaml + score
3. 按模板抽取
   POST /he/extract             → 指定 template_override，extract_and_write()
4. 产出候选
                                 → 候选进入 Candidate Store（status=DRAFT）
5. 提交审核
                                 → status=PENDING_REVIEW，生成 ApprovalTask
```

### 4.3 待补齐的接口

| 接口 | 说明 |
|------|------|
| `GET /api/he/templates` | 列出预设模板（现在只有 `/templates/{ontology_id}`） |
| `POST /api/he/templates/custom` | 提交文本 + 本体 schema + 缺口 → 返回 LLM 生成的 YAML 模板 |
| `POST /api/he/templates/assess` | 对给定文本评估各模板适配度（复用 `assess`） |
| `POST /api/he/extract` 扩展 | 支持 `template_path`（预设/自定义）而非仅 `template_override` |

---

## 5. 角色化审核（指定业务角色）

复用平台已有的 **Roles 模块**（`odap/biz/platform/roles`），把"审核"绑定到**业务角色**而非写死的 `schema_auditor` / `final_approver` 字符串。

### 5.1 角色映射

| 现有硬编码角色 | 语义 | 统一为业务角色 |
|----------------|------|----------------|
| `schema_auditor` | L1 审核员 | 可配置的「语义审核员」业务角色 |
| `final_approver` / `admin` | L2 管理员 | 可配置的「语义管理员」业务角色 |

**实现**：在语义管理配置（`sa_config`）中新增角色映射配置，把 `assigned_role` 与实际 `platform/roles` 中的角色 ID 关联；`ApprovalService.list_tasks(assigned_role=...)` 按业务角色过滤。

### 5.2 审核任务分配

- 抽取完成后，`candidate` 进入 `PENDING_REVIEW`，同时生成 `ApprovalTask`，其 `assigned_role` 指向配置的「语义审核员」角色。
- 前端审核台按当前登录用户的业务角色拉取"我的待审"。
- 审核动作：`通过`（→ AUDITOR_APPROVED 或 ADMIN_PENDING）、`修改`（改同义词/定义后重审）、`驳回`（→ REJECTED → STOPLISTED）。

---

## 6. 前端「语义资产管理」统一视图

### 6.1 信息架构（收敛 Tab）

将现有 6 个重叠 Tab 收敛为 **4 个清晰区块**：

| 区块 | 职责 | 合并自 |
|------|------|--------|
| **语义资产**（术语 + 同义词 + 定义 + 层级/属性/约束） | 查看/维护正式 USL 资产 | 原 `usl`（5 子 Tab 保留）+ 统一术语/同义词入口 |
| **抽取任务** | 选模板 → 跑抽取 → 看进度/产出候选 | 原 `pipeline` + 新的模板选择 UI |
| **候选审核** | 按业务角色审核候选（改同义词/定义、通过/驳回） | 合并原 `candidates` + `approvals` |
| **质量与治理** | 质量雷达 + 仪表盘 | 原 `quality` + `dashboard` |

### 6.2 状态枚举前端唯一收敛

在 `pipelineApi.ts` 或 `types` 中定义**唯一** `CandidateStatus`（对齐 §3 大写枚举），删除 `ApprovalsPage` 内联的 `STATUS_COLOR` 与 mock 状态名，两页统一引用。

---

## 7. 落地改动清单（按实施顺序）

### 阶段 0：统一状态机（低风险、收益最大）
1. 后端：确认 `ApprovalService._norm_status` 覆盖所有旧值（已基本覆盖）。
2. 前端：`pipelineApi.ts` 的 `CandidateStatus` 改为大写枚举；`constants.tsx` / `types.ts` 收敛 `STATUS_COLOR`。
3. 删除 `ApprovalsPage` 内联 mock 状态与裸 fetch，改走 `approvalApi`。

### 阶段 1：打通模板抽取闭环
4. 后端 `hyper_extract/api/routes.py` 新增 `GET /templates`、`POST /templates/custom`、`POST /templates/assess`。
5. 前端新增「抽取任务」页：模板选择（预设下拉 + 自定义 YAML 编辑器 + 本体生成）→ 触发抽取 → SSE 进度。

### 阶段 2：角色化审核
6. `sa_config` 新增「审核角色映射」配置（semantic_auditor_role_id / semantic_admin_role_id）。
7. `ApprovalService` 的 `assigned_role` 改由配置注入业务角色，而非硬编码。
8. 前端审核台按当前用户业务角色过滤"我的待审"，审核操作内嵌同义词/定义编辑。

### 阶段 3：统一视图收敛
9. 合并 `CandidatesPage` + `ApprovalsPage` 为一个「候选审核」页。
10. 在「语义资产」区提供术语 + 同义词 + 定义的一体化编辑入口。

---

## 8. 关键原则（与本体论改造一致）

- **LLM 只做"生成候选/生成模板"的辅助**，审核通过、写库、状态流转等**确定性**，不引入 LLM 判断。
- **同义词归一化走 USL 字典精确查表**（与 QA 侧 `UslTermResolver` 一致），禁止字符相似度/向量近似判重。
- **单一权威状态机**：前后端只用 §3 的一份枚举，杜绝三套并存。
