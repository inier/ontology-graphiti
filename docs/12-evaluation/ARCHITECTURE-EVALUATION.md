---
id: odap.l12.architecture-evaluation
status: authoritative
owner: pm
version: ''
layer: L12
concern: evaluation-architecture
lifecycle: frozen
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
governance_reason: 架构评估唯一权威，ADR-091~098 的诊断来源
---

# ODAP 架构评估报告（Architecture Evaluation）

> 版本：v1.0 | 日期：2026-10-17 | 作者：首席架构师
> 评估基线：仓库 `C:/Users/changan/WorkBuddy/Worktrees/ontology-graphiti/feat-semantic-gap-drift-02c5070c`
> 评估方法：静态代码勘验（Grep/Read/行数统计）+ 依赖边静态核验（对照 `apps/api/pyproject.toml` 的 import-linter 契约）+ 文档扫描
> 证据纪律：所有结论标注 `文件:行`。核实不了的项显式标注「未验证」。本报告不使用 emoji。

---

## 0. 结论摘要

| 维度 | 结论 | 严重级别 |
|------|------|----------|
| 文档真相源 | 无单一真相源，11 篇 `ARCHITECTURE_*.md` 相互覆盖无 superseded 标记；ADR 存在重号与跨目录编号冲突 | 高 |
| 编号体系 | `docs/07-adr/` 已存在 ADR-001~090（非任务书所述 001-008）；ADR-061 一号两文；`docs/02-architecture/reports/ADR-065_BULKHEAD_AUDIT.md` 与 `docs/07-adr/ADR-065_*.md` 撞号 | 高 |
| 图谱渲染栈 | 7 套并存（cytoscape / g6 / sigma / xyflow / ant-design-graphs / graphology / echarts）；`@ant-design/graphs` 已安装但零引用 | 高 |
| 重复路由 | `/semantic-admin/pipeline` 与 `/semantic-admin/pipeline-runs` 同指一页（真重复）；`/policies` 已为 redirect（非真重复） | 中 |
| 主题系统 | 无分层 Design Token 体系；`violet` 调色板产出紫→品红渐变，命中 P0-2 硬违规 | 高（P0） |
| 伪实现 | 图谱生成/文件上传的 Celery 任务为 `time.sleep` + 硬编码返回值；存在静默 except 且日志格式化缺陷 | 高 |
| 层级依赖 | `biz→web` 反向依赖已清零；`infra→biz` 仍有 10 条直接边（有棘轮契约守护，属已登记技术债） | 中 |
| 文件组织 | 后端 219 / 1414 个 py 文件超 300 行；前端 88 个 ts/tsx 超 300 行；入口文件超「只装配」上限 | 高 |

**门禁判定：Fail（不通过）**。存在 P0 硬违规（紫→品红渐变）与伪实现，须先收敛方进入 Phase 2。

---

## 1. 七类问题的代码实证复核

### 1.1 文档冗余无真相源 — 严重级别：高

**事实核验**

- `docs/02-architecture/` 下 `ARCHITECTURE_*.md` 共 **11 篇**（任务书所述 10 篇，实测 11 篇，多出 `ARCHITECTURE_TARGET_PLAN.md`）：
  `ARCHITECTURE.md`(61730B)、`ARCHITECTURE_ANALYSIS_REPORT.md`、`ARCHITECTURE_BIZ.md`(82740B)、`ARCHITECTURE_EVOLVE.md`、`ARCHITECTURE_FOUR_STEPS.md`、`ARCHITECTURE_FULL_CHAIN.md`、`ARCHITECTURE_INFRA.md`、`ARCHITECTURE_OPS.md`、`ARCHITECTURE_TARGET_PLAN.md`、`ARCHITECTURE_TOOLS.md`、`ARCHITECTURE_WEB.md`。
