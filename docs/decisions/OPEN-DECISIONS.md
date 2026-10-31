---
id: odap.l13.open-decisions
status: authoritative
owner: architect
version: ''
layer: L13
concern: open-decisions
lifecycle: living
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
governance_reason: 悬而未决项唯一登记册
---

# 悬而未决登记册（Open Decisions Parking Lot）

> 规范依据：`references/01-standards/open-decisions-register.md`
> 纪律：只追加（append-only）、就地关闭（resolve-in-place）。新条目追加到文件末尾，绝不重写或删除已有条目。
> 类别固定三种 slug：`waiting-on-external-condition` | `design-decision-to-evaluate` | `existing-design-boundary`
> 开工复现：每个 Phase 开始时先扫描本文件，把仍为 `OPEN` 的条目复现到工作上下文最前面，逐条判断当前步骤能否就地关闭。

---

## RESOLVED — design-decision-to-evaluate — ADR 顺序编号基线冲突（ADR-009~090 已存在）

- **Date**: 2026-10-17
- **Source**: Phase 1 任务书「任务 C」；本轮架构勘验；项目总监更正指令
- **Open item**: 任务书要求新 ADR 从 `ADR-009` 起顺序编号，但仓库 `docs/07-adr/` 实际已存在 `ADR-001` ~ `ADR-090`。
- **Related constraints**: `docs/07-adr/README.md` 索引一致性；ADR 编号不可重用。
- **Current leaning**: 自 `ADR-091` 起编号。
- **Blocked by**: none yet
- **Resolves when**: 项目总监对编号基线给出书面确认。
- **Resolution**: 项目总监 2026-10-17 更正确认：新 ADR 必须自 `ADR-091` 起，不覆盖现有 89 个文件，文件名格式 `ADR-0XX_<kebab-case-主题>.md`。本轮已按此落地 **ADR-091 ~ ADR-098（8 条）**，文件名统一为下划线格式；编号治理（061 重号/缺 087/跨目录 065 撞号）归 PM 的 F3 范围。

---

## OPEN — eval-saturation — 意图识别评测集已饱和（540 条 + 59 条留出集均 100%）

- **Date**: 2026-10-17
- **Source**: 第三轮意图识别达标攻坚（项目总监独立复跑 `scripts/eval_intent.py`）
- **Open item**: 主集 540 条与留出集 59 条目前**全部满分**（Acc@1 1.0000 / Slot-F1 1.0000 / Gen-Gap 0.0000）。
  满分不是问题本身，问题是**该评测集已失去区分能力**：任何 L2 层面的残余缺陷都无法再被它发现，
  后续改动只能被"是否会掉到 1.0 以下"这一条粗糙信号约束。
- **已知的具体盲区**（均有数据支撑）：
  1. `Clarify-Rate 0.2037` 恰等于干扰项占比（110/540）→ 澄清全部发生在干扰项上，
     「真实用户模糊提问该不该澄清」这条路径未被覆盖。
  2. 留出集 59 条由实现方自撰 → 1.0 是"自撰集上达标"，不等于真实口语泛化。
  3. L3 正向路径仅由 fake client 覆盖（本机 chat 模型返回 HTTP 400 Failed to load model），
     生产模型输出稳定性未验证。
- **Current leaning**: 不改现有集（改了就失去回归基线），**另建第三套"难例集"**：
  来源优先取线上真实问句与 `gap_pool` 未映射样本，人工标注后作为独立门禁；
  在难例集建立前，现有 baseline 锁定能力、禁止回退。
- **Blocked by**: 需要真实用户问句来源（线上日志或可用 chat 模型生成后人工校验）。
- **Resolves when**: 存在一套**非自撰、且当前实现不能满分**的评测集进入 CI。

---

## OPEN — doc-set-hygiene — specs/ 下 6 条 spec-kit 历史残留死链

- **Date**: 2026-10-17
- **Source**: `python scripts/check_dangling_doc_links.py --roots docs specs`
- **Open item**: 死链已从 16 条降至 6 条，剩余 6 条全部位于 `specs/`（非设计文档集）：
  `specs/001-odap-platform/tasks.md:329` 指向不存在的 `.specify/extensions/superspec/{templates/tasks-template.md, references/superpowers-bridge.md}`；
  `specs/008-semantic-retrieval-bus/tasks.md:150/169/188/208` 指向不存在的 `../../.trae/documents/008-semantic-retrieval-bus-phase2.md`。
- **Why not fixed in this round**: `specs/` 是 spec-kit 流程的**历史执行留痕**，改写等于篡改历史产物；
  且指向的 `.trae/`、`.specify/extensions/` 为 IDE/工具链目录，随工具版本变化，不宜作为长期链接目标。
- **Current leaning**: 保持 `specs/` 原样，仅在 `specs/README.md` 顶部加一句「本目录含历史死链，不做维护」；
  CI 门禁已限定 `--roots docs`，不会因这 6 条阻断构建。
- **Resolves when**: `specs/` 整体归档进 `docs/11-archive/` 时一并处理。

---

## OPEN — design-decision-to-evaluate — ADR-061 编号重复（一码两文）

- **Date**: 2026-10-17
- **Source**: 本轮架构勘验（`docs/07-adr/` 目录扫描）
- **Open item**: 存在 `ADR-061-semantic-admin-suite-architecture.md`（11570 字节）与 `ADR-061_skill_plugin_packaging.md`（3276 字节）两个文件共用 `ADR-061` 编号，违反「一个编号一条决策」。
- **Related constraints**: ADR README 索引可寻址性；决策引用不可歧义。
- **Current leaning**: 将 `ADR-061_skill_plugin_packaging.md` 重编为新的空闲号（如 `ADR-102`，本轮到 098 之后），`ADR-061` 保留给 semantic-admin-suite（内容更重）。重编不删原文，仅更新文件名与索引。
- **Blocked by**: 需确认两文的实际引用方（README、其他 ADR 的交叉引用）后再重编，避免断链。
- **Resolves when**: `grep -rn "ADR-061" docs/` 的引用全部裁定并完成重编与索引更新。

---

## OPEN — design-decision-to-evaluate — frontend_compat 兼容层下线触发条件未定

- **Date**: 2026-10-17
- **Source**: 本轮架构勘验；`docs/00-requirements/documents/前端功能实现与设计对比报告.md`（2026-04-20）
- **Open item**: `apps/api/odap/biz/integration/frontend_compat/`（968 行，4 个路由文件）是为迁就前端历史调用路径而生的过渡层。任务要求评估其技术债与收敛路径，但「何时可下线」取决于前端调用方是否全部改指原生 `/api/v1/*` 路由，当前无调用方清单。
- **Related constraints**: 不能破坏前端存量功能；必须先建立「兼容层端点 → 原生端点」映射并确认前端已迁移，才可删层。
- **Current leaning**: Phase 2 先产出兼容层端点→原生端点映射表 + 前端调用点清单，用「调用计数告警」而非直接删除的方式灰度下线。
- **Blocked by**: 需要一线前端在 Phase 2 产出「兼容层调用点清单」，且需要一轮线上观测期确认零调用。
- **Resolves when**: 兼容层所有端点在观测期内零调用，且映射表内每条都有原生端点承接。

---

## OPEN — design-decision-to-evaluate — 图谱渲染栈收敛的执行方式（一次性 vs 分批）

- **Date**: 2026-10-17
- **Source**: 本轮架构勘验；本轮 ADR-091
- **Open item**: 本轮锁定唯一图谱渲染栈（见 ADR-091），但「一次性替换全部 7 套栈相关组件」与「按模块分批替换」两种执行方式的工作量/风险不同，尚未定。
- **Related constraints**: 用户已确认「全量一次性推进」，但图谱组件涉及 cytoscape 局部操作 + sigma 全局浏览 + g6 决策链 + xyflow 蓝图四类语义不同的场景，硬并可能损失交互能力。
- **Current leaning**: 收敛口径为「拓扑浏览=sigma+graphology、编辑/流程=@xyflow/react、统计=echarts」，**cytoscape 不再保留例外**（其图算法能力由 graphology 覆盖），分批替换：导航/图标(lucide) → 决策链(g6→xyflow) → 局部图(cytoscape→sigma/xyflow)。
- **Blocked by**: 需 Phase 2 前端对 BlueprintDesigner / DecisionChainGraph / HierarchyGraph 三个场景做能力对齐评估（编辑态节点能力是否可迁到统一栈）。
- **Resolves when**: 三个场景的能力对齐结论产出，且用户确认是否接受交互能力降级。

---

## OPEN — existing-design-boundary — TBox(SQLite) 与 ABox(Neo4j) 跨库一致性仅 final 一致

