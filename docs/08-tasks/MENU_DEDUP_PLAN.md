# 菜单相似项去重方案（已落地）

> **版本**: v1.0（2026-10-02）— 已按方案执行落地（种子 55→57，配套迁移脚本 + 测试 + redirect + i18n + 文档同步）
> **依据**: [MENU_REFACTOR_PLAN.md](MENU_REFACTOR_PLAN.md) §6A.3（Iter 7）· [ARCHITECTURE_FOUR_STEPS.md](../02-architecture/ARCHITECTURE_FOUR_STEPS.md)
> **权威菜单源**: `apps/api/odap/biz/platform/menu_config/seeds/seed_four_steps.py`
> **迁移脚本**: `apps/api/odap/biz/platform/menu_config/migrations/iter7_dedup.py`
> **目标**: 消除四步法菜单执行层遗留的 9 处相似/重叠项，**不推翻四步法顶层信息架构**，并让"基于本体的辅助决策"主线在 IA 中显性化
> **状态**: ✅ 已落地（离线单测 31 passed：种子 25 + 迁移 6）

---

## 0. 结论速览（TL;DR）

1. **真实菜单是后端种子驱动的动态树**（`AdminLayout` → `menuConfigApi.getUserTree()`），共 6 顶级目录 / 49 项。前端 `AppRoutes.tsx` 只定义路由，不定义菜单。
2. **`ProLayout.tsx` 是一份完全独立、无人引用的硬编码死菜单**，已于本次删除（含 `shared/index.ts` 的 re-export）。以后改菜单只认 `seed_four_steps.py`。
3. 四步法（建/见/演/用）作为信息架构**方向合理**，"相似项多"的根因是**执行层把同一功能领域的页面按"阶段"硬拆到不同目录**（QA、语义管理、知识库、图谱被打散），以及**部分命名不体现职责区别**。
4. **关键实现约束**：`init_default_menu()` 对已存在的 `code` 直接 skip → **改 seed 里的 name/parent_id/path 对已有数据库无效**，必须配套"按 code 迁移"脚本（见 §4）。

### 0.1 代码核实的关键真相（v0.2 新增，均已读页面源码验证）

> 这些是本次评估最有价值的发现——相似感很大程度来自**命名错误**，而非功能真重复。

| 菜单项 | 现名 | 源码实际职责 | 判定 |
|------|------|------|------|
| `/qa` (QAPage) | "QA 管理" | `AIChatPanel mode="full"`，标题写死"智能问答" | ❌ **命名错误**：它是对话式智能问答，不是"管理" |
| `/qa/query` (QueryPage) | "QA 查询" | NL 本体检索台：三支柱+五阶段+Cypher 预览+查询计划+审计 | ✅ 名字偏弱，实为"检索查询台" |
| `/qa/evaluation` (EvaluationPage) | "QA 评估" | 检索质量评估仪表盘+基准测试 | ✅ 合理 |
| `/agent` (AgentPage) | "智能体对话" | OODA 决策链调度台：intent→dispatch→决策链(observe/orient/decide/act) | ❌ **命名错误**：是"调度"非"对话"（真对话在 `/agent-chat/:id`）。被删的 ProLayout 里原本正确叫"Agent调度" |
| `/semantic-admin/dashboard` vs `/semantic-admin/quality` | "总览仪表盘"/"质量仪表盘" | **两者调用同一组后端 API**（summary/terms-trend/approvals-breakdown），仅布局不同 | 🔴 **真功能重复**：应合并 |
| `/iframe-viewer` (IframeViewerPage) | "图谱查看器" | 通用 iframe 容器，靠 `?url=` 驱动，无 url 显示"未指定页面地址"空状态 | ❌ **不该是固定菜单项**：点进去必空 |
| `/ontology/designer` vs `/blueprint` | "本体设计器"/"蓝图设计器" | designer=`DesignMethod(manual/database/natural_language)` 本体类型定义工作台；blueprint=独立实体(own API/store/CRUD/nodes/edges/scenario 绑定) | ✅ **非重复**：仅"设计器"字面撞名 |
| `/ontology/explorer`·`/semantic-map`·`/abution-graph` | "本体图谱"/"语义地图"/"消歧图" | explorer=可编辑本体 schema 图(GraphCanvas+NodeEdgeEditor)；semantic-map=语义映射产物 CRUD **列表**；abution=消歧快照 CRUD **表格** | ⚠️ **职责不同但命名误导**：后两个是"管理台"却叫"图" |

