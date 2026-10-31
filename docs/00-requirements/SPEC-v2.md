---
id: odap.l0.spec-v2
status: authoritative
owner: pm
version: 2.0.0
layer: L0
concern: dev-spec
lifecycle: living
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
governance_reason: 本次交付唯一开发权威（13 节 + AC-01~AC-56）
governance_evidence: 本文件 §1 权威声明；docs/09-checklists/contract-rulings.md 以其为仲裁依据
---

# Spec — ODAP v2 规格契约

> 版本：v2.0.0 | 生成日期：2026-10-17 | 状态：**已确认（用户 Phase 1 三文档确认后自动生成）**
> 上游依据：`docs/00-requirements/PRD-v2.md`(v2) + `docs/02-architecture/ARCHITECTURE-v2.md`(v2.0) + `docs/04-ui/UIUX-DESIGN-v2.md`(v2) + `docs/12-evaluation/PRODUCT-EVALUATION.md` + `docs/12-evaluation/ARCHITECTURE-EVALUATION.md`
> 本文件为**唯一开发依据**。任何与本文冲突的实现均视为缺陷；需求变更须走 §13 变更流程。
> 本文档不使用 emoji，不使用紫色→粉色/品红渐变，不含空洞占位文案。

---

## 1. 产品定义

- **一句话描述**：ODAP 是基于本体（TBox+ABox）双时态知识图谱的智能辅助**决策**平台——不止回答"是什么"，而是回答"该怎么办、该由谁办、办完是否合规"，且每条结论可溯源到本体元素。
- **目标用户**（3 类）：
  1. **本体建模者**（数据/语义工程师）：建本体、维护 TBox/ABox、治理语义缺口。
  2. **业务分析决策者**：用自然语言提问、看推演结果、接受执行建议。
  3. **平台管理员**：权限、策略、审计、渠道与系统配置。
- **核心问题**：现有平台"能建模、能看图、能推演"，但（a）无统一意图识别与本体约束的问答闭环，（b）无文档真相源与治理，（c）前端 60+ 路由职责重叠、7 套图谱栈并存、主题系统违规。

---

## 2. 可交付范围（锁定 — 不在此列表的功能一律不做）

### 2.1 Wave 0 — P0 存量修复（前置门禁，必须先全绿才能进 Wave 1）

| 编号 | 事项 | 验收标准摘要 |
|---|---|---|
| W0-1 | 删除紫→品红渐变与行内主题注入 | `colorThemeUtils.ts` 的 `violet` 调色板与 `linear-gradient(135deg,#7C3AED,#D946EF)` 全部移除；`global.css` 跨色相渐变移除；主题改由 `design-tokens.css` 的 `data-appearance`/`data-accent` 驱动 |
| W0-2 | 消除伪实现 | `frontend_compat/api/tasks.py` 的 `generate_graph_task`（`time.sleep(10)` + 硬编码 100/150）与 `process_file_upload_task`（sleep 后不落库）改为真实执行或**明确返回 not_implemented 并拒绝假成功**；`ontology_routes.py` 的 ImportError 分支**禁止**返回 `completed` |
| W0-3 | 修复静默吞异常与日志 bug | `tasks.py` 三处 `except` 不得静默；修正缺 `f` 前缀的 f-string（`{exc}` 必须插值）；异常须带 `error_code` + 具体原因（禁止"处理失败"式模糊文案） |
| W0-4 | 消除 infra→biz 顶层反向依赖 | `infra/resilience/fault_tolerance.py:17` 模块级 `from odap.biz.core.agent.swarm_orchestrator import AgentState` 改为协议/数据类下沉到 `common`，或改惰性注入 |
| W0-5 | 清理 emoji 功能图标 | 55 个含 emoji 的 `.tsx` 全部替换为 `lucide-react` 对应语义角色图标（经 `Icon` 包装组件） |
| W0-6 | 门禁脚本落地 | 新增并接入 CI：`apps/web/scripts/check-lucide-icons.mjs`（白名单/emoji/语义角色+minSize/直连导入禁令）、`scripts/verify_provenance.py`、扩展 `scripts/check_dangling_doc_links.py` |

### 2.2 Wave 1 — 全量并行交付（用户决策：全部并行）