- **Date**: 2026-10-17
- **Source**: `CONTEXT.md`（TBox 存 SQLite `odap_main.db`、ABox 存 Neo4j）；本轮架构勘验
- **Open item**: 本体由 TBox（SQLite）与 ABox（Neo4j）双存储承担，两者跨库无分布式事务，Schema 变更（TBox）与实例写入（ABox）之间只能最终一致。本轮架构给出「TBox 为真相源、ABox 为投影 + 版本戳对账」的收敛口径，但未在本轮引入跨库补偿事务。
- **Related constraints**: 不允许伪实现；一致性方案必须可落地且可回滚；Neo4j 与 SQLite 无原生两阶段提交。
- **Current leaning**: 采用「TBox 变更 → 发领域事件 → ABox 投影器消费 → 版本戳对账 + 漂移扫描兜底」的最终一致方案（复用既有 `drift_scan` 模块），Phase 1 不做跨库强一致。
- **Blocked by**: 需 Phase 2 量化 ABox 投影延迟与对账窗口的可接受阈值（业务侧确认可容忍的漂移时长）。
- **Resolves when**: 业务侧给出 ABox 一致性 SLO（如「TBox 变更后 ≤ N 秒 ABox 可见」），方案据此定稿。

---

## OPEN — waiting-on-external-condition — lucide-react 图标映射表冻结（待 Phase 2 pin 版本）

- **Date**: 2026-10-17
- **Source**: `docs/07-adr/ADR-092_icon-library-lock.md`；设计侧 `docs/04-ui/UIUX-DESIGN-v2.md` §5.2 终裁裁决表
- **Open item**: 图标语义裁决（A 组 8 条 + B 组 22 项）已由设计侧终裁回签，但映射表与 codemod 尚不能冻结——`lucide-react` 尚未安装、版本未 pin；Lucide 跨版本会重命名导出（已实测 4 例：`MessageCircleQuestion`→`message-circle-question-mark`、`HelpCircle`→`CircleHelp`→`circle-question-mark`、`Layers3`→`layers`、`BookMarked`→`book-bookmark`），冻结须以 pinned 版本的导出清单为准。
- **Related constraints**: 禁止按通用印象写图标名（幻觉接口失效模式）；裁决表以「语义角色」为主键，图标名为按版本解析的候选。
- **Current leaning**: Phase 2 安装并 pin `lucide-react` 版本后，产出「版本号 + 该版本**全量导出清单快照（含 deprecated aliases）**」交设计侧核对，并配套 (i) CI 不变量脚本 `apps/web/scripts/check-lucide-icons.mjs`（白名单 / emoji / 语义角色表+minSize / 直连导入禁令 四校验）与 (ii) 项目级 Icon 包装组件（唯一设置 `strokeWidth` 的位置）。本轮已对设计侧点名的 13 个候选经 lucide.dev 核验，全部存在，无需降级。
- **Blocked by**: Phase 2 依赖安装与版本 pin（`apps/web/package.json` 新增 `lucide-react`）。描边档位子决策（`nonScalingStroke` 恒定 1.5px）已由设计侧 2026-10-17 终裁，不再阻塞。
- **Resolves when**: `lucide-react` 版本 pin 定、全量导出清单快照 + CI 不变量脚本 + Icon 包装组件就绪、经设计侧核对并回签，映射表冻结。

---

## RESOLVED — redundancy-needs-disposition — 本体模块 17 个「有实现无入口」组件已逐个判定（删除 7 / 挂载 2）

- **Date**: 2026-10-17（当日判定并执行）
- **Source**: 前端零引用扫描（`apps/web/src/modules/ontology/components/*.tsx`，排除 barrel 与测试后统计 import 方）
- **Disposition**: 17 个零引用组件全部给出结论，无一项悬置。

  **一、直接删除（5 个，含 3 个级联）—— 证据**
  | 组件 | 行数 | 删除依据 |
  |---|---|---|
  | `OntologyIngestPipeline.tsx` | 569 | 纯伪实现：`MOCK_ENTITIES` / `MOCK_RELATIONS` / `MOCK_EVENTS` + `setTimeout` 假进度，零 API 调用 |
  | `EntityTypeEditor.tsx` | 235 | 与已挂载的 `OntologyDesignerPage.ObjectTypeEditor` 能力重合（名称/显示名/密级/描述/属性增删/关系增删+基数+link_type），且按旧 `EntityType` 形状（`relations`/`primary_key`）实现，真实模型是 `ObjectTypeDefinition`（`type_id`/`links`/`ONE_TO_MANY`） |
  | `PropertyEditor.tsx`（级联） | 111 | 仅被 `EntityTypeEditor` 引用 |
  | `RelationEditor.tsx`（级联） | 102 | 仅被 `EntityTypeEditor` 引用 |
  | `TypeSafeSelect.tsx`（级联） | 40 | 仅被上述三者引用 |
  | `SemanticConfig.tsx` | 261 | 端点 `/api/semantic/synonyms`、`/api/semantic/expansion-rules` 在 `apps/api` 全仓**零实现**（断链）；同义词/术语配置的真实入口是已挂载的 `semantic-admin/TermForm`（含 `synonyms`/`near_synonyms`/`aliases`） |
  | `VersionPanel.tsx` | 255 | 与已挂载的 `VersionHistoryPanel`（设计器抽屉）+ `/versions` 页重复：同一「版本列表 + 回滚 + 对比」交互，后者走真实 `ontologyApi.schemaVersions` |

  合计删除 **1573 行**。

  **二、挂载（2 个）**
  | 组件 | 挂载点 | 为什么必须保留 |
  |---|---|---|
  | `ActionPanel.tsx` | 新路由 `/decisions/actions`（菜单「动作执行」） | 全仓唯一消费「动作提交 → OPA 裁决 → 执行 → 写回」闭环的 UI；`/semantic-admin/approvals` 是另一个关注点（语义资产审批） |
  | `DocumentImporter.tsx` | `OntologyDesignerPage` 新增「文档导入导出」Tab | 文档级导入/导出（`POST /api/ontology/model/documents`、`/{id}/export`）与抽取（`NLExtractor`/`DatabaseExtractor`）是不同职能 |

- **伴随修复的真实缺陷**（挂载后才会暴露，均已修）
  - `api.approveAction` 请求体缺必填字段 `action_record_id` → 后端 `ActionApproval` 校验 422；已补齐并注明该端点的真实语义是「批准并执行」。
  - `ActionPanel` 原有「批准/拒绝」按钮：后端 `approve_and_execute` 只对 `approved` 状态执行，且**没有人工拒绝接口**，点「拒绝」同样会触发执行；已删除这两个按钮，只保留 `approved → 执行`。
  - `ActionPanel` 提交动作时 `target_object_type` 用魔法常量 `'Unit'` 兜底；改为取 `OmsActionType.target_type`，缺失则明确报错。
  - `ActionPanel` 拉取 `listObjectTypes()` 却从未使用（死请求）；已删除。
  - `DocumentImporter` 原打 `POST /api/ontology/documents/import`（404）与 `.../{id}/export?format=owl|rdf`（404，后端 `to_palantir()` 无 format 参数）；已改真实契约并移除 OWL/RDF 虚构格式选项。
  - `documentImport.*` 命名空间键在 zh-CN/en-US/ja-JP **均不存在**（UI 会显示原始键名）；已按「中文即键」基线改为中文键并三语补齐。
- **Evidence**: `npx tsc -b --noEmit` 0 error；`npx eslint .` 0 error / 64 warning（与基线持平）；`npx vitest run` 60 files / 712 passed（新增 `ActionPanel.contract.test.tsx` 4 例、`DocumentImporter.contract.test.tsx` 6 例，含「不得出现「批准/拒绝」按钮」「不得请求 `/api/ontology/documents/import`」等负向断言）。
- **Resolves when**: ✅ 上述 7 个文件已删除，2 个已挂载并有契约测试钉住。

---

## RESOLVED — redundancy-needs-disposition — 全站零引用组件清点完成（15 个 / 3996 行：删除 8、挂载 7）