---

## 1. 相似项诊断（9 处，按严重度）

| # | 严重度 | 领域 | 现状菜单项（路径） | 问题 |
|---|:--:|------|------|------|
| C1 | 🔴 高 | 图谱可视化 | 见本体：本体图谱 `/ontology/explorer`、图谱查看器 `/iframe-viewer`、语义地图 `/ontology/semantic-map`、消歧图 `/ontology/abution-graph`、知识导航 `/knowledge/navigation` | 4~5 个"看图"入口平铺，名字不体现区别，用户无法判断该点哪个 |
| C2 | 🔴 高 | QA | 见本体：QA 管理 `/qa`；用本体：QA 查询 `/qa/query`、QA 评估 `/qa/evaluation` | 同一领域被劈到两个顶级目录；"管理"vs"查询"字面难分 |
| C3 | 🔴 高 | 语义管理(semantic-admin) | 建本体>语义管理：6 项（含质量仪表盘 `/semantic-admin/quality`）；见本体：总览仪表盘 `/semantic-admin/dashboard` | 同后端模块页面被拆散；出现两个"仪表盘" |
| C4 | 🟠 中 | 知识库 | 建本体：知识库 `/knowledge`；见本体：知识导航 `/knowledge/navigation` | 同 `/knowledge` 前缀跨两目录（建=管理/见=浏览，逻辑成立但命名未体现） |
| C5 | 🟠 中 | 本体设计 | 建本体：本体设计器 `/ontology/designer`、蓝图设计器 `/blueprint` | 两个"设计器"，职责边界对用户不可见 |
| C6 | 🟠 中 | 智能体 | 用本体>智能体：我的智能体 `/my-agents`、智能体对话 `/agent`、管理后台 `/admin/agents`、技能管理 `/skills` | 「智能体对话」实际指向 `/agent`（非 `/agent-chat`）；「管理后台」名过泛；Header 另有重复切换按钮 |
| C7 | 🟠 中 | 演本体过载/错位 | 演本体 10 项，含 5 个"业务*"、策略编辑器 `/policy-editor`、仿真沙盘/本体记忆/感知数据/决策智能 | 「策略编辑器」是 OPA 权限策略，应属系统管理；5 个业务建模项扁平堆叠 |
| C8 | 🟡 低 | 数据接入 | 建本体：数据摄入 `/ingest`、HE 抽取链 `/he/extraction` | 两个"数据进来"入口，职责区别未体现（另有 `/business/extraction` redirect 到 `/ingest`） |
| C9 | 🟡 低 | 系统管理 | 系统管理：设置 `/settings`、渠道管理 `/settings/channels/default` | 渠道本是设置的子页，却与之平级 |

---

## 2. 逐项处理建议（已按源码核实）

> 图例：🔀移位(改 parent_id) · ✏️改名(改 name) · 🔗合并(页面级整合) · 🗑️软删(is_active=False)
> **原则**：尽量**保留 `code` 不变**（`id`=`code`，`role_menus` 依赖它），只动 `name`/`parent_id`/`sort_order`/`path`，避免 RBAC 授权失效。

### C1 图谱可视化（见本体）— 结论：不合并，改名 + 移出 iframe
源码核实四项职责互不相同，相似感来自命名，不来自功能：
- 本体图谱 `/ontology/explorer`（可编辑 schema 图）→ ✏️改名 **「本体图谱浏览」**
- 语义地图 `/ontology/semantic-map`（语义映射产物 CRUD 列表）→ ✏️改名 **「语义映射管理」**
- 消歧图 `/ontology/abution-graph`（消歧快照 CRUD 表格）→ ✏️改名 **「消歧快照管理」**
- 图谱查看器 `/iframe-viewer`（通用 iframe 容器）→ 🗑️**从主菜单移除**（`is_active=False`）。它是被其他页面用 `/iframe-viewer?url=...` 内嵌调用的工具路由，作为固定菜单点进去必然显示"未指定页面地址"空状态。路由保留，仅撤菜单入口。
- 建议将上述 3 项收进"见本体"下新子目录 **「图谱与映射」**，减少顶层平铺。

