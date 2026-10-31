---
id: odap.l12.product-evaluation
status: authoritative
owner: pm
version: ''
layer: L12
concern: evaluation-product
lifecycle: frozen
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
governance_reason: 产品设计合理性评估唯一权威，问题编号（P0-x/P1-xx）的原始出处
governance_evidence: PRD-v2.md:15 引用其问题总表编号体系
---

# ODAP 产品设计合理性评估报告

> **文档编号**: EVAL-ODAP-001
> **版本**: 1.0.0
> **状态**: 正式
> **作者**: 产品经理 许清楚（MVP 开发专家团）
> **日期**: 2026-10-16
> **评估范围**: 前端 26 个模块 / docs 全量 259 篇 md / 后端 `apps/api/odap` 全量路由
> **方法论**: 全部结论基于对代码与文档的直接取证（文件路径 + 行号），不采信历史报告结论；无法在线复核的标注「未验证」。
> **关联交付**: `docs/00-requirements/PRD-v2.md`（本报告每条整改项在 PRD v2 中均有对应功能）

---

## 0. 一句话结论

ODAP 的**架构骨架（四步法 + 双时态 + USL）是成立的、甚至领先于国内多数同类平台**，但**产品层存在系统性失血**：入口碎片化、同名多份实现、文档无单一真相源、图谱渲染栈 7 套并存、以及历史「伪实现」残留的降级分支。这些问题共同导致「能用」但「不好用」，且随功能增长呈加速恶化。**核心矛盾不是缺功能，而是缺「收敛」**——收敛入口、收敛文档、收敛实现、收敛技术栈。

---

## 1. 评估方法与证据基线

| 取证手段 | 覆盖对象 | 说明 |
|---|---|---|
| 路由清单全量提取 | `apps/web/src/AppRoutes.tsx` | 共 67 条 `path=` 定义（含约 12 条 `Navigate` 重定向），26 个模块目录 |
| 前端 API 契约抽样 | `apps/web/src/modules/shared/services/api.ts`（2329 行） | 抽查工作空间 / 摄入 / 图谱 / 查询 / QA 五条链路 |
| 后端路由注册表 | `apps/api/odap/web/router_registry.py` | 全量业务路由的单一注册入口 |
| 依赖清单 | `apps/web/package.json` | 图谱/图表渲染栈清点 |
| 文档盘点 | `docs/**/*.md` | `find` 统计实际 259 篇（历史基线文档声称 ~130 篇） |

> 说明：任务书给定的文档总量为 271 篇，实测为 **259 篇**（`find docs -name "*.md" | wc -l`）。差异可能来自任务书下达后的增删或统计口径（是否含子模块）。以实测 259 为准。

---

## 2. 任务书 8 类问题的逐条实证复核

### 问题 1：架构文档冗余、无单一真相源 —— 【P1，属实】

**证据**
- `docs/02-architecture/` 实测含 10 篇 `ARCHITECTURE_*.md`：`ARCHITECTURE_ANALYSIS_REPORT.md`、`ARCHITECTURE_BIZ.md`、`ARCHITECTURE_EVOLVE.md`、`ARCHITECTURE_FOUR_STEPS.md`、`ARCHITECTURE_FULL_CHAIN.md`、`ARCHITECTURE_INFRA.md`、`ARCHITECTURE_OPS.md`、`ARCHITECTURE_TARGET_PLAN.md`、`ARCHITECTURE_TOOLS.md`、`ARCHITECTURE_WEB.md`。
- 同目录另有评审报告：`DEEP_REVIEW_REPORT_20260505.md`、`REVIEW_REPORT_20260505.md`、`SCALABLE_ARCHITECTURE_2026.md`、`SCALABLE_ARCHITECTURE_OVERVIEW.md`，以及 `reports/` 下 `AUDIT_REPORT.md`、`COMPLETENESS_REPORT.md`、`ANOMALY_REPORT.md`。
- 仅 `ARCHITECTURE_FULL_CHAIN.md` / `ARCHITECTURE_TARGET_PLAN.md` / `ARCHITECTURE_ANALYSIS_REPORT.md` 三份即存在「结论互相覆盖」的语义重叠；**无一携带 `superseded` / `deprecated` / `status` 标记**（Grep `superseded|deprecated` 在 `docs/02-architecture/*.md` 无命中）。
- **基线文档自身已过时**：`docs/DOCUMENT_BASELINE_v1.0.0.md:16` 声明「ADR 文档数 54（ADR-001 到 ADR-054）」，`同文件:54` 声明 `docs/07-adr/` 有 54 篇；实际 `docs/07-adr/` 已到 **ADR-090**（且缺 ADR-035、ADR-087）。基线文档版本号自称 1.1.0 但文件名仍是 v1.0.0，自称「正式」却与事实冲突。