| 编号 | 功能 | RICE | 验收标准摘要 |
|---|---|---|---|
| F1 | **LLM Wiki 模块**（产品侧：条目 CRUD / 版本 / 引用图 / 去重合并 / 发布状态机） | 高 | 见 AC-01~AC-08 |
| F2 | **文档治理后端**（统一纳管模型 / superseded 链 / owner 必填 / 陈旧检测 / 机械校验） | 高 | 见 AC-09~AC-14 |
| F3 | **Wiki ↔ 仓库 docs/ 双向打通**（import 生成条目、export 回写 md，带审批） | 高 | 见 AC-15~AC-17 |
| F4 | **统一导航与信息架构**（60+ 路由收敛为 6 工作区，旧路由 redirect + 埋点） | 高 | 见 AC-18~AC-20 |
| F5 | **重复实现归并**（Policy 三处→一处、Knowledge 两处→一处、AuditTimeline 双份→一份、pipeline 双路由→一） | 高 | 见 AC-21~AC-23 |
| F6 | **本体约束编排层六步管线**（IntentRouter→OntologyAligner→RuleGuard→RetrievalExecutor→AnswerComposer→OutputContractGate） | 高 | 见 AC-24~AC-31 |
| F7 | **意图识别四级漏斗 + 泛化评测集** | 高 | 见 AC-32~AC-35 |
| F8 | **溯源与答案信封**（Provenance 六步齐全、证据可解析、TBox 版本锚定） | 高 | 见 AC-36~AC-39 |
| F9 | **Action 层 / HITL**（后续执行建议 + 风险分级 + 人工确认） | 中 | 见 AC-40~AC-42 |
| F10 | **主题系统重构 + 双风格切换 + Token 迁移** | 中 | 见 AC-43~AC-47 |
| F11 | **图谱渲染栈收敛 7→3** | 中 | 见 AC-48~AC-50 |
| F12 | **图标库迁移至 lucide-react**（含 Icon 包装组件 + 映射表 + codemod） | 中 | 见 AC-51~AC-54 |
| F13 | **路由↔后端↔API 契约对账矩阵**（全量 67 路由） | 中 | 见 AC-55~AC-56 |

---

## 3. 明确不做（Out-of-Scope — 锁定）

| 不做的功能 | 原因 | 何时考虑 |
|---|---|---|
| 替换 Neo4j 或自研图数据库 | 违"沿用现状+增量重构"决策；属架构师职责 | 图规模超单机阈值后 |
| 发明新 DSL | `CONTEXT.md:20` 明令禁止；复用 HE YAML 与 UModel 语法 | 永不 |
| Palantir 式 FDE 陪跑交付 | 违产品化定位 | 永不 |
| 重做已可用的工作空间隔离与审计 | 已有 ADR-023/042，ROI 为负 | 有实测缺陷时 |
| 多模态本体抽取（图像/音视频） | 长尾；本轮聚焦文本 + 结构化 | v2.1 |
| 消费级移动 App | 专业用户桌面场景为主 | 永不 |
| 商业化计费体系 | 非产品能力 | 商业化阶段 |
| 自建富文本编辑器 | 用成熟方案；不为 Wiki 造编辑器 | 永不 |
| 一次性把 219+88 个超 300 行文件全拆完 | 破坏面过大 | 按模块增量拆，每模块触达时拆分 |

---

## 4. 技术架构（锁定 — 版本来自实际文件）

> 规则：每层锁定到具体版本；`lucide-react` 版本已由 Phase 3 安装时锁定并回填（`apps/web/package.json` + `pnpm-lock.yaml`，CI 由 `apps/web/scripts/check-lucide-icons.mjs` 的 `PINNED_VERSION` 常量比对）。

| 层 | 技术 | 实际版本 | 锁定原因 |
|---|---|---|---|
| 前端框架 | React / React DOM | `^19.2.4` | 沿用现状 |
| 语言 | TypeScript | `~6.0.2` | 沿用现状 |
| 构建 | Vite / @vitejs/plugin-react | `^8.0.4` / `^6.0.1` | 沿用现状 |
| UI 组件 | antd | `^6.3.5` | 沿用现状；主题经 ConfigProvider(cssVar) |
| UI 扩展 | @ant-design/pro-components | `^3.1.12-0` | 沿用现状 |
| **图标（唯一）** | **lucide-react** | `^1.58.0`（实际安装 1.58.0，CI `check:icons` 钉死） | ADR-092：唯一能满足"统一描边 1.5px + round cap/join + fill:none"的库 |
| 拓扑图谱（唯一浏览栈） | sigma + @react-sigma/core + @react-sigma/minimap + graphology | `^3.0.3` / `^5.0.6` / `^5.0.6` / `^0.26.0` | ADR-091 |
| 编排编辑（唯一编辑栈） | @xyflow/react | `^12.10.2` | ADR-091（语义=编辑） |
| 统计图表（唯一） | echarts | `^6.0.0` | ADR-091（非拓扑） |
| 状态 | zustand | `^5.0.12` | 沿用现状 |
| 路由 | react-router-dom | `^7.14.1` | 沿用现状 |
| 国际化 | i18next / react-i18next / i18next-http-backend | `^26.3.1` / `^17.0.8` / `^4.0.0` | 沿用现状 |
| 测试 | vitest / @testing-library/react / jsdom | `^4.0.0` / `^16.1.0` / `^25.0.0` | 沿用现状 |
| 后端框架 | FastAPI + Pydantic v2 | 以 lockfile 为准（Phase 3 回填） | 沿用现状 |
| 后端语言 | Python | `>=3.10` | `pyproject.toml:5` |
| 架构适应度 | import-linter（C1/C2/C3 严格 + C4 棘轮 + **新增 C5**） | `>=2.0` | 既有治理资产，勿推倒 |
| 测试 | pytest / pytest-asyncio / pytest-mock | `>=8.0.0` / `>=0.23.0` / `>=3.12.0` | 沿用现状 |
| TBox 存储 | SQLite `odap_main.db`（**真相源**） | — | `CONTEXT.md:11` |
| ABox 存储 | Neo4j（`Instance` 标签，双时态 valid_from/valid_to） | — | `CONTEXT.md:12` |
| 缓存/队列 | Redis | — | 沿用现状 |
| 对象存储 | MinIO | — | 沿用现状 |
| 策略 | OPA `.rego`（`infra/opa/policies/`） | — | ADR-003 |
| 认证 | Bearer JWT | — | 沿用现状 |
| 部署 | Podman + docker-compose（dev / prod 两套隔离） | — | AGENTS.md §2.2 |
| 灰度 | 新增 `feature_flags` 表 + `hashUserId % 100` | — | ADR-093/§8.3 |