- 另有 5 篇评审报告：`DEEP_REVIEW_REPORT_20260505.md`、`REVIEW_REPORT_20260505.md`、`SCALABLE_ARCHITECTURE_2026.md`、`SCALABLE_ARCHITECTURE_OVERVIEW.md`、`README.md`。
- `docs/` 下 md 共 **259 篇**（任务书所述 271 篇，实测 259 篇；差异可能因统计口径含 `11-archive` 与否，标「口径待核」）。
- superseded/deprecated 标记扫描：仅 3 个文件命中（`docs/02-architecture/reports/ANOMALY_REPORT.md`、`ARCHITECTURE_REVIEW_20260423.md`、`RESTRUCTURE_PLAN.md`），**11 篇主架构文档零 superseded 标记**。
- `docs/DOCUMENT_BASELINE_v1.0.0.md`（内容标题实为 v1.1.0，`DOCUMENT_BASELINE_v1.0.0.md:1`）自述「ADR 文档数 54（ADR-001 到 ADR-054）」，但 `docs/07-adr/` 实际已到 ADR-090 —— **基线文档本身已失真**。

**判定**：真相源缺失成立。`docs/DOCUMENT_BASELINE_v1.0.0.md` 文件名与内部版本号不一致（v1.0.0 vs v1.1.0），且其 ADR 计数落后 36 个编号，证明「基线漂移」已发生。

### 1.2 编号体系冲突 — 严重级别：高

- `docs/02-architecture/reports/ADR-065_BULKHEAD_AUDIT.md`（8869B）与 `docs/07-adr/ADR-065_microservice_extraction_playbook.md` 共用 `ADR-065`。
- `docs/07-adr/` 内部重号：`ADR-061-semantic-admin-suite-architecture.md` 与 `ADR-061_skill_plugin_packaging.md` 共用 `ADR-061`。
- `docs/07-adr/` 缺失编号（001~090 非连续，如 034/035/087 未见文件），说明编号曾跳号或删除，破坏「编号即寻址」。
- **任务书认知修正**：任务书要求「ADR-009 起顺序编号，避免与现有 001-008 冲突」。实测 `ADR-009`~`ADR-090` **均已存在**，此指令与实际仓库不符。经项目总监更正确认，本轮新 ADR 自 `ADR-091` 起编号，实际使用区间为 **ADR-091 ~ ADR-098（共 8 条）**，文件名统一为 `ADR-0XX_<kebab-case-主题>.md`；不覆盖、不重命名现有 89 个 ADR。编号治理（ADR-061 重号、缺 087、跨目录 ADR-065 撞号）建议归 PM 的 F3 范围处理，详见 `docs/decisions/OPEN-DECISIONS.md`。

**判定**：编号体系冲突成立，且任务书基线需修正。

### 1.3 图谱/图表渲染栈 7 套并存 — 严重级别：高

`apps/web/package.json` 实际安装（版本为实际锁定值）：

| 库 | package.json 版本 | src 引用文件数 | 备注 |
|----|-------------------|----------------|------|
| `cytoscape` (+cose-bilkent/cxtmenu/dagre/navigator/panzoom/popper) | `^3.34.0` | 4 | 局部图/层级 DAG |
| `@antv/g6` | `^5.1.0` | 1 | `decision/components/DecisionChainGraph.tsx` |
| `sigma` + `@react-sigma/core` + `@react-sigma/minimap` | `^3.0.3` / `^5.0.6` | 3~7 | 全局图谱浏览 |
| `@xyflow/react` | `^12.10.2` | 3 | `ontology/components/blueprint/*` |
| `@ant-design/graphs` | `^2.1.1` | **0** | 已安装零引用 |
| `graphology` (+8 个 graphology-* 包) | `^0.26.0` | 5 | 图数据结构/算法 |
| `echarts` | `^6.0.0` | 10 | 统计图表 |