**结论**：属实且严重。文档量是实际需求的 2 倍以上，读者无法判断哪份是当前有效版本，**新人 onboarding 成本极高**。

---

### 问题 2：文档编号体系冲突 —— 【P1，属实】

**证据**
- `docs/07-adr/ADR-061-semantic-admin-suite-architecture.md` 与 `docs/07-adr/ADR-061_skill_plugin_packaging.md` —— **同一编号 ADR-061 被两个不同主题占用**（连命名分隔符都不一致：`-` vs `_`）。
- `docs/02-architecture/reports/ADR-065_BULKHEAD_AUDIT.md` 与 `docs/07-adr/ADR-065_microservice_extraction_playbook.md` —— **编号 065 跨目录冲突**，且前者是「审计报告」却占用正式 ADR 编号。
- 命名风格混乱：`ADR-049_...`（下划线）与 `ADR-068-...`（连字符）与 `ADR-069_...` 混用；编号缺口 ADR-035、ADR-087。

**结论**：属实。ADR 本应是不可变决策记录，「同号多义」直接破坏其可引用性。

---

### 问题 3：需求文档不可追溯 —— 【P1，属实】

**证据**
- `docs/00-requirements/req-ok.md`（自称「唯一需求真相来源」，见 `DOCUMENT_BASELINE_v1.0.0.md:28`）
- `docs/00-requirements/archive/req-alpha.md`、`docs/00-requirements/archive/req-beta.md`
- 三份文档均**无语义命名、无状态标记、无 owner 字段、无版本号**（Grep `owner|status:|版本` 无命中于文件名/首行）。`req-ok.md` 同时被 `docs/00-requirements/documents/` 下的两份「前端功能实现对比报告」绕过。

**结论**：属实。需求侧没有一个可信的单一真相源。

---

### 问题 4：前端重复实现 —— 【P0，属实】

**证据（文件级实测，含字节数）**

| 概念 | 重复文件 | 大小 | 判定 |
|---|---|---|---|
| 审计时间线 | `audit/components/AuditTimeline.tsx` | 4,861 B | 组件版，疑似被裁剪 |
| 审计时间线 | `audit/pages/AuditTimeline.tsx` | 11,573 B | 页面版，功能更全 |
| 策略管理 | `config/pages/PolicyManagement.tsx` | 14,590 B | 功能最全 |
| 策略管理 | `config/pages/PolicyManager.tsx` | 11,557 B | 疑似旧版 |
| 策略管理 | `audit/pages/PolicyPage.tsx` | 11,610 B | 路由 `/policy-editor` 实际指向此文件 |
| 知识库 | `knowledge/pages/KnowledgeBase.tsx` | 43,694 B | 巨型页面（超大，需拆分） |
| 知识库 | `knowledge/pages/KnowledgePage.tsx` | 10,198 B | 路由 `/knowledge/navigation` 指向此文件 |

**关键结论**：Policy 存在**三份**同概念实现，且**实际被路由挂载的是 `audit/pages/PolicyPage.tsx`**（见问题 5），而 `config/pages/` 下两份**无任何路由引用**（Grep 全 `AppRoutes.tsx` 无 `PolicyManagement` / `PolicyManager` import）→ 它们是死代码。

---

### 问题 5：重复路由 / 入口碎片化 —— 【P0，属实】

**证据（`apps/web/src/AppRoutes.tsx` 逐行）**