**下线项（锁定）**：`@ant-design/graphs`（零引用，移除依赖）；`@antv/g6`（迁 `@xyflow/react`）；`cytoscape`( +6 插件)（迁 sigma/graphology + xyflow）。

---

## 5. API 端点清单（锁定 — 以 `openapi-v2.yaml` 为机器可读真源）

> 前缀统一 `/api/v1`（存量 `/api/*` 由 `frontend_compat` 兼容层过渡，零调用后下线）。全部需 Bearer。

| Method | Path | 功能 | 请求体 | 响应体 |
|---|---|---|---|---|
| GET | `/api/v1/wiki/entries` | 列出条目（分页/筛选 status·owner·tag） | query | `WikiEntryList` |
| POST | `/api/v1/wiki/entries` | 创建条目 | `WikiEntryCreate` | `WikiEntry` |
| GET | `/api/v1/wiki/entries/{entry_id}` | 条目详情 | — | `WikiEntry` |
| PATCH | `/api/v1/wiki/entries/{entry_id}` | 部分更新（乐观锁 version） | `WikiEntryPatch` | `WikiEntry` |
| DELETE | `/api/v1/wiki/entries/{entry_id}` | 软删除归档 | — | `204` |
| POST | `/api/v1/wiki/entries/{entry_id}/publish` | 发布（校验 owner + 内容核验 + content_hash） | — | `WikiEntry` |
| GET | `/api/v1/wiki/entries/{entry_id}/versions` | 版本历史 | — | `WikiVersionList` |
| GET | `/api/v1/wiki/entries/{entry_id}/references` | 引用关系图（出/入） | — | `ReferenceGraph` |
| POST | `/api/v1/wiki/sync/import` | 从仓库 `docs/` 导入为条目 | `DocsImportRequest` | `DocsImportResult` |
| POST | `/api/v1/wiki/sync/export` | 回写为仓库 md（需写权限 + 审批） | `DocsExportRequest` | `DocsExportResult` |
| POST | `/api/v1/ontology/qa` | 本体约束问答（六步管线） | `QaRequest` | `AnswerEnvelope` |
| GET | `/api/v1/ontology/qa/{trace_id}/provenance` | 溯源证据链 | — | `Provenance` |
| GET | `/api/v1/docs/governance/documents` | 列纳管文档 | query | `GovernedDocList` |
| GET | `/api/v1/docs/governance/documents/{doc_id}` | 文档详情 | — | `GovernedDoc` |
| POST | `/api/v1/docs/governance/documents/{doc_id}/supersede` | 标记被取代（保留真相源链） | `SupersedeRequest` | `GovernedDoc` |
| POST | `/api/v1/docs/governance/verify` | 机械校验（悬空引用/缺 owner/孤立/陈旧/重复哈希） | — | `VerifyReport` |
| GET | `/api/v1/docs/governance/dedupe` | 去重合并候选 | query | `DedupeCandidateList` |

**错误契约（全局统一）**：`{ "error_code": string, "message": string, "detail": object|null, "trace_id": string }`。
- `error_code` 必须具体（如 `WIKI_OWNER_REQUIRED`、`GUARD_FAIL_CLOSED`、`TBOX_UNMAPPED_SLOT`、`OUTPUT_CONTRACT_VIOLATION`、`NOT_IMPLEMENTED`）。
- **禁止** `"处理失败"` / `"操作异常"` 之类模糊文案（用户明确要求可调试性）。
- OPA 不可用 → `503` + `GUARD_FAIL_CLOSED`（仅只读查询放行时 `degraded=true`）。

---

## 6. 数据库表清单（锁定）