- **Date**: 2026-10-19（当日判定并执行）
- **Source**: 全站零引用扫描（`apps/web/src/modules/**`，**含 `pages/`**）。上一轮扫描（见上一节）只覆盖 `ontology/components/`，漏掉 `pages/` 与其他模块；本轮重新枚举实得 **15 个文件 / 3996 行**（该 15 个与本文件下一节仍 OPEN 的 10 个本体组件**不重叠**）。
- **判据（单一决定性标准）**：*该组件依赖的后端端点是否真实存在，且这项能力当前是否已可达。* 三项结论只有三种，不允许悬置：**冗余 → 删；能力可达但无入口 → 挂载；端点不存在且能力已被别处覆盖 → 删。**
- **Disposition**:

  **一、直接删除（8 个 / 2239 行）**
  | 文件 | 行数 | 删除依据 |
  |---|---|---|
  | `ontology/pages/UnifiedManagementPage.tsx` | 875 | 与已挂载 `OntologyDesignerPage` 的 9 页签编辑器功能重合；且按遗留 `EntityType`/`registryStore` 形状实现（真实模型是 `ObjectTypeDefinition`） |
  | `ingest/components/SimulatorConsole.tsx` | 254 | 纯假数据；真实入口是已挂载的 `pages/Simulator.tsx`（756 行） |
  | `agent/components/SkillManager.tsx` | 220 | 5 个端点里 4 个全仓无实现（`/api/skill/register`、`/discover`、`/{id}/lifecycle`、`DELETE /{id}`） |
  | `knowledge/components/QueryPanel.tsx` | 192 | `/api/query` 结构化 NL 查询与 `qa/QueryPage` 重复，唯一消费方只经由 `sharedApi` 的封装 |
  | `qa/components/SessionDrawer.tsx` | 186 | `AIChatPanel` 自带 `SessionSidebar`，同一交互重复 |
  | `qa/hooks/useSession.ts` | — | 级联死代码（仅被 `SessionDrawer` 引用） |
  | `semantic-admin/pages/CandidatesComingSoon.tsx` | 183 | "Iteration 3 再实现"占位页 + 硬编码行；真实页面是 `CandidatesPage` |
  | `semantic-admin/pages/PipelineComingSoon.tsx` | 123 | 同上；真实页面是 `PipelineRunsPage` |

  删除时同步清掉三处悬空引用：`qa/index.ts` 的 `useSession` 导出、`semantic-admin/index.ts` 的 `QualityComingSoon` 别名、`QualityDashboardPage` 里**渲染进界面的调试小字**（`P0-4 重命名落地：QualityComingSoon → QualityDashboardPage`）。

  **二、挂载（7 个组件 + 5 个页面外壳）**
  | 组件 | 挂载点 | 为什么必须保留 |
  |---|---|---|
  | `system/components/ToolRegistry.tsx` | `SkillManagement` 新增「工具注册表」Tab | 技能体系三层：技能声明做什么 / 工具是可供调用的实现 / 钩子是执行前后拦截点。缺这一层，「技能」只剩声明 |
  | `system/components/HookManager.tsx` | 同上「钩子管理」Tab | 同上；`/api/hooks` 五个端点全部真实存在 |
  | `ontology/components/ViewDesigner.tsx` | 新页 `ObjectViewsPage`（`/ontology/object-views`），1280px 弹窗承载三栏布局 | 对象视图的唯一可视化编辑器；`ObjectViewPage` 只管列表/查询/导出/权限 |
  | `audit/pages/OPAMonitorPage.tsx` | `/audit/opa` | 全仓唯一暴露 OPA 判决指标（放行/拒绝率、策略延迟）的界面 |
  | `ingest/components/BatchImporter.tsx` | `IngestPanel` 新增「批量导入」Tab | 与单条录入、文档抽取并列为三种入库方式 |
  | `agent/components/CognitionPanel.tsx` | 新页 `CognitionPage`（`/qa/cognition`） | 意图识别 / 解释链 / 角色视图三合一的唯一入口 |
  | `agent/components/SessionMemory.tsx` | 新页 `SessionMemoryPage`（`/qa/memory`），补会话选择器 | 短期 / 工作 / 长期三层记忆的唯一可视面；原组件要求手输 sessionId，实际无从获知 |

  **三、挂载即暴露的隐性缺陷（均已修，这是本轮主要收益）**
  | 组件 | 若直接上线会发生什么 |
  |---|---|
  | `ToolRegistry` | 语义检索结果被丢弃（只弹一句 toast 再全量重载），用户永远看不到「发现了什么」 |
  | `HookManager` | 表单 `hook_type` 提供 6 个后端不认的值（`event/data/validation/...`），真实枚举是 `pre_execute/post_execute/on_error/on_timeout/pre_commit/post_commit`，且后端严格校验 → **每次注册必 400** |
  | `HookManager`（**后端**） | `DELETE /api/hooks/{hook_id}` 只做存在性检查就返回成功，**从未调用 `manager.delete_hook`** —— 删除是静默空操作。已补 `HookService.delete_hook()` 并让路由在未命中时返回 404；`list_hooks` 的 `enabled` 改为从 `status` 派生 |
  | `viewApi` | `GET /api/ontology/object-types` **不存在**（真实路径带 `/oms` 前缀：`/api/ontology/oms/object-types`，且 `response_model=List[...]` 返回数组、字段名是 `property_type`）→ 设计器左侧对象类型树恒为空 |
  | `ViewDesigner` | `void t;` 把 i18n 整个关掉；且只能改、不能建（`viewId` 为必填）→ 新视图无处创建 |
  | `BatchImporter` | 打向不存在的 `/api/ingest/batch?scenario_id=...`，并把 `scenarioId` 当 `entity_type_id` 传（语义错位） |
  | `OPAMonitorPage` | 空 `catch` → 页面停在 0，与「策略从未被调用」无法区分 |
  | `CognitionPanel` | 三个页签被焊死在三个角色上（`activeKey` 由 `activeRole` 推导并反写），看解释链必须先切角色；且 `director`/`operations` 在后端 `RoleViewManager` 未登记 → 恒空 |
  | `SessionMemory` | 三处空 `catch` →「没有记忆」与「接口挂了」在界面上完全一致 |

- **新增代码约定（本轮确立）**：`react-hooks/set-state-in-effect`（`reactHooks.configs.flat.recommended` 内置，error 级）禁止在 effect 内同步写状态。既有代码里 `void (async () => { load(); })()` 的写法只是**分析器盲区**，不是正解。约定：
  1. 请求函数**只做 I/O、返回数据**，不写状态；
  2. 状态写进 effect 里的 promise 回调（`.then/.catch/.finally`），并用 `ignore` 标记丢弃过期/卸载响应 —— 顺带补上了原先缺失的竞态保护；
  3. 「加载中」优先由「已完成请求的 key ≠ 当前 key」**推导**，不要 `setLoading(true)`；仅用户点击触发的刷新可以在事件处理里同步置位。
- **Evidence**: `node scripts/check-i18n-keys.mjs` → 阻断 0 / 缺失引用 0 / 冗余点号键 0；`npx tsc -b --noEmit` 0 error；`npx eslint .` **0 error** / 61 warning（全部 `exhaustive-deps`，与基线持平）；`npx vitest run` **67 files / 746 passed**（新增 7 个契约测试文件 34 例，含「表单类型选项不得包含 `event/data/validation/...`」「新建模式不得 GET `/views/{id}`」「未选数据源不得 POST」等负向断言）；`pytest tests/unit/test_hook_system.py` **52 passed**（新增 `TestHookServiceDelete` 3 例）。
- **Resolves when**: ✅ 15 个文件全部给出结论；删除的 8 个已从工作树移除且 `tsc` 无悬空引用；挂载的 7 个均有入口、有契约测试、有真实端点。
- **遗留（不属本项）**: AntD 6 的 `List` 已标记 deprecated（`[antd: List] The List component is deprecated`），全站仍有 20+ 处使用，另立条目跟踪。

---

## RESOLVED — redundancy-needs-disposition — 本体 10 个零引用组件：已处置 4（删 3 + 挂 1）

- **Date**: 2026-10-17 登记；2026-10-19 处置
- **复核前置**: 逐文件核对 import 方后确认这 10 个**零真实消费方** —— 唯一「引用」来自
  `ontology/index.ts` 与 `ontology/components/index.ts` 的 barrel 转出。**barrel 转出不计为引用**，
  否则「零引用」永远扫不出来（本轮判据已按此修正）。
- **处置结论（4/10）**

  **一、删除（3 个）**

  | 组件 | 行数 | 删除依据（逐条核对后端后成立） |
  |---|---|---|
  | `ObjectViewList.tsx` | 403 | 与已挂载 `ObjectViewPage` 是同一份数据的两套呈现。**但先做能力保全**：其独有的「克隆 / 启停 / 删除」已并入 `ObjectViewPage` 的列表行操作（克隆走 `POST /views` 复制——后端没有 `/{id}/clone` 端点；启停 `PUT /views/{id}`；删除 `DELETE /views/{id}`）；「每视图权限计数」**不搬**——它对每个视图各发一次 `/permissions`（N+1 请求），而本页只在选中视图时查一次已够用 |
  | `ViewFieldMapping.tsx` | 811 | 与已挂载 `ViewDesigner` **六项能力一一对应**（字段/过滤/排序/行数上限/权限/测试查询）；且其过滤算子枚举 `eq/ne/gt/lt/contains/starts_with/in` 不在后端白名单（`= != > < contains`）内，挂上去过滤条件会被静默丢弃 |
  | `ActionRegistrationForm.tsx` | 513 | 见下方「契约虚构」明细；更关键的是后端**三套并存 action_type 存储**，写哪一套都会「建了在设计器看不到」——挂载等于亲手造一条新断链（已另立 OPEN 条目） |

  `ActionRegistrationForm` 的契约虚构明细（**新建必然 422**）：
  - 路径 `/api/ontology/action-types` 不存在，真实为 `/api/ontology/oms/action-types`；
  - 列表按 `{action_types: [...]}` 取值，真实 `response_model=List[ActionTypeDefinition]` 返回**数组** → 唯一性校验恒拿到空列表；
  - 报文体：`return_type` / `linked_skill_id` / `preconditions` / `tags` 后端**均无此字段**；
    `opa_policy_id` 实为 `opa_policy`；参数 `type`/`default_value` 实为 `param_type`/`default`；
    **缺**必填的 `action_type_id` 与 `target_object_type`；
  - `action.*` 下约 30 个 i18n 键在三语中**全部不存在** → 界面直接显示 `action.nameRequired` 等原文；
  - 「保存并测试」调用的 `/action-types/{id}/test` 不存在，所谓「跳转测试页」只有一行 `console.log`。

  **二、挂载（1 个）**
  | 组件 | 挂载点 | 伴随修复 |
  |---|---|---|
  | `ReasoningTracePanel.tsx` | 本体设计器新增「推理追踪」页签（页签处正好持有 `currentOntology.ontology_id`） | 全文中文硬编码零 i18n → 中文即键（25 个新键三语补齐）；`Alert message`（AntD 6 已弃用）→ `title`；`rows` 里的对象值统一转字符串，避免 object 直塞 JSX；`rule_trace` 缺省时改为**解释性空态**（否则会被误读成「没命中」）；未选本体时按钮禁用并说明原因 |