| 行号 | 现象 | 判定 |
|---|---|---|
| `125-126` | `/semantic-admin/pipeline` 与 `/semantic-admin/pipeline-runs` **均指向 `PipelineRunsPage`** | 同组件双路由，冗余 |
| `111-112` | `/policy-editor` → `PolicyPage`；`/policies` → `Navigate` 到 `/policy-editor` | 保留其一即可 |
| `67,68,69,96,118` | Agent 入口 **5 个**：`/my-agents`、`/agent-chat/:agentId`、`/agent`、`/skills`、`/admin/agents` | 职责边界模糊，用户无法判断该进哪个 |
| `101-102` | `/knowledge` → `KnowledgeBase`；`/knowledge/navigation` → `KnowledgePage` | 同概念两个入口 |
| `77,91,92,93` | `/blueprint`、`/ontology/service-catalog`、`/ontology/semantic-map`、`/ontology/abution-graph` | 本体相关入口分散在两级路径下，无统一信息架构 |
| `74,75,107,110,130,141` | 6 条 `Navigate` 重定向 | 说明历史路径多次迁移，**契约不稳定** |

**结论**：属实。**67 条路由中约 1/3 属于重复或历史残留**。

---

### 问题 6：图谱/图表渲染栈 7 套并存 —— 【P0，属实】

**证据（`apps/web/package.json`）**

| 渲染栈 | 声明版本 | 前端实际引用文件数（Grep `apps/web/src`） |
|---|---|---|
| `cytoscape`（+ cose-bilkent/cxtmenu/dagre/navigator/panzoom/popper 共 6 插件） | ^3.34.0 | 2 |
| `@antv/g6` | ^5.1.0 | 1 |
| `sigma` + `@react-sigma/core` + `@react-sigma/minimap` | ^3.0.3 / ^5.0.6 | 3 |
| `@xyflow/react` | ^12.10.2 | 3 |
| `@ant-design/graphs` | ^2.1.1 | **0（死依赖）** |
| `graphology`（+ 8 个子包） | ^0.26.0 | 5 |
| `echarts` | ^6.0.0 | 10 |

**结论**：属实且严重。**7 套渲染栈、约 20 个图论/绘图依赖同时存在**，其中 `@ant-design/graphs` 零引用为纯死依赖；`cytoscape` 与 `@xyflow/react`、`@antv/g6` 三者功能高度重叠。这直接推高包体积（`pnpm-lock.yaml` 达 252,943 B）、构建时长与维护成本，并导致「不同页面图谱交互不一致」。

---

### 问题 7：P0 违规实锤（紫色 → 品红渐变）—— 【P0，属实】

**证据（`apps/web/src/modules/shared/styles/colorThemeUtils.ts`）**
- `:69` 定义 `violet` 调色板；
- `:73` `primary['600'] = '#7C3AED'`（紫）；
- `:78` `accent['500'] = '#D946EF'`（品红/粉）；
- `:143` `linear-gradient(135deg, ${p('600')} 0%, ${accent['500']} 100%)` → 展开即 **`linear-gradient(135deg, #7C3AED 0%, #D946EF 100%)`**，命中团队 P0-2 红线（禁止紫色 → 粉色/品红渐变）。

**结论**：属实。此外 `indigo` 调色板 `accent['600']` 亦为 `#7C3AED`（`:31`），虽未构成紫→品红渐变，但紫色系被广泛用于 AI 场景主视觉，与企业级平台定位不符（见 `references/industries/enterprise.md` 反模式警告）。

---

### 问题 8：历史「伪实现」风险复核 —— 【P0/P1 混合，部分已修复、部分残留】

对 `docs/00-requirements/documents/前端功能实现与设计对比报告.md`（2026-04-20）的四条待完善项逐条到代码复核：