| 表名 | 核心字段 | 索引 | 关联 |
|---|---|---|---|
| `wiki_entries` | `id`(ULID PK), `title`, `status`(draft/review/published/superseded/archived), `owner_id`, `version`(semver), `source_ref`, `superseded_by`, `content_hash`(sha256), `last_verified`, `tags`(json), `concept_refs`(json), `workspace_id`, `created_at`, `updated_at` | `(status)`, `(owner_id)`, `(content_hash)`, `(workspace_id,status)`, `(source_ref)` | `superseded_by → wiki_entries.id`；`concept_refs → TBox ObjectType` |
| `wiki_versions` | `id`(PK), `entry_id`(FK), `version`, `content`(md), `content_hash`, `author_id`, `change_note`, `created_at` | `(entry_id, created_at DESC)`, `(content_hash)` | `entry_id → wiki_entries.id` |
| `wiki_citations` | `id`(PK), `entry_id`(FK), `kind`(doc/tbox_node/metric/graph_edge/opa_decision), `ref`, `created_at` | `(entry_id)`, `(ref)` | `entry_id → wiki_entries.id`；反向建引用图 |
| `governed_documents` | `id`(PK), `title`, `status`, `owner_id`, `version`, `source_ref`(uniq), `superseded_by`, `content_hash`, `last_verified`, `role`(pm/architect/designer/fe/be/qa/devops), `tags`(json) | `(source_ref UNIQUE)`, `(status)`, `(role)`, `(content_hash)`, `(last_verified)` | 与 `wiki_entries` 通过 `source_ref` 双向映射 |
| `qa_traces` | `trace_id`(PK, urn), `query`, `workspace_id`, `user_id`, `intent_json`, `tbox_version`, `contract_ok`(bool), `degraded`(bool), `created_at` | `(workspace_id, created_at DESC)`, `(user_id)`, `(contract_ok)` | `trace_id` 被 `qa_provenance` 引用 |
| `qa_provenance` | `id`(PK), `trace_id`(FK), `step`(intent/map/guard/retrieve/compose/gate), `component`, `component_version`, `evidence`(json), `ts` | `(trace_id, step)`, UNIQUE`(trace_id, step)` | `trace_id → qa_traces` |
| `qa_actions` | `id`(PK), `trace_id`(FK), `action_type`, `risk_level`(low/high), `payload`(json), `status`(proposed/approved/rejected/executed), `approved_by`, `executed_at` | `(trace_id)`, `(status)`, `(risk_level)` | `trace_id → qa_traces` |
| `feature_flags` | `key`(PK), `enabled`(bool), `rollouts`(json: user_ids/percentage), `updated_at` | `(enabled)` | — |

**约束**：`wiki_entries.owner_id` NOT NULL（无 owner 不合格）；`status=published` 时 `last_verified` 不得过期（>180 天视为陈旧）；`content_hash` 相同即判重；合并只置 `superseded`，**禁止物理删除**。

---

## 7. 页面清单（锁定）

| 页面 | 路由 | 核心组件 | 对应 API | 主题 |
|---|---|---|---|---|
| 工作台 | `/` `→ /workspace` | 概览卡 + 最近 Wiki + 待处理缺口 | 多源聚合 | luminous 默认 |
| **Wiki 列表** | `/wiki` | `WikiListPage`：筛选器 + 表/卡双视图 + 状态徽标 | `GET /wiki/entries` | 双风格 |
| **Wiki 详情** | `/wiki/:entryId` | `WikiEntryPage`：阅读器 + 检查器（版本时间线 / 引用图 / 溯源 / 去重候选） | 详情/versions/references | 双风格 |
| **Wiki 去重合并** | `/wiki/dedupe` | `WikiDedupePage`：左右对照 diff + 合并动作 | `GET /docs/governance/dedupe` | 双风格 |
| **智能问答** | `/qa` | `QaConsolePage`：五段式可解释卡片（意图→映射→约束命中→答案→溯源→执行建议）+ 右栏推理检查器 | `POST /ontology/qa`、`GET .../provenance` | 双风格 |
| 文档治理 | `/governance/documents` | `GovernanceListPage` + 校验报告 | governance 系列 | 双风格 |
| 本体建模 | `/ontology/designer` | 画布 + 资源树 + 校验检查器 | 既有 | 双风格 |
| 图谱探查 | `/ontology/explorer` | sigma 画布 + 图例面板 + 选择面板 + 缩略图 | 既有（迁 sigma） | 双风格 |
| 语义治理 | `/semantic-admin/*` | 既有子页（pipeline 双路由归一） | 既有 | 双风格 |
| 平台管理 | `/platform/*` | 用户/角色/策略/渠道/审计 | 既有 | 双风格 |