- **Evidence**: `node scripts/check-i18n-keys.mjs` → 阻断 0 / 缺失引用 0 / 冗余点号键 **0**
  （本轮新增键曾使 3 个历史点号键（`conflict.duration`、`materializedView.statDuration`、`result.resultCount`）
  成为冗余，已按既定做法合并：前两者零引用直接删，后者调用点改为 `{t('结果数')}：{total}` ——
  顺带修掉「值里没有 `{{count}}` 占位符、count 被静默丢弃」的老问题）；
  `npx tsc -b --noEmit` 0 error；`npx eslint .` 0 error / 61 warning；
  `npx vitest run` **69 files / 760 passed**（新增 `ReasoningTracePanel.contract.test.tsx` 6 例、
  `EditLockIndicator.contract.test.tsx` 5 例，`ObjectViews.contract.test.tsx` 扩到 8 例，含「克隆不得请求 `/clone`」「启停 PUT 只带 enabled」
  「删除需二次确认」等断言）。
- **Resolves when**: ✅ 10 个中 4 个已给出终局结论并有证据；余 6 个见下一条 OPEN。

---

## OPEN — redundancy-needs-disposition — 本体剩余 4 个零引用组件（2 个需按 MR 流重写，2 个待定宿主）

- **Date**: 2026-10-19
- **状态（2026-10-19 更新）**: 6 个里又处置 2 个，余 **4 个**：

  | 组件 | 行数 | 核对结果 | 状态 |
  |---|---|---|---|
  | `BranchList.tsx` | 351 | ❌ 四处硬伤：① 列表主键用 `branch_id`，真实 `BranchResponse` 主键是 **`id`**，所有行操作会打到 `/branches/undefined/...`；② 创建发 `workspace_id`，`CreateBranchRequest` **必填 `ontology_id`**、`base_version_id` 亦必填；③ `/switch`、`/archive`、`/{id}/merge` **三个端点全部不存在**；④ 列表过滤参数应为 `ontology_id` 而非 `workspace_id` | **待重写**：list/create/delete + 「发起合并请求」 |
  | `MergeDiffViewer.tsx` | 388 | ❌ 依赖 `GET /branches/{id}/diff` —— **该端点不存在**（diff 只在 `merge_engine` 内部作为 MR 冲突检测的实现存在）；`POST /branches/merge` 也不存在 | **待重写**为 MR 五步流：`POST /merge-requests` → `detect-conflicts` → `resolve` → `execute` |
  | `ProvenanceViewer.tsx` | 146 | ✅ `GET /api/extraction/provenance/{entity_id}` 存在，props 自洽；语义是**抽取溯源**（源文档/切片/抽取方法） | **待挂**：宿主必须是「有实例/抽取实体的列表」，图谱页的类型节点不适用（对 ObjectType 查抽取溯源无意义） |
  | `TemplateRecommender.tsx` | 196 | ✅ `/api/extraction/templates/recommend`、`/generate-web-search` 均存在；但 `createOntology()` 只接受 `name/description/workspace_id/scenario_id`，**没有 template 字段** | **待定宿主**：接在「新建本体」不成立（选了也不生效＝假实现），应接在 NL 提取流程里选模板 |

  **本轮已消项（2 个）**

  | 组件 | 处置 | 详情 |
  |---|---|---|
  | `EditLockIndicator.tsx` | 已挂载到设计器页头 | ⚠️ **更正上一版登记的错误结论**：此前写「零 API 调用、后端无编辑锁路由」是错的。真实情况是 **WebSocket**：`/ws/ontology/edit-lock/{ontology_id}`（`odap/web/ws/routes.py` 注册），`edit_lock_service` 落 `edit_locks.db`，服务端 30s 无心跳释放。修复：props 未导出→补 `export`（含 named export）；`editLock.editingTooltip`/`lockedByOtherTooltip` 的值**没有 `{{user}}`/`{{time}}` 占位符**，调用时传的参数被静默丢弃（ja 值还混入中文「正在編集」）→ 三语改对；设计器通过 `useAuthStore` 取 `user.id` 传入 |
  | `AISuggestionList.tsx` | 已挂载到设计器「AI 助手」抽屉的第二个页签 | 抽屉拆成「AI 对话 / AI 建议」两个关注点；接受建议等同一次写操作，`onAccept` 触发本体重载 |

- **Related constraints**: 仍适用 —— 挂载必须带契约测试（断言 URL/body），不得为「消灭零引用」而草率接线。
- **Resolves when**: 余 4 个各自落到路由/Tab，或给出归档记录（含取代证据）。

---

## OPEN — structural-defect — 后端存在三套并存的 action_type 存储（会导致「建了看不到」）

- **Date**: 2026-10-19
- **现象**: 同一个「动作类型」概念在后端有三份互不相通的实现，写进去的东西彼此不可见：

  | 存储 | 表 | 端点 | 使用者 |
  |---|---|---|---|
  | `ontology_service` | `action_type_definitions` | `/api/ontologies/{id}/action-types` | **设计器「动作类型」Tab**（唯一有 UI 的） |
  | `oms_service` | `action_types` | `/api/ontology/oms/action-types` | `ActionPanel` 的动作执行闭环 |
  | `action_service` | `action_types`（另一套 schema，含 `return_type`/`linked_skill_id`/`opa_policy_ref`） | `/api/ontology/actions` | 无人调用，但**是唯一带 `/{id}/execute` 的** |

- **影响**: 任何「注册动作类型」的新界面都必须先选边；选错就是「保存成功但列表里没有」。
  这也是 `ActionRegistrationForm` 不能挂载、只能删除的根本原因。
- **待决策**: 选哪一套作为唯一真相源。倾向 `ontology_service`（设计器已在用、有 ontology 作用域），
  但要把它缺的 `opa_policy` / `writeback_config` 字段和 `/{id}/execute` 能力从 `action_service` 迁过来。
- **Related constraints**: 收敛前**不得**再新增第 4 个动作类型 UI；也不得靠「同时写两套」来兼容。


---

## RESOLVED — i18n-convention — 确认「中文即 key」约定，清除 en-US 全部占位译文并落地 CI 不变量

- **Date**: 2026-10-17（当日判定并执行）
- **Source**: 用户澄清国际化方案；`apps/web/src/modules/*/locales/*`
- **Convention（已确认）**: **以项目原始中文为 key，其他语言是针对该中文 key 的翻译**。因此 `zh-CN` 是唯一真相源；`fallbackLng = 'zh-CN'`（`modules/shared/stores/i18nStore.ts`）使 en/ja 缺译时自然回落中文，**不需要、也不允许**用占位串去"凑齐"键集合。
- **Defect（原 OPEN 项）**: ontology/en-US 有 562 个点号键的值是 `"attributeCard arrayItems"` 这类占位串——既不是翻译，也不会回落中文，界面直接显示垃圾。
- **Fix applied**
  1. **冗余点号键合并**：131 个点号键的 zh 值恰好等于某个已存在的「中文键」→ 合并到该中文键（源码 141 处静态引用同步改写，0 处动态拼接受影响），合并后**免费获得**已有的 en/ja 译文，冗余键从 131 降到 **0**。
  2. **占位译文清零**：ontology 内 432 条点号占位译文全部删除（删除即回落中文，符合约定）。
  3. **补齐已挂载组件缺失文案**：`extraction.*`(12) / `nodeEditor.classificationOptions.*`(4) / `version.*`(2) / `common.*`(5) 共 23 个键 × 三语补齐——这些键此前在代码里被 `t()` 引用但语言包没有，界面显示原始键名（如 `extraction.preview.conflictCount`）。
  4. **修复 Mixin 空态文案**：`InheritanceGraph` 的 Mixin 列表为空时误用了「无父类型」，新增 `inheritanceGraph.noMixins`（无 Mixin / No mixins / ミックスインなし）。
  5. **CI 不变量上线**：`apps/web/scripts/check-i18n-keys.mjs` + `pnpm check:i18n`（已接入 `pnpm ci`），校验四条：① 无占位译文 ② 无幽灵键（en/ja ⊆ zh）③ 无冗余点号键（值等于既有中文键）④ 代码里 `t('x.y')` 必须能在对应模块 zh-CN 中找到，既存欠债登记在 `scripts/i18n-key-baseline.json`，**只允许减少，新增即失败**。
