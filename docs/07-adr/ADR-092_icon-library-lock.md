---
id: odap.l7.adr-092-icon-library-lock
status: active
owner: architect
version: ''
layer: L7
concern: adr
lifecycle: frozen
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
---

# ADR-092: 图标库锁定为 lucide-react（统一描边 SVG）

## Status

**已接受（2026-10-17）**。本轮锁定全项目唯一 SVG 图标库为 `lucide-react`。
> 编号：任务书更正后自 ADR-091 起顺序编号；本条为 ADR-092。

---

## Background

关联铁律：团队级 P0-1 ——「Spec/架构/API 中禁止 emoji 作功能图标；必须锁定一套 SVG 图标库，尺寸 16/20/24px，全项目不混用」。

**设计侧不可变规格**（来源：`docs/04-ui/UIUX-DESIGN-v2.md` + `docs/04-ui/design-tokens.css:234-237`）：

- 统一描边 SVG：`stroke-width: 1.5`（`--odap-size-icon-stroke: 1.5`，@24px 网格）、round cap/join、`fill: none`。
- 尺寸仅三档：`--odap-size-icon-inline:16px` / `--odap-size-icon-button:20px` / `--odap-size-icon-standalone:24px`。
- 颜色 `currentColor`；禁止 emoji 作功能图标；装饰图标 `aria-hidden`；图标按钮命中区 ≥44x44（`--odap-size-control-xl:44px`）。

**现状（文件:行证据）**：

- `apps/web/package.json:20` 安装 `@ant-design/icons@^6.1.1`；全项目 **186 个文件**导入它。
- **关键事实核验**：`@ant-design/icons` 的图标为**填充式 SVG path**（1024x1024 viewBox，`fill="currentColor"`，`Outlined` 变体亦是填充式描边观感而非 `stroke` 属性），**不暴露 `stroke-width`/`stroke-linecap`/`stroke-linejoin` 控制**，**无法满足**设计侧「stroke-width 1.5 + round cap/join + fill:none」的不可变规格（本环境 node_modules 未安装，结论基于该库公开的 SVG 生成机制；标「Phase 3 实现前抽样复核一次」）。
- `apps/web/package.json:16-62` 无任何统一描边 SVG 库；无 `lucide-react`。
- 55 个 tsx 文件含 emoji 作图标（emoji 扫描命中）。
- 冲突记录：`docs/04-ui/05-ODAP-V2-DESIGN-SYSTEM.md:659` 曾推荐 `@ant-design/icons`；但 `references/industries/enterprise.md`、`ai-native.md` 均推荐 Lucide 描边风。二者不可长期并存（混用即违反 P0-1）。

**候选方案对比**（详见架构 v2 §6.3）：

| 方案 | 库 | 满足描边规格 | 迁移成本 | 与知识库一致 | 评分 |
|------|-----|--------------|----------|--------------|------|
| A（原倾向） | `@ant-design/icons` Outlined | **不满足**（填充式，无 stroke 控制） | 零 | 否 | 5.0 |
| **B（选定）** | **`lucide-react`** | **完全满足**（24px 网格、stroke、round cap/join、fill:none、strokeWidth 可设 1.5） | 高（186 文件，codemod + 映射表分批） | **是** | **8.6** |
| C | `@tabler/icons-react` | 满足 | 高 | 部分 | 7.0 |

---

## Decision

锁定 **`lucide-react`** 为全项目唯一图标库。

1. **规格对齐**：`strokeWidth={1.5}`、`strokeLinecap="round"`、`strokeLinejoin="round"`、`fill="none"`（Lucide 默认即 round cap/join + fill:none，仅需显式把 `strokeWidth` 设为 1.5）；尺寸仅 16/20/24（`size="16|20|24"`）；颜色 `currentColor`（继承 `--odap-color-*`）。
   - **描边档位（设计侧 2026-10-17 终裁，§5.3）**：三档（16/20/24）**统一恒定 1.5px**，启用 **`nonScalingStroke`**，**拒绝等比变细**。依据：等比变细会使 16px 档降到约 1.0px，在 1x/分数 DPR 下发虚、暗色面上读作噪点，打穿「层级靠亮度与描边」的设计原则。
   - **降级口径（同一决策族，免二次终审）**：若 pinned 版本无 `nonScalingStroke`，退化为**显式逐档 `strokeWidth`**（三档仍 1.5、仍不做等比，只放弃 `vector-effect`）；若 1x 屏实测仍发虚，允许 `24=1.5 / 20=1.5 / 16=1.4`（**仍非等比**）。
   - **16px 复杂度门禁（`minSize`，并入 CI 校验）**：16px 档相对笔画更重（1.5/16≈9.4% vs 1.5/24=6.25%），复杂图标会糊。允许 16px（单轮廓/简单几何）：`Circle`/`Square`/`Link`/`Clock`/`Gauge`/`Bot`/`Ticket`/`Stamp`/`CircleDashed`；**最小 20px**（多内轮廓/密集/交叉线）：`Shapes`/`Network`/`Workflow`/`Boxes`/`Package`/`FlaskConical`/`GitFork`/`Radar`/`ScanLine`/`Waypoints`。若某处必须 16px 且该语义 `minSize=20`，须**退用简化替代图标**，不得硬缩。