**工作区收敛（60+ 路由 → 6 个工作区）**：工作台 / 本体 / 知识（Wiki+文档治理）/ 问答与决策 / 语义治理 / 平台管理。旧路由全部保留 `<Navigate replace/>` 重定向 + 重定向埋点。
**真重复路由处理**：`/semantic-admin/pipeline` → `/semantic-admin/pipeline-runs`（redirect）。`/policies` 已是 redirect，**不需改动**（订正：非真重复）。

---

## 8. 设计 Token（锁定 — 真源 `docs/04-ui/design-tokens.css` + `design-tokens.json`）

- **主色**：`cobalt #1E45DB`（默认）/ `teal #0A6E5D` / `indigo #4F46E5` / `graphite #334155`；**全部纯色使用**。
- **风格（双轴切换）**：`data-appearance = luminous | nebula`（亮/暗面）× `data-accent = cobalt|teal|indigo|graphite`（强调色族）；另 `data-density = comfortable|compact|dense`（默认 compact）。
- **字体**：展示 `Manrope` / 正文 `Inter` / 中文 `Noto Sans SC` / 数据与代码 `JetBrains Mono`。
- **图标库**：**lucide-react（唯一）**；`strokeWidth=1.5`、round cap/join、`fill:none`、`currentColor`；尺寸仅 16/20/24px；经 `shared/components/Icon.tsx` 统一设置；**禁 emoji**、禁混用第二套库、禁 `import * as Icons`。
- **Token 三层**：primitive（唯一允许 hex 的层）→ semantic（主题切换点）→ component；`semantic`/`component` 100% alias，禁止散落 hex。
- **图谱/图表 Token**：`--odap-graph-*`（8 类节点分类色）、`--odap-chart-*`（8 序列色）；渲染库自带主题色**禁止**。
- **渐变**：`--odap-gradient-brand` **不存在**；仅允许同色相深浅（`--odap-color-accent` ↔ `-hover`）。
- **动效**：`--odap-duration-*` + `--odap-ease-*`；ease 仅 `standard/decelerate/accelerate/linear`，控制点 ≤1；**禁** oveshoot/spring（`cubic-bezier(0.68,-0.55,...)`）。
- **响应式**：7 断点（`--odap-bp-xs/sm/md/lg/xl/2xl/3xl`）。
- **旧 Token 迁移**：现网 `global.css` 347 处 `--odap-*` 需产出映射表并逐条迁移（旧 `--odap-color-accent-*` → 新 `--odap-accent-*` 等）。
- **硬编码清理**：现存 1044 处 hex（排除 `#fff`/`#000`）按模块清理，清理率进质量门禁。

---

## 9. 验收标准（EARS 格式 — QA 以此为唯一依据）