- **Evidence**: ontology 命名空间现状 —— zh-CN 1160 键（673 中文键 + 487 点号键）、en-US 728 键（**0 占位**、0 幽灵键）、冗余点号键 **0**；`node scripts/check-i18n-keys.mjs` exit 0；`tsc` 0 error；`vitest run` 60 files / **712 passed**。
- **Resolves when**: ✅ ontology 命名空间四条不变量全绿，且 CI 已能拦住回退。

---

## RESOLVED — quality-gap — 全站 i18n 阻断级欠债清零（1102 条违规 + 160 条引用缺失 → 0 / 0）

- **Date**: 2026-10-19（2026-10-17 登记，本次清零）
- **Source**: `pnpm check:i18n` 基线 `scripts/i18n-key-baseline.json`
- **Fix applied**
  1. **占位译文全站清零 853 条**：`shared/common` 712、`agent` 69、`ingest` 45、`simulation` 15、`ai-assistant` 7、`audit` 3、`version` 2。占位串（`"common.button.save": "common button save"`）既非译文也不回落中文，界面直接显示垃圾；删除后由 `fallbackLng='zh-CN'` 回落中文，**显示中文优于显示垃圾**。
  2. **`fallbackNS: 'common'` 上线**（`modules/shared/stores/i18nStore.ts`）：`common` 是跨模块共用词表（按钮/标签/提示），配置回退后各模块写 `t('common.label.status')` 即可解析。这一步单独消化了 **159 / 160** 条「引用缺失」，避免了把同一批文案复制进每个模块语言包。
  3. **ontology 自身去重**：删除 5 个 `common.*` 重复键（改由 fallbackNS 解析）、2 个 `extraction.*` 合并到既有中文键，冗余点号键 6 → 0。
  4. **检查脚本判据修正两处**：① 冗余点号键从 FAIL 降为 WARN（用户不可见，属维护成本；跨命名空间引用时强行合并会破坏解析）；② `t(` 正则加左断言，排除 `getByText('1.2.0')` / `i18n.t(` 这类误匹配（曾误报 1 条不存在的缺失）。
- **Evidence**: `node scripts/check-i18n-keys.mjs` → 阻断违规 **0**（基线 1102）、缺失引用 **0**（基线 160）、冗余点号键警示 **0** 处；基线文件 `violations: [] / missingKeys: []` 已重生成；`tsc -b --noEmit` 0 error；`eslint .` 0 error / 63 warning；`vitest run` 60 files / **712 passed**。
- **Resolves when**: ✅ 基线两数组均为空，且 CI 已能拦住回退（`pnpm ci` 含 `check:i18n`）。

---

## RESOLVED — quality-gap — 剩余 243 个冗余点号键全站合并（WARN 5 → 0）

- **Date**: 2026-10-19
- **Source**: `pnpm check:i18n` 警示项（承接上一条剩余部分）
- **Fix applied**: 把「点号键的值恰好等于某个既有中文键」的 243 个键全部合并到该中文键，源码静态引用同步改写 **30 文件 / 120 处**：
  | 命名空间 | 合并数 | 说明 |
  |---|---|---|
  | `shared/common` | 214 | 主体；`t('common.button.save')` → `t('保存')` |
  | `ingest/ingest` | 13 | |
  | `menu-config/menu-names` | 11 | |
  | `agent/agent` | 4 | |
  | `version/version` | 1 | |
  合并的收益不只是删键：点号键在 en/ja 里多数**没有对应译文**（当初只为中文能显示才写的），合并到中文键后**免费继承**该中文键已有的 en/ja 译文，等于顺手补了翻译。
- **Why the earlier "不能全局批量合并" constraint no longer blocks it**: 该约束的前提是「点号键可能被 `useI18n(other-ns)` 的组件引用，合并后只有目标 ns 能解析」。实际扫描结果：这 243 个键的引用方**全部**与其目标中文键同属一个命名空间；跨命名空间的情形（`t('common.xxx')` 写在 ontology/agent 等模块里）由上一轮的 `fallbackNS: 'common'` 兜住——`common` 是唯一被跨模块引用的命名空间，而它自己内部的合并不会改变解析归属。
- **Evidence**: `node scripts/check-i18n-keys.mjs` → 阻断违规 **0**、缺失引用 **0**、冗余点号键 **0**（此前 5）；`--update-baseline` 后 `violations: [] / missingKeys: []`；`tsc -b --noEmit` 0 error；`eslint .` 0 error / 63 warning；`vitest run` 60 files / **712 passed**（含所有 `t()` 可见文本断言，证明改写未改变界面文案）。
- **Residual (非阻断，新登记)**: en-US 键数仍低于 zh-CN 若干模块——`agent` 112/177、`shared/common` 1893/2391、`ingest` 317/349、`ontology` 721/1153。这些键在英文环境回落中文（`fallbackLng='zh-CN'`），符合「中文即键」约定，故不计为违规；属**待补译**而非待修缺陷。见下一条 OPEN。

---

## OPEN — quality-gap — en-US / ja-JP 待补译缺口（不阻断，属译文产能问题）

- **Date**: 2026-10-19
- **Source**: `node scripts/check-i18n-keys.mjs` 命名空间键数对比
- **Open item**: 按「中文即 key」约定，en/ja 不需要凑齐键集合（缺则回落中文），因此下列缺口**不是**缺陷，但它决定了英文/日文环境的实际可用度：
  | 命名空间 | zh-CN | en-US | 缺口 | 回落比例 |
  |---|---|---|---|---|
  | `ontology` | 1153 | 721 | 432 | 37% 显示中文 |
  | `shared/common` | 2391 | 1893 | 498 | 21% |
  | `agent` | 177 | 112 | 65 | 37% |
  | `ingest` | 349 | 317 | 32 | 9% |
  | `simulation` | 149 | 134 | 15 | 10% |
  | `version` | 109 | 108 | 1 | 1% |
  ja-JP 除 `ingest`(32) / `ai-assistant`(7) / `audit`(3) / `business`(0) 外基本已齐；缺口集中在 en-US。
- **Why not urgent**: 回落中文是**正确行为**（显示中文 ≫ 显示占位垃圾），且中文是项目第一语言。这是产能问题，不是正确性问题，故不阻断 CI。
- **Current leaning**: 按「用户可见频次」排序补，而不是按命名空间顺序：优先 `shared/common` 的按钮/状态/提示词（跨模块复用，一处补全全站受益），其次 `ontology` 的高频页签（设计器/关系/属性），最后低频管理页。
- **Resolves when**: 各命名空间 en-US 缺口 ≤ 5%，或明确宣布「英文环境仅覆盖核心路径」并写入 README。

---

## RESOLVED — structural-defect — `data_pipeline.py` 被同名包遮蔽，4 个适配器 import 期即失败

- **Date**: 2026-10-17（当日发现并修复）
- **Source**: 本轮全模块导入勘验（1499 个模块逐个 `importlib.import_module`）
- **Defect**: `odap/infra/data_pipeline.py`（模块）与 `odap/infra/data_pipeline/`（包）同名共存，Python 包优先规则让模块**永久不可达**；包 `__init__` 当时为空，导致 `adapters/{api,db,sensor}_adapter.py` 的 `from ..data_pipeline import ...` 恒抛 `ModuleNotFoundError: No module named 'odap.infra.data_pipeline.data_pipeline'`。
- **Fix applied**: 原模块内容整体移入 `odap/infra/data_pipeline/core.py`（内容零改动）；包 `__init__` re-export 全部 11 个公开符号，使 `from odap.infra.data_pipeline import DataPipeline` 等旧写法重新成立；3 个适配器改为 `from ..core import ...`。
- **Evidence**: 全仓导入失败数 15 → 4（剩余 4 项均为环境条件：3× `JWT_SECRET` 未设置属 fail-closed 设计、1× `matplotlib` 未安装属可选依赖）；`lint-imports` C1~C4 全 KEPT（1499 files / 2714 deps）；`pytest tests/unit/test_data_pipeline.py tests/unit/biz/knowledge tests/unit/test_inheritance.py` → 214 passed。
- **Related**: 同批还修复了 5 处 import 期必崩的死引用（`application/{explanation,intent,navigation}` 三个桥接包仍 re-export 已重构掉的模块级函数；`reasoning/inference` 的 `TypeInferenceRule` 已改成 `TypeInferenceEngine`；`application/query_api/schemas.py` 的 `..model.s.*` 是 models→model 改名误替换产物且缺 `Enum` 导入），以及 `session_memory` 在 import 期用 `os.getcwd()` 拼 sqlite 路径导致「从 `apps/api` 启动就 unable to open database file」的启动路径耦合问题。

---

## RESOLVED — redundancy-needs-disposition — 全站零引用组件重扫：删 53 个 / 6904 行，挂 1 个