| 历史问题 | 当前代码状态 | 复核结论 |
|---|---|---|
| 文件上传后端缺处理逻辑 | 后端已有 `POST /api/ingest/file`（`apps/api/odap/biz/integration/frontend_compat/api/simulation_routes.py:77`），仅接受 `.json/.csv/.txt`，调用 `process_file_upload_task.delay()`（`:94`），任务定义于 `apps/api/odap/tasks.py:135` | **已修复（代码层）**，仍依赖 Celery worker 实际运行 —— 运行时验证见「未验证清单」 |
| 图谱「异步任务」实为同步返回 task_id | `POST /api/graph/generate`（`frontend_compat/api/ontology_routes.py:148`）现调用 `generate_graph_task.delay()`（`:162`），进度查询用 `celery.result.AsyncResult`（`:209`） | **基本修复，但残留伪实现**：`get_graph_progress` 在 `ImportError` 分支（`:226-233`）直接返回 `status=completed, progress=100, entities_generated=0` —— **Celery 不可用时静默伪造「已完成」但零产出**，属典型伪实现兜底，必须移除 |
| 角色切换 UI 未落地 | `apps/web/src/modules/shared/stores/authStore.ts:156` 有 `setCurrentRole()`，写入 `localStorage['currentRoleId']`；但 Grep 全前端未发现独立的「角色切换」UI 组件（仅 store 层） | **部分落地**：能力在 store 层具备，UI 入口缺失，用户无法自助切换 |
| 查询结果可视化未落地 | `api.ts` 有 `queryEntities/queryRelations/complexQuery`（`:817-838`）；`echarts` 被 10 个文件引用，但**未见查询页将结果渲染为图表** | **未验证**（需人工进入 `/qa/query` 走查确认） |

---

## 3. 任务书之外的产品层深挖（补充问题）

### 3.1 功能设计错误：四步法语义与前端实现不匹配 —— 【P1】

**现象**：`CONTEXT.md` 定义严格四步法（建/见/演/用），但前端信息架构未按四步法组织：
- 「见本体」的探查页 `ontology/pages/OntologyGraphPage.tsx` 内 `editorVisible` 状态（`:63-69,369-375`）表明**编辑态与探查态混在同一页面**，与 `CONTEXT.md:14`「编辑态与探查态强制分离」的要求冲突。
- 「候选态」的语义（`CONTEXT.md:14`「候选态默认对业务人员不可见」）在前端**未发现基于角色的可见性开关**；候选数据由后端 `semantic_admin/candidate_store/api/routes.py:164-355` 管理，但前端消费端未见权限门。

**结论**：四步法在**后端服务层是清晰的**（`semantic_admin`、`ontology/design`、`simulation`、`semantic_retrieval` 各自独立），但**前端把四步法揉进了扁平路由列表**，用户认知与领域模型脱节。

### 3.2 功能冗余清单（页面级 + 组件级 + API 级）——【P0】

**页面级**（同问题 4/5，去重建议）：

| 概念 | 保留 | 下线/合并 | 理由 |
|---|---|---|---|
| 审计时间线 | `audit/pages/AuditTimeline.tsx` | `audit/components/AuditTimeline.tsx`（若无组件复用） | 页面版功能完整 |
| 策略 | `audit/pages/PolicyPage.tsx` | `config/pages/PolicyManagement.tsx`、`config/pages/PolicyManager.tsx` | 后两者无路由引用，为死代码 |
| 知识库 | `knowledge/pages/KnowledgeBase.tsx`（需拆分） | `knowledge/pages/KnowledgePage.tsx` | 双入口收敛为单入口 + 内嵌导航 |
| 语义流水线 | 合并 `/semantic-admin/pipeline` 与 `/pipeline-runs` 为单路由 | — | 同组件双路由 |

**API 级**（疑似重复契约）：
- `api.ts` 同时存在 `/api/ontology/ingest/*`（`:299-546`）与 `/api/ingest/*`（`:578-612`）两套摄入端点族 —— 前者为旧契约、后者为 `frontend_compat` 兼容层，**同业务双 API**，需合并为单一契约。

### 3.3 功能断链（路由存在但后端缺失 / 契约不一致）——【P0】

**实证**
- 前端路由 `AppRoutes.tsx` 定义了 67 条 path，其中多条对应页面的数据依赖需后端支撑。抽取五条关键链路核对后端注册表（`router_registry.py`）：
  - QA/语义检索：后端 `semantic_retrieval/api/routes.py` 提供 `/query /graph /nl /metric /chain /mdl /hybrid /semantics /stream`（`:86-363`）→ **契约存在**。
  - 决策：后端 `decision_record/api/routes.py`（ADR-076，7 端点）已注册 → **契约存在**。
  - 溯源：`router_registry.py` 注册 `provenance_router` → **契约存在**。
  - 候选态：`semantic_admin/candidate_store/api/routes.py` 提供 get/patch/delete/promote-to-usl → **契约存在**。
  - 图谱生成：`frontend_compat` 提供 `/graph/generate|progress|cancel|history|{id}` → **契约存在**。