| 编号 | 功能 | EARS 验收标准 | 优先级 |
|---|---|---|---|
| AC-01 | Wiki 创建 | When 用户提交合法条目（title+owner+content），系统**必须**创建条目并返回 ULID 与 `version=0.1.0` | P0 |
| AC-02 | Wiki 缺 owner | If 创建时 `owner_id` 缺失，系统**必须**返回 `400 WIKI_OWNER_REQUIRED` | P0 |
| AC-03 | Wiki 发布 | Where 条目内容未变化且 owner 存在，When 发布，系统**必须**置 `status=published` 并写 `wiki_versions` 快照 | P0 |
| AC-04 | Wiki 发布拦截 | If 条目 `content_hash` 与已发布条目重复，系统**必须**阻止发布并返回 `WIKI_DUPLICATE_CONTENT` + 冲突条目 id | P0 |
| AC-05 | Wiki 版本 | When 用户请求 versions，系统**必须**按 `created_at DESC` 返回全部快照且含 `change_note` | P0 |
| AC-06 | Wiki 引用图 | When 请求 references，系统**必须**返回 `outgoing[]` 与 `incoming[]`，每条含 `kind` 与 `ref` | P0 |
| AC-07 | Wiki 软删除 | When 删除条目，系统**必须**置 `status=archived` 且保留全部版本（禁止物理删除） | P0 |
| AC-08 | Wiki 乐观锁 | If 提交的 `version` 与服务端不一致，系统**必须**返回 `409 WIKI_VERSION_CONFLICT` | P0 |
| AC-09 | 文档纳管 | When 列出纳管文档，系统**必须**返回 `owner/status/role/last_verified/superseded_by` 五字段 | P0 |
| AC-10 | supersede 链 | When 标记 A 被 B 取代，系统**必须**置 `A.status=superseded`、`A.superseded_by=B`、`B.supersedes` 含 A，且**不得**删除 A | P0 |
| AC-11 | 悬空引用检测 | If 文档 citations 指向不存在的 id，When 执行 verify，系统**必须**在报告中标记 `DANGLING_REF` 并返回非零退出 | P0 |
| AC-12 | 缺 owner 检测 | If 纳管文档无 owner，When 执行 verify，系统**必须**标记 `MISSING_OWNER` | P0 |
| AC-13 | 陈旧检测 | If `last_verified` 超过 180 天，When 执行 verify，系统**必须**标记 `STALE` | P1 |
| AC-14 | 重复哈希 | If 两文档 `content_hash` 相同，When 请求 dedupe，系统**必须**作为合并候选返回并附相似度 | P0 |
| AC-15 | 仓库导入 | When 导入 `docs/**/*.md`，系统**必须**解析 front-matter 生成/更新 `wiki_entries` 并保留 `source_ref` | P0 |
| AC-16 | 回写仓库 | Where 用户具备写权限且审批通过，When 导出，系统**必须**写入 `.md` 且 front-matter 与条目字段一致 | P0 |
| AC-17 | 回写拒绝 | If 用户无写权限或审批未通过，系统**必须**返回 `403 WIKI_EXPORT_FORBIDDEN` 且不改动文件 | P0 |
| AC-18 | 旧路由重定向 | When 访问被收敛的旧路由，系统**必须** `<Navigate replace/>` 到新路由并上报 `route_redirect` 埋点 | P0 |
| AC-19 | 导航分区 | When 渲染全局导航，系统**必须**仅呈现 6 个工作区，且每项可达 | P0 |
| AC-20 | 无死链 | If 菜单项指向的路由不存在，构建阶段**必须**失败（新增路由一致性测试） | P0 |
| AC-21 | Policy 归一 | When 构建完成，`config/pages/PolicyManagement.tsx` 与 `PolicyManager.tsx` **必须**已删除且无引用 | P0 |
| AC-22 | Knowledge 归一 | When 构建完成，`knowledge/pages/KnowledgeBase.tsx` 与 `KnowledgePage.tsx` **必须**收敛为一处，另一处删除 | P0 |
| AC-23 | pipeline 路由归一 | When 访问 `/semantic-admin/pipeline`，**必须**重定向到 `/semantic-admin/pipeline-runs` | P0 |
| AC-24 | 意图识别 | When 输入可被 USL 术语表命中的 query，`IntentRouter` **必须**返回 `L1` 命中且 `confidence≥0.9`，不调用 LLM | P0 |
| AC-25 | 低置信澄清 | If 四级漏斗均未达阈值，系统**必须**返回澄清问句（`clarify_required`），**禁止**猜测作答 | P0 |
| AC-26 | 本体映射 | When 槽位可映射到 TBox `ObjectType`/`RelationType`，`OntologyAligner` **必须**返回对应 `mapped[]` 与 `prov` | P0 |
| AC-27 | 未映射入缺口 | If 槽位无法映射，系统**必须**写入 `gap_pool` 并在响应中返回 `unmapped[]`，**禁止**静默丢弃或用 LLM 幻觉补全后执行 | P0 |
| AC-28 | 规则 fail-closed | If OPA 不可用，`RuleGuard` **必须**拒绝高风险动作（`503 GUARD_FAIL_CLOSED`），只读查询放行并标 `degraded=true` | P0 |
| AC-29 | 检索降级 | If 单检索引擎失败，系统**必须**按 graph→nl→mdl→metric 降级并在 `degraded_engines[]` 记录 | P0 |
| AC-30 | 证据不足不编造 | If 检索无证据，`AnswerComposer` **必须**返回 `no_answer=true` + 原因，**禁止**生成无来源答案 | P0 |
| AC-31 | 输出契约 | If 输出违反 TBox/SHACL 形状，`OutputContractGate` **必须**置 `contract_ok=false` 并返回 `blocked_reasons[]` | P0 |
| AC-32 | 意图评测集 | When 运行评测，**必须**覆盖同义改写≥200 / 跨域迁移≥100 / 复合意图≥100 / 干扰项≥100 | P0 |
| AC-33 | 意图指标 | When 评测完成，`Intent-Acc@1 ≥ 0.90` 且 `Slot-F1 ≥ 0.85`，否则 CI **必须**失败 | P0 |
| AC-34 | 泛化缺口 | When 评测完成，`Gen-Gap ≤ 0.10`，否则 CI **必须**失败 | P1 |
| AC-35 | 未映射率 | When 评测完成，**必须**输出 `Unmapped-Rate` 用于驱动本体补全 | P1 |
| AC-36 | 溯源六步齐全 | When 问答返回，`Provenance.steps` **必须**覆盖 intent/map/guard/retrieve/compose/gate 六步，缺步即 `400` | P0 |
| AC-37 | 证据可解析 | When 校验溯源，每个 `evidence.ref` **必须**可解析（TBox 节点存在 / OPA decision 可复算 / Neo4j 边存在 / chunk 存在） | P0 |
| AC-38 | 版本锚定 | When 校验溯源，`tbox_version` **必须**与本次使用的 TBox 快照哈希一致 | P0 |
| AC-39 | 溯源脚本 | When 运行 `scripts/verify_provenance.py`，**必须**对上述三条规则做门禁并返回非零退出码 | P0 |
| AC-40 | 执行建议 | When 答案含可执行后续，**必须**返回 `suggested_actions[]` 且每项含 `risk_level` | P0 |
| AC-41 | 高风险 HITL | If `risk_level=high`，系统**必须**进入 HITL 待确认，**禁止**自动执行 | P0 |
| AC-42 | 动作溯源 | When 动作被执行，**必须**写入 `qa_actions` 且关联同一 `trace_id` | P0 |
| AC-43 | 双风格切换 | When 用户切换 `data-appearance`，**必须**整站切换且刷新后保持（持久化） | P0 |
| AC-44 | 强调色切换 | When 用户切换 `data-accent`，**必须**仅 semantic 层变化，primitive 不动 | P0 |
| AC-45 | 无紫粉渐变 | When 扫描全部源码与 Token，**必须** 0 处跨色相紫→粉/品红渐变 | P0 |
| AC-46 | 无过冲缓动 | When 扫描全部源码，**必须** 0 处 `cubic-bezier(0.68,-0.55,...)` | P0 |
| AC-47 | 硬编码颜色 | When 扫描组件代码，hex 硬编码**必须**仅剩 `#fff`/`#000`；清理率 100% | P1 |
| AC-48 | 渲染栈收敛 | When 检查 `package.json`，**必须**不含 `@ant-design/graphs`、`@antv/g6`、`cytoscape` | P0 |
| AC-49 | sigma 上下文 | When 审查图谱代码，**必须**经 `@react-sigma/core` 上下文，**禁止**裸 `new Sigma()` | P0 |
| AC-50 | Token 消费 | When 渲染图谱/图表，**必须**使用 `--odap-graph-*` / `--odap-chart-*`，无库自带主题色 | P0 |
| AC-51 | 图标唯一库 | When 扫描源码，除 `Icon.tsx` 外**必须** 0 处直接 `from 'lucide-react'` | P0 |
| AC-52 | 描边规格 | When 审查 `Icon.tsx`，**必须**固定 `strokeWidth=1.5` 且不对外暴露该 prop | P0 |
| AC-53 | 无 emoji 图标 | When 扫描 `.tsx/.ts/jsx/js/html`，**必须** 0 处 emoji 功能图标 | P0 |
| AC-54 | 图标尺寸 | When 扫描 `Icon.tsx` 使用点，size **必须**仅为 16/20/24 | P0 |
| AC-55 | 契约对账 | When 运行对账脚本，67 路由**必须**全部有对应实现或显式 `NOT_IMPLEMENTED` 标注 | P0 |
| AC-56 | 模糊错误文案 | When 扫描后端错误返回，**必须** 0 处 `"处理失败"`/`"操作异常"` 类模糊文案 | P0 |