2. **禁用项**：禁用 emoji 作功能图标；禁用 `@ant-design/icons` 作为**项目图标系统**（其仅作为 AntD 组件内部渲染的传递依赖保留，如 Table 排序箭头、Modal 关闭，属 AntD 内建、不在「项目图标系统」范围内）；两种混用视为违规。
3. **迁移策略**（分批 + codemod，不一次性重写）：
   - 产出「`@ant-design/icons` 图标名 → Lucide 图标名」映射表（覆盖 186 文件用到的全部图标）。
   - 编写 codemod（`scripts/migrate_icons.mjs`）批量替换 import 与 JSX，人工复核灰名单（语义不完全对应的图标）。
   - 按模块分批：AdminLayout/导航 → 图谱页 → 其余业务页；每批 Feature Flag 灰度，旧图标保留一 release。
   - emoji 图标 55 文件同批替换为 Lucide 图标。
   - **版本锚定（强制）**：映射表与 codemod 必须对**已 pin 的 `lucide-react` 版本**冻结。原因：Lucide 跨版本会重命名导出，已实测三例——`MessageCircleQuestion`（工作区 ask）在新版为 `message-circle-question-mark`；`HelpCircle`→`CircleHelp`→`circle-question-mark`；`Layers3`→`layers`、`BookMarked`→`book-bookmark`。冻结前须以该版本 `lucide-react` 的导出清单为准，禁止按通用印象写图标名（否则命中「幻觉接口」失效模式）。
   - **结构前提（设计侧设定）**：裁决表以「语义角色」为主键（稳定），图标名称为「须按 pinned 版本导出清单解析」的候选；因此 Lucide 改名不使裁决失效，只有映射表需按版本冻结。
   - **冻结交付物**：pin 定 `lucide-react` 版本后，产出「版本号 + 该版本**全量导出清单快照（含 deprecated aliases）**」交设计侧核对 codemod 命名，作为映射表冻结凭据（Phase 2 安装时执行）。快照必须**全量**（`Object.keys(await import('lucide-react'))`），不得只列"用到的"——Lucide 为改名前的旧名保留 alias 导出（如 `HelpCircle`、`Layers3`），codemod 据全量清单把「旧名 → 新名」做成确定性映射。
   - **Lucide React API 事实（经官方文档核验，供冻结实现引用）**：① 图标以**具名导入**使用（`import { Camera } from 'lucide-react'`），库为 ESM、可 tree-shake；② 组件接受标准 SVG 属性作为 props，`strokeWidth`（number，**默认 2**）透传为 SVG `stroke-width`；③ 因此 `1.5` **必须显式设置**，否则被默认值 2 覆盖；④ `absoluteStrokeWidth`（boolean，默认 false）**已在当前源码标注 @deprecated**，替代为 `nonScalingStroke`（为子元素加 `vector-effect="non-scaling-stroke"`，使描边不随尺寸缩放）；⑤ Lucide 默认描边**随 size 缩放**（24px 网格下 1.5，在 16px 下按比例变细）——是否对 16/20 档启用 `nonScalingStroke` 以保持视觉一致，属设计侧子决策（已提请设计侧确认）。⑥ 下划线：`absoluteStrokeWidth` 与 `nonScalingStroke` 的确切可用性随 pinned 版本而定，冻结时以该版本为准。