### C2 QA（跨目录割裂）— 结论：三项职责不同，聚合到"用本体"并纠正错名
- 「QA 管理」`/qa` → ✏️改名 **「智能问答」** + 🔀从"见本体"移到"用本体"（源码即 `AIChatPanel` 对话页，"管理"是错名）
- 「QA 查询」`/qa/query` → ✏️改名 **「检索查询台」**（NL→Cypher 检索调试）
- 「QA 评估」`/qa/evaluation` → ✏️改名 **「检索评估」**
- 三项在"用本体"下建子目录 **「问答检索」** 聚合。"见本体"不再保留 QA 项。

### C3 语义管理 + 双仪表盘 — 结论：真重复，合并
源码核实 `/semantic-admin/dashboard` 与 `/semantic-admin/quality` **调用同一组后端 API**（summary/terms-trend/approvals-breakdown），仅布局不同 → 🔗**合并为一个仪表盘**：
- 保留「质量仪表盘」`/semantic-admin/quality` 作为唯一仪表盘；🗑️软删「总览仪表盘」`/semantic-admin/dashboard` 菜单项，路由 redirect 到 quality（`AppRoutes.tsx` 加 `<Navigate>`）。
- 其余 semantic-admin 页面已在"建本体>语义管理"子目录，dashboard 合并后该模块**全部聚合在建本体**，"见本体"不再有 semantic-admin 项。

### C4 知识库（跨目录）— 结论：分组保留，改名消歧
建=管理、见=浏览符合四步法逻辑，仅命名未体现（注：此项未深读 KnowledgeBase/KnowledgePage 内部，证据等级中）：
- 建本体「知识库」`/knowledge` → ✏️改名 **「知识库·管理」**
- 见本体「知识导航」`/knowledge/navigation` → ✏️改名 **「知识库·浏览」**

### C5 本体设计器 vs 蓝图设计器 — 结论：非重复，仅改一字
源码核实 `DesignMethod = manual|database|natural_language`（不含 blueprint），Blueprint 是有独立 API/store/CRUD 的场景绑定实体，与本体类型定义是两套数据模型：
- 「本体设计器」`/ontology/designer` → 保留（或 ✏️**「本体类型设计」** 更精确）
- 「蓝图设计器」`/blueprint` → ✏️改名 **「蓝图编排」**，消除"设计器×2"撞名。**低优先级**。

### C6 智能体命名与重复入口 — 结论：纠正两处错名
- 「智能体对话」`/agent` → ✏️改名 **「智能体调度」**（源码是 OODA 决策链调度台，非对话）
- 「管理后台」`/admin/agents` → ✏️改名 **「智能体管理」**（名过泛）
- 「我的智能体」`/my-agents`、「技能管理」`/skills` 保留。
- Header 的"我的智能体/管理后台"切换按钮与菜单入口重复 → 建议保留菜单，Header 按钮✏️改为纯模式切换或移除（前端改动，非 seed）。

### C7 演本体过载 + 策略编辑器错位 — 结论：策略编辑器移位 + 业务项收组
- 「策略编辑器」`/policy-editor`（OPA 权限策略）→ 🔀从"演本体"移到**系统管理**（与「角色权限」相邻）。这是明确错位，改进无争议。
- 5 个"业务*"（流程/规则/指标/逻辑/对象）→ 在"演本体"下建子目录 **「业务建模」** 收拢，减少顶层扁平项。
  - 注：MENU_REFACTOR_PLAN Iter1(D1) 已明确把 `/business/*` 归"演本体"，是既定架构决策，本方案**不推翻**，仅在其内部收组。是否改归"建本体"属产品语义判断，留作可选议题（见 §6）。
- 演本体顶层收敛为：仿真沙盘 · 业务建模(子目录) · 本体记忆 · 感知数据 · 决策智能。

### C8 数据摄入 vs HE 抽取链 — 结论：非重复，收组 + 改名
源码核实 `/ingest`(IngestPanel) 是多源统一摄入管道（Web搜索/爬虫/上传/DB + 六阶段 collection→cleaning→llm→ontology→version→graph 日志）；`/he/extraction`(HeExtractionPage) 是专用的 hyper-extract 文本抽取工具（选本体+文本→实体/关系，含模板/批量）。职责不同：
- 在"建本体"下建子目录 **「数据接入」** 收拢两项：
  - 数据摄入 `/ingest` → ✏️改名 **「数据摄入管道」**
  - HE 抽取链 `/he/extraction` → ✏️改名 **「HE 文本抽取」**