- **但存在两类断链隐患（未逐页验证，标注为待验证）**：
  1. `/ontology/abution-graph`（`AppRoutes.tsx:93`）与 `/iframe-viewer`（`:119`）等边缘页面，其数据来源（`abution` 命名暗示外部图数据库）在 `router_registry.py` 中**未见对应后端服务**，疑似「前端先行、后端未接」。
  2. `api.ts` 中 `/api/ontology/ingest/*` 与 `/api/ingest/*` 双族并存，若其一已废弃，则存在**前端调用已下线后端契约**的风险。

> **建议**：由架构师产出「前端路由 ↔ 后端路由 ↔ API 契约」三方对账矩阵，作为 PRD v2 中「契约一致性校验」功能的输入。本报告已完成前端侧 67 路由与后端注册表的清点，全量对账列为未验证项。

### 3.4 功能冲突（同概念两套口径）——【P1】

- **策略口径**：`config/pages/PolicyManager.tsx`（疑似「策略编排」）与 `audit/pages/PolicyPage.tsx`（疑似「策略审计」）对「策略」的定义与操作不同 —— 若同一业务概念在 UI 上有两套互斥交互，将直接导致用户误操作。
- **知识库口径**：`KnowledgeBase.tsx`（43KB，疑似文档存储管理）与 `KnowledgePage.tsx`（10KB，疑似知识导航）对「知识」的边界定义不同，易造成用户语义混淆。

> 两者均需在 PRD v2 中定义**唯一概念模型**并给出「保留哪套口径」的决策。

### 3.5 LLM Wiki 模块：完全缺失 —— 【P0（新缺口）】

**证据**：用户需求第 3 条要求「首先建立 LLM Wiki 功能模块」。实测：
- `ls apps/web/src/modules/` 26 个模块目录中**无 `wiki` 相关模块**；
- Grep `wiki`（忽略大小写）于 `apps/web/src/modules/**/*.tsx` **零命中**；
- `find apps/api -iname "*wiki*"` **零命中**。

**结论**：LLM Wiki 为**绿地功能**，不存在任何现状实现。这是 PRD v2 的 P0 首批交付物。

### 3.6 文档治理与 LLM Wiki 的双向打通缺口 —— 【P1（新缺口）】

**证据**：`docs/` 259 篇 md 无统一元数据头（除 12 篇核心文档），`DOCUMENT_BASELINE` 已过时（见问题 1）。用户要求「依靠 wiki 管理项目设计文档集（不同角色交付物）」。

**结论**：当前文档体系**不具备被 Wiki 索引的结构化元数据**（缺 `owner` / `role` / `status` / `version` / `supersedes` / `trace` 字段），需先补齐元数据规范才能被 LLM Wiki 消费。

---

## 4. 端到端能力缺口分析（对应用户需求第 2 条）

链路：**摄入（ingest / Hyper-Extract）→ 建本体（designer）→ 见本体（explorer）→ 演本体（simulation）→ 用本体（QA / 语义检索 / MCP）**