4. **图标身份与可访问性**：图标一律 `aria-hidden` 除非承担语义（如仅有图标的按钮加 `aria-label`）；图标按钮命中区 ≥44x44。
5. **必须覆盖的语义图标（终裁冻结版，设计侧 2026-10-17 回签）**（均经 lucide.dev 存在性核验）：
   - 工作区：`LayoutDashboard`(dashboard)、`Network`(ontology)、`BookOpen`(knowledge)、`MessageCircleQuestion`(ask，注意版本重命名)、`ShieldCheck`(governance)、`Settings`(settings)。
   - 图谱节点类型：`Box`(object-type)、`Link`(link-type)、`Zap`(action-type)、`Circle`(instance)、`Clock`(event)、`Gauge`(metric)、`Shield`(rule)、`Bot`(agent)（配合 `--odap-graph-node-*` 分类色，颜色之外叠加 shape+icon 冗余编码，须与设计 §4.4 形状冗余编码自洽）。
   - 工具栏：`Play`/`Pause`/`Square`(播放/暂停/停止)、`Crosshair`/`Locate`(定位)、`Download`(导出)、`Layers`(图层)、`Search`(搜索)、`Filter`/`Funnel`(筛选)、`Waypoints`(展开邻接，备 `Share2`)、`EyeOff`(隐藏)、`Undo2`/`Redo2`(撤销/重做)。
   - 其余终裁：平台治理工作区 `Scale`；质量门 Quality Gate `ShieldCheck`（备 `BadgeCheck`）；审批 Approval `Stamp`（备 `ClipboardCheck`）；本体建模（设计器视图）`PenTool`（备 `Blocks`）；编排/蓝图编排 `Workflow`；版本分支/分叉 `GitFork`。
   - **完整裁决表（A 组 8 条冲突 + B 组 22 项 ODAP 专有概念）以设计侧 `docs/04-ui/UIUX-DESIGN-v2.md` §5.2 为准**，本条仅记录与架构相关的终裁结论。
6. **灰名单终审机制**（与设计侧分工，权威归设计侧）：映射表中「语义不等价 / 全局语义冲突 / ODAP 专有概念」三类条目为灰名单，由设计侧按准则终裁并回签后冻结；架构侧产出映射表草案与灰名单标注，前端 Phase 3 遇遗漏语义须走「提交→终审→回签」，不得就近自选。**例外（免二次终审）**：裁决表中标注"须核验"的图标若在 pinned 版本不存在，按同语义族的「备用」列降级即可，不重开终审；仅新语义才走完整流程。
7. **ODAP 专有概念语义约定（终裁冻结版）**：语义缺口 Gap `CircleDashed`（备 `Puzzle`）、语义资产 Asset `Package`、路由工单 Routing Ticket `Ticket`、USL `Layers`、指标 MetricType `Gauge`、溯源 Provenance `Footprints`（备 `Route`）、历史/变更记录 `History`、决策 Decision `Signpost`（备 `Compass`）、仿真推演 Simulation `FlaskConical`、漂移 Drift `Radar`、扫描 Scan `ScanLine`、审批 Approval `Stamp`（备 `ClipboardCheck`）、变更提案 ChangeProposal `FileDiff`、SHACL 形状约束 `Shapes`、版本 OntologyVersion `GitCommit`（备 `GitFork`）、概念缺口回路 `RefreshCw`（备 `RotateCw`，须按 pinned 版本核验）。保留未分配：`Tags`(标签/分类)、`ChartLine`(图表/趋势)、`Cpu`(运行时/算力)、`Route`(路径/链路)、`Compass`、`History`、`BadgeCheck`、`Share2`、`ClipboardCheck`、`FileCheck`、`GitBranch`、`Puzzle`、`Blocks`。
8. **同一语义跨位置复用是正确而非违规（重要，防迁移误判）**：一个语义对应一个图标；**同一语义出现在多个位置属正确复用**，只有"同一图标承载不同语义"才算违规。本项目中属**正确复用**的有：`Gauge`（图谱节点 Metric 与 指标平台指标，同一"度量"语义）、`Circle`（图谱节点 instance 与 ABox，同一"实例"语义）、`Boxes`（TBox，同一"结构集合"语义）。迁移期不得因"图标出现多次"而误判为双用并改错。
9. **有意视觉亲缘（intended affinity，非冲突，禁改）**：以下图标间的形似为设计侧有意建立的心智映射，须在映射表与后续评审中显式注明，防止被当作冲突误改：`Box`(图谱节点 object-type) 与 `Boxes`(TBox)；`Circle`(图谱节点 instance) 与 `Circle`(ABox)（同一图标即同一语义）；`Gauge`(图谱节点 Metric) 与 `Gauge`(指标平台指标)。同理 `Shield`(图谱节点 Rule) 与 `ShieldCheck`(质量门) 属同隐喻族的**有意区分**：Rule 用 `Shield`、质量门用 `ShieldCheck`、治理用 `Scale`、审批用 `Stamp`，四处刻意拉开距离。
10. **导入约定（锁定）**：全项目统一**具名导入** `import { Network, Bot } from 'lucide-react'`；**禁止 per-icon 深导入**（如 `lucide-react/dist/esm/icons/network`）。理由：codemod 改写简单（只改 import 语句）；tree-shaking 交给 bundler；CI 白名单校验只需解析 import 语句，无需同时解析路径形式。Phase 3 不得两种写法混用。
11. **冻结 gate = CI 不变量（把"约定"变成"可执行约束"，强制）**：pin 后配套 CI 校验脚本 `apps/web/scripts/check-lucide-icons.mjs`，以 pinned 版本的全量导出快照为**唯一白名单**，任一条件不满足即**构建失败**：
    - (a) 源码 `from 'lucide-react'` 的具名导入名，必须 ∈ 白名单；清单外图标名 → fail（禁止静默降级或"就近改选一个清单内的"）。
    - (b) 扫描 emoji 字符（防迁移期回灌 P0-1；现网 55 个含 emoji 文件待清）。
    - (c) 内置设计侧 §5.2 的**语义角色表**校验：每个语义角色必须绑定其裁决图标（`语义角色 → 期望图标名`），并合并 **`minSize` 门禁**（某处使用尺寸 < 该图标 `minSize` → fail，须退用简化替代图标）。仅校"名字在清单里"无法发现"名字对但语义被换错"或"复杂图标被硬缩到 16px"，故必须做角色绑定 + minSize 校验。
    - (d) **直连导入禁令 + strokeWidth 单点校验**：源码若直接 `import ... from 'lucide-react'` 且出现在 JSX 中 → fail；业务侧必须经项目级 Icon 包装组件（见第 12 条）。同一检查再扫 `strokeWidth` 字面量：除 Icon 包装组件自身外，其他源码出现 `strokeWidth` → fail（确保"唯一位置"成立，防止"误传=静默变别的值"）。
    - 该脚本纳入 CI 门禁，与现有 import-linter 契约并列运行。