### C9 设置 vs 渠道管理 — 结论：渠道收为设置子项
- 「渠道管理」`/settings/channels/default` 是设置的子页 → 🔀收进「设置」子目录，或✏️改名明确从属。低优先级。

---

## 3. 目标菜单树（建议稿，前后对照）

```
建本体 (dir:build)
├─ 本体类型设计          /ontology/designer          （C5，原"本体设计器"，可选改名）
├─ 蓝图编排              /blueprint                  （C5，原"蓝图设计器"）
├─ 目标看板              /ontology/goals
├─ 版本管理              /versions
├─ 数据接入 [新子目录]    ← C8
│   ├─ 数据摄入管道        /ingest                     （原"数据摄入"）
│   └─ HE 文本抽取        /he/extraction              （原"HE 抽取链"）
├─ 知识库·管理           /knowledge                  （C4 改名）
└─ 语义管理 [子目录]
    ├─ USL 配置          /semantic-admin/usl
    ├─ USL 本体管理       /semantic-admin/usl-ontologies
    ├─ OL 流水线         /semantic-admin/pipeline
    ├─ 候选管理          /semantic-admin/candidates
    ├─ 审批工作流         /semantic-admin/approvals
    └─ 质量仪表盘         /semantic-admin/quality     （C3：dashboard 合并至此，dashboard 项软删+redirect）

见本体 (dir:see)
├─ 图谱与映射 [新子目录]  ← C1
│   ├─ 本体图谱浏览        /ontology/explorer          （原"本体图谱"）
│   ├─ 语义映射管理        /ontology/semantic-map      （原"语义地图"，实为 CRUD 列表）
│   └─ 消歧快照管理        /ontology/abution-graph     （原"消歧图"，实为 CRUD 表格）
│   （图谱查看器 /iframe-viewer：C1 已核实为通用容器 → 移出主菜单，路由保留）
└─ 知识库·浏览           /knowledge/navigation       （C4 改名，原"知识导航"）

演本体 (dir:simulate)
├─ 决策智能              /decisions                 （Iter7：从末位提升到首位，决策主线显性化）
├─ 仿真沙盘              /simulation
├─ 业务建模 [新子目录]    ← C7
│   ├─ 业务流程          /business/process
│   ├─ 业务规则          /business/rules
│   ├─ 业务指标          /business/indicators
│   ├─ 业务逻辑          /business/logic
│   └─ 对象管理          /business/entities
├─ 本体记忆              /simulation/memory
└─ 感知数据              /simulation/perception
（策略编辑器 /policy-editor → 移至系统管理，见下）

用本体 (dir:use)
├─ 问答检索 [新子目录]    ← C2（QA 三项全部聚合到此，"见本体"不再有 QA）
│   ├─ 智能问答          /qa                         （原"QA 管理"，实为对话页）
│   ├─ 检索查询台         /qa/query                   （原"QA 查询"）
│   └─ 检索评估          /qa/evaluation              （原"QA 评估"）
├─ MCP 工具集            /mcp/tools
├─ 服务化目录            /ontology/service-catalog
└─ 智能体 [子目录]
    ├─ 我的智能体         /my-agents
    ├─ 智能体调度         /agent                      （C6，原"智能体对话"，实为 OODA 调度台）
    ├─ 智能体管理         /admin/agents               （C6，原"管理后台"）
    └─ 技能管理          /skills

系统管理 (dir:system)
├─ 工作空间              /workspace/manage
├─ 角色权限              /roles
├─ 用户管理              /users
├─ 策略编辑器            /policy-editor              ← C7 从"演本体"移入（OPA 权限域）
├─ 审计日志              /audit
├─ 菜单配置              /menu-config
├─ 设置                  /settings
├─ 渠道管理              /settings/channels/default   （C9 暂缓收编：保持系统管理直属，见 §7.1）
└─ 国际化                /i18n-admin

帮助 (dir:help)
└─ 使用指南              /guide
```

> 净效果：顶层可见项显著减少（图谱 3→1 组、业务 5→1 组、QA 3→1 组、演本体 10→5）；两处错名（QA管理/智能体对话）纠正；一处真重复（双仪表盘）合并；一个伪菜单（iframe-viewer）移除。四步法顶层框架不变。

---

## 4. 实现约束与影响清单（落地前必读）