- **Date**: 2026-10-20
- **Source**: 全站符号级零引用重扫（`apps/web/scripts/scan-unused.tmp.mjs`，扫 496 个源文件）
- **判据（本轮修正，比前两轮更严）**：
  1. **barrel 转出不等于引用**。`index.ts` 里 `export { X } from './X'` 只说明「可能被转出」，不说明有人消费；必须看**符号级**消费。
  2. **根集合必须是「入口 + 整张路由表」**（`main.tsx` / `App.tsx` / `src/routes/**` / `modules/*/routes.tsx`）。第一版扫描漏了 `src/routes/routeDefs.tsx`，把全站页面判成死代码 —— 漏路由表 = 扫描结果整体不可信。
  3. **测试引用不等于产品引用**。只有 `*.test.tsx` 引用的组件属「测试空转」，产品里已死。
  4. **零引用 ≠ 可删**。必须再查一次「非 import 接入方式」（动态 `import()`、字符串映射表、WebSocket、路由清单）与「后端契约是否真实存在」。上一轮 `EditLockIndicator` 就是被 `grep apiClient` 漏掉的（它走 WebSocket）。
- **Disposition**:

  **一、删除（53 个 / 6904 行）** —— 归档于 `.workbuddy/archive/zero-ref-2026-10-19/`（含 `MANIFEST.json` 与逐文件原始字节，因这些文件相对 HEAD 已有本地改动，`git checkout` 无法安全回滚）
  | 分组 | 文件数 | 行数 | 依据 |
  |---|---|---|---|
  | 设计系统残留（`atoms` / `molecules` / `templates` / `ChatPanel`+`DataTable`+`FormPanel`） | 19 | 1103 | 三层抽象零消费；项目实际直接用 AntD + ProComponents；`docs/` 无任何条款强制经 atoms 访问 |
  | shared 层零消费工具与死 barrel（`useResponsive`/`useUndo`/`responsive`/`sanitize`/`stores`/`types`/`utils`/`styles`/graph hooks） | 13 | 780 | 响应式断点、撤销栈、graph 选中/工具栏均已内聚到 `GraphCanvas` 或改用 AntD 栅格 |
  | 被 `GraphCanvas` 合并替代的旧图谱实现（`pages/OntologySemanticNetwork` 1478 + `components/OntologySemanticNetwork` 340 + `OntologySchemaViewer` 581） | 3 | 2399 | `GraphCanvas.tsx` 文件头明写「合并了原 GraphCanvas + OntologySemanticNetwork 的能力」；同名两份旧实现并存本身就是断链风险 |
  | workspace 重复实现（`WorkspaceManager` 1284 + `WorkspaceSwitcher` + barrel） | 3 | 1412 | 路由指向 `WorkspacePage`（1068 行）；同名职能两套实现 |
  | 仅测试引用 / 级联死代码（`StatCard`/`QAPanel`/`ToolHealthIndicator`/`OntologyBuildProgress`/`versionStore`×2/`DecisionTimeline`/`ReasoningChain`/本体 `index`+`constants`） | 12 | 1093 | 有测试无产品入口；两个 `versionStore` 与 `modules/version` 重复且均无消费 |
  | 无后端调用的静态页（`business/pages/SmartGeneration`） | 1 | 117 | 全文件零 API 调用，纯静态占位 |
  | 合计 | **53** | **6904** | |

  同步清掉 8 处悬空导出（`shared/index.ts`、`shared/components/organisms/index.ts`、`shared/modules/graph/index.ts`、`agent/index.ts`、`business/index.ts`、`ontology/index.ts` 等），删除 4 个空目录，移除 5 个失效测试文件。

  **二、挂载（1 个）**
  | 组件 | 挂载点 | 为什么不是「删」 |
  |---|---|---|
  | `shared/hooks/PageContextProvider.tsx`（172 行） | `App.tsx` 的 Workspace/Scenario Provider 内侧（Router 之内） | `AIChatPanel` 通过 `useAIContext()` 读「当前页面 / 选中本体 / 选中类型 / 页面摘要」。Provider 此前**从未挂载**，`useContext` 恒为 `null` → AI 助手只能拿到 `ontologyStore` 兜底值，**永远不知道用户在哪一页、选中了什么**。这是静默失效（界面不报错），不是死代码 |

- **Evidence**: `npx tsc --noEmit -p tsconfig.app.json` 0 error；`npx eslint .` **0 error / 57 warning**（原 61，减少的 4 条随被删文件消失）；`npx vitest run` **64 files / 725 passed**（原 69/760，减少的 5 个测试文件全部属于被删组件；`test/components.test.tsx` 里两条针对已删 barrel 的断言改为直引真实 store）；`node scripts/check-i18n-keys.mjs` 阻断 0 / 缺失引用 0。
- **Resolves when**: ✅ 53 个文件已从工作树移除且 `tsc` 无悬空引用；`PageContextProvider` 已在 `App.tsx` 挂载。
- **遗留**：本轮判为「有真实契约但无入口」的 8 项**不删**，见下一节 OPEN 条目。

---

## RESOLVED — redundancy-needs-disposition — 8 个「有真实后端契约、但无前端入口」的项目已逐项处置（删 5 / 挂 5 / 后端补 2 处注册）

- **Date**: 2026-10-20
- **Source**: 同日零引用重扫的「被 import 但符号从未被消费」与「零引用」两档，逐一核对后端路由后筛出
- **结论**: 这 8 项里只有 5 项真的是「差一个入口」，另外 3 项（合并后 5 个文件 / 1580 行）是契约虚构或已被收敛的旧实现，按契约虚构流程删除。**「后端端点存在」不等于「前端能挂上去」**——必须两端逐字段核对。
- **逐项处置**:
  | 原条目 | 行数 | 核对后真相 | 处置 |
  |---|---|---|---|
  | `ontology/components/HealthDashboard.tsx` + `HealthRuleEditor.tsx` + `pages/HealthDashboard.tsx` | 911 | 后端 `/api/ontology/health/*` **存在但两处注册表都没登记**（9 个端点写好却没接电）；前端两个组件的报文与字段全是虚构（`rule_id` 主键、规则上读 `status`/`failure_count`/`last_checked_at`、打 `/rules/{id}/scan` 与 `/violations`） | 后端补注册（8 条路由上线）；删两个组件（695 行）；页面**整体重写**；新增 6 例契约测试（含 4 条负向断言） |
  | `simulation/components/WhatIfPanel.tsx` | 189 | **我上一轮的判断有误**：`/api/simulation/what-if` 路径是对的（`parallel_routes.py` 里 prefix `/api/simulation` + `/what-if`）。真实缺陷是报文**缺必填的 `base_scenario`**、发了后端不读的 `sandbox_id`/`scenario_id`、读后端不返回的 `impact`/`direction`（对 `undefined` 调 `.toFixed()` 直接抛错） | 重写；新增 7 例契约测试；挂到 `/simulation/sandbox` 的「假设推演」页签 |
  | `simulation/...` 六件套（`SandboxManager` + 4 个展示组件 + `FeedbackPanel`） | 1181 | `SandboxManager` 的本体下拉打 `GET /api/ontology`（不存在）；`RecommendationPanel` 打 `/api/simulation/recommendations`（不存在）；`ParallelComparison`/`TimelineView`/`SimulationProgress` 是纯展示且仿真页已有等价能力；**后端 `SandboxManager.stop_sandbox` 有实现但 service 与 HTTP 层都没转发**（运行中的沙箱既不能停也不能销毁） | 删 4 个（281+153 行）；`SandboxManager` 改为读 `useOntologyStore`；后端补 `POST /api/simulation/sandbox/{id}/stop`；新建 `SandboxLabPage` 三页签聚合（沙箱/假设推演/反馈闭环）并接管 `/simulation/sandbox` |
  | `qa/agui/*`（10 个文件） | 1403 | 后端 `/api/ag-ui` router **已注册**，前端 `RunAgentInput` 字段与后端 Pydantic 模型逐字段一致。真实问题是：后端端点走 `Depends(get_current_user)`，而 AG-UI 客户端用裸 `fetch`+`EventSource` 绕过 apiClient 的鉴权拦截器，页面挂载时又没传 token → **必然 401，表现为「页面能打开但发不出消息」** | 挂 `/qa/copilot`；`QACopilotDemoPage` 默认从 `useAuthStore` 取 token、从 `currentOntology` 取 workspaceId |
  | `system/components/MCPManager.tsx` + `system/stores/skillStore.ts` | 403 | `MCPManager` 四处虚构：注册打 `/servers/register`（真实是 `POST /servers`）、调工具打 `/tools/{tool_id}/invoke`（真实是 `/servers/{server_id}/tools/{name}`）、用 `tool_id` 当主键（MCP 协议用 `name`）、参数键叫 `parameters`（真实读 `arguments`）。`skillStore` 则全站零消费，且与 `SkillManagement` 页面的 `api` 对象重复 | `MCPManager` 三处契约修正 + 5 例契约测试，挂到 `SkillManagement` 第三个 Tab；删 `skillStore.ts` |
  | `minio-admin/*`（3 个文件） | 319 | 后端 7 个 `/api/minio-admin/*` 端点**全部实现且已注册**，前端 `minioAdminApi.ts` 7 个方法也全写好——**但页面只有 iframe 代理与「关于」两个页签，service 从未被任何 UI 消费** | 新建 `StorageBrowser`（bucket 列表 / 对象浏览 / prefix 导航 / 元数据 / 预签名复制 / 删除）并作为 `/settings/storage` 默认页签；8 例契约测试（含 403 detail 原样透出） |
  | `config/components/PolicyEditor.tsx` | 141 | 零 API 调用，所有操作只写本地 state，刷新即丢；真实策略页是已挂载的 `audit/pages/PolicyPage.tsx` | 删除；连带删空的 `config/index.ts` 与 `config/components/` 目录 |
  | `semantic-admin/pages/DashboardPage.tsx` + `saConfigApi.ts` | 731 | `saConfigApi` 的 `/api/semantic-admin/config` 已注册（保留）；但 `DashboardPage` 与 `QualityDashboardPage` 打**完全相同的三个端点**，且 `legacyRedirects.ts` 早已把 `/semantic-admin/dashboard` 收敛到 `/semantic-admin/quality` | 删除 `DashboardPage.tsx` 与 `qualityApi.ts` 里 3 个 `getDashboard*` 函数；测试同步收敛 |