12. **项目级 Icon 包装组件（唯一允许设置 `strokeWidth` 的位置）**：新建 `apps/web/src/modules/shared/components/Icon.tsx`（暂定名），作为全项目唯一图标出口：
    - 内部统一设置 `strokeWidth={1.5}`、`strokeLinecap="round"`、`strokeLinejoin="round"`、`fill="none"`、`nonScalingStroke`（版本支持时）、`aria-hidden` 默认值、尺寸仅允许 16/20/24、颜色 `currentColor`。
    - **API 以「语义角色」为键（采纳设计侧建议）**：业务侧一律 `<Icon role="ontology" size={20} />`。理由：语义角色是 §5.2 的稳定主键（Lucide 改名不影响，见第 3 条前提）；以角色为键时"传一个未经终裁的角色"**编译期即不通过**，语义绑定从"CI 事后扫描"升级为"类型层构造即合法"；且天然规避下方 `import *` 陷阱（映射表必然显式静态）。
    - **注册表必须是手工维护的静态映射**：只列 §5.2 终裁过的图标集合，**禁止 `import * as Icons from 'lucide-react'`**（动态按名取值会让 bundler 无法静态分析、把上千图标全量打进 bundle，静默膨胀且不报错）。
    - **不对外暴露 `strokeWidth` prop**：组件可接 `role` / `size` / `className`（及语义化 `aria-*`），**不得接 `strokeWidth`**——否则业务侧仍可覆盖，"唯一位置"等于没收敛（把"漏传=静默变 2"变成"误传=静默变别的值"，更难查）。
    - 业务代码**不得**直接 import `lucide-react`。该组件是「显式 1.5」的唯一实现点，把 186 处约定收敛为 1 处实现，使 CI 不变量 (d) 可守。codemod 的目标输出形态即改写为经该包装组件调用（`role` 键 + 静态注册表）。
    - **若最终仍选 `name` 键**（不反对但代价更高）：则第 11 条 (c) 的语义角色表校验由"可选加固"升级为**必需补偿**，不得省略。

**备份方案**：若 `lucide-react` 在某类领域图标覆盖不足，自绘 SVG 须遵守同一描边规格（1.5 / round cap/join / fill:none），仍归属 Lucide 体系，不引入第二库。

---

## Consequences

**正面**：
- 满足设计侧不可变描边规格，避免 Phase 3 返工。
- 满足 P0-1（唯一 SVG 库、16/20/24、禁 emoji）。
- 与知识库 `industries/enterprise.md`、`ai-native.md` 的 Lucide 推荐一致；`currentColor` 天然消费 `--odap-color-*` token。
- 图标可 tree-shake，包体可控。

**负面**：
- 186 文件迁移成本高（一支 codemod + 分批 + 灰名单复核）。
- 迁移期存在「两库并存」窗口，须靠 Feature Flag 与「新代码只准 Lucide」纪律压缩窗口。
- 个别 AntD 生态专有图标（如 `@ant-design/pro-components` 内置图标）仍需映射或自绘。
- `@ant-design/icons` 作为 AntD 传递依赖仍会进 bundle（无法完全移除），须在文档中界定其范围（仅 AntD 内建图标）。

---

## Related ADRs

- ADR-007（前端 React + Ant Design 技术栈）
- ADR-091（图谱渲染栈收敛；节点类型图标与图谱栈协同）
- ADR-093（Design Token；图标颜色与尺寸 token 来源）