**已知隐患复核（成立）**：
- `apps/web/src/modules/shared/modules/graph/hooks/useSigmaGraph.ts:197` 直接 `const sigma = new Sigma(g, container, {...})` 实例化并 `sigma.kill()`（:301）手动销毁；`apps/web/src/modules/shared/modules/graph/components/GraphCanvas.tsx:20-21,331-348` 经 `GraphView` 暴露 `sigmaRef/graphRef` 给 Minimap 使用。`@react-sigma/core` 虽在 `package.json:25` 安装且 `MinimapPanel.tsx` 引用，但核心生命周期未走 `SigmaProvider`/`useSigma` 上下文，**上下文管理与实例实例化割裂**。
- `GraphView.tsx:212-217` 用 `engine` 分支在 sigma / cytoscape 间切换，两套引擎 API 面（`exportPng`/`selectNode` 仅 cytoscape 有，`highlightPath`/`applyCommunityColoring` 仅 sigma 有，见 `GraphView.tsx:26-35`）**不对称**，构成跨引擎能力缺口。
- `graphAlgo.ts` 的社区发现返回结构在注释中被记录为已修 bug（`useSigmaGraph.ts:170-171`「P0-C3 fix: communities 类型已从 Map 改为 plain object」），说明该栈曾有运行时缺陷且有补丁留痕。

### 1.4 重复路由 — 严重级别：中

`apps/web/src/AppRoutes.tsx` 实测：

- **真重复**：`AppRoutes.tsx:125` `/semantic-admin/pipeline` → `PipelineRunsPage`；`:126` `/semantic-admin/pipeline-runs` → `PipelineRunsPage`。两路由同指一页，无 redirect 关系。
- **非真重复（任务书描述需修正）**：`AppRoutes.tsx:111` `/policy-editor` → `PolicyPage`；`:112` `/policies` → `<Navigate to="/policy-editor" replace />`。`/policies` 已是**归一化 redirect**，不再是双入口。
- 另有大量归一化 redirect 属健康实践（`:74 /ontology/graph`、`:75 /ontology`、`:84 /business/extraction`、`:98 /simulator`、`:99 /simulation/deduction`、`:107 /workspace`、`:130 /semantic-admin/dashboard`、`:141 /admin`）。
- 路由总数 79 条（`Route path` 计数），其中 redirect 12 条。

**判定**：真重复 1 处（`/semantic-admin/pipeline` 与 `/pipeline-runs`）；`/policies` 一项为任务书误判，已纠正。

### 1.5 P0 违规实锤（紫→品红渐变）— 严重级别：P0

`apps/web/src/modules/shared/styles/colorThemeUtils.ts`：

- `:69-84` 定义 `violet` 调色板：`primary['600'] = '#7C3AED'`（`:73`）、`accent['500'] = '#D946EF'`（`:78`）。
- `:142-144` 用 `--odap-gradient-brand` 生成 `linear-gradient(135deg, ${p('600')} 0%, ${accent['500']} 100%)`。
- 代入 violet 调色板即得 **`linear-gradient(135deg, #7C3AED 0%, #D946EF 100%)`**（紫→品红），**逐字命中 P0-2**。
- `:145-147` `--odap-gradient-brand-hover` 代入为 `#6D28D9`→`#C026D3`，同为紫→品红族。
- 同一文件 `:34,50,66,82,98` 还定义了 5 个 sidebar 的深色渐变（非违规），但 **primary/accent 组合生成品牌渐变**这一模式是全调色板级的，`indigo`（`#4F46E5`→`#8B5CF6`，`:25,31`）亦属紫系。

**主题系统缺 Design Token 实证**：
- `colorThemeUtils.ts:12-18` 的 `ColorPalette` 接口只有 `primary/accent/glowRgba/sidebar/logoAccent` 五组，**无 primitive→semantic→component 分层**，无 spacing/radius/shadow/typography token。
- `:119-164` `applyColorTheme` 直接在 `<html>` 上写行内 CSS 变量，无 token 源文件，无 `design-tokens.json`。
- 全项目硬编码颜色（排除 `#fff`/`#000`）在 ts/tsx 中高达 **1044 处**；`GraphCanvas.tsx:379,386,404,411,441` 等直接硬编码 `#1677ff`/`#52c41a`/`#FF6B6B`/`#4ECDC4`。