---

## 10. 边界与约束

- 不支持 IE；目标 Chrome/Edge 最新两个大版本。
- 响应式断点 7 档；专业桌面优先，最小可用宽度 1280px。
- 性能目标：图谱首屏 ≤3s（1 万节点）；问答 P95 ≤8s（含 LLM）；Wiki 列表 P95 ≤500ms。
- 单文件 ≤300 行（新代码强制；存量按模块触达时拆分）。
- 后端分层依赖只向下；`infra` 不得 import `biz`（C4）；新增 C5（tools 边界）。
- 所有变更经 Feature Flag 灰度（内测→5%→50%→全量）。
- 不允许伪实现：任何未实现能力必须显式 `501 NOT_IMPLEMENTED`，**禁止**返回假成功。

---

## 11. 内嵌已知坑（来自本轮实测，直接注入开发）

| 坑 | 指纹 | 根因 | 修法 |
|---|---|---|---|
| 假异步任务 | `tasks.py:108-131` | `time.sleep` + 硬编码计数冒充真实抽取 | 改为真实执行或显式 `NOT_IMPLEMENTED` |
| ImportError 时假报 completed | `ontology_routes.py:203-237` | 异常分支兜底返回成功态 | 异常必须上抛为明确错误码 |
| 静默吞异常 | `tasks.py:76,126,168` | 裸 `except` 无日志 | 必须记录 `error_code` + 具体原因 |
| f-string 缺前缀 | `tasks.py:76,126,168` | `"{exc}"` 未加 `f` | 加 `f`，并纳入 lint 规则 |
| infra→biz 顶层反向依赖 | `fault_tolerance.py:17` | 模块级 import 业务类型 | 类型下沉 `common` 或惰性注入 |
| 裸 new Sigma | `useSigmaGraph.ts:197` | 未走 `@react-sigma/core` 上下文 | 改 `SigmaProvider` + hooks |
| Violet 紫→品红渐变 | `colorThemeUtils.ts:69,73,78,142-144` | 调色板跨色相 + 渐变生成 | 整段删除，改 Token 驱动 |
| 过冲缓动 | `global.css:125` | 使用 `cubic-bezier(0.68,-0.55,...)` | 换 `--odap-ease-standard` |
| 路由重复 | `AppRoutes.tsx:125-126` | 两条 Route 同组件 | 归一 + redirect |
| 摄入 API 双族 | `api.ts:299-546,578-612` | `/api/ontology/ingest/*` 与 `/api/ingest/*` 并存 | 收敛为单族 + 兼容层过渡 |
| ADR 一号两文 | `ADR-061` 两份 | 历史并发提交 | 重编号治理（F2） |
| ADR 跨目录撞号 | `reports/ADR-065_*` vs `07-adr/ADR-065_*` | 无编号分配机制 | 归档 reports 内 ADR，统一入 `07-adr` |
| 基线文档过期 | `DOCUMENT_BASELINE_v1.0.0.md` 自述 ADR 001-054 | 未随实际更新 | verify 门禁纳入计数一致性 |