- **本轮额外发现（不在原 8 项里）**:
  1. **补路由时被测试拦下**：曾尝试给 `DashboardPage` 加 `/semantic-admin/dashboard` 路由，`routeManifest.test.tsx` 的「重定向路径不与页面路径冲突」断言直接失败——这才发现该路径早就被收敛。**先查重定向表，再决定挂载还是删除。**
  2. **「service 写好了」不等于「功能存在」**：`minioAdminApi.ts` 7 个方法零消费，`grep apiClient` 找不到是因为它用的是 `fetchJson`。这类只有渲染层才暴露，`grep` 端点名同样看不见。
  3. 归档补齐 `MANIFEST.json`：本轮所有删除（13 个文件 / 约 2100 行）逐条记录「原路径 / 行数 / 判定 / 替代物 / 理由」，位于 `.workbuddy/archive/zero-ref-2026-10-20/`。
- **遗留（本阶段不处理，已在别处登记）**:
  - 新增中文即 key 的文案尚未补 en-US / ja-JP 译文（属译文产能，不阻断，见下方 `i18n` 条目）
  - `FeedbackPanel` 仍用 antd 6 已标记 deprecated 的 `List`（全站 20+ 处同类，统一迁移）
  - `minio-admin` 的 `/objects` 后端对非管理员直接 403（"仅管理员可访问"），若后续要放开需先补工作空间隔离查询
- **Resolves when**: 8 项各自有入口、有契约测试（含负向断言），或明确记录「本阶段不提供该功能」并连同后端端点一并下线。**→ 已全部满足。**

## OPEN — redundancy-needs-disposition — 剩余 24 项零引用：已按「契约真实性」分组，待逐组处置

> **2026-10-21 更新**：QA 旧栈组已处置完毕（删除 6 个文件 / 782 行，见文末 RESOLVED 条目）。
> 重跑 `scan-unused.mjs` 后当前为 **16 项 / 2948 行**：A 组零引用 10 个、B 组「被 import 但符号从未被消费」6 个。
> 剩余组为：分支/合并 741、类型注册表 583、冲突解决 536、AI 内联补全 364、地图 127、store/service 孤儿 573、`qa/agui/index.ts` barrel 24（**不可删**，被 `qa/index.ts` 转出）。

- **Date**: 2026-10-20
- **Source**: `pnpm scan:unused`（`apps/web/scripts/scan-unused.mjs`）在上一轮删除 53 个 + 本轮删除 15 个之后的最新扫描：A 组零引用 16 个、B 组「被 import 但符号从未被消费」8 个，合计 **24 项 / 约 3727 行**。
- **关键前提**：这 24 项**大多不是死代码**。已逐个核对后端注册表（`DEFAULT_ROUTER_REGISTRY` 展平后 1003 条路由），下列端点**全部真实在线**：
  | 前缀 | 路由数 | 抽样 |
  |---|---|---|
  | `/api/ontology/branches` | 10 | `/branches`、`/branches/merge-requests`、`/branches/merge-requests/{mr_id}` |
  | `/api/ontology/versions` | 4 | `/versions/{document_id}`、`/compare`、`/rollback` |
  | `/api/ontology/conflict` | 3 | `/detect`、`/resolve`、`/conflicts` |
  | `/api/cognition` | 4 | `/explain`、`/navigate`、`/recognize-intent` |
  | `/api/extraction/provenance` | 2 | `/{entity_id}`、`/by-source/{doc_id}` |
  | `/api/semantic-admin/config` | 4 | `/config`、`/ensure-builtin` |
  | `/api/ontology/registry` | 15 | `/action-types`、`/link-types`、… |
- **分组与判定**:
  | 组 | 文件 | 行数 | 判定 | 依据 |
  |---|---|---|---|---|
  | 分支 / 合并 | `BranchList` 352 + `MergeDiffViewer` 389 | 741 | **需按 MR 五步流重写** | 前端仍用 `/branches` + `/branches/merge` 直连式 API，而后端已改为 `/branches/merge-requests`（含 `{mr_id}`）——契约代际不一致，直接挂载会打错端点 |
  | 类型注册表 | `registryStore` 311 + `registryApi` 223 + `registryAdapters` 49 | 583 | **需选宿主**（本体设计器「类型注册表」Tab） | 三者闭环互引、无外部入口；后端 `/api/ontology/registry/*` 15 条路由齐全；顺带可解 ADR 里 `registryApi.update` 12 字段与响应键 `type_id` 的既有缺陷 |
  | 冲突解决 | `ConflictResolver` | 536 | **需选宿主**（本体设计器「冲突」Tab） | 打 `/api/ontology/conflict/*` 三条路由，契约匹配；文件内是自引用（无外部消费） |
  | 目标血缘 / 变更提案 | `GoalLineage` 208 + `ChangeProposalCard` 392 | 600 | **待核契约** | `GoalLineage` 内无 `/api/` 字面量（走 props 或 service），需先确认数据来源再定 |
  | AI 内联补全 | `AIInlineCompletion` 187 + `useTypeInference` 177 | 364 | **可选增强** | 依赖 LLM 可用性（`OPENAI_API_KEY` / 本地模型）；挂载前需有降级路径 |
  | 溯源 | `ProvenanceViewer` | 147 | **需选宿主**（抽取结果详情 / 实体详情抽屉） | `/api/extraction/provenance/{entity_id}` 在线 |
  | 模板推荐 | `TemplateRecommender` | 197 | **待核契约** | 内无 `/api/` 字面量 |
  | 地图 | `MapView` | 127 | **需先过地图合规** | 涉及地理数据，必须先走 `geo-map-compliance-guard`（合规数据源白名单），不能直接挂 |
  | QA 旧栈 | ~~`ChartRenderer` + `QAIProvider` + `qaStore` + `qaApi`~~ | ~~279~~ → **782** | **已删除**（2026-10-21，见下方 RESOLVED 条目） | 核实后从 4 个文件扩到 6 个：连同 `useQAI` 403 + `useChatStorage` 104 一并删除 |
  | store / service 孤儿 | `cognitionStore` 101 + `i18nAdminApi` 53 + `knowledgeStore` 124 + `knowledgePageApi` 88 + `versionStore` 110 + `saConfigApi` 97 | 573 | **需逐个查重** | 对应的功能页可能已用别的 store 实现（`saConfigApi` 即典型：后端 4 条路由在线，但语义配置页没有 UI 消费它） |
- **barrel 类不可机械删除**: `qa/agui/index.ts` 出现在零引用名单里，但 `qa/index.ts` 通过 `export … from './agui'` 转出——删掉它会直接断链。**扫描器的「barrel 转出不算引用」是故意设计**（否则无法发现只被转出、从未被消费的模块），但落到处置时必须人工复核。
- **Blocked by**: 每一项都要「选宿主 + 逐字段核契约 + 补契约测试（含负向断言）」，属于功能补齐而非清理，不适合与删除混在一批。分支/合并组还要先定 MR 五步流的交互规格。
- **Resolves when**: 每组各自有入口且契约测试通过，或明确判定「本阶段不提供该功能」并连同后端端点一并下线（后者需同步 `router_registry.py`，避免留下无人使用的 API 面）。

---

## RESOLVED — redundancy-needs-disposition — QA 旧栈整组删除（6 个文件 / 782 行）

- **Date**: 2026-10-21
- **Source**: `scan-unused.mjs` 分组表「QA 旧栈」组；原估 4 个文件 279 行，核实后扩大到 6 个文件 782 行。
- **判定**：整组是 **QA v1 的独立对话栈**，已被 `ai-assistant` 的 `useAIChat` + `AIChatPanel` 取代。不是「差一个入口」，而是**入口已被另一套实现占走**。

### 决定性证据

1. `pages/QAPage.tsx` 全文只剩 3 行 import（`AIChatPanel` + `useI18n`），注释原文：
   > 统一使用 AIChatPanel full 模式。不再使用独立的 QAChatPage 实现，所有 AI 助手功能共享同一份代码。