**判定**：P0-2 命中成立（硬实锤）；Design Token 体系缺失成立。

**P0-2 同类违规补充（设计侧 Phase 1 定位，来源 `docs/04-ui/UIUX-DESIGN-v2.md` §7.4）**：

| 文件 | 行 | 违规 |
|------|-----|------|
| `apps/web/src/modules/shared/styles/global.css` | L79-80 | `--odap-gradient-brand: linear-gradient(135deg, #4F46E5 0%, #8B5CF6 100%)`（跨色相） |
| `apps/web/src/modules/shared/styles/global.css` | L441-447 | `.ant-btn-primary` 使用跨色相渐变 + hover 叠加 glow（AI 模板套路） |
| `apps/web/src/modules/shared/styles/global.css` | L125 | 过冲缓动（spring/overshoot） |
| `apps/web/src/modules/shared/styles/global.css` | L375 / L649 | `border-left` 侧条纹 |
| `apps/web/src/modules/shared/styles/global.css` | L3/L7/L14-23/L113/L608 等 | 裸色值 / 字体与设计系统不一致 |
| `apps/web/src/modules/shared/styles/colorThemeUtils.ts` | L142-147 | 跨色相渐变生成 |

> 以上清单由设计侧维护于 `UIUX-DESIGN-v2.md` §7.4（含动作），本轮纳入 ADR-093 与架构 v2 §10 的技术债清理项。

### 1.6 疑似伪实现复核 — 严重级别：高（伪实现实锤）

| 历史报告自述（2026-04-20） | 代码实测结论 | 证据 |
|---|---|---|
| 文件上传后端缺处理逻辑 | **成立（伪实现）** | `apps/api/odap/tasks.py:134-172` `process_file_upload_task`：`:139 time.sleep(3)`（注释「模拟处理时间」），仅解析 JSON/CSV/TXT 返回统计，**不落库、不进图谱** |
| 图谱生成「异步任务」实为同步返回 task_id | **部分成立 + 更严重（伪实现）** | `frontend_compat/api/ontology_routes.py:148-182` 确为 `generate_graph_task.delay(...)` 真异步派发；但被派发的 `tasks.py:108-131` 任务是 `:112 time.sleep(10)`（注释「模拟处理时间」）+ `:119-120` 硬编码 `entities_generated: 100, relations_generated: 150`（注释「模拟生成结果」）—— **异步外壳为真、内核为假** |
| 角色切换 UI 未落地 | **不成立（已修复）** | `apps/web/src/modules/shared/stores/authStore.ts:157` `setItem('currentRoleId', roleId)`、`:167` 读取；`authStore.test.ts:319-331` 有用例覆盖 |

**附加发现（伪实现治理缺口）**：
- `tasks.py:76`、`:126`、`:168` 三处 `logger.warning("silent except caught in {exc} (line 75)")` —— ① 静默 except（吞异常仅 warning）；② **字符串缺 `f` 前缀**，`{exc}` 不会被插值，日志恒输出字面量，属「沉默逻辑错误」+「日志失效」双重缺陷。
- `tasks.py:14-15,107-108,134-135` 三个 `@celery_app.task` 均未做幂等键与重试语义，`process_ingest_task` 无幂等保护。

**判定**：伪实现成立（图谱生成、文件上传两处），须在 Phase 2 前重做或明确降级口径。

### 1.7 `frontend_compat` 兼容层 — 严重级别：中