### 4.1 幂等 skip → 改 seed 对已有 DB 无效（最关键）
`MenuConfigService.init_default_menu()`（`menu_config_service.py:296-304`）逻辑为：
```python
existing = self._storage.get_menu_item_by_code(item["code"])
if existing:
    skipped += 1
    continue   # ← 已存在的 code 直接跳过，不更新 name/parent_id/path
```
**含义**：
- ✏️改名 / 🔀移位 / 改 path / 改 sort_order → **对已有数据库不生效**，seed 只能新增全新 code。
- 🗑️从 seed 删除某项 → **不会删除已有 DB 的行**。
- 新增子目录（如「图谱浏览」「业务建模」「数据接入」）→ 是新 code，重跑 `init-default` 会插入，但**其下已有子项的 `parent_id` 不会自动改指向新目录**。

**因此必须配套一次性迁移脚本**（推荐）：
- 位置：`apps/api/odap/biz/platform/menu_config/migrations/`（新建）或 `scripts/`。
- 逻辑：按 `code` 定位现有行，`UPDATE` 其 `name`/`parent_id`/`sort_order`/`path`；新增目录行；软删项置 `is_active=False`。
- **保持 `code`/`id` 稳定** → `role_menus`（存 id）授权不失效。
- 幂等：迁移脚本本身可重复执行。

### 4.2 RBAC 影响
- `role_menus` 存的是菜单 `id`(=`code`)。**只要 code 不变，改名/移位不影响已有角色授权**。
- `_ensure_default_role_menus()`（`menu_config_service.py:321-348`）**仅在角色零分配时**写默认全量授权 → **新增的菜单项对已有非 admin 角色默认不可见**，需在 `/menu-config` 页面重新分配，或在迁移脚本里显式补授权。
- `admin` 由 `is_admin` 短路，始终可见全部，不受影响。

### 4.3 路由兼容（redirect）
- 任何 path 变更或菜单合并，都需在 `apps/web/src/AppRoutes.tsx` 加 `<Navigate ... replace>` 兼容旧 URL（沿用 Iter 2/3 的做法，保护书签）。
- 本方案多数为"改名/移位"，path 不变 → redirect 需求少；仅 C2/C5 若涉及页面合并才需新增 redirect。

### 4.4 i18n
- 菜单名经 `resolveMenuName(t, label)` + `t(name)` 翻译（中文名即 i18n key）。**改名必须同步 i18n 资源**（`apps/web` 语言包），否则界面显示 key 原文。

### 4.5 测试与文档同步（AGENTS 规则 9/12）
- `apps/api/tests/unit/test_menu_seed_four_steps.py` 会断言种子结构 → 改 seed 必须同步改该测试。
- 迁移脚本需新增单测（幂等性 + code 稳定性 + 授权不丢）。
- 文档：更新本方案为"已落地"、`MENU_REFACTOR_PLAN.md` 追加 Iter 7、`ARCHITECTURE_FOUR_STEPS.md` 菜单树章节。

---

## 5. 建议实施批次

| 批次 | 内容 | 风险 | 依赖 |
|------|------|:--:|------|
| **B0（已完成）** | 删除 ProLayout 死代码 | 低 | — |
| **B1** | 迁移脚本骨架 + C3(仪表盘归位) + C7(策略编辑器移位) + C9(渠道收编) — 纯移位/改名，职责清晰 | 低 | 迁移框架 |
| **B2** | C1(图谱聚合) + C4(知识库改名) + C6(智能体改名) + C8(数据接入子目录) — 改名/建子目录 | 中 | B1 |
| **B3** | C2(QA 聚合) + C5(设计器合并) — 需先确认职责边界，可能涉及页面级整合 | 高 | 职责确认 |

---

## 6. 结论与仅剩的产品决策项

### 6.1 已通过源码核实、可直接执行的结论（无需再问）
| 原开放问题 | 核实结论 |
|------|------|
| C1 iframe-viewer 是否保留 | **移除**：通用 iframe 容器，固定菜单点进去必空 |
| C2 /qa vs /qa/query 区别 | **职责不同**：/qa=对话式智能问答(AIChatPanel)；/qa/query=NL 检索查询台(Cypher/计划/支柱)。"QA管理"是错名 |
| C3 两个仪表盘是否合并 | **合并**：调用同一组后端 API，真重复。保留 quality，dashboard 软删+redirect |
| C5 设计器 vs 蓝图是否重叠 | **非重复**：DesignMethod 不含 blueprint；Blueprint 是独立实体。仅改名消歧 |
| C6 /agent 是对话还是调度 | **调度**：OODA 决策链调度台。"智能体对话"是错名，改「智能体调度」 |
| C8 数据摄入 vs HE 抽取 | **非重复**：/ingest=多源摄入管道；/he=专用文本抽取工具。收组+改名 |