2. `grep "useQAI("` **只命中它自己的定义**，全站零调用点。
3. 两套引擎不是同一个：
   | | 端点 | 协议 |
   |---|---|---|
   | 旧栈 `useQAI` | `/api/qa/ask`（`qa_engine` SSE） | `{type: "chart" / "temporal" / "reasoning"}` 自定义事件 |
   | 现行 `useAIChat` | `/api/assistant/chat` | AG-UI 标准事件 `RUN_STARTED` / `TEXT_MESSAGE_CONTENT` / `TOOL_CALL_*` / `CUSTOM` / `RUN_FINISHED` |
   复活旧栈等于让项目同时跑两个对话引擎，与「所有 AI 助手共享同一份代码」直接冲突。
4. `useAIChat.ts` 里虽有 `charts?: unknown[]` / `temporal?: unknown[]` 两个字段，但**只是会话历史 DTO 的兼容声明，没有任何渲染逻辑** —— 上一轮我把这处 grep 命中误判为「图表能力已有替代实现」，此处更正：**现行栈其实根本不渲染图表**。

### 逐项处置

| 文件 | 行数 | 判定 | 依据 |
|---|---|---|---|
| `qa/hooks/useQAI.ts` | 403 | 已被取代 | `useQAI()` 零调用点；其 `ChartSpec`/`TemporalCard`/`ReportLink` 三个类型仍被活的 AG-UI 卡片消费，已迁至新文件 `qa/types.ts` |
| `qa/hooks/useChatStorage.ts` | 104 | 随宿主失效 | 唯一消费者是 `useQAI.ts` |
| `qa/components/ChartRenderer.tsx` | 148 | 重复实现 + 伪实现分支 | 6 类只是再包一层 `InlineChart`；`GraphView` 是项目第三套图渲染（已有 Sigma.js `GraphCanvas` + ReactFlow `BlueprintDesigner`）；`MapView` 用 echarts `geo: { map: 'world' }` 但项目从未 `registerMap` 任何 GeoJSON，一旦触发必然抛 `Map world not exists` |
| `qa/stores/qaStore.ts` | 69 | 零消费 | 只在 barrel 转出 |
| `qa/services/qaApi.ts` | 41 | 随宿主失效 | 唯一消费者是 `qaStore.ts` |
| `qa/providers/QAIProvider.tsx` | 17 | 死包装 | 全站零消费；是 `@openharness/react` 的薄包装，而该依赖**全站仅此一处 import** |

归档：`.workbuddy/archive/zero-ref-2026-10-20/modules/qa/`，逐文件 sha256 与原件比对一致后才删除；`MANIFEST.json` 已补 6 条（现 19 条 ⇄ 19 个文件，脚本校验双向对齐）。

### 顺带修掉一个隐性伪实现：`InlineChart` 的地图/网络图

`InlineChart.chartTypeNames` 声明了 8 个别名（含 `map` 地图、`network` 网络图），但 `buildEChartsOption` 只实现 6 类，另 2 类落 `default` 分支 —— **静默画成折线图**：标题写「地图」、画出来是折线。这不是缺功能，是产出错误结论，已改：

- `RENDERABLE_TYPES` 显式白名单（6 类），其余走 `UnsupportedChart`；
- 不支持时给出具体原因而非笼统提示：地图→「需注册 GeoJSON 底图并受地图数据合规约束」、网络图→「请使用知识图谱画布查看」；
- 原因文案进入 `qa` 命名空间 zh-CN / en-US / ja-JP 三语；
- 新增 `InlineChart.contract.test.tsx` **10 例**，含负向断言「map / network 绝不调用 `echarts.init`、绝不调用 `setOption`」——从测试层杜绝再退回静默降级。

### 顺带修掉一个既有 lint error

`ProvenanceViewer.tsx` 的 `setLoadToken` 定义了却从未接线（`@typescript-eslint/no-unused-vars`，eslint 唯一 error）。设计意图显然是「重试」，故接到错误横幅 `Alert` 的 `action` 上（与 `MinioAdminPage` 同一写法），并补 1 例断言「点击重试确实再打一次 GET、成功后错误横幅消失」。

### 新发现：后端 3 个端点成孤儿（本阶段不处置，登记待决）

删掉 `qaApi.ts` 后，以下后端端点**有实现、有注册、但无任何 UI 消费者**：

| 端点 | 位置 | 说明 |
|---|---|---|
| `POST /api/qa/ask` | `biz/data/qa/api/routes.py` | `qa_engine` SSE；活路径改用 `/api/assistant/chat` |
| `POST /api/qa/chart` | `routes.py:734` | 依赖 `ChartRenderer`（后端 spec 生成器） |
| `POST /api/qa/ask/temporal` | `routes.py:698` | 时序问答 |

**注意区分**：`QAEngineV2` 本身**是活的** —— `biz/core/chat/api/routes.py` 与 `chat/tools/qa_retriever_tool.py` 都在 import 它，`/api/assistant/chat` 的检索段复用它。死的是这三个 HTTP 端点，不是引擎。三条端点是否下线需单独决策（下线要同步 `router_registry.py`，避免留下无人使用的 API 面）。

### 已闭环：`@openharness/react` 依赖（2026-10-22 移除，见 ADR-099）

2026-10-21 时本项登记为「故意不动」。2026-10-22 复核后判定必须处置，理由升级：

1. **不只是零引用，而是协议不兼容**：SDK 的 `createOHTransport` 只解析 **AI SDK 5 data stream** 协议（`node_modules/@openharness/react/dist/transport.d.ts` 原文 "parses the AI SDK 5 data stream protocol"），而本项目后端对 `data stream` / `ai_sdk` / `x-vercel` **全量零命中**，实现的是 AG-UI（`apps/api/odap/infra/openharness/agui/`）。装上也用不了。
2. **ADR-070 已定调**：「AG-UI 协议覆盖所有场景，前端只需一套解析器」（`ADR-070:287`）。装第二套解析器与既有决策冲突。
3. **文档在误导人**：`ARCHITECTURE-v2.md:410-411`、`ADR-039:216`、`qa_engine/INTEGRATION.md`（整篇）、`webui-enhancement-design.md:37`（原文「✅ 集成良好」）都按 AI SDK 路线描述前端。

**已完成**：新建 [ADR-099](../07-adr/ADR-099_frontend-agent-protocol-agui.md)；从 `apps/web/package.json` 移除 `@openharness/react` 与 `ai`（连带 `@openharness/core`、`@ai-sdk/react`、`zod` 该条链路），重生成 `pnpm-lock.yaml`；修订上述 4 处文档，`INTEGRATION.md` 重写为 v2.0（AG-UI 集成方案）。

**复引入条件**：仅当①后端新增 AI SDK 5 data stream 端点、且②ADR-070「前端只需一套解析器」被显式修订为允许双协议时，方可重新评估。不得以「框架自带能力」为由单方面加回。

**验证（2026-10-23，依赖物理删除后复跑）**：

| 门禁 | 结果 |
|---|---|
| `apps/web/package.json` / `pnpm-lock.yaml` | `@openharness` 与 `@ai-sdk` 引用数均为 **0** |
| `node_modules` | `@openharness`、`@ai-sdk` 两个 scope 目录已物理删除（`pnpm install --frozen-lockfile` 报 "Already up to date" **不会**清理孤儿包，须手动删，否则形成幽灵依赖） |
| `tsc -p tsconfig.app.json` / `tsconfig.test.json` | 0 error / 0 error |
| `eslint .` | **0 error** / 56 warning（与删除前一致） |
| `vitest run` | 72 files / **782 passed** —— 证明确无代码依赖这两个包 |
| `check-i18n-keys.mjs` / `check-lucide-icons.mjs` | 阻断 0；PASS |
| `doc_governance.py audit --ci` | 纳管 md 277 → **278**（+ADR-099），error 0 / warn 15（既有） |
| `check_dangling_doc_links.py` | 死链 6 条（既有，均在 `specs/`），新增文档链接全部可达 |

### 验证

| 门禁 | 结果 |
|---|---|
| `tsc -p tsconfig.app.json` | 0 error |
| `tsc -p tsconfig.test.json` | 0 error |
| `eslint .` | **0 error** / 56 warning（原 57，净减 1） |
| `vitest run` | 72 files / **782 passed**（新增 InlineChart 10 + ProvenanceViewer 重试 1） |
| `check-i18n-keys.mjs` | 阻断 0 / 缺失引用 0 / 冗余点号键 0（qa 命名空间 86 → **81** 键：新增 3 条「不支持」说明，删除 8 条随旧栈失效的图表/时序表单键；三语键数一致） |
| `scan-unused.mjs` | 24 项 / 3727 行 → **16 项 / 2948 行** |

> 注：一次并发跑 `eslint` + `vitest` 时出现 2 例 5000ms 超时（`ObjectViews` / `RoleManager`）。隔离复跑均全绿（`ObjectViews` 8/8），确认为机器负载导致的抖动，非代码问题。后续门禁应串行跑。