- 路径修正：非 `apps/api/odap/biz/frontend_compat/`（任务书所述，系 2026-04 报告时的旧路径），实际在 **`apps/api/odap/biz/integration/frontend_compat/`**。
- 规模：`api/routes.py`(17)、`_deps.py`(169)、`agent_routes.py`(235)、`ontology_routes.py`(433)、`simulation_routes.py`(114)，合计 **968 行**。
- `routes.py:3-4` 自述「仅保留真正做跨服务聚合的端点，1:1 重复原生服务层的端点已删除」—— 说明兼容层已做过一轮收敛，但仍在承担 `/graph/generate`、`/graph/progress/{task_id}`（`ontology_routes.py:148,203`）等**已被证明为伪实现**的端点。
- 该层挂在 `biz/integration` 下，属业务层内，向下依赖 infra、向上不依赖 web，**层级方向正确**；但其存在意义是「迁就前端历史调用路径」，是典型的过渡层技术债。

**判定**：技术债成立，需收敛路径（见 §4）。

---

## 2. 分层与依赖方向审计

### 2.1 依赖方向（对照 `apps/api/pyproject.toml` import-linter 契约）

仓库已有 4 条架构适应度契约（`apps/api/pyproject.toml:109-291`），这是本项目最扎实的治理资产，直接引用：

| 契约 | 目标边界 | 当前状态 | 证据 |
|------|----------|----------|------|
| C1 | `common` 为叶子层（不得依赖 biz/infra/web） | **完全严格、零 ignore** | `pyproject.toml:121-125` |
| C2 | `web` 为顶层（biz/infra 不得依赖 web） | **完全严格、零 ignore** | `pyproject.toml:146-150` |
| C3 | ontology 内部只能经 `public.py`/`public_routers.py` 门面访问 | **完全严格、零 ignore** | `pyproject.toml:176-220` |
| C4 | `infra` 为 biz 下层（infra 不得依赖 biz） | **棘轮：10 条存量 ignore（债账）** | `pyproject.toml:265-291` |

**独立核验结果**（不用 import-linter，直接 grep 交叉验证）：

- `biz → web` 反向依赖：**0 条**（`grep -rn "odap\.web" biz/` → 0 命中）。**C2 成立，方向正确。**
- `biz → infra` 正向依赖：**419 条**（合理，向下依赖）。
- `infra → biz` 直接反向依赖：**23 处命中**，其中多数为函数内惰性 import 或注释；契约登记的存量直接边为 **10 条**（`pyproject.toml:271-291`），与 grep 一致（差异为注释行与惰性/间接边）。
- `infra → biz` **模块级（顶层）** 直接边：`infra/resilience/fault_tolerance.py:17` `from odap.biz.core.agent.swarm_orchestrator import AgentState` —— 这是**非惰性**的顶层反向依赖，风险最高（导入即触发层间循环），已在契约 `:279` 登记。
- 残留结构性隐患：`odap.tools`（领域 Skill 层，独立顶级包）**间接**打通 `infra → tools → biz`，契约 `:228-235` 明确「tools 层的间接可达性是独立技术债，留待后续 tools 契约评估」。**即：第 5 条契约（tools 边界）缺失**。

**分层审计结论**：

| 检查项 | 结论 | 证据 |
|--------|------|------|
| 依赖只向下（biz 不向上） | 通过 | C2 严格；`grep odap.web biz/`=0 |
| 依赖只向下（infra 不向上） | **部分未通过** | 10 条 `infra→biz` 直接边存量（`pyproject.toml:271-291`） |
| 无循环依赖 | **未验证** | 未跑 `import-linter`/`grimp`（本环境无依赖服务，标「未验证」）；仅静态确认无 `biz→web` 环 |
| 跨域不直连数据层 | **存在例外** | `infra/storage/scenario_store.py:143` 经包根 `OntologyVersionManager` 取数（契约自注「稍劣」）；`infra/queue/tasks.py:72,143,169` 直取 `he_adapter`/`ontology_mapper` |
| `tools` 层边界 | **契约缺失** | 无 C5 契约，`infra→tools→biz` 可达性未治理 |

**层级设计合理性**：`common(叶) ← infra ← biz ← web(顶)` 四层清晰，且 `web/router_registry.py`(494 行) 承担路由中心化装配，方向设计正确。问题不在「层设计错」，而在「存量越界边未烧完」+「tools 层未纳管」。