### 6.2 产品/成本决策（已由用户拍板"按建议执行"）
1. **C7 归属**：5 个"业务建模"项 → **留在演本体**（沿用 Iter1 D1 既定决策），仅收进「业务建模」子目录。✅ 已落地
2. **实施成本**：→ **接受配套一次性迁移脚本**（否则改动对已有环境不生效）。✅ 已落地 `migrations/iter7_dedup.py`
3. **改名幅度**：→ **全量采纳**（纠正错名 + 消歧改名一起做）。✅ 已落地

> C1~C9 全部处理完毕；下方 §7 记录本次落地相较原建议稿的两处微调。

---

## 7. 落地纪要（v1.0，与建议稿的差异 + 架构对齐）

### 7.1 相较 §3 建议稿的两处微调
- **C9（渠道管理收为设置子项）暂缓**：把「设置」`/settings` 从 menu 改成 directory 会破坏其自身页面路由，收益低风险高。本次**保持渠道管理为系统管理直属项**（仅 sort 排在设置之后），不改层级。
- **移除项采用"从种子删除 + 迁移软删"双轨**：全新部署的种子直接不含 viewer/dashboard（干净）；既有 DB 由迁移脚本置 `is_active=False`（保留行以维持 role_menus 历史一致性）。两条路由本身在 `AppRoutes.tsx` 保留，dashboard 加 `<Navigate>` redirect 到 quality。

### 7.2 架构对齐：让"辅助决策"主线在 IA 中显性化
本次去重不止是"整理相似项"，而是从平台目标（**基于本体的辅助决策平台**，ADR-073/ADR-076）反推 IA：
- 四步法本质是本体生命周期（建 TBox/ABox → 见 → 演 → 用），**决策价值兑现在"演本体 + 用本体"**。
- 原 IA 把「决策智能」压在演本体末位（sort 10）、把 OODA 调度台错名为"智能体对话"，导致决策主线被埋没。
- 本次将「决策智能」`/decisions` **提升到演本体首位**，并把「智能体调度」正名，使"观察→判断→决策→行动"的闭环在菜单上一眼可循；「问答检索」「服务化目录」「MCP 工具集」聚合到用本体，让"本体能力如何被消费以支撑决策"成为显性路径。

### 7.3 落地清单（全部完成）
- [x] `seed_four_steps.py` 重写为目标树（57 项，code 全稳定）
- [x] `migrations/iter7_dedup.py` + `migrations/__init__.py`（幂等，按 code 就地 UPDATE + 软删）
- [x] `test_menu_seed_four_steps.py` 更新（25 用例）+ `test_menu_migration_iter7.py` 新增（6 用例）→ 离线 31 passed
- [x] `AppRoutes.tsx`：`/semantic-admin/dashboard` → `/semantic-admin/quality` redirect（并移除未用的 DashboardPage import）
- [x] i18n `menu-names`（zh-CN / en-US / ja-JP 各新增 19 键）
- [x] 文档同步：本文件、`MENU_REFACTOR_PLAN.md` §6A.3 Iter 7、`ARCHITECTURE_FOUR_STEPS.md` §7 菜单树
- [ ] **既有环境需手动执行迁移**：`python -m odap.biz.platform.menu_config.migrations.iter7_dedup`（未接入自动启动，避免未经确认的启动期副作用 — AGENTS 规则 14）

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v0.1 | 2026-10-01 | 初稿：9 处相似项诊断 + 逐项建议 + 目标菜单树 + 实现约束 + 7 个待确认问题 |
| v0.2 | 2026-10-01 | 逐项读页面源码核实，7 个开放问题降级为证据结论（新增 §0.1）；确认 2 处错名(QA管理/智能体对话)、1 处真重复(双仪表盘)、1 处伪菜单(iframe-viewer)、2 处非重复(设计器/数据接入)；更新 §2/§3/§6，仅剩 3 项产品/成本决策待拍板 |
| v1.0 | 2026-10-02 | 已落地：种子重写(55→57) + 迁移脚本 + 测试(31 passed) + redirect + i18n + 文档同步；§6.2 三项决策按建议拍板；新增 §7 落地纪要（C9 暂缓、双轨移除、决策主线显性化的架构对齐） |