| 能力项 | 现状（证据） | 缺口 | 严重级别 |
|---|---|---|---|
| **1. 意图识别** | 后端 `semantic_retrieval` 提供多模式检索（`/nl /chain /mdl /graph /metric /hybrid`，`routes.py:86-363`），具备「分类路由」雏形 | 缺少**统一意图分类器 + 置信度门限**；无「意图不明时反问用户」的兜底；无意图识别准确率评测集 | P0 |
| **2. 泛化能力** | 依赖本体覆盖度；`semantic_admin/gap_pool`（概念缺口回路，ADR-086）存在，说明有「缺口发现」机制 | 本体未覆盖时**无降级兜底**（未建模即失败）；跨域泛化无验证；「零幻觉」承诺无评测支撑 | P0 |
| **3. 本体约束输入/输出** | 后端有 SHACL 治理（ADR-077、ADR-085 形状持久化与写路径校验）、open-typed 双层事实模型写路径不变量（ADR-084） | 约束**仅覆盖写入路径**；QA/检索的**输出侧未见本体校验**；前端输入侧无实时本体提示 | P1 |
| **4. 溯源** | `provenance_router` 已注册；审计日志完整（ADR-008/042） | 问答结果的**溯源粒度未到「依据哪条本体规则/哪个数据源」**；溯源不可视化 | P1 |
| **5. 后续执行提醒与建议** | 决策智能（ADR-076 决策一等公民，`decision_record` 7 端点）、`action_service` 存在 | QA 结果**未串联到「建议方案 + 执行提醒」闭环**（问答与决策/动作两张皮）；无「提醒用户执行」的触达通道 | P0 |
| **6. 端到端连通** | 各环节后端服务独立可用 | **前端入口碎片化**（Agent 5 入口、知识库 2 入口）导致用户无法形成「摄入→问答」的单一顺畅路径；双 API 族（ingest）契约不一致 | P0 |

**结论**：后端「零件」基本齐备（四步法各阶段均有对应服务模块），**真正的缺口在「串联」与「收敛」**：意图识别缺统一入口、问答未闭环到决策执行、输入输出本体约束不对称、前端入口割裂。这正是 PRD v2 应聚焦的方向。

---

## 5. 问题总表（按严重级别排序）

| # | 问题 | 级别 | 证据（文件:行） |
|---|---|---|---|
| 1 | Policy 同概念三份实现，两份为死代码 | P0 | `config/pages/PolicyManagement.tsx`、`config/pages/PolicyManager.tsx`（均无路由引用）；`audit/pages/PolicyPage.tsx`（`AppRoutes.tsx:111`） |
| 2 | 图谱「进度」在 Celery 不可用时伪造 completed | P0 | `frontend_compat/api/ontology_routes.py:226-233` |
| 3 | 7 套图谱/图表渲染栈并存，`@ant-design/graphs` 零引用 | P0 | `apps/web/package.json:18,22,25,29,32,41,60` |
| 4 | 紫色→品红渐变命中 P0-2 红线 | P0 | `shared/styles/colorThemeUtils.ts:69,73,78,143` |
| 5 | LLM Wiki 模块完全缺失（绿地） | P0 | `apps/web/src/modules/` 无 wiki；Grep `wiki` 零命中 |
| 6 | 重复路由：`/semantic-admin/pipeline` 与 `pipeline-runs` 同组件 | P0 | `AppRoutes.tsx:125-126` |
| 7 | Agent 入口 5 个、知识库入口 2 个，边界模糊 | P0 | `AppRoutes.tsx:67,68,69,96,118,101,102` |
| 8 | 摄入 API 双族（`/api/ontology/ingest/*` vs `/api/ingest/*`）契约重复 | P0 | `shared/services/api.ts:299-546,578-612` |
| 9 | 同概念组件重复（AuditTimeline / Knowledge） | P1 | `audit/components/AuditTimeline.tsx` vs `audit/pages/AuditTimeline.tsx`；`knowledge/pages/KnowledgeBase.tsx` vs `KnowledgePage.tsx` |
| 10 | 架构文档 10 篇互相覆盖，无 superseded 标记 | P1 | `docs/02-architecture/ARCHITECTURE_*.md`（10 篇） |
| 11 | ADR 编号冲突（061 双份、065 跨目录） | P1 | `docs/07-adr/ADR-061*`（2 份）；`docs/02-architecture/reports/ADR-065_BULKHEAD_AUDIT.md` vs `docs/07-adr/ADR-065_*` |
| 12 | 文档基线已过时（称 ADR 54 篇，实为 90 篇） | P1 | `docs/DOCUMENT_BASELINE_v1.0.0.md:16,54` |
| 13 | 需求文档无语义命名/状态/owner | P1 | `docs/00-requirements/req-ok.md`、`archive/req-alpha.md`、`archive/req-beta.md` |
| 14 | 四步法语义与前端扁平路由脱节；编辑态/探查态未强制分离 | P1 | `CONTEXT.md:13-16`；`ontology/pages/OntologyGraphPage.tsx:63-69` |
| 15 | 问答未闭环到「建议方案 + 执行提醒」 | P0 | 决策服务（`decision_record`）与 QA（`semantic_retrieval`）无串联证据 |
| 16 | 本体约束仅覆盖写入侧，输出/输入侧不对称 | P1 | ADR-084/085（写路径）；QA 输出侧未见校验 |
| 17 | 角色切换能力仅在 store 层，无 UI 入口 | P1 | `shared/stores/authStore.ts:156`；Grep 无切换 UI 组件 |
| 18 | 77 编号：ADR-035、ADR-087 缺口 | P2 | `docs/07-adr/` 目录清单 |
| 19 | 双时态推演隔离（`scenario_id` + `valid=false`）前端未见可见性控制 | P2 | `CONTEXT.md:15`；前端未见开关 |