### 2.2 入口与文件组织（对照 `references/01-standards/code-organization.md`）

规范硬规则：入口只装配、单文件 ≤300 行、单一职责、按资源分包。

| 文件 | 行数 | 规范上限 | 判定 |
|------|------|----------|------|
| `apps/api/main.py` | 331 | 入口 <100 | **超限** |
| `apps/api/odap/web/app.py` | 414 | 入口 <100 | **超限** |
| `apps/api/odap/web/router_registry.py` | 494 | 装配类 <300 | **超限** |

超 300 行文件统计：

- 后端：**219 / 1414** 个 py 文件超限（15.5%）。头部：`biz/core/ontology/design/ingestion_split/ingestion.py` **4469 行**、`biz/data/qa/qa_engine.py` **2979 行**、`biz/semantic_admin/candidate_store/storage/sqlite_candidate_storage.py` **2091 行**、`infra/opa/opa_service.py` **1368 行**。
- 前端：**88** 个 ts/tsx 超限。头部：`modules/shared/services/api.ts` **2329 行**（单体 API 客户端）、`modules/knowledge/pages/KnowledgeBase.tsx` 1772、`modules/simulation/pages/SimulationPage.tsx` 1749。

**判定**：文件组织硬规则**大面积不合格**。`ingestion.py` 单文件 4469 行（上限 300 的 15 倍）是最严重结构烂账；`main.py`/`app.py` 入口含业务逻辑需核（行数已超「只装配」上限，具体业务下沉情况见 Phase 2 拆分计划）。

---

## 3. 耦合度与可组合性评估（须解耦的边界）

| 边界 | 耦合类型 | 风险 | 解耦必要性 |
|------|----------|------|-----------|
| `frontend_compat` 兼容层 | 前端历史路径 ↔ 后端业务层 | 过渡层常驻、承接伪实现端点 | 高（须收敛映射后下线） |
| 7 套图谱/图表栈 | 前端渲染层 | 包体膨胀、能力不对称、维护成本线性增长 | 高（须锁唯一栈） |
| TBox(SQLite) ↔ ABox(Neo4j) | 数据层双存储 | 无跨库事务，只能最终一致 | 高（须定一致性口径） |
| `infra → biz` 10 条直接边 | 层间反向 | 导入期循环、启动顺序脆弱 | 中（已登记棘轮，分批烧账） |
| `tools` 层未纳管 | 跨层间接可达 | `infra→tools→biz` 隐性耦合 | 中（须补 C5 契约） |
| `api.ts` 2329 行单体 | 前端服务层 | 单点爆炸半径，任何接口改动牵全身 | 高（按域拆分） |
| `ingestion.py` 4469 行 | 后端业务层 | 单文件爆炸半径 | 高（按子流程拆包） |
| `colorThemeUtils` 无 token 层 | 前端样式 | 颜色硬编码 1044 处，主题冲突 | 高（须建 token 体系） |

**可组合性结论**：后端已具备较好的门面化基础（`ontology.public`/`public_routers` 门面 + provider 注册表 `infra/providers.py` 依赖倒置），组合根装配模式（`biz/providers_bootstrap.py`）是正确的可组合性支点。前端则相反——渲染栈与 API 客户端高度单体化，**可组合性最弱**。

---

## 4. 收敛方案与迁移映射

> 用户已授权「合并/下线重复路由与模块」，以下为落地映射、影响面与回滚策略。

### 4.1 图谱渲染栈收敛（详见 ADR-091）