---

## 12. 端到端验证步骤（锁定）

```bash
# ---------- 0. 静态门禁 ----------
cd apps/web && pnpm install && pnpm typecheck && pnpm lint && pnpm test
cd ../.. && python -m pytest apps/api/tests -q
python scripts/verify_provenance.py --self-test
node apps/web/scripts/check-lucide-icons.mjs
python scripts/check_dangling_doc_links.py docs/

# ---------- 1. 启动 ----------
python apps/api/bootstep.py dev          # 期望 graphiti-main-app (healthy)

# ---------- 2. 核心成功流：Wiki 建→发→版 ----------
curl -s -X POST localhost:8000/api/v1/wiki/entries -H "Authorization: Bearer $T" \
  -H "Content-Type: application/json" \
  -d '{"title":"ODAP 本体约束问答设计","owner_id":"u-arch","content":"# ...","tags":["design"]}'
# 断言：200 + id(ULID) + version=0.1.0
curl -s -X POST localhost:8000/api/v1/wiki/entries/$ID/publish -H "Authorization: Bearer $T"
# 断言：200 + status=published
curl -s localhost:8000/api/v1/wiki/entries/$ID/versions -H "Authorization: Bearer $T"
# 断言：至少 1 条 version 快照

# ---------- 3. 关键错误流 ----------
curl -s -o /dev/null -w "%{http_code}" -X POST localhost:8000/api/v1/wiki/entries \
  -H "Authorization: Bearer $T" -H "Content-Type: application/json" \
  -d '{"title":"无 owner","content":"x"}'
# 断言：400 且错误码 WIKI_OWNER_REQUIRED

# ---------- 4. 本体约束问答 + 溯源 ----------
R=$(curl -s -X POST localhost:8000/api/v1/ontology/qa -H "Authorization: Bearer $T" \
  -H "Content-Type: application/json" -d '{"query":"上个季度退货率最高的三个品类是什么","workspace_id":"ws-1"}')
# 断言：answer_envelope 含 content / citations[] / provenance.trace_id / contract_ok
curl -s localhost:8000/api/v1/ontology/qa/$TRACE/provenance -H "Authorization: Bearer $T"
# 断言：steps 覆盖 6 步；每个 evidence.ref 可解析；tbox_version 与快照一致

# ---------- 5. 约束拦截流 ----------
curl -s -X POST localhost:8000/api/v1/ontology/qa -H "Authorization: Bearer $T" \
  -d '{"query":"把库存表删了","workspace_id":"ws-1"}'
# 断言：risk=high → status=clarify/blocked，禁止自动执行；OPA 停掉时应返回 GUARD_FAIL_CLOSED

# ---------- 6. 文档治理 ----------
curl -s -X POST localhost:8000/api/v1/docs/governance/verify -H "Authorization: Bearer $T"
# 断言：报告含 DANGLING_REF / MISSING_OWNER / DUPLICATE_HASH 分类计数；存在问题时退出码非零

# ---------- 7. 前端 E2E ----------
cd apps/web && pnpm vitest run --coverage
# 断言：行覆盖 ≥80%，关键模块（Icon/wiki/qa/theme）分支覆盖 ≥70%
```

---

## 13. 变更记录

| 日期 | 变更内容 | 原因 | 影响范围 |
|---|---|---|---|
| 2026-10-17 | Spec v2.0.0 初始锁定 | 用户确认 Phase 1 三文档后自动生成 | 全量 |
| 2026-10-17 | 图标库锁定由 `@ant-design/icons` 改为 `lucide-react` | 技术核验证明前者不暴露 `stroke-width`，无法满足"统一描边 1.5px"规格（ADR-092） | F12、§4、§8、AC-51~54 |
| 2026-10-17 | `/policies` 标记为非重复路由，不做改动 | 实测 `AppRoutes.tsx:112` 已是 `<Navigate replace/>` | F5、AC-23 |
| 2026-10-17 | 执行策略：Wave 0（P0 存量修复）先行，Wave 1 全量并行 | 用户决策：先修 P0 再开发 + 全部并行 | §2 |