---

## 6. 未验证清单（明确标注，不臆断）

1. **运行时验证**：Celery worker 是否实际运行、`generate_graph_task` / `process_file_upload_task` 是否真实产出图与数据 —— 仅做了静态代码取证。
2. **查询结果可视化**：`/qa/query` 页是否已将结果渲染为图表 —— 需人工走查 UI。
3. **断链全量对账**：67 条前端路由与后端路由的**逐条**匹配未完成，本报告仅抽样 5 条关键链路；`/ontology/abution-graph`、`/iframe-viewer` 数据源存疑。
4. **后端测试真实性**：`apps/api/tests/` 下测试是否 mock 真实、是否覆盖端到端 —— 未逐文件核验（用户需求第 8 条要求「不接受伪实现」，此为架构师/测试侧职责）。
5. **菜单配置驱动**：`menu-config` 模块生成的菜单是否与实际路由一致（是否存在「菜单指向空页」）—— 未验证。

---

## 7. 整改方向（传递给 PRD v2 与架构师）

| 方向 | 说明 | 对应 PRD 功能 |
|---|---|---|
| **收敛入口** | 按四步法重构信息架构；Agent/知识库多入口合并；删除重复路由 | F1 统一导航与信息架构 |
| **收敛实现** | 下线死代码；清除重复组件；合并双 API 族 | F2 重复实现归并 + 迁移映射表 |
| **收敛文档** | 建立文档元数据规范 + superseded 机制 + ADR 编号治理 | F3 文档治理（Wiki 后端） |
| **收敛技术栈** | 图谱渲染栈由 7 套收敛为 1-2 套 | F4 渲染栈收敛（架构师立项） |
| **建立 LLM Wiki** | 产品内模块 + 仓库文档治理双向打通 | F5 LLM Wiki 模块（P0 首批） |
| **闭环问答** | 意图识别统一入口 + 本体约束双向 + 溯源可视化 + 决策执行提醒 | F6 端到端智能问答闭环 |
| **P0 合规** | 消除紫→品红渐变；统一设计 Token | F7 主题系统重构 |

---

## 8. 合规声明（团队 P0 红线）

- 本报告**未使用任何 emoji 作为功能图标或正文装饰**（文中所有图标均以文字描述，如「火箭图标」）。
- 本报告**未推荐紫色→粉红/品红渐变方案**；相反，第 3.5 节明确将其列为待整改红线。
- 本报告**无空洞占位文案**（无 Lorem ipsum / Welcome to 类内容）。

---

## 附录 A：本轮取证命令摘要

```
find docs -name "*.md" | wc -l                                  # 259
ls docs/02-architecture/                                        # 10 篇 ARCHITECTURE_*.md
ls docs/07-adr/                                                 # ADR-001..090，含 ADR-061 双份、缺 035/087
grep -c "path=" apps/web/src/AppRoutes.tsx                      # 67
ls apps/web/src/modules | wc -l                                 # 26
grep -n "linear-gradient" colorThemeUtils.ts                    # :143 紫→品红
grep -n "<graph libs>" apps/web/package.json                    # 7 套渲染栈
find apps/api -iname "*wiki*"                                   # 零命中
```

## 附录 B：版本历史

- **v1.0.0 (2026-10-16)** —— 初版。基于代码/文档实证，完成 8 类问题复核 + 6 类新问题深挖 + 端到端能力缺口分析。