- **锁定唯一栈**：`sigma` + `@react-sigma/core`（全局浏览/关系图）+ `graphology`（图数据结构与布局算法）+ `@xyflow/react`（仅编辑态蓝图/流程编排，语义不同保留）+ `echarts`（仅统计图表，非图拓扑）。
- **下线**：`@ant-design/graphs`（零引用，直接移除依赖）。
- **逐步替换**：`@antv/g6`（仅 `DecisionChainGraph.tsx` 一处）→ 迁 `@xyflow/react`；`cytoscape`（4 文件，局部 DAG）→ 评估迁 `@xyflow/react` 或保留为唯一例外（见 OPEN-DECISIONS 第 4 条）。
- **迁移映射表**：

| 现组件 | 现栈 | 目标栈 | 影响面 |
|--------|------|--------|--------|
| `DecisionChainGraph.tsx` | `@antv/g6` | `@xyflow/react` | 决策链可视化 1 处 |
| `blueprint/*`（BlueprintDesigner/Node/Edge） | `@xyflow/react` | 保持 | 无 |
| `shared/modules/graph/*`（GraphCanvas/GraphView/useSigmaGraph） | sigma+graphology | 保持并统一为唯一浏览栈 | 全部图谱浏览页面 |
| `HierarchyGraph.tsx`／`useCytoscapeGraph.ts` | cytoscape | 评估迁 xyflow 或保留例外 | 层级图 |
| 全项目 | `@ant-design/graphs` | 移除依赖 | 无（零引用） |

- **回滚策略**：替换按「组件 + 开关」双写，旧栈文件保留一个 release，通过 Feature Flag（`feature_flags` 表，见架构 v2 §8）灰度；异常则翻开关回退。

### 4.2 路由合并（详见 ADR 与架构 v2 §7）

| 被合并/下线 | 迁移映射 | 影响面 | 回滚策略 |
|---|---|---|---|
| `/semantic-admin/pipeline` | → 归一为 `/semantic-admin/pipeline-runs`（旧路径保留 `<Navigate replace>`） | 菜单 config、外链、书签 | 恢复一条 `<Route>` 即可 |
| `/policies` | 已归一（`/policies` redirect `/policy-editor`） | 无额外动作 | 已具备 |
| `@ant-design/graphs` 依赖 | 移除 `package.json` 依赖项 | lockfile、bundle | `pnpm add` 还原 |

### 4.3 `frontend_compat` 收敛（详见 ADR-098）

- **目标**：兼容层端点全部 1:1 映射到原生 `/api/v1/*`，前端改指原生路由后下线兼容层。
- **迁移映射**：须先产出「兼容层端点 → 原生端点」映射表（Phase 2 由前后端共同确认）。已知待处理：`/graph/generate`、`/graph/progress/{task_id}`（当前内核为伪实现，须先重做内核）。
- **影响面**：`biz/integration/frontend_compat/` 968 行 + 前端调用点。
- **回滚策略**：兼容层保留到观测期零调用后再删；删除前打 tag。

### 4.4 文档真相源与溯源（详见 ADR-097）

- **收敛**：`docs/02-architecture/` 11 篇降为 1 篇 `ARCHITECTURE-v2.md`（本文架构设计）+ 归档其余 10 篇加 `status: superseded` front-matter。
- **溯源机制**（可机械校验）：文档头部强制 front-matter（`id/status/superseded_by/owner/last_verified`）；复用既有 `scripts/check_dangling_doc_links.py` 扩展为「文档 id 图 + 悬空引用 + 孤立文档」三项校验，进 CI 门禁。详见架构 v2 §5 与 ADR-097。

---

## 5. 技术债与风险清单（按严重级别）

| # | 问题 | 级别 | 证据 |
|---|------|------|------|
| 1 | violet 调色板产出紫→品红渐变（P0-2） | P0 | `colorThemeUtils.ts:73,78,142-144` |
| 2 | 图谱生成任务伪实现（硬编码 100/150） | 高 | `tasks.py:108-131` |
| 3 | 文件上传任务伪实现（不落库） | 高 | `tasks.py:134-172` |
| 4 | 静默 except + 日志格式化缺陷（`{exc}` 未插值） | 高 | `tasks.py:76,126,168` |
| 5 | 无 Design Token 体系，硬编码颜色 1044 处 | 高 | `colorThemeUtils.ts:12-18`；全项目 grep |
| 6 | 11 篇架构文档无真相源/无 superseded | 高 | `docs/02-architecture/ARCHITECTURE_*.md` |
| 7 | ADR 重号与跨目录撞号 | 高 | `ADR-061` 两文；`reports/ADR-065_BULKHEAD_AUDIT.md` |
| 8 | 7 套渲染栈并存，`@ant-design/graphs` 零引用 | 高 | `package.json:16-62` |
| 9 | 单文件超 300 行：后端 219、前端 88 | 高 | `ingestion.py` 4469；`api.ts` 2329 |
| 10 | 入口文件超「只装配」上限 | 中 | `main.py` 331；`web/app.py` 414 |
| 11 | `infra→biz` 10 条直接边 + `fault_tolerance.py:17` 顶层反向依赖 | 中 | `pyproject.toml:271-291` |
| 12 | `tools` 层无边界契约 | 中 | `pyproject.toml:228-235` 自注 |
| 13 | 真重复路由 `/semantic-admin/pipeline` | 中 | `AppRoutes.tsx:125-126` |
| 14 | LLM Wiki 模块完全缺失（须首建） | 中 | `grep -rl "llm.wiki\|llm_wiki"` = 0 命中 |
| 15 | 前端 tsx 内 55 文件含 emoji 作图标 | 中 | emoji 扫描 |

---

## 6. 门禁判定

**verdict: fail**

不通过理由（任一即不通过）：
1. P0-2 硬违规实锤未消除（`colorThemeUtils.ts:73,78,142-144`）。
2. 伪实现实锤存在（`tasks.py:108-172`），违反「不接受伪实现」铁律。
3. 文档无真相源 + ADR 重号，违反「溯源须可机械校验」。

**通过 Phase 2 的前置条件**：
1. 按 ADR-092（Token 分层）重建调色板，消除紫→品红渐变。
2. 重做 `generate_graph_task` / `process_file_upload_task` 内核为真实实现（或明确降级为「仅校验不入库」并在契约中标注）。
3. 按 ADR-097 建立文档 front-matter 真相源 + CI 校验。

---

## 附录 A：核实不了/未验证项

- 「无循环依赖」：未运行 `uv run lint-imports`（环境无 grimp 运行时依赖），仅静态确认无 `biz→web` 环。标 **未验证**。
- `docs/` md 总数 259 vs 任务书 271：统计口径差异（是否含 `11-archive`/`.trae`），标 **口径待核**。
- `main.py`/`app.py` 是否夹带业务逻辑：行数超限已确认，但「是否只装配」需逐行读，Phase 2 拆分计划中处理。

## 附录 B：证据索引（文件:行）

- `apps/web/src/modules/shared/styles/colorThemeUtils.ts:69-84,142-147`
- `apps/web/src/AppRoutes.tsx:111-112,125-126`
- `apps/web/src/modules/shared/modules/graph/hooks/useSigmaGraph.ts:197,301`
- `apps/web/src/modules/shared/modules/graph/components/GraphView.tsx:26-35,212-217`
- `apps/api/odap/tasks.py:14-15,76,107-172`
- `apps/api/odap/biz/integration/frontend_compat/api/ontology_routes.py:148-182,203-237`
- `apps/api/odap/biz/integration/frontend_compat/api/routes.py:3-4`
- `apps/api/pyproject.toml:109-291`
- `apps/api/odap/infra/resilience/fault_tolerance.py:17`
- `apps/api/odap/infra/storage/scenario_store.py:143`
- `docs/02-architecture/reports/ADR-065_BULKHEAD_AUDIT.md`
- `docs/07-adr/ADR-061-semantic-admin-suite-architecture.md` / `ADR-061_skill_plugin_packaging.md`
- `docs/DOCUMENT_BASELINE_v1.0.0.md:1,19-21`
- `apps/web/package.json:16-62`
