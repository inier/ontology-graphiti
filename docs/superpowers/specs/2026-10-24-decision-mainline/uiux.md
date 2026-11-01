---
id: odap.l15.specs-2026-10-24-decision-mainline-uiux
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

# 决策主线贯通 — UI/UX 设计规格

> 版本：v1.12 ｜ 2026-10-24（对齐 `api-spec.yaml` **v1.5.0** + 矩阵收窄 7/23 / PRD 39 条）｜ v1.9 出口改为恒定列（对齐 Spec AC-15，含未超窗）、补「失败方向安全」判据、门禁脚本 `check_doc.py` 落地 ｜ v1.10 门禁加自测与变异测试、加「跳过代码块」「表头 vs 分隔行」「反引号切断」三条判据 ｜ v1.11 新增 §10.6「错误读取单点封装」 ｜ **v1.12 AC-17 落地：403/404 迁进信封，`parseApiError` 加 `status`（401 无 `code`）、`ErrorCode` 按 `ErrorCodeCatalog` 全 13 码穷举、标注大小写不一致陷阱；门禁改为「先自检再他检」（`main()` 与 `--all` 都被闸门拦，EXIT=2 拒绝出报告），用例单一来源 ｜ v1.13 新增团队规则 **R3：在别人正在编辑的文件上不报绝对数字**（同一文件三段统计得到 40/41/42 张表，架构师同时段报 39——差异在快照不在判据）**
> 上游：`prd.md`（PM 范围锁定）、`ADR-076` §4/§9
> 本文所有结论均基于对 `apps/web` 与 `apps/api` 的**实际代码勘查**，每条都附文件路径与行号。未勘查的项不写入。
>
> **设计寄存器**：Product（产品型界面，标杆是"赢得熟悉感"，不是"制造惊叹"）
> **三轴刻度**：`DESIGN_VARIANCE=4`（克制，不玩非对称）/ `MOTION_INTENSITY=3`（功能性动效，150ms 收敛）/ `VISUAL_DENSITY=6`（台账偏密集，队列偏留白）
>
> **编号口径**：PRD 的 EARS 编号已重排过一次（PM 告知 E31→E28、E28→E29、E29→E30、E30→E31），随后又增补到 37 条。因此本文**易变的验收项一律用「PRD 章节 + 名称」引用，不引用 E 编号**，避免评审时对不上号。
> 例外：`E26`（Agent 决策链越权 / P0）、`E27`（Agent 过滤服务端化）、`E33`（状态矩阵服务端强制）、`E34`（写入原子）、`E35`（裁决不得改选）、`E36`（执行幂等与失败回写）这六条保留编号——它们已成团队词，且**直接约束前端实现**，评审时写编号更容易对上。
> **引用约定（行号会漂移，别把它当主键）**：本文所有 `文件:行号` 都是**核实当时的快照**，上游文档一改就失效——实测 `prd.md` 在一次改动后，`## 13.` 从 807 行漂到 805 行。所以**检索主键是「章节号 + 章节名」或「字段名」**，行号只是"当时在这里"的辅助。看到行号对不上时，先按名称找，不要以为引用错了。
> 同理，本文门禁脚本（`check_doc.py`）每次**现读**上游文件取实时行号，避免它自己也变成过期信息。
>
> 但**编号作辅助，名称作主键**：上列六条每次出现都必须同时写出名称（如"E33 状态矩阵服务端强制"），**不允许只写编号**。理由与本文不引用其余 E 编号同源——PRD 已改过三轮、架构 Spec 也踩过编号漂移，只写编号的引用到第四轮就指向不明，而名称不会变。

---

## 1. 图标库锁定

### 结论

**锁定 `@ant-design/icons` v6.1.1，全项目唯一，不混用、不新增。**

### 证据

| 证据 | 位置 | 说明 |
|---|---|---|
| 依赖声明 | `apps/web/package.json` → `"@ant-design/icons": "^6.1.1"` | antd 6 官方配套，零新增依赖 |
| 使用广度 | 全仓 **187 个** `.ts/.tsx` 文件 import 该库 | 已是事实标准 |
| 无竞争库 | `grep -rl "lucide-react\|react-icons\|@heroicons\|@tabler/icons"` 返回 **0 结果** | 不存在多套混用 |
| 唯一内联 `<svg>` | `modules/semantic-admin/pages/PipelineRunsPage.tsx:291` | 是气泡图数据可视化，**不是功能图标**，不构成图标库混用 |
| 菜单图标以字符串形式存储 | `apps/api/.../menu_config/seeds/seed_four_steps.py:250` → `"FundOutlined"` | 后端菜单存的就是 antd 图标名，前端按名映射 |

**判定：图标系统无混用，无需统一整改。** 这一点比预期干净——`@ant-design/icons` 是 React 组件形式的 SVG 图标，满足"统一描边、可矢量缩放、语义明确"，不是字体图标也不是 emoji。

### 图标尺寸规范（全项目一致）

| 场景 | 尺寸 | 决策模块典型用法 |
|---|---|---|
| 行内（跟随正文） | **16px** | 状态标签内的小图标、表格单元格内的提示图标 |
| 按钮内 | **20px** | 采纳 / 驳回 / 批量操作的按钮图标（antd `Button` 默认已按此规则） |
| 独立图标（工具栏、空态） | **24px** | 卡片头部操作、空态主图、筛选区图标 |

### 决策模块图标语义映射（全部来自 `@ant-design/icons`）

| 语义 | 图标组件 | 尺寸 | 用于 |
|---|---|---|---|
| 待裁定 | `ClockCircleOutlined` | 16 | 队列状态标签 |
| 待执行确认 | `SyncOutlined` | 16 | 队列状态标签、执行状态列 |
| 执行成功 | `CheckCircleOutlined` | 16 | 台账结果列、详情页 |
| 部分成功 | `MinusCircleOutlined` | 16 | 台账结果列 |
| 执行失败 | `CloseCircleOutlined` | 16 | 台账结果列、错误提示 |
| 已驳回 | `StopOutlined` | 16 | 台账结果列 |
| 采纳动作 | `CheckOutlined` | 20 | 队列卡片主按钮 |
| 驳回动作 | `CloseOutlined` | 20 | 队列卡片次按钮 |
| 查看详情 | `EyeOutlined` | 20 | 队列卡片、台账行操作 |
| 证据不完整提示 | `WarningOutlined` | 16 | 证据数列、影响面板 |
| 时间范围筛选 | `CalendarOutlined` | 16 | 筛选区 |
| 筛选 | `FilterOutlined` | 20 | 筛选区容器 |
| ~~导出~~ | ~~`DownloadOutlined`~~ | — | **本期不渲染**（已降 P1，契约 `api-spec.yaml:22` 已移除 `/export.csv`）。映射关系保留在此备查，恢复时直接用。**按钮整个不渲染，不做 `disabled`、不做"暂不支持"提示**（§11 第 24 条） |
| 复制决策 ID | `CopyOutlined` | 16 | 台账 ID 列 |
| 刷新 | `ReloadOutlined` | 20 | 工具栏（`AdvancedTable` 已内置，`AdvancedTable.tsx:17`） |
| 因果链 | `PartitionOutlined` | 24 | 详情页区块标题 |
| 先例 | `HistoryOutlined` | 24 | 详情页区块标题 |
| 影响分析 | `ApartmentOutlined` | 24 | 详情页区块标题 |
| SLA 已超时 | `FieldTimeOutlined` | 16 | 队列等待时长 |
| 批量操作 | `CheckSquareOutlined` | 20 | 队列批量工具栏 |

---

## 2. Design Token 引用表

### 2.1 Token 来源（勘查结论）

项目是**双轨 Token 体系**，两层都必须尊重：

| 轨道 | 定义位置 | 作用域 | 证据 |
|---|---|---|---|
| **CSS 变量轨** | `apps/web/src/modules/shared/styles/global.css` | 自定义 `--odap-*` 变量，含浅色（`:root`）与深色（`[data-theme="dark"]`）两套 | `global.css:30-140`（浅色）、`:147-177`（深色） |
| **antd ConfigProvider 轨** | `AdminLayout.tsx:653-690`（`antdThemeConfig`）、`AgentLayout.tsx:117-137` | antd 组件内部 token，按当前 `colorTheme` + `theme` 动态生成 | `/decisions` 被 `AdminLayout` 包裹，见 `App.tsx:243-249` |
| **动态调色板** | `modules/shared/styles/colorThemeUtils.ts:20-101` | 6 套配色（indigo/blue/green/violet/amber），运行时写入 `<html>` 的 `--odap-color-primary-*` | `applyColorTheme()` 在 `colorThemeUtils.ts:119` |

**因此组件的取色规则有两条，不可混用：**

- 非 antd 元素（自定义 div、G6 画布、CSS 类）→ 用 `var(--odap-*)`
- antd 组件内部 / 需要跟随主题的运行时计算值（如 G6 节点填充）→ 用 `theme.useToken()` 返回的 antd token

### 2.2 决策状态 → 语义 Token 映射表

> **全部写 token 名。本文档不出现任何硬编码色值。**
>
> **色系约束（PM §三 定调）**：结果标签只允许 **4 个色系**（success / warning / error / 中性），"待定"是**一类**，其下的"待裁定 / 待执行确认"是**细分文案**，不占独立色系。

| 结果标签（列内展示文案） | 前景 | 背景 | 边框 | 图标（非颜色冗余） |
|---|---|---|---|---|
| **执行成功** | `--odap-color-success` | `--odap-color-bg-tertiary` | `currentColor` | `CheckCircleOutlined` |
| **部分成功** | `--odap-color-success` | `--odap-color-bg-tertiary` | `currentColor` | `MinusCircleOutlined` |
| **执行失败** | `--odap-color-error` | `--odap-color-bg-tertiary` | `currentColor` | `CloseCircleOutlined` |
| **待定（待裁定）** | `--odap-color-warning` | `--odap-color-bg-tertiary` | `currentColor` | `ClockCircleOutlined` |
| **待定（待执行确认）** | `--odap-color-warning` | `--odap-color-bg-tertiary` | `currentColor` | `SyncOutlined` |
| **已驳回** | `--odap-color-text-secondary` | `--odap-color-bg-tertiary` | `--odap-color-border` | `StopOutlined` |

**"待定"为什么两细分同色**：PM 明确"待定是一类，括号内是细分文案，不要新增第六种状态色系"。两细分靠**图标 + 括号内文字 + 队列分组标题**三重区分，不靠颜色。这比给"待执行确认"单独一个色系更抗色觉障碍——色觉障碍用户读到的是"待定（待执行确认）"，色盲用户也一样。

> 表格有 6 行但只有 **5 类标签**：后两行同属"待定"一类，只是括号内细分不同。

**"部分成功"为什么与"执行成功"同色**：部分成功是**已完成**的结果（不是待办、不是失败），归入 success 语系合理；与"执行成功"靠图标（`MinusCircleOutlined` vs `CheckCircleOutlined`）+ 完整文字区分。这样避免为"部分成功"单开第三档黄色——**现有代码里它用的是 antd `lime`，与 `green` 肉眼几不可辨（`types.ts:70-71`），这才是真正的"色系混乱"**。

**"已驳回"为什么用中性色而不用错误色**：驳回是**合规的决定**（可能是策略门禁拒绝，也可能是人判断不该做），不是系统故障。用错误色会让台账整屏飘红，掩盖真正的执行失败。这是一个刻意的语义区分。

**`--odap-color-info` 保留给"执行状态"列，不进结果标签**：执行状态（排队/校验中/执行中/已批准）是**过程态**，与结果态是两个正交维度、分列展示（§4.6），沿用 info 蓝色表达"正在进行中"不构成 5 类结果的色系混乱。

### 2.3 影响完整度 → 语义 Token 映射表

> **注意（与任务书口径不同）：`impact_completeness` 实际是 3 个值，不是 2 个。**
> 证据：`modules/decision/types.ts:59` → `'full' | 'degraded_target_resolution' | 'partial'`
> PM 任务书按 partial/full 两态表述，此处按代码事实修正为三态。

| 值 | 前景 | 容器 | 图标 | 文案（见 §6.3） |
|---|---|---|---|---|
| `full` | `--odap-color-success` | `--odap-color-bg-tertiary` | `CheckCircleOutlined` | 影响分析完整 |
| `degraded_target_resolution` | `--odap-color-warning` | `--odap-color-bg-tertiary` | `WarningOutlined` | 目标解析降级 |
| `partial` | `--odap-color-warning` | `--odap-color-bg-tertiary` | `WarningOutlined` | 影响分析不完整 |

`degraded_target_resolution` 与 `partial` 同色不同文案——因为二者的**用户行动不同**（前者是"目标实体没解析出来"，去查数据；后者是"强影响维度未落地"，等 ADR-074），靠文案而非颜色区分，符合"不只靠颜色传达含义"。

### 2.4 通用 Token 引用表（组件层）

| 用途 | Token | 备注 |
|---|---|---|
| 页面背景 | `--odap-color-bg-secondary` | 由 `AgentLayout.tsx:161` 统一设置，决策页不再重复设置 |
| 卡片 / 面板背景 | `--odap-color-bg-primary` | |
| 三级表面（标签底、斑马行） | `--odap-color-bg-tertiary` | |
| 主文本 | `--odap-color-text-primary` | |
| 次文本（描述、辅助） | `--odap-color-text-secondary` | |
| 三级文本（元数据、占位） | `--odap-color-text-tertiary` | |
| 禁用文本 | `--odap-color-text-disabled` | |
| 表格行分隔 | `--odap-color-border-light` | |
| 卡片 / 输入框边框 | `--odap-color-border` | |
| 品牌强调（每屏 ≤2 处） | `--odap-color-primary` | 仅用于：① 当前选中视图的 Tab 指示 ② 主操作按钮 |
| 低置信度警示文字 | `--odap-color-warning` | 置信度 < 60% |
| 置信度数字 | `--odap-color-text-primary` + `font-variant-numeric: tabular-nums` | 等宽数字防跳动 |
| 间距 | `--odap-spacing-xs`(4) / `-sm`(8) / `-md`(16) / `-lg`(24) / `-xl`(32) | **只用这 5 档**，均为 4px 整数倍 |
| 圆角（卡片） | `--odap-radius-md` (8px) | 不超过 12px，避免"Ai 过度圆滑" |
| 圆角（标签） | `--odap-radius-sm` (6px) | |
| 圆角（头像/圆点） | `--odap-radius-round` | |
| 阴影（默认） | 无 | 用 1px `--odap-color-border` 表达层级，不用阴影 |
| 阴影（浮层） | `--odap-shadow-md` | 仅 Popover / Dropdown / 抽屉 |
| 字号 | `--odap-font-size-xs`(11) / `-sm`(12) / `-base`(14) / `-lg`(16) / `-xl`(20) / `-2xl`(24) | 台账正文用 `-sm`(12)，因密度高；队列卡片正文用 `-base`(14) |
| 字体族 | `--odap-font-family`（DM Sans 栈）| 项目已配置，不引入新字体 |
| 等宽（决策 ID、耗时） | `--odap-font-family-mono`（JetBrains Mono 栈） | |
| 动效时长 | `--odap-transition-fast`（150ms `--odap-ease-out`） | **决策模块唯一允许的过渡时长** |
| 过渡缓动 | `--odap-ease-out` | 禁止使用 `--odap-ease-spring`（详见 §9.2） |

### 2.5 antd 侧 token（用于 G6 画布与需要运行时取色的场景）

```ts
// 仅在需要"跟随主题的运行时颜色值"时使用（G6 画布 fill、动态 style）
const { token } = theme.useToken();
// token.colorPrimary / colorSuccess / colorWarning / colorError / colorInfo
// token.colorTextSecondary / colorTextTertiary / colorBorder
```

这是替换 `DecisionChainGraph.tsx:14-20` 硬编码色值的**正确做法**（详见 §6.2）。

### 2.6 状态标签的落地方式（不允许 JS 里写色值）

新建 `modules/decision/components/DecisionStatusTag.tsx` + `DecisionStatusTag.css`：

```css
/* 色值全部走 CSS 变量，JS 侧只传状态枚举 */
.dsi-status { display:inline-flex; align-items:center; gap: var(--odap-spacing-xs);
  padding: 0 var(--odap-spacing-sm); height: 22px;
  border: 1px solid currentColor; border-radius: var(--odap-radius-sm);
  background: var(--odap-color-bg-tertiary);
  font-size: var(--odap-font-size-xs); line-height: 1; white-space: nowrap; }
.dsi-status--success      { color: var(--odap-color-success); }
.dsi-status--partial      { color: var(--odap-color-success); }
.dsi-status--failure      { color: var(--odap-color-error); }
.dsi-status--pending      { color: var(--odap-color-warning); }
.dsi-status--rejected     { color: var(--odap-color-text-secondary); border-color: var(--odap-color-border); }
```

`--partial` 与 `--success` 同色是有意为之（PM 定调：结果只允许 4 个色系）。两者的 CSS 类分开保留，是为了将来若要给"部分成功"加独立视觉时只需改一行，不必回头改组件。

**组件签名**（契约 `api-spec.yaml:631-641` 已写死映射函数名）：

```ts
// 唯一映射入口：吃两个字段，吐 5 类标签 + 1 个修饰类
type DecisionStatusTagProps = {
  status: DecisionStatus;          // 6 值
  outcome?: DecisionOutcome;       // 5 值，可空
  statusAssumed?: boolean;         // true → 右侧补"历史数据"标注（§5.1.5）
  size?: 'sm' | 'md';
};
```

`status='pending'` 与 `status='decided'|'executing'` 都映射到 `--pending` 类（同色），靠**文案的括号细分 + 图标**区分（§2.2）。**不要为"待执行确认"再加一个 CSS 类**——加了就等于承认它是第五个色系，与 PM 定的口径冲突。

`statusAssumed` 只影响是否渲染那枚说明文字，**不影响标签颜色**——历史数据不是第七种状态（§5.1.5）。

**为什么不用 `Tag color="green"`**：antd 预设色名绕过 Token 体系，且不随 `colorTheme` / 深色模式切换。这正是现有 `types.ts:68-74` `OUTCOME_META` 的问题（详见 §9.2）。

---

## 3. 信息架构

### 3.1 结论：改造现有页面 + 新增 2 个子路由，**不新增菜单项**

```
/decisions                    → 重定向至 /decisions/ledger（兼容既有书签）
/decisions/queue              → 视图一：待决策队列
/decisions/ledger             → 视图二：决策台账（默认视图）
/decisions/detail/:decisionId → 视图三：决策详情（子路由，承载现有三组件）
```

对应代码：
- `AppRoutes.tsx:117` 现有 `<Route path="/decisions" element={<DecisionIntelligencePage />} />` 改为 4 条
- `modules/decision/index.ts` 增加 `DecisionQueuePage`、`DecisionLedgerPage`、`DecisionDetailPage` 导出
- 现有 `DecisionIntelligencePage.tsx` **拆解**：三组件下沉进 `DecisionDetailPage`，页面壳废弃

### 3.2 为什么是子路由而不是新增 3 个菜单项（关键理由）

**菜单是后端驱动的**——证据：
- `AdminLayout.tsx:425-426` `allMenus` 由 static + dynamic menu 合并
- `apps/api/.../menu_config/seeds/seed_four_steps.py:250` 决策智能菜单在后端 seed 里定义，`parent="dir:simulate"`，`sort_order=1`

三个一级菜单项 = 三次后端 `menu_config` seed 变更 + 一次数据迁移，收益只是"少点一次"。**代价大于收益，故不采用。**

改用路由内一级视图切换（`Segmented` 或 `Tabs`），菜单仍是「决策智能」一项，`sort_order=1` 不动。

### 3.3 决策详情为什么不是第三个 Tab

| 方案 | 问题 |
|---|---|
| 三个平级 Tab | 详情需要 `decisionId` 作为主语；Tab 无法携带可变主键，只能"先选一条再去第三个 Tab"，产生一个语义空洞的中间态 |
| **子路由（选定）** | 可深链接、可分享、可从先例卡片/影响面板/台账/队列四路进入；浏览器返回键语义正确 |

**三视图的实际形态**：

```
┌─ 决策智能 ──────────────────────────────────────────────┐
│  [待决策队列 12]  [决策台账]              ← Segmented，两项  │
│                                                          │
│  /decisions/queue      /decisions/ledger                 │
│                                    │                     │
│                          点击行/卡片 │                     │
│                                    ▼                     │
│                        /decisions/detail/dec_xxxxxxxx    │
│                        （整页，带面包屑返回来源视图）        │
└──────────────────────────────────────────────────────────┘
```

### 3.4 与既有 `/decisions` 页面的关系

**是拆解复用，不是废弃。**

| 现有资产 | 去向 | 改动 |
|---|---|---|
| `DecisionIntelligencePage.tsx` 页面壳（16-79 行的 ID 输入框 + 查询按钮） | **废弃** | 决策 ID 不再是入口（PM §2 核心问题陈述：用户手上没有 ID）。深链接能力由 `/decisions/detail/:id` 承接，URL 即入口 |
| `DecisionIntelligencePage.tsx:81-125` 三栏布局 | **保留结构**，迁入 `DecisionDetailPage` | 布局不变（`Row gutter=16` + `Col 14/10`）|
| `DecisionChainGraph` | 复用 | 需修硬编码色值（§6.2） |
| `PrecedentSearch` | 复用 | 需要 `initialQuery` + `autoSearch` 两个可选 prop（§6.2） |
| `ImpactPanel` | 复用 | 需要 3 态完整度文案（§6.3） |
| `DecisionIntelligencePage.tsx:88-116` 决策详情 `Descriptions` | 迁入详情页 | 需要增加"裁决人 / 裁决时间 / 驳回理由 / 来源入口 / 执行动作"五行 |

**保留 ID 输入框的降级入口**：在 `/decisions/ledger` 工具栏放一个"按 ID 直接打开"的次要按钮（`Input.Search` 收在 `Dropdown`/`Popover` 里），供本体工程师调试用，但**不作为页面主视觉**。

### 3.5 Agent 页决策 Tab 的收敛（PM §13 问题 Q5）

**PM 倾向**：保留 Tab、换数据源、Tab 内复用台账组件。**我同意方向，但"换数据源"不是换个 URL 就行**——两边的数据根本不是同一种对象。

#### 勘查到的事实（比 PM 描述的更严重）

| # | 事实 | 证据 |
|---|---|---|
| 1 | Agent 决策服务是**进程内单例 + 内存字典**，重启即失，且**不按工作空间分区** | `apps/api/odap/biz/core/agent/services/decision_service.py:19-24` → `self._decisions: Dict[str, DecisionChain] = {}`，`__new__` 单例 |
| 2 | 数据形状是 `DecisionChain`（含 `steps` / `task_id` / `steps_count`），**不是** ADR-076 的 `DecisionRecord` | `AgentPage.tsx:51-72` 的 `decisionColumns`：`ID / Task / Steps / Created` 四列，与台账 10 列无一处重合 |
| 3 | 前端调用**故意没传 workspace_id** | `AgentPage.tsx:47-49` → `loadDecisions(undefined, 1, 20)` |
| 4 | 分页协议不同 | `agentApi.ts:80-88` 用 `page` / `page_size`；台账用 `limit` / `offset` |
| 5 | Tab 文案是英文，与其他页面中文不一致 | `AgentPage.tsx:131-136`：`Decisions` / `Decision Records` / `Refresh` |

**第 1 + 3 条合起来是安全问题**：内存单例不分区 + 前端不传 workspace，意味着任何登录用户在这个 Tab 里可能看到**其他工作空间的 Agent 决策步骤**。这不是设计问题，但必须在收敛时一并解决——**我把它写在这里是因为 PM 的 A4"单一数据源"如果不含这一条，收敛完仍然会漏数据**。

> 这条后来被 PM 核实并**加重了一层**（单条与链详情是 IDOR，不止列表泄露），已升级为 PRD 的 G6 / P0 缺口 E26。详见本节末「安全缺口不止列表」。

#### 设计结论：拆成两个东西，不是一个 Tab 换源

Agent Tab 里现在混着**两种不同粒度**的信息：

- **列表粒度**：有哪些决策 → 这属于台账，应该复用
- **单条内部粒度**：这条决策的推理走了 observe/orient/decide/act 哪几步 → 这是详情页的一个区块，不该占列表位

因此：

| 现状 | 收敛后 | 落点 |
|---|---|---|
| Agent Tab 的「Decision Records」表（4 列，内存源） | 改为「该 Agent 产生的决策」表，**复用台账的列定义与组件**，数据走 `GET /api/decisions?agent_id=<当前Agent>` | 仍在 Agent 页 Tab 内，但组件来自 `modules/decision` |
| `DecisionTimeline`（推理链步骤时间线） | **本期不迁移、不下沉**。它随 Agent Tab 一起隐藏，不进详情页 | 留在 `modules/agent` 原位置；理由见本节末「推理路径区块：本期不做」 |
| `getDecision` / `getDecisionChainDetail`（`agentApi.ts:75-78`） | 保留（推理步骤是 Agent 专有能力），但**detail 接口改为按 `decision_id` 读权威存储**，不再读内存单例 | 后端改造 |

#### 复用台账组件的组件化要求（这是对前端的具体约束）

台账**不能写成页面**，必须拆成「页面壳」+「可复用表」两层，否则 Agent Tab 里塞不进去：

```
modules/decision/
├── components/
│   ├── DecisionLedgerTable.tsx      ← 纯表格：props = { filters, onFilterChange, agentId?, embedded? }
│   ├── DecisionFilterBar.tsx        ← 纯筛选区：props = { value, onChange, compact? }
│   └── DecisionStatusTag.tsx        ← 状态标签
├── pages/
│   ├── DecisionLedgerPage.tsx       ← 页面壳：面包屑 + 视图切换 + 组合上面两个
│   └── DecisionQueuePage.tsx
```

- `DecisionLedgerTable` 接受 `agentId?: string`，传了就加 `agent_id` 过滤条件
- `embedded?: boolean`（默认 `false`）：为 `true` 时隐藏面包屑，列宽按容器自适应。（原"隐藏导出按钮"一条随导出降 P1 失效——按钮本身本期就不渲染了。）
- **Agent Tab 内不重复实现筛选区**，直接放 `DecisionFilterBar compact` + `DecisionLedgerTable embedded`

#### Agent Tab 的降级形态（因为它嵌在 Tab 里，容器更窄）

| 差异 | 台账页 | Agent Tab 内 |
|---|---|---|
| 列 | 10 列全显 | 6 列：ID / 问题 / 推荐方案 / 结果 / 置信度 / 创建时间（其余进列设置） |
| 筛选区 | 完整 6 控件 | `compact`：时间范围 + 结果 + 关键词，其余收进"更多筛选" |
| 导出 | **本期均无**（P1，整块不渲染） | **本期均无** |
| 分页 | 20/50/100 | 固定 10（Tab 内空间有限） |
| 行点击 | 跳详情 | **跳详情**（同上，Agent 页内不再弹小窗） |

#### 顺带修掉的文案不一致

Agent Tab 的 `Decisions` / `Decision Records` / `Refresh` 三个英文串改为中文，与全站一致（PRD §10 i18n 要求：文案走既有 i18n 机制）。这不在我本期视觉范围内，但既然要动这个 Tab，一起改成本最低。

#### 安全缺口不止列表：单条与链详情是 IDOR（PM 核实后升级为 G6 / E26）

我最初只从"前端不传 workspace"这条线摸到列表泄露。PM 顺这条线往下多走一步，核出了更严重的一层——**这两个接口连 workspace 参数都不存在**：

| 端点 | 现状 | 缺口性质 |
|---|---|---|
| `GET /api/agent/decisions/{decision_id}`（`decision_routes.py:13-23`） | 入参只有 `decision_id` + `Depends(get_current_user)`；调 `decision_service.get_decision(decision_id)` → `self._decisions.get(decision_id)`（`decision_service.py:44-45`）**纯主键查字典，无任何归属校验** | **IDOR**：凭 ID 即可读任意工作空间的决策详情 |
| `GET /api/agent/decisions/{decision_id}/chain`（`decision_routes.py:26-36`） | 同上，读 `get_decision_chain(decision_id)`（`decision_service.py:60-61`）**同样纯主键** | **IDOR**：推理步骤流水一并泄露 |
| `GET /api/agent/decisions`（`decision_routes.py:39-51`） | `workspace_id: Optional[str] = None` 透传给 `list_decisions`，其内部 `if workspace_id:`（`decision_service.py:85`）——**假值即不过滤，返回全量** | 空上下文 → 全空间列表 |

**加重情节**：`get_decision` 的返回体里带 `workspace_id` 字段（`decision_service.py:54`），所以泄露不只是"能读到别人的决策"，还包括**能反查该决策归属哪个工作空间**，跨租户映射因此可行。

#### 修复不接受"前端补传 workspace"（我原先的兜底建议是错的，已废弃）

我在上一版 §3.5 结尾写过"若超范围，至少要满足 Agent Tab 的 `loadDecisions` 补传 `workspace_id`"。**这条建议作废。** 理由（与 PRD §8.7 E26 一致）：

- 客户端传 workspace 本身就是 ADR-076 §7 明令禁止的信任模型。补传只是把"空上下文返回全量"改成"**伪造上下文读别人空间**"，漏洞性质没变；
- 对两个 IDOR 接口而言，**没有 workspace 参数可传**，前端补传根本够不到。

**修复基础设施其实已经就绪，这个 router 只是没接上**（这点值得写进文档，能显著降低修复成本估算）：

| 已有能力 | 位置 | 行为 |
|---|---|---|
| `get_current_workspace` | `odap/infra/security/workspace_access.py:154` | 从 JWT 的 `workspace_id` → `ws_id` 解析；**缺失即 422（fail-closed）**，符合 ADR-076 §7 非空拒绝决议 |
| `assert_workspace_access` | 同文件 `:34` | 非 admin 指定他人 workspace → 403；非 admin 未指定 → **强制回落到归属空间** |

而在 `decision_routes.py` 中，`get_current_workspace` 的出现次数是 **0**（已 grep 确认）。所以正确修法是给三个端点加 `workspace_id: str = Depends(get_current_workspace)`，并把该值下推到 service 的查询与主键校验里——**不是新建安全机制，是补上已有机制**。

#### `task_id` 放详情页，不占台账列

`task_id` 是 Agent 链路特有的关联键（`AgentPage.tsx:60-65` 现有四列之一是 `Task`）。台账 10 列已经很挤（总宽约 1580px），**不为它再加第 11 列**。改为放进详情页 `Descriptions`（§6.4 已补该行），且仅当该决策由 Agent 产生时渲染。

#### 落地时序：不留中间态，因此不产出维护态设计

**项目总监已裁定：E26 的中间态为「Tab 直接隐藏」，不做维护态页面。**

这条裁定对设计稿的影响是**减法**，需要写清楚，否则前端会自己脑补一版：

| 情形 | 处理 |
|---|---|
| Agent 页决策 Tab 在接口收口完成前 | **整块隐藏**，不渲染 Tab 标签、不渲染"功能升级中"占位、不渲染"即将上线"文案 |
| Tab 隐藏后 Agent 页的 Tab 数量 | 由 `AgentPage.tsx:131-136` 现有 Tab 列表自然减少，**不新增任何填补项**（不为了视觉对称补一个空 Tab） |
| 决策数据在中间期从哪里看 | 从 `/decisions/ledger` 看。台账是最终形态，不依赖 Agent 页 Tab 是否上线 |
| 本设计稿的 §3.5 内容定位 | **最终态**，不是过渡态。Tab 恢复时直接按本节的「Tab 内嵌台账表」实现（推理路径区块不在本期范围），中间不需要再出一版设计 |

**为什么不设计"该功能正在维护"页面**（记录理由，避免后续被要求补）：批次 A 把"数据源统一 + 接口收口"放在同一批完成，**中间不存在"Tab 还在但接口已下线"的窗口期**。为一个不存在的窗口期设计一个页面，等于凭空造一个只活几小时的界面，还要额外承担它的文案、空态、错误态与可访问性验收——成本全在，收益为零。

**推理路径区块：本期不做（team-lead 裁定，推翻我原提案与架构的实装意愿）。**

我原以为这是"契约有就能做"，team-lead 的裁定给了另一个判据，我认同：**`/{id}/reasoning-steps` 虽已进契约（`api-spec.yaml:474-540`），但不在本批实现范围**；而详情页已有因果链图承载"这条决策为什么这么来"，推理路径属**增强**，不是主链。为一个增强项占排期、再承担它自己的空态/错误态/上限态（单决策 200 条上限）验收，性价比不成立。

所以设计侧按**减法**处理，且不留任何痕迹：

| 项 | 处理 |
|---|---|
| 详情页"推理路径"区块 | **整块不渲染**。不留折叠面板、不写"暂无"、不写"即将上线"、不占版面位置 |
| 左侧 14 栏的内容 | 只有因果链图 + `Descriptions`（§6.1 已相应调整） |
| `DecisionTimeline` 组件 | 暂不下沉，仍留在 Agent 页原位置随 Tab 隐藏（§3.5 落地时序） |
| Agent 页 Tab 收敛范围 | 只做**内嵌台账表**这半边；"推理步骤独立区块"不做 |
| 契约里的 `reasoning-steps` | 本期无消费方。**契约不删**（后续要用），但设计稿不引用它，避免前端误以为有活要干 |

**为什么连"暂无"都不写**：写"暂无"等于告诉用户"这里本该有内容但坏了"，而事实是"这块本期不做"。**前者是产品缺陷的暗示，后者只是范围决定。** 用户不该为我们的排期看见一个洞。这条与 §11 第 24 条「宁可不渲染，不留空壳控件」是同一条纪律的两面。

---

## 4. 决策台账页（`/decisions/ledger`）

### 4.1 实现载体

**必须用项目既有的 `AdvancedTable`**（`modules/shared/components/AdvancedTable.tsx`），不自建表格。

证据：
- 全仓 **54 个**文件使用 `AdvancedTable`
- 它已内置刷新 / 密度 / 列设置 / 全屏 / 列宽拖拽（`AdvancedTable.tsx:261-270`），`search={false}`（`:601`）——正好适合"筛选区外置"的台账
- 参考既有台账页实现范式：`modules/audit/pages/AuditLog.tsx:33-93`（`limit`/`offset` 分页 + 筛选变更时重置 `current=1`）

### 4.2 列定义

**共 10 列，总最小宽度约 1580px，必须启用横向滚动 `scroll={{ x: 1580 }}`，并固定左侧"决策 ID"列（`fixed: 'left'`）** —— 符合 PRD §10 兼容性要求（"列过多时固定 ID 列并允许横向滚动"）。

| # | 列 | `dataIndex` | 宽度策略 | 对齐 | 可排序 | 说明 |
|---|---|---|---|---|---|---|
| 1 | 决策 ID | `decision_id` | **固定 150px**，`fixed: 'left'`，不换行 | 左 | 否 | `--odap-font-family-mono`，`--odap-font-size-xs`；后跟 16px `CopyOutlined` 复制按钮；点击整行进详情，ID 本身不单独做链接（避免两个点击目标冲突） |
| 2 | 问题 | `context_summary` | **弹性**，`minWidth: 260`，不设 `width`（占满剩余） | 左 | 否 | `ellipsis` 单行 + `Tooltip` 全文；空值渲染"未填写场景描述"（`--odap-color-text-tertiary`）。**执行状态列降 4 档后省出的宽度全部给这一列**（PM 明确建议） |
| 3 | 推荐方案 | `recommended_option` | 弹性 `minWidth: 160` | 左 | 否 | 单行省略 + Tooltip；空值"未给出方案" |
| 4 | 结果 | 派生状态 | **固定 148px**（容纳"待定（待执行确认）"最长文案） | 左 | 否 | `DecisionStatusTag`（§2.6），含图标 + 文字；文案按 5 类标签，待定带括号细分 |
| 5 | 置信度 | `confidence` | **固定 88px** | **右** | **是**（升/降） | `tabular-nums`；`< 60%` 加 `--odap-color-warning` 文字 + "低"字标记；无值"未评估" |
| 6 | 证据数 | 派生 | **固定 132px** | 左 | **否**（降 P1，`sort=evidence_count` 已从契约移除） | 格式 `实体 N + 出处 M`；`M=0` 时该段 `--odap-color-text-disabled` + 16px `WarningOutlined` + Tooltip"出处层证据缺失（覆盖率受限）"。**列照常显示，只是表头不可点**——契约没有这个排序键，加了就是点了没反应 |
| 7 | 执行状态 | 派生 4 档 | **固定 88px**（原 112px，降档后收窄） | 左 | 否 | **4 档**（见 §4.6）：未开始 / 进行中 / 已完成 / 失败或已回滚；无动作显示"无动作"置灰。**精确 8 态只在详情页**，列表不查跨库动作状态（避免 N+1） |
| 8 | 裁决人 | 派生 | **固定 140px**（原 120px，容纳"系统（策略门禁）"） | 左 | 否 | **三种取值 + 历史数据**：`系统（策略门禁）` / `{人名} · 10-22 14:30` / `未处理`（置灰） / `—`（历史数据，无 `status`）。门禁拒绝时必须显示为系统来源，不得显示成人名或空白；历史数据显示 `—` 不显示"未处理"——详见 §4.8 / §5.1.5 |
| 9 | 来源入口 | 派生 | **固定 112px** | 左 | 否 | 值域见 §4.4；缺值"来源未标注"置灰（**不猜测**） |
| 10 | 创建时间 | `created_at` | **固定 148px** | 左 | **是**（默认倒序） | `YYYY-MM-DD HH:mm`，`tabular-nums`；可切换为回填时间（列头 `Dropdown` 切换） |

**对齐原则**：文本左对齐；数值右对齐（置信度）；时间左对齐但启用 `tabular-nums` 保证纵向对齐；状态标签左对齐。

**为什么"问题"列不设固定宽度**：它是唯一的非结构化长文本列，也是用户认决策的主依据（PRD §4.1"用户认决策靠的是当时在问什么"），必须吃掉剩余空间。

### 4.3 筛选区

**筛选区外置在表格上方**（因为 `AdvancedTable` 已 `search={false}`，用其自带搜索表单会与列定义打架）。

| 控件 | 组件 | 默认值 | 交互 |
|---|---|---|---|
| 时间范围 | `DatePicker.RangePicker` + 快捷预设（今天 / 近 7 天 / 近 30 天） | **近 30 天** | 变更即查询；不提供"全部时间"（保护性能，PRD §10 容量要求） |
| 结果 | `Select` mode=`multiple` | 全选 | **6 个选项**（与 PRD §4.2 一致）：待裁定 / 待执行确认 / 执行成功 / 部分成功 / 执行失败 / 已驳回。筛选项按**派生态**给（6 个），展示时归 5 类标签——因为"待定"下两态用户确实要分别筛（一个要他动手、一个只读）。契约 `outcome` 已改为 array + explode（`api-spec.yaml:57-71`），**多选有契约支撑，直接做**；后端做 `n.outcome IN $outcomes`，前端不拼 OR |
| 按 Agent 过滤 | **不出现在筛选栏**，作为隐藏查询参数 | 不启用 | 仅在 Agent Tab 内嵌时由 `agentId` prop 注入（PRD Q8）。理由见下方"为什么 Agent 过滤不做可见筛选器" |
| 来源入口 | `Select`（**单选**） | 不限 | 7 个值域（§4.4）。**注意：契约 `entry_source` 是单值参数**（`api-spec.yaml:72-75`），不是数组——多选是合理诉求但不属本期能力，**不渲染多选控件**，等契约改成 array 再开 |
| 置信度区间 | `Segmented`：不限 / 低(<60%) / 中(60–80%) / 高(>80%) | 不限 | 单选，四选项在认知负荷限内。**契约给的是 `min_confidence` / `max_confidence` 两个 0–1 浮点**（`api-spec.yaml:101-116`），没有 `confidence_band` 枚举——**前端把三档映射成一对 min/max 即可**：低=`max 0.6`、中=`min 0.6 & max 0.8`、高=`min 0.8`。不要求后端加枚举，多加一套枚举等于同一件事两种表达 |
| ~~仅看证据不完整~~ | ~~`Checkbox`~~ | — | **本期不渲染（已降 P1，§10.2.2 E）**。口径未定，上了会返工。**不留灰色占位、不加"暂不支持"文案**——留个死控件比没有更伤信任（§11 第 24 条） |
| 关键词 | `Input.Search`，宽 240px | 空 | 对"问题"+"推荐方案"做包含匹配，忽略大小写；300ms 防抖 |

**筛选区规则**：
- 变更任一筛选 → 重置 `current = 1`（照 `AuditLog.tsx:76` 既有范式）
- 筛选条件**同步到 URL query**（`useSearchParams`），作为 keep-alive 之外的兜底——刷新/分享链接仍可复现视图（PRD §4.2"筛选与排序条件在页面刷新后保持"）
- 筛选区右上角显示"共 N 条，已筛选出 M 条"

**筛选区布局响应式**：≥1280 一行排完（RangePicker 240 + 结果 200 + 来源 180 + 置信度 280 + 关键词 240，合计约 1140 + 间距）；<1280 两行；<768 收进 `Drawer`（底部抽屉）由"筛选"按钮唤起。**注意：证据不完整勾选框移到 P1 后，控件数 5 → 释放 140px，布局反而宽松了**；置信度区间若因契约未到位暂不渲染，同一行会剩 280px 空位，**此时把关键词输入框从 240 撑到 320，不要留空洞**。

#### 6 个人话选项怎么翻译成 `status[]` + `outcome[]`（必须写死，否则前端各拼一套）

契约给的是**两个独立的多值参数**（`status` 数组 + `outcome` 数组，语义是 `AND`），而界面上 6 个选项是**人话结果**，其中"执行成功/部分成功"两者同为 `status=executed`、只差 `outcome`。所以翻译规则必须显式定义：

| 界面选项 | 是否选中 | 写入 `status[]` | 写入 `outcome[]` |
|---|---|---|---|
| 待裁定 | 选中 → | `pending` | 不写 |
| 待执行确认 | 选中 → | `decided`, `executing` | 不写 |
| 执行成功 | 选中 → | `executed` | `success` |
| 部分成功 | 选中 → | `executed` | `partial_success` |
| 执行失败 | 选中 → | `failed` | 不写 |
| 已驳回 | 选中 → | `rejected` | 不写 |

**拼装规则三条**：

1. `status[]` = 所有选中项贡献的 status 值**去重并集**。
2. `outcome[]` = **仅当"执行成功"或"部分成功"至少一个被选中时**才传；否则整个参数不传。理由：传了 `outcome` 就等于对非 `executed` 记录施加了额外约束，会把本来就该出现的 `failed` / `pending` 记录筛掉。
3. 映射集中在一个函数 `toLedgerQuery(displayStatuses)`，与 `toDisplayLabel` **放在同一个文件、方向相反**——**正反两个方向必须成对维护**，改一个必须看另一个。

> **必读前提（本节唯一的强依赖）：筛选翻译的正确性建立在「E33 状态矩阵服务端强制」之上，不是独立的。**
>
> `status[]` 与 `outcome[]` 是 `AND` 语义，所以"执行成功 + 执行失败"会翻译成：
> ```
> status IN (executed, failed) AND outcome IN (success)
> ```
> 它之所以能得出正确结果，是因为**矩阵保证 `failed` 记录不可能带 `outcome=success`**——若 `(failed, success)` 合法，上面这个 AND 就会把"执行失败"的记录一起捞进"执行成功"的筛选结果里。
>
> 所以 E33 状态矩阵服务端强制**不只是后端的数据洁净约束，它同时是这条筛选翻译的正确性前提**。矩阵未落地或失效时，这个筛选会**静默给出错误结果**（少返回或多返回），接口 200、页面无报错、用户看不出错——这比页面报错严重得多。
>
> **可测的验证方式（不靠人眼）**：对同一份种子数据，分别按 6 个人话选项各筛一次，逐条比对「返回记录的 `toDisplayLabel()` 结果」与「所选选项」是否**完全一致**（双向：返回集内无他项，他项集内无返回项）。这条断言不通过，就说明矩阵或翻译规则有一处失效。
>
> 换言之：这不是"前端多写个兜底"能解决的问题——**前端无法从结果集反推出自己筛错了**。唯一的修法在矩阵。

**这是我不改用"后端收人话枚举"方案的原因**：让后端收 `display_status` 会让前端简单，但等于把 6 个界面文案固化进接口——文案一改就要动接口。当前这套翻译的复杂度可控（一个 20 行纯函数 + 一张测试表），而它依赖的矩阵本来就必须落地。

#### 为什么"按 Agent 过滤"不做可见筛选器（回 PRD Q8）

**采纳 PM 倾向：隐藏参数，不露出筛选器。** 但补一条实施细节，否则会出问题：

- **不出筛选器**：业务决策者不按 Agent 想问题；筛选栏已有 5 个控件（证据不完整移 P1 后），再加一个就到 6，逼近工作记忆边界且 `agent_id` 是内部实现概念，露出来会诱导用户把它当业务维度。
- **但内嵌时必须"可见"**：Agent Tab 里表格被 `agentId` 隐式过滤后，用户看到的是"只有 3 条"，若界面上没有任何提示，他会以为**台账漏数据**。所以 `embedded` 模式下，筛选区左上角固定显示一枚**不可移除的语境标签**："当前仅显示 {Agent 名} 产生的决策"，右侧一个"查看全部决策"链接（跳 `/decisions/ledger`）。

**一句话**：过滤条件对用户隐藏，但**过滤这个事实必须对用户可见**。隐藏的是控件，不是状态。

### 4.4 来源入口值域（7 值，按 api-spec.yaml `DecisionEntrySource`）

> 架构 Spec 定稿为 7 值，比 PRD §4.4 的 5 类多出 `import` 与 `legacy`。**以 api-spec 为准**（PRD 少的两类需要补进 PRD §4.4，已上报）。

| 值 | 展示名 | 备注 |
|---|---|---|
| `qa` | 问答 | |
| `agent` | Agent 决策链 | 注意枚举值是 `agent`，不是 `agent_chain` |
| `pipeline` | 流水线 | |
| `recommendation` | 推荐采纳 | |
| `manual` | 手工录入 | `DecisionRecordCreate.entry_source` 的默认值 |
| `import` | 批量导入 | **本期只要求"能识别、能筛选"，不提供导入界面**——它是将来预留的识别位，不是本期功能。所以筛选下拉里有这一项，页面上没有任何导入入口（PRD 已确认） |
| `legacy` | 来源未标注 | **历史数据兜底**，展示为"来源未标注"并置灰 `--odap-color-text-tertiary`；**不猜测、不归到 manual** |

**未知枚举值的兜底**：接口返回本表外的值时，前端渲染"来源未标注"（与 `legacy` 同款视觉），并在 `console.warn` 一次。**不抛错、不空白、不猜成最接近的已知值**——静默归类会污染"哪条入口真在被使用"的统计。

> 承载字段由架构师定（复用 `decision_method` 还是新增字段）。设计侧只约束：**值域固定、可按来源筛选、缺值显示"来源未标注"**。若架构师选择新增字段，前端 `types.ts` 加一个可选枚举即可，不影响本设计。

### 4.5 加载 / 空 / 错误 / 超大分页

| 场景 | 表现 |
|---|---|
| **加载中（首次）** | `AdvancedTable` 骨架（antd Table `loading` 的骨架态）；**不显示"共 0 条"、不显示空态**——骨架与"暂无数据"绝对不能并存 |
| **加载中（翻页/筛选）** | 表格内容降不透明度至 `0.6` + 顶部 2px 进度条（`--odap-color-primary`），**保持旧数据可见**，避免布局跳动（CLS） |
| **空态 — 本空间无任何决策** | 居中插画位用 24px `PartitionOutlined`（不用大图）；标题"当前工作空间还没有决策记录"；副文案"从问答发起一次决策，它会自动出现在这里"；主按钮"去问答发起第一个决策"（跳 `/qa`）。**不渲染空表格、不显示"共 0 条"** |
| **空态 — 筛选后为空** | 标题"当前筛选条件下没有决策"；副文案列出当前生效的筛选条件摘要；按钮"清除筛选"。与上一种空态**文案与按钮不同**（用户下一步动作不同） |
| **错误 — 列表接口失败** | 表格区域整块替换为错误块：`CloseCircleOutlined`(24px) + "决策台账加载失败" + 错误摘要（不含堆栈，取 `error.message` 前 120 字） + "重试"按钮。**筛选区保持可见可用**，用户可改条件重试 |
| **错误 — 仅计数接口失败** | 列表正常渲染，计数位置显示"共 — 条"，不阻断主任务 |
| **超大分页（>1 万条）** | ① 后端必须返回 `total_is_estimate: boolean`；② `total` 为估算时文案改为"约 N 条（估算）"；③ 分页器 `showSizeChanger` 保留（20/50/100），**关闭"快速跳末页"**，只提供上一页 / 下一页 / 页码输入；④ 页码输入越界时提示"页码超出范围"而非静默跳首页；⑤ `has_more=false` 时立即禁用下一页。**前端绝不全量加载**（PRD §10 容量：按 10 万条设计） |

### 4.6 执行状态列：4 档（列表）+ 精确 8 态（详情）

**PM 裁定：列表降为 4 档，精确 8 态移到详情页。** 理由我认同并补一条设计侧的：

| 理由 | 说明 |
|---|---|
| 性能（PM 给的） | 跨库查真实动作状态会把列表变成 N+1 |
| **认知（我补的）** | 业务决策者在列表里只回答一个问题——"这事在做没有"。8 态里 `校验中`/`已批准`/`排队` 三者的**用户行动完全相同**（都是"等"），拆开只是制造分辨负担 |

**列表 4 档映射**（由 `action.status` 归并，归并逻辑在后端更好；若前端归并，集中在一个函数里）：

| 4 档展示名 | 归并的 8 态 | 颜色 token |
|---|---|---|
| **未开始** | `pending` / `validating` / `approved` | `--odap-color-text-secondary` |
| **进行中** | `executing` | `--odap-color-info` |
| **已完成** | `completed` | `--odap-color-success` |
| **失败或已回滚** | `failed` / `rolled_back` / `rejected` | `--odap-color-error` |

**第 5 个显示值「无动作」——它不是第 5 档，是这一列的空态**：`action_record_id` 为空（决策还没派发执行）时显示「无动作」，`--odap-color-text-disabled`。

为什么必须单独给一个值而不是并入"未开始"：`无动作` = 这个决策**从没派发过**执行；`未开始` = 派发了但还没跑起来。前者用户可以去详情点"发起执行"（`decided` 档就是这么来的），后者只能等。**把两者并成一格，会让"已裁决未执行"的决策在列表里看起来和"正在校验"一样，等于把 PM 要解决的那个漏点又盖回去了。**

档数口径说明：PM 说的"4 档"指**执行进度的分段**，共 4 段；「无动作」是"该维度不适用"，不占段位。设计上它只多一个显示值，不多一个色系。

**PM 已据此改 PRD §4.1（"4 个档位 + 1 个空态"）并留痕记录原口径错在哪**——这一步很关键：原来那句"只出 4 档"写得很像验收口径，若不写明「并进『未开始』会把『已裁决未执行』伪装成『正在校验』」，下一个人看到 5 个显示值会以为设计没照做。

**一个存量数据的陷阱（演示时一定会撞到）**：现网 `_backfill_decision_outcome`（`pipeline.py:659-694`）**从不产出 `partial_success`**，且 `rolled_back` 掉进 `else` 被写成 `outcome=pending`。所以**迁移前的历史"回滚"决策，在台账里会显示成"待定"**。这不是本设计的问题，T6 会修。

> **演示与验收一律用 T11 种子数据（跑新逻辑生成），不要拿迁移前的历史记录做验收。** 用旧数据验收会得出"新逻辑把回滚显示成待定"的错误结论，而这个结论会让人去改本来对的代码。

**详情页保留完整 8 态**（§6.4.1 "执行动作"区块）：`排队 / 校验中 / 已批准 / 已拒绝 / 执行中 / 已完成 / 失败 / 已回滚` 逐条列出，含动作 ID、目标对象、参数摘要。单条查询无 N+1 问题，精确信息给需要排查的人。

### 4.7 行 → 详情：整页跳转（结论）

**结论：整页跳转 `/decisions/detail/:decisionId`。不用抽屉。**

| 理由 | 依据 |
|---|---|
| 详情内容体量不适合抽屉 | 因果链图固定高度 420px（`DecisionChainGraph.tsx:138`）+ 影响面板三段列表 + 先例列表 + 详情 `Descriptions` 10 项，抽屉内必然出现"抽屉套滚动、内部再滚动"的双层滚动 |
| 详情本身是导航中枢 | 影响面板的下游决策、协同证据决策都可点击跳转（`ImpactPanel.tsx:45,79`），先例卡片也跳转（`PrecedentSearch.tsx:68`）。在抽屉里点跳转 = 抽屉内换内容，用户会丢失"我在哪一层"的方位感 |
| 需要可分享 | PRD US-3：本体工程师要把"这条决策的证据"发给同事看 → 要 URL |
| 返回时筛选态不丢 | 双保险：① 项目已有 `KeepAliveOutlet` 组件级缓存（`App.tsx:243-249` 路由包裹 + `KeepAliveOutlet.tsx:37`）；② 筛选条件同步 URL query（§4.3） |
| 与项目既有范式一致 | `semantic-admin` 的 `PipelineRunsPage.tsx:138` 用 760px 抽屉放"运行详情"，那是纯文本 + 小表格；`CandidatesPage.tsx:231` 也是短内容。重型可视化在项目里没有抽屉先例 |

**行点击行为**：整行 `onRow.onClick` 跳转；`--odap-color-bg-tertiary` 作为 hover 底色；`cursor: pointer`；同时提供键盘可达——行内放一个 `tabIndex=0` 的"查看"按钮（20px `EyeOutlined`），`Enter` 可触发（整行 `onRow` 只响应鼠标，不能作为唯一入口）。

---

### 4.8 裁决人列的三种取值（PM 新增，必须有区分）

**被驳回有两种完全不同的来源，复盘意义相反：**

| 来源 | 列内展示 | 图标 | 详情页额外展示 |
|---|---|---|---|
| **系统策略门禁拒绝**（`resolution.actor_type = system`） | 「系统（策略门禁）」 | 16px `SafetyCertificateOutlined`，`--odap-color-text-secondary` | 门禁判定摘要（`resolution.reason` 即门禁摘要） |
| **人工驳回**（`resolution.actor_type = user`） | `{人名} · 10-22 14:30` | 无（人名本身是信息） | 人工填写的驳回理由（`resolution.reason`） |
| 人工采纳 | `{人名} · 10-22 14:30` | 无 | 参考的先例（如有） |
| 尚未处理 | `未处理`（`--odap-color-text-tertiary`） | 无 | — |
| 历史数据（`status_assumed = true`） | `—` | 无 | "历史数据，流程状态未记录"（§5.1.5） |

**判定依据是 `resolution.actor_type`，不是猜 `by` 的字符串。** 契约（`api-spec.yaml:665-669`）明写 `actor_type: system | user`，且 `actor_type=system` 时 `by` 就是"系统（策略门禁）"。**禁止用 `by === 'system'` 或 `by` 是否为空来反推来源** —— 那是拿显示名当语义判据，改一次显示名就全错。

**为什么必须区分**：一个是"规则问题"（策略配错了），一个是"判断问题"（人看错了）。都显示成人名或空白，复盘时无法归因，也就无法回答"我们的策略门禁是不是太严/太松"这个 PRD 明确关心的指标。"历史数据"显示 `—` 而不是"未处理"，因为后者暗示"还在等人处理"，会误导用户去催（§5.1.5）。

---

## 5. 待决策队列页（`/decisions/queue`）

### 5.1 状态机（`status` 落库 + 写侧矩阵，前端只做映射）

> **本节已按 `api-spec.yaml` 修订。** 架构 Spec 引入了 `DecisionStatus` 六值枚举（`pending / decided / executing / executed / failed / rejected`）并保留 `DecisionOutcome` 五值。因此**前端不再自己派生状态**——`status` 由后端给，`group` 也由后端给。这比原设计更稳（少一处可能与后端不一致的推断），但引入了两个必须堵住的风险，见 §5.1.3。

#### 5.1.1 台账结果列的标签映射（`status` × `outcome` → 5 类标签）

**映射表按契约的合法性矩阵（7 合法 / 23 非法）逐行列出**——因为非法组合写不进去，所以**表里每一行都是穷尽的，没有"其他情况"**：

| `status` | 允许的 `outcome` | 界面标签 | 色系 |
|---|---|---|---|
| `pending` | `pending` | **待定（待裁定）** | warning |
| `decided` | `pending` | **待定（待执行确认）** | warning |
| `executing` | `pending` | **待定（待执行确认）** | warning |
| `executed` | `success` | **执行成功** | success |
| `executed` | `partial_success` | **部分成功** | success |
| `failed` | `failure` | **执行失败** | error |
| `rejected` | `rejected` | **已驳回** | 中性 |

**为什么仍然必须双参**：`status` 只有 `executed`，没有 `partial_success`——只按 `status` 渲染，"部分成功"这个 PRD 明确要求的标签会丢失。签名必须是 `toDisplayLabel(status, outcome)`。

**但好消息是不需要写任何"例外分支"**（架构把矩阵收窄后确认）：`outcome = partial_success` **⟺** 界面"部分成功"，**一一对应、无例外**。`(failed, partial_success)` 现已非法、写不进去。所以映射函数不需要 `if (status === 'failed' && outcome === 'partial_success')` 这类兜底——**那种行不存在**。

**这条对我上一版设计的实质简化**：我原表里有"`executed` + 其他 outcome → 执行成功 + 异常标记"和"`failed` + 任意"两行，都是为"矩阵未收窄时可能出现的组合"预留的。现在矩阵收窄，**这两行可以删掉**，映射函数变成一张 7 行的纯查表，没有默认分支、没有异常标记。**少一条分支就少一个能在线上走到的未知路径。**

**表里没有的 `(status, outcome)` 组合，前端收到时按契约违约处理**：`console.error` + 走 §5.1.3 末的"状态同步中"兜底展示，**不猜、不映射成最接近的标签**。猜会把契约违约伪装成正常数据，让缺陷永远不被发现。

**`rolled_back` 不在本表**：它已归为 `failed` + `failure`，界面标签就是"执行失败"（列表口径）。曾达成的明细在 `outcome_details` 里，只在详情页展示（§6.4.1 末）。

#### 5.1.2 队列分组（后端 `group` 二分 + 前端按 `status` 再分两段）

**PM 裁定（PRD §5.1 重写）：次队列不再是"一档只读"，拆成两档，其中 `decided` 档要能操作。**

| 后端 `group` | 前端渲染段落 | `status` | 界面标题 | 可用动作 |
|---|---|---|---|---|
| `to_resolve` | 第 1 段 | `pending` | **待我拍板** | `approve` / `reject` |
| `to_execute` | 第 2 段 | `decided` | **已裁决，待执行**（需催办） | **`execute`** / `reject` |
| `to_execute` | 第 3 段 | `executing` | **执行中** | 无（只读） |

**分组依据**：`group` 决定"进哪个大区"，`status` 决定"在 to_execute 里进第 2 段还是第 3 段"。前端**不从 `status` 反推 `group`**（那是后端的事），但**可以在 `group` 内用 `status` 分段**——这两个判断层次不同，不构成重复。

**为什么必须拆出"已裁决，待执行"这一段**（PM 的漏损场景，我认同并补一句设计侧的观察）：
"采纳了却忘了执行"比"没人拍板"更隐蔽——它表面上已处理过，不进任何人的待办，直到复盘才发现从没落地。**在界面上它同样隐蔽**：如果它和执行中混在一段、且都没有操作按钮，用户扫过去只会看到"一堆在进行的事"，不会意识到其中几条根本还没开始。所以第 2 段除了有按钮，还需要一个主动语感的标记（见 §5.2 SLA 表新增的"待催办"档）。

#### 5.1.3 两个必须堵住的风险

**风险一（已由 PM + 项目总监裁定解决方案）：`status` 与 `outcome` 是两个可互相矛盾的字段。**
`DecisionRecord` 同时 required `status` 与 `outcome`，而 `DecisionRecordCreate` 不含 `status`——说明 `status` 由服务端产生。但"服务端产生"不等于"不会漂移"。

**我最初主张"`status` 优先读时派生、不落库"，这条已被否，我接受。** 项目总监裁定 `status` 必须落库（新增 6 态是明确裁定），且实际**不可派生**——`action_record_id` 全仓从未被赋值（实测），"派生"的前置条件根本不成立。我当时缺的正是这一步核实，属于把"更优雅"当成了"可行"。

**PM 给的正确解法，比我原方案强**：

| 层 | 机制 | 效果 |
|---|---|---|
| 写侧断言 | `status × outcome` 合法组合矩阵（6 × 5 = 30 组，**8 合法 / 22 非法**）在写路径断言 | 非法组合**写不进去**，不是事后对账 |
| 原子性 | 两字段在**同一条 Cypher** 里写（`SET n += $patch` 是单节点原子操作） | 不存在"一个已改、一个未改"的中间态 |
| 测试 | 必须有测试断言（PRD 验收项 E33 状态矩阵服务端强制 / E34 写入原子） | 矩阵与原子性不是口头约定 |

**关键区分（PM 指出，我原先搞混了）**：US-8 要消灭的是**跨入口不一致**（Agent Tab 内存字典 vs 台账图库各说各话），**不是"记录内有多个字段"**。多字段只要写侧受约束、写入原子，就不是"两个状态"，而是**同一状态的流程维与结果维**。

**前端警示图标兜底：已撤销（架构确认写侧断言后，这个分支不可达）。**

我上一版设计了"矛盾时以 `status` 为准 + 行内 `WarningOutlined`"。架构的回答是：`transition_status` 的 `SET n += $patch` 是 Neo4j 单节点原子操作，两字段在同一 patch 字典里；再加 `LEGAL_OUTCOMES` 矩阵在写侧断言（非法组合 → **409**）。所以 `status=executed` + `outcome=failure` 这种组合**写不进去**，不是"写进去了靠前端发现"。

**因此我删掉警示图标**。理由不是"省代码"，而是：**保留一个永不可达的分支，会让后来人以为矛盾是允许的**——它会在代码里长期存在、被复制到别的映射里、并在真的出现时被当成"设计考虑到的情况"而降低排查优先级。少一条分支就少一个"我们的设计允许这种数据"的错觉。

**真正需要兜底的是另一件事，我原来没想到**：`ActionRecord.status` 在 SQLite，`DecisionRecord.status` 在 Neo4j，**跨库无法同事务**（架构没假装做到，这点我认可——假装做到比承认做不到更危险）。实际处理是：`execute` 编排顺序为「CAS 决策 status → 调 `ActionService.submit_action` → 立刻用返回的 `ActionRecord.status` 映射回写」，异常路径在 `finally` 回写 `failed`+`failure`，不留 `executing`；两步之间崩溃会残留 `executing`，由 **`execute` 幂等重放自愈**。

**这一段残留期要在界面上诚实表达，但只在详情页表达**（PM 已裁定，2026-10-24；详见 §6.4.1 / §7.3）。

**我上一版把判定条件写成「`status=executing` 且 `sla_state ∈ {warning, breached}`」，这个条件是错的，PM 驳回得对。** 两个独立错误：

1. **字段不存在**：`sla_state` 是 `PendingDecisionItem` 的字段（`api-spec.yaml:903/935`），**只有 `/pending` 队列有**。台账和详情页的 DTO 里根本没有这个字段，这个条件在详情页**永远为假**——我写的时候没核实字段归属。
2. **信号被偷换**：即使字段有，`sla_state` 表达的是"等待时长是否超阈值"，不是"回写是否完成"。执行跑了 5 分钟完全可能是正常的长任务，用 SLA 档位冒充回写状态，会在**每一次正常执行中**闪一下"同步中"，把真正的异常淹掉。排障告警一旦常态化误报，就等于没有告警。

**这正好违反我自己写在 §11 的纪律**（"不臆造 `action_status`"、"当前不做假字段"）——我用一个能拿到的信号冒充了另一个拿不到的信号，和"用显示名反推 `actor_type`"是同一类错。PM 按我自己的纪律裁的，我接受。

> **PM 把它抽象成了一条禁令，比只针对 `sla_state` 有用**：**不得用任何"等待时长档位"冒充"回写完成度"。**
> 两件事的语义不同——"等了多久"是**外部观察**，"落库了没有"是**系统内部事实**。观察可以推测量，但不能推出事实。
> 之所以要抽象：下一个接手的人很可能换个字段犯同一个错，比如拿 `waited_minutes` 的数值大小当"是不是卡住了"的信号——那同样是把观察当事实，而且更难发现（因为它看起来"更直接"）。
> **判断方法**：问一句"这个字段能证明我知道的这件事吗"，而不是"这个字段和那件事相关吗"。相关 ≠ 能证明。

**落地结论**：台账列表与队列卡片**都不显示**「状态同步中」，仍是 4 档 + 1 空态（§4.6）。理由是可实现性而非偏好：这两个 DTO 没有"回写是否完成"这个信息，任何在列表上的表达都只能是猜测。

跨库这一段的结论我按架构口径写进稿子：**不承诺跨库事务，承诺幂等自愈 + 诚实展示**。这不是打折，是承认边界。

**风险二（已被 PM 裁定解决）：`available_operations` 含 `execute` / `retry`，但原契约里两个分组都用不上。**
api-spec `:645-655` 的枚举是 `[approve, reject, execute, retry]`，但 `to_execute` 组原描述为恒 `[]`、`to_resolve` 组只有 `approve`/`reject`，于是 `execute` / `retry` 在队列里不可达。

**PM 已裁定（PRD §5.1 重写）**：次队列拆两档，`decided` 档**可发起执行** —— 这正好给 `execute` 找到了归属：

| 档 | 条件 | 可用动作 |
|---|---|---|
| 待裁定 | `pending` | `approve` / `reject` |
| **已裁决未执行（需催办）** | `decided` | **`execute`**（发起执行）+ `reject`（撤回性驳回） |
| 执行中（只读） | `executing` | 无（`available_operations` 为空） |

**缺口 K 已关闭（契约 v1.1.0）**：`available_operations` 现在是"这条记录当前能做的操作"，由状态机**单点派生**，队列与详情页**共用同一个派生函数**，不存在两处各判一次。契约明写：`pending → [approve, reject]`；`decided → [execute]`（队列里可点）；`failed → [retry]`（`failed` 不入队列，只在详情页出现）；`executing / executed / rejected → []`。所以 `retry` 不再是"无归属"，只是"不出现在队列"。

#### 5.1.4 队列页"无可用操作"时的渲染（与架构原建议不同，理由仍然成立，且已升级为 PRD 正式口径）

架构原建议：`to_execute` 的行"渲染成禁用态 + Tooltip"。**我已把它改为不渲染按钮、改渲染状态说明，架构已采纳（D-1），PM 已写进 PRD §5.6.1。**

**PRD §5.6.1 把两种"不可操作"正式分开，并规定不得混用**：

| 语义 | 用户读到 | 正确表现 | 为什么不能反着做 |
|---|---|---|---|
| 你**没权限**做这个动作 | "我是不是缺权限？找谁要？" | 按钮**存在但禁用** + Tooltip 说明所需权限 | **不得静默隐藏**——隐藏会让人以为系统没这个功能，连去申请授权的念头都不会有 |
| 这个动作**对谁都不存在**（结构上不可用） | "系统坏了？" | 按钮**不出现**，位置换成状态说明 | **不得渲染灰按钮**——灰按钮只有一种读法"我缺权限"，会让用户反复点击并怀疑自己 |

`executing` 档属于后者：不是"你不能执行"，是"已经在执行了，谁都不该再点"。

**具体表现**：`available_operations.length === 0` 时，卡片右下角不出现按钮组，改显示一行 `--odap-color-text-secondary` 文字 + 16px `SyncOutlined`：「执行中，等待完成（{执行状态}）」。仍在轮询刷新，但不给假操作入口。

**注意：`executing` 档的"等待完成（{执行状态}）"里的执行状态是 4 档口径**（§4.6），不在这里展开 8 态——队列卡片不是排查界面。
#### 5.1.5 历史数据（`status_assumed=true`）—— 不进队列，数据层排除

**背景**：旧决策只有 `outcome`、没有 `status`（`status` 是本批新增字段）。这类记录不能当成 `pending` 处理——否则队列一上线就被历史数据灌满，**演示第一屏全是假待办**，用户第一印象就是"这功能没用"。

**三条硬规则**：

| # | 规则 |
|---|---|
| 1 | 历史数据**一律归入「待定」标签**（`outcome` 有值时按 §5.1.1 正常映射；其余按"待定"兜底） |
| 2 | **不得进入待决策队列任何一段**（不是只排除主队列——`decided` / `executing` 两段同样排除）。**且这是数据层的排除，不是前端过滤**：队列的 Cypher 恒带 `coalesce(n.status_assumed,false)=false`，这类记录压根到不了前端 |
| 3 | 详情页与台账行需标注：**「历史数据，流程状态未记录」**，且**不出任何裁决 / 执行按钮**（不是禁用，是不渲染——对谁都不适用） |

**排除范围是队列 `items` 与顶部四个 `counts` 两处，且必须同时满足**（team-lead 特别提醒）：这两处走不同查询路径（分页查 vs 聚合查），只验队列的话，很容易出现"列表干净了但计数还把历史数据算进去"——而计数是给管理层看的口径，错了没人会当场发现。

> 原第三条"CSV 导出"随导出降 P1 **本期不存在**（`api-spec.yaml:22` 已移除该端点）。**恢复导出时必须同步把排除条件补回第三条查询**——导出走的是与列表完全独立的查询路径，最容易漏。这条留在这里是给恢复时的提醒，不是当前验收项。

**前端的兜底只是防御，不是机制**：若某条 `status_assumed=true` 仍出现在队列响应里，说明后端过滤漏了——前端**丢弃该条并 `console.warn` 一次**（§7.2 已列），**不渲染成待办卡片**，也不自作主张调补。丢弃是为了不让用户看到不可处理的条目，`warn` 是为了让缺陷被发现；两个都要有，只丢弃不告警等于把 bug 藏起来。

**标注样式（PM 要求"轻量、不抢视觉重心"，我的实现）**：

- **不做新色系**。用 `--odap-color-text-tertiary` 文字 + 16px `InfoCircleOutlined`，**不加背景、不加边框、不做成标签胶囊**——胶囊会被读成"一种状态"，而它不是状态，是数据说明。
- 位置：台账 → 结果标签右侧同行，`--odap-font-size-xs`；详情页 → 状态标签右侧；队列 → 不出现（因为本就不该进队列）。
- 全文案（**可见文字 + 可展开完整说明，不能只靠 Tooltip**）：「历史数据，流程状态未记录」
- 完整说明（点 `InfoCircleOutlined` 展开，或详情页直接展开）：「这条决策创建于流程状态字段上线之前，当时只有结果记录。它的实际处理过程无法追溯。」
- **不显示成"未处理"**：台账"裁决人"列对这类数据显示"—"而非"未处理"。"未处理"暗示"还在等人处理"，会误导用户去催。

**为什么标注不能只放 Tooltip**：截图、打印、键盘操作、屏幕阅读器快速浏览这四种场景下 Tooltip 全部丢失。**架构特意强调过这一点**，我把它固化为规则：**任何"这条数据不能按常规理解"的说明，必须是页面上可见的文字，Tooltip 只能承载补充细节。**

**契约已到位（缺口 Q 关闭，team-lead 裁定用已有字段而非可空枚举）**：`DecisionRecord.status_assumed: boolean`（`api-spec.yaml:781-787`，默认 `false`）。`true` = 该记录的 `status` 是迁移时为存量数据**推定**的，不是当时真实写入的。

**它不是第二个真相源**（架构的解释我认同，记下来避免以后有人再提"两处看到两个状态"）：`status_assumed` 回答的不是"这条决策是什么状态"，而是"**你看到的 `status` 值是记录下来的、还是迁移时推定的**"。这是数据**来源**，不是数据**取值**，与 `status` 正交。始终只有一个状态值，只是旁边多了一个"此值存疑"的戳。

**我原来提的"`status` 可为空"被否，理由成立且比我想的更硬**：迁移守卫是 `WHERE n.status IS NULL`，若历史数据就该留 `NULL`，守卫永远命中它们——"二次运行 0 行"这条要求直接破产，而且每次启动都会重跑一遍；另外队列与状态机全部依赖非空 `status`（CAS 里 `coalesce(n.status,'pending')`），可空会让每条过滤都要写 `status IS NULL OR ...`。**我当时只从"语义更准确"考虑，没考虑迁移守卫和 CAS 的连锁代价。**

| 字段值 | 界面处理 |
|---|---|
| `status_assumed = true` | 显示"待定"标签 + 历史数据标注 + **不出任何裁决 / 执行按钮**（不是禁用，是不渲染，因为对谁都不适用） |
| `status_assumed = false` | 常规处理，按 §5.1.1 映射 |

**我不采用"`status` 可空"方案了**——`status_assumed` 比 `null` 更好：`null` 只能表达"不知道"，而 `status_assumed` 能表达"系统已经推定了一个值、但你要知道这个值不是记录下来的"。后者信息量更大，且不需要在 TS 里把 `status` 变成可空类型（否则每个用到 `status` 的地方都要处理 `null`，成本扩散）。**PM 和架构选对了，我原来的建议撤回。**

#### 5.1.6 状态迁移（方括号为 `status`，括号为界面标签）

```
              ┌────────── 驳回（reason ≥5 字）──────────┐
              │                                        ▼
[pending] ────┼──────────────────────────────────▶ [rejected]
(待定·待裁定)  │                                    (已驳回) 终态
   │          │
   │ approve  │
   ▼          │
[decided] ────┘
(待定·待执行确认)
   │
   ├── 发起执行（execute，第 2 段按钮）──▶ [executing]（待定·待执行确认，第 3 段只读）
   │                                          │
   │                                          ├── 成功 ──▶ [executed] + outcome=success       → 执行成功
   │                                          ├── 部分 ──▶ [executed] + outcome=partial_success → 部分成功
   │                                          └── 失败 ──▶ [failed]                            → 执行失败
   └── 未发起执行 ──▶ 停留 [decided]（超 24h/72h 触发"需催办"标记）
```

**这条链是本期最容易漏的一环**：原设计 `decided` 没有出边——它只是"等"，等谁、等什么没定义。PM 补的漏损场景（"采纳了却忘了执行"）正是在这个悬空状态里发生的。现在 `decided → executing` 有了显式动作，且这个动作出现在队列第 2 段，用户扫一眼就知道"这几条还没开始"。

**五条状态机约束（PRD 验收项 E36 执行幂等与失败回写，界面必须能正确反映，不能只靠后端保证）**：

| # | 约束 | 界面后果（前端要处理的） |
|---|---|---|
| 1 | `decided → executing` 合法 | 第 2 段"发起执行"成功后，该卡片移出第 2 段、进入第 3 段（或按刷新结果重排），**不能留在原地变成灰按钮**。若响应带 `idempotent_replay=true`，文案改为「已按当前执行状态同步」而不是「已发起执行」——用户没做新动作，不该读到自己没做的事 |
| 2 | **`pending` 不得直跳 `executing`** | 第 1 段卡片上**不得出现"发起执行"按钮**，即使后端误传 `execute` 到 `available_operations`。前端按 `status` 做一次防御性校验：`status !== 'decided'` 时忽略 `execute`，并 `console.warn` |
| 3 | **重复发起必须幂等** | 用户连点/网络重试不得产生第二个执行记录。按钮提交后立即 `loading` 且**同一卡片在响应返回前不解除 loading**；成功后按返回的 `action_record_id` 更新本地状态，不乐观递增计数 |
| 4 | **执行失败必须回写 `failed`** | 第 3 段卡片若执行失败，要能反映为"执行失败"（不是一直停在"执行中"）。队列接口若无实时推送，第 3 段需**低频轮询**（如 30s），并在卡片上标出"最后更新于 {时间}"，避免用户盯着一个不动的"执行中" |
| 5 | 跨库残留期（`executing` 但执行动作已结束） | **队列卡片不做任何特殊表达**（§5.1.3）：队列 DTO 没有"回写是否完成"的字段，去猜就会每次正常执行都闪一下异常。第 3 段的卡片照常显示"执行中"，**前端不做时间判断**。残留期的诚实表达在详情页（§6.4.1），因为详情页能拿到执行明细 |

**第 2 条的防御性校验不该只有前端做**——它是双保险，不是替代后端校验。之所以前端也做，是因为一旦发生，用户会直接看到一个本该不存在的按钮，**这是"系统错了"级别的错，不该靠用户上报才发现**。

**跨行一致性：不再是前端问题。** `status` 与 `outcome` 的合法组合由写侧矩阵强制（**7 合法 / 23 非法**，非法组合返回 409），且两字段在同一 `SET n += $patch` 里写。所以前端**不需要**做"矛盾时以 `status` 为准 + 警示图标"的兜底——那条分支已按架构建议删除（§5.1.3）。前端只处理一种情况：收到表外的组合（契约违约）时 `console.error` 并按"状态同步中"展示，**不猜、不映射成最接近的标签**。

**映射函数只写一处**：`toDisplayLabel(status, outcome)` 放在 `modules/decision/utils/displayStatus.ts`，台账 / 队列 / 详情 / 队列卡片四处共用。**不要在各处各写一遍 if-else**——PRD §4.1.1 已把"映射只在状态标签组件内发生"写成验收口径，契约 v1.1.0 也在 `DecisionStatus` 的 description 里写死了签名。原设计里的 `deriveVisibleStatus(record, action)` 因后端直接给 `status` 而**取消**，改为纯映射，少一层推断即少一处不一致。

### 5.2 队列条目卡片

**布局**：单列卡片流（不用表格）——队列是"逐条处理"场景，卡片能承载更丰富的信息，且天然适配窄屏降级。

```
┌────────────────────────────────────────────────────────────────┐
│ [待定（待裁定）] [已超时 3天4小时]                    置信度 42% 低 │
│                                                                │
│ 华东区 A 类门店库存跌破安全线，按现有补货策略是否继续执行自动补货？      │
│                                                                │
│ 推荐方案  按门店等级分批补货，A 类门店优先，单店上限 200 件             │
│                                                                │
│ 证据  实体 7 + 出处 0   [!]      来源  问答      等待  76 小时       │
│                                                                │
│                              [ 查看详情 ]  [ 驳回 ]  [ 采纳 ]      │
└────────────────────────────────────────────────────────────────┘
```

**第 2 段（`decided` 档）卡片不同处**——同一组件，三处差异，别复制一份新卡片：

```
┌────────────────────────────────────────────────────────────────┐
│ [待定（待执行确认）] [需催办 · 裁决后 28 小时]          置信度 68%    │
│                                                                │
│ ...（问句 / 推荐方案 / 证据 / 来源，同上）                            │
│                                                                │
│ 裁决  李敏 · 10-23 09:12                                        │
│                                                                │
│                        [ 查看详情 ]  [ 驳回 ]  [ 发起执行 ]        │
└────────────────────────────────────────────────────────────────┘
```

| 差异点 | 第 1 段（待裁定） | 第 2 段（已裁决待执行） |
|---|---|---|
| 状态标签文案 | 待定（待裁定） | 待定（待执行确认） |
| SLA 文案与字段 | "等待 76 小时"，用 `waited_minutes` | "需催办 · 裁决后 28 小时"，用 `decided_waited_minutes` |
| 主按钮 | 采纳（`approve`） | **发起执行（`execute`）** |
| 多一行"裁决"信息 | 无 | 裁决人 + 裁决时间（`resolution.by` / `at`） |

**为什么主按钮从"采纳"换成"发起执行"**：第 2 段的前提是"已经采纳过了"，此时用户唯一该做的事是让它跑起来。把"采纳"留在卡片上会让人重复裁决，把"发起执行"藏进详情页则等于让漏损场景继续存在——**这正是 PM 要堵的那个洞，按钮必须在这一段就可见**。

| 字段 | 位置 | Token / 规则 |
|---|---|---|
| 状态标签 | 左上 | `DecisionStatusTag`，16px 图标 + 文字；主队列卡片文案"待定（待裁定）"，次队列卡片"待定（待执行确认）"。**队列按主/次分组渲染，分组标题补足扫描线索**（同色不碍事） |
| SLA 标记 | 状态标签右侧 | **直接消费 `sla_state`（`ok` / `warning` / `breached`）三档，别自己算**：<br>**① 待裁定段（`pending`）**：`ok` 不显示；`warning`（24–72h）「等待较久」`--odap-color-warning` + `FieldTimeOutlined`；`breached`（>72h）「已超时」`--odap-color-error` + `FieldTimeOutlined`，且带时长"已超时 3 天 4 小时"。<br>**② 待执行段（`decided`）**：同三档，文案前缀换成裁决后语感——「裁决后 28 小时未执行」/「裁决后 80 小时未执行」，时长取 `decided_waited_minutes`（自裁决起算）。<br>**③ 执行中段（`executing`）**：不显示 SLA（正在跑，催无意义，只显示执行状态）。<br>**配对规则（契约原话）**：`sla_state` 与哪个 `*_waited_minutes` 配对由 `group` 决定，两者必须一致——`to_resolve` 配 `waited_minutes`，`to_execute` 配 `decided_waited_minutes`。<br>全部**图标 + 文字，不只靠颜色**。**前端不自己算阈值、不自己判档**——契约明写"阈值走服务端配置，为契约常量而非入参，客户端不得自定义 SLA 口径"（`api-spec.yaml:960-968`）。三档直接消费 `sla_state` |
| 可用操作 | 右下 | 由 `available_operations` 数组驱动，**不按 `status` 硬编码**：含 `approve` → 采纳；含 `reject` → 驳回；含 `execute` → **发起执行**（主按钮，第 2 段专用）；`retry` 不入队列（归详情页，§5.1.3）。**数组为空则整组不渲染**，改显示进度说明（§5.1.4），**不要渲染禁用按钮** |
| 置信度 | 右上，右对齐 | `tabular-nums`；< 60% 加 `--odap-color-warning` + "低"字标记；< 50% 时采纳按钮触发二次确认 |
| 问题（`context_summary`） | 第二行，主视觉 | `--odap-font-size-base`(14) / `--odap-color-text-primary`；最多 2 行 `-webkit-line-clamp`，超出 Tooltip |
| 推荐方案 | 第三行 | 前置标签"推荐方案"用 `--odap-color-text-tertiary` + `--odap-font-size-xs`；内容 `--odap-color-text-primary` |
| 证据 | 第四行 | `实体 N + 出处 M`；`M=0` 显示 `WarningOutlined` + `--odap-color-text-disabled` + Tooltip"出处层证据缺失（覆盖率受限）"。**取值全都不可得时显示"证据数未知"，不显示"0 条"**——`PendingDecisionItem.evidence_count` 已随排序降 P1 移除，前端只能从 `decision` 派生，派生不出来是**常态**而非异常。**不要把"不知道"渲染成"零"**，这是本 PRD 反复在防的同一个错（台账证据数列 / 出处层证据缺失同一判据） |
| 来源入口 | 第四行 | 同 §4.4 值域 |
| 等待时长 | 第四行 | **按段取不同字段，不是同一字段换个标签**：第 1 段 `pending` 用 `waited_minutes`（自创建）→ 显示"等待 76 小时"；第 2 段 `decided` 用 `decided_waited_minutes`（自裁决）→ 显示"裁决后 28 小时"；第 3 段 `executing` 不显示。`--odap-font-family-mono`，粒度到小时，不用相对时间自动刷新（避免每秒渲染抖动）。字段缺失时整块不显示，**不用 `waited_minutes` 顶替**（§11 第 21 条） |
| 操作按钮 | 右下 | 顺序：次要（查看详情，`type="text"`）→ 危险（驳回，`type="default"` + `--odap-color-error` 文字）→ 主（采纳，`type="primary"`）。**主操作放最右**，符合西式阅读终点 |

**排序切换器：只剩"置信度"一项，且只在第 1 段渲染**（原设计的"置信度 / 证据数"两项，证据数已随 P1 移除）。第 2/3 段固定 `waited_desc`，**不渲染切换器**——契约里这两段没有可选排序键，渲染出来就是点了没反应的假控件（§11 第 24 条 / §10.2.1 J）。

**卡片间距**：`--odap-spacing-md`(16)；卡片内边距 `--odap-spacing-md`(16)；卡片圆角 `--odap-radius-md`(8)。

### 5.3 裁决动作交互流程

> **范围冲突已处理**：任务书列了 4 个动作（采纳 / 改选备选 / 拒绝并填理由 / 转人工补充信息），但 PRD §5.4 只定义 3 个（采纳 / 驳回 / 查看详情），且 PRD §7 第 8 条明确排除"在裁决时修改推荐方案"、第 5 条排除"协作讨论/转人工"。**本设计按 PRD 执行**，差异已在 §9.3 上报 team-lead。

#### 动作一：采纳

```
点击"采纳"
  ├─ 置信度 ≥ 50% ──▶ 直接提交 → 乐观移除该卡片 → toast"已采纳，可在台账查看 [查看]"
  └─ 置信度 < 50% ──▶ Modal 二次确认
                        标题：这条决策的置信度较低（42%）
                        正文：采纳后将以该方案进入执行。低置信度决策建议先查看证据链。
                        次要按钮：查看证据（→ 详情页）
                        主按钮：仍然采纳
                        ──▶ 提交 → 同上
```

- 提交中：按钮 `loading`，卡片其余操作禁用，**不做全屏遮罩**（避免打断浏览其他条目）
- 先例勾选：若该决策有可匹配先例（`findSimilarDecisions` 返回非空），采纳弹窗内提供"我参考了哪几条先例"多选，勾选后留痕（PRD US-6 / `PRECEDENT_FOR` 边）
- 成功后：卡片从队列移除（乐观更新），**不做撤销**（PRD §5.4 明确）

#### 动作二：驳回

```
点击"驳回" → Modal
  标题：驳回这条决策
  正文：驳回后该决策将标记为"已驳回"，不会进入执行。
  字段：驳回理由（TextArea，必填，≥5 字，maxLength 500，显示字数计数器）
        占位文案："例如：库存数据是上周的，需要先更新再决策"
  校验：少于 5 字时提交按钮禁用 + 字段下方 inline 错误"请填写至少 5 个字，说明为什么没有采纳"
  主按钮：确认驳回（危险色文字）
  ──▶ 提交 → 移除卡片 → toast"已驳回，理由可在台账查看"
```

**错误不在顶部集中提示，在字段下方就近显示**（符合表单规范）。

#### 动作三：发起执行（第 2 段专用）

只在 `decided` 档出现（`available_operations` 含 `execute`）。**这是 PM 拆两档的直接目的，不能只做按钮不做流程。**

```
点击"发起执行"
  ├─ 动作已派发（action_record_id 存在）──▶ 直接 POST /{id}/execute → loading → toast"已发起执行"
  └─ 动作未派发（action_record_id 为空）──▶ 先调 create，再 execute（或由后端在一个请求内完成）
                                            期间按钮 loading，不弹二次确认
```

- 提交中：按钮 `loading`，卡片内"驳回"禁用（避免执行与驳回同时提交）
- 成功：该卡片从第 2 段移除（乐观更新），**不 toast 跳转**——用户可能连续催办多条
- **幂等重放要能读出来**：响应若带 `idempotent_replay=true`（说明这条早已发起过、本次只是把当前执行状态补写回来），toast 文案改成「已按当前执行状态同步」，**不能写"已发起执行"**——用户没做新动作，界面不该让他以为自己做了一次。同一个点击给出两种反馈，靠的是响应里的标记，不是前端猜
- 失败：卡片内 inline `Alert`，**按 `error.code` 区分（不按 HTTP 状态码、不按文案）**——`403` → "你没有发起执行的权限"；`409` + `illegal_transition` → "该决策已被他人处理"；`409` + `execute_in_progress` → "该决策正在执行中，无需重复发起"；`409` + `concurrent_append_conflict` → "该决策刚被更新，请刷新后重试"；其他 → "发起执行失败，可重试"。**不回退整段列表**。读取方式见 §10.6（`parseApiError` 单一封装，三套形状并存）
- **不做二次确认**：与"采纳"不同，发起执行不改变决策结论，只是让它开始跑，误点成本低（且执行本身还有门禁）。加确认会让连续催办变得很烦

#### 动作四：查看详情

直接跳 `/decisions/detail/:id`，无弹窗。**证据不完整的决策，用户走这条路先看证据再决定**——这就是"转人工补充信息"这个动作的实际替代路径。

#### 并发冲突

提交时若该条已被他人处理，`409` + `error.code=illegal_transition` → toast「该决策已被 {处理人} 处理」+ 自动刷新该行（**不覆盖他人结果**，PRD §5.6）。

**处理人姓名取 `error.details.handler_name`（契约 1.4.0 起在 `details` 里，不在顶层）。** 不是前端猜，也不是从 `detail` 字符串里截。`handler_name` 为 `null` 时降级为「该决策已被他人处理」，**不要渲染成「已被 null 处理」**——凡是插值进文案的字段都必须有 `null` 分支，这是 §6.4.1「三级判据」的同一条纪律。

#### 权限只读

无裁决权限时：采纳 / 驳回按钮 **`disabled` + `Tooltip`"需要决策审批权限"**，查看详情保持可用。**整页不 403、不空白**（PRD §5.6）。发起执行同理，Tooltip"需要执行权限"——**两种权限分开判断**，有裁决权不等于有执行权。

**但按钮禁用只是前端预判，它会过期**：用户在页面上停留时权限可能被撤（换角色、管理员改了策略），此时点下去会收到 `403` + `error.code=FORBIDDEN`。处理方式必须与 401 不同——**就地 `Alert` 提示「你没有该操作的权限」，不跳转、不清空页面、不清空已填的理由**。理由：403 是"这件事你不能做"，不是"你的登录失效了"；整页跳走会让用户以为系统坏了，而且丢掉他已经填的内容。**401 才跳登录页**（无 `code`，只能靠 `status` 判，见 §10.6）。

### 5.4 批量裁决：可用性与限制

**入口**：卡片左上 `Checkbox`；勾选 ≥1 后，顶部浮现批量操作条（`sticky`，不是 Modal）：

```
已选 12 条   [ 清空 ]                    [ 批量驳回 ]  [ 批量采纳 ]
```

| 规则 | 定义 | 依据 |
|---|---|---|
| 可批量采纳 | 是 | PRD §5.5 |
| 可批量驳回 | 是，**必须填统一驳回理由（≥5 字）** | PRD §5.5 |
| 单次上限 | **50 条**。超出时提交按钮 `disabled` + 内联提示"单次最多 50 条，请分批处理"，**不静默截断** | PRD §5.5 |
| 含低置信度条目 | 批量采纳中含 <50% 的条目时，二次确认 Modal 必须**显式列出该数量**："其中 3 条置信度低于 50%" | PRD §5.5 |
| 结果呈现 | "成功 10 条 / 失败 2 条"，失败条目**逐条列出具体原因**（已被他人处理 / 不属于当前工作空间 / 权限不足 / 状态已变更），每条可点进详情 | PRD §5.5 |
| 部分失败 | **不回滚已成功的条目**，如实展示 | PRD §5.5 |
| 不可批量的情况 | **只对 `available_operations` 含 `approve` 的条目开放勾选**，即第 1 段（`pending`）。第 2 段（`decided`）与第 3 段（`executing`）**不显示 Checkbox**——第 2 段的主操作是"发起执行"，批量执行不在 PRD §5.5 范围内（§5.5 只定义批量采纳/驳回），不擅自扩；第 3 段只读 | 派生状态定义 + PRD §5.5 范围 |

**为什么不做"全选当前页之外"**：分页之外的决策用户没看过，"全选全部筛选结果"会导致盲采。勾选范围严格限定在**已加载且可见**的条目，这是安全边界。

### 5.5 队列顶部计数

**契约给四个计数**（`api-spec.yaml:996-1024` → `counts.{to_resolve, to_execute, sla_warning, sla_breached}`），四个全渲染，**前端零二次请求、零本地计算**：

```
待裁定 12 条    待执行 4 条    |    等待较久 5 条    已超时 3 条
```

| 计数 | 契约字段 | 点击行为 |
|---|---|---|
| 待裁定 N 条 | `counts.to_resolve` | 定位到第 1 段 |
| 待执行 N 条 | `counts.to_execute` | 定位到第 2 段开头（`decided` 优先于 `executing`） |
| 等待较久 N 条 | `counts.sla_warning` | 按 `sla_state=warning` 收窄（两段合计，跨段筛选） |
| 已超时 N 条 | `counts.sla_breached` | 按 `sla_state=breached` 收窄（两段合计，跨段筛选） |

**两个分区分隔**：前两个是"流程维度"（该我做什么），后两个是"紧迫度维度"（有多急）。视觉上用一条 `--odap-color-border` 竖线隔开（16px 高，`--odap-spacing-md` 两侧），**不要用不同底色区分**——它们都是计数，只是回答不同问题。

**三个契约保证，前端可以直接信任**（都是契约原话，我抄下来是因为它们直接决定实现方式）：

1. **全库口径、不受分页影响**："四个计数由与 `items` 完全相同的过滤条件派生、**不受分页影响、全库口径**（页内算出来的计数会让用户以为'只有 3 条超时'）"。
2. **`to_execute` 与 `group` 同源**："`to_execute > 0` 时该分组不得为空，反之亦然。两者走同一 `grp` 表达式。"
3. **两个 SLA 计数也按分档取计时基准**："`to_resolve` 用 `created_at`，`to_execute` 用 `resolution.at`，与 `sla_state` 严格一致。"

**第 2 条要写成验收（team-lead 点名让 QA 按这条测）**：`counts.to_execute > 0` 但第 2/3 段渲染为空 = 缺陷。这是防 A-1（次队列恒空）复发的回归断言，造数两遍即可：

- 造 3 条 `decided` → `counts.to_execute === 3` **且** `group=to_execute` 非空
- 造 0 条 → 计数为 0 **且**该分组为空

**一处与 team-lead 裁定的偏差，需要确认**：你裁的是"只渲染两个契约计数，分档计数降 P1"。那条裁定的前提是"契约没有 `sla_warning` / `sla_breached`，前端要算就得拉全量"。**架构已经把这四个计数都补进契约了**（全库口径、不受分页影响、按各档基准计时），所以现在渲染它们**零成本、零额外请求**，不再有"空位"问题。我按你那条裁定的**意图**（不留空位、不做假控件）渲染四个，**与字面不同**。若你仍要两个，删掉 §5.5 后两行与卡片里对应的两枚标记即可，一行改动。

按当前工作空间统计，由服务端完成（PRD §5.3）。**计数接口失败时显示"—"，不阻断列表，也不退化成 0**——`0` 与"—" 是两种完全不同的信息，显示 0 会让人以为队列空了。

### 5.6 空 / 加载 / 错误

| 场景 | 表现 |
|---|---|
| **加载中** | 3 张卡片骨架（`--odap-color-bg-tertiary` + 微光扫过动画，动画走 `prefers-reduced-motion` 全局降级 `global.css:780`）。**不显示"暂无待决策"** |
| **空态** | 24px `CheckCircleOutlined` + 标题"待决策队列已清空" + 副文案"当前没有等你拍板的决策。"+ 次要链接"去台账看看最近的决策"（→ `/decisions/ledger`）。**不使用"太好了！"这类空洞语气** |
| **错误** | `CloseCircleOutlined` + "待决策队列加载失败" + 错误摘要 + "重试"。计数条保持上次值并标注"数据可能过期" |
| **次队列为空但主队列非空** | 不显示第二分组标题，避免出现空分组 |

---

## 6. 决策详情页（`/decisions/detail/:decisionId`）

### 6.1 布局

布局沿用现有 `Row gutter=16` + `Col 14 / 10`（`DecisionIntelligencePage.tsx:81-125`），不重排——已有结构是合理的：左侧"这条决策怎么来的"，右侧"它影响了什么 / 相似情况怎么处理的"。

```
┌─ 面包屑：决策台账 / dec_7f3a2b1c9d0e ─────────────────────────────┐
│  dec_7f3a2b1c9d0e  [复制]   [待裁定]                     [采纳][驳回] │
│  ─────────────────────────────────────────────────────────────  │
│  ┌─ 左 14 ─────────────────────────┐  ┌─ 右 10 ───────────────┐  │
│  │ 决策溯源因果链            (G6)   │  │ 先例参考                │  │
│  │ ┌────────────────────────────┐  │  │ ┌────────────────────┐ │  │
│  │ │  420px 画布                 │  │  │ │ 相似历史决策卡片列表  │ │  │
│  │ └────────────────────────────┘  │  │ └────────────────────┘ │  │
│  │                                 │  │                        │  │
│  │ 决策详情（Descriptions 15 项）    │  │ 影响分析                │  │
│  │ ┌────────────────────────────┐  │  │ ┌────────────────────┐ │  │
│  │ │ 决策ID / 可见状态 / 推荐方案  │  │  │ │ 完整度提示          │ │  │
│  │ │ 置信度 / 证据数 / 来源入口    │  │  │ │ 下游决策 N          │ │  │
│  │ │ 裁决人 / 裁决时间 / 驳回理由  │  │  │ │ 目标对象变化 N       │ │  │
│  │ │ 执行动作 / 执行状态 / 反馈摘要 │  │  │ │ 协同证据决策 N       │ │  │
│  │ │ 推理摘要                     │  │  │ └────────────────────┘ │  │
│  │ └────────────────────────────┘  │  └────────────────────────┘  │
│  └─────────────────────────────────┘                              │
└──────────────────────────────────────────────────────────────────┘
```

**顶部操作区**：详情页也要有采纳/驳回（从台账点进来发现该处理时，不必跳回队列）。权限判定同 §5.3。**这是唯一使用品牌强调色的主按钮，加上 Segmented 的选中态，本屏强调色使用 2 处，符合上限。**

### 6.2 三组件复用与所需改动

| 组件 | 是否复用 | 需要的改动 |
|---|---|---|
| `DecisionChainGraph` | **复用，必须改** | ① **删除 `NODE_COLORS` 硬编码字面量**（`:14-20`，6 个十六进制常量 + `:108,120` 两处灰色回退），改为由父级 `theme.useToken()` 取值后经 `nodeColors` prop 传入（**G6 不消费 CSS 变量，必须 JS 传解析后的值** —— 与架构锁定一致）；② 节点标签里拼的 `outcome` 原文（`:42,51,61` 的 `(${center.outcome})`）改为中文标签，且**必须走 `toDisplayLabel(status, outcome)`**，否则"部分成功"在图上显示成 `partial_success`；③ 新增可选 prop `height?: number`（默认 420，窄屏 320）；④ **`useEffect` 依赖加 `nodeColors`**（`:133` 现在只有 `[chain]`，切主题不重绘） |

#### G6 节点配色方案（只给 token 名，不含任何色值）

| 节点类型 | antd token | 语义 |
|---|---|---|
| `center`（当前决策） | `token.colorPrimary` | 品牌主色，唯一的"你在看这条" |
| `parent`（上游 CAUSED_BY 决策） | `token.colorWarning` | **不再用紫色**——原 `NODE_COLORS.parent` 是紫色系，既违规又无业务语义 |
| `precedent`（先例） | `token.colorInfo` | 历史参考 |
| `entity`（证据实体） | `token.colorSuccess` | 事实依据 |
| `episode`（证据出处） | `token.colorTextSecondary` | 弱化，因为覆盖率本就不全 |
| 未匹配类型的兜底 | `token.colorFillSecondary` | 替代原来的灰色字面量回退 |
| 边标签文字 | `token.colorTextTertiary` | 替代 `:120` 的灰色字面量 |

**为什么 `episode` 用弱化色而非第四种彩色**：ADR-076 已明确 Episode 层覆盖率受限（`§4.2` 的 MENTIONS 说明）。给它高饱和色会让用户以为"出处证据很完整"，与事实相反。弱化色 + 图例文字说明才是诚实的表达。

**`act` 相位不要红色**（关联 §9.2 第 9 条）：`DecisionTimeline` 与 G6 里表示"执行"的语义，用 `token.colorPrimary` 而不是 `token.colorError`——执行动作本身不是错误。

| 组件 | 复用方式 | 改动说明 |
|---|---|---|
| `PrecedentSearch` | **复用，需加 2 个可选 prop** | ① `initialQuery?: string`——详情页传 `decision.context_summary`，进入即预填；② `autoSearch?: boolean`（默认 `false`）——详情页传 `true`，进入即自动检索，用户不用再手打一遍（现在这个组件是"空搜索框 + 手动搜"，在详情页语境里是多余的重复劳动）；③ 结果列表加"引用"勾选回调 `onReference?: (ids: string[]) => void`，供采纳时留痕 |
| `ImpactPanel` | **复用，需改完整度文案** | 见 §6.3 |

**`DecisionChainGraph` 为什么改 props 而不只改内部**：G6 在 `useEffect` 里一次性 `new Graph()`，主题切换时不会自动重绘（`:92-133` 的依赖数组只有 `[chain]`）。因此需要把 `theme.useToken()` 的结果放进 effect 依赖，或由父组件传色。**建议后者**：新增 `nodeColors?: Record<string, string>`，父组件用 `useToken()` 算好传入，effect 依赖改为 `[chain, nodeColors]`，主题切换即重绘。

### 6.3 `impact_completeness` 显式提示文案

**现有实现问题**：`ImpactPanel.tsx:16-20` 的 `COMPLETENESS_META` 只给了一个短标签，`partial` 写的是"部分维度缺失"——用户看不懂"哪部分"。ADR-076 §9 第 3 条要求"`impact_completeness="partial"` 时展示'影响分析数据不完整'提示"。

**三态完整文案（替换现有 `COMPLETENESS_META`）：**

| 值 | Alert type | 标题 | 说明文案 |
|---|---|---|---|
| `full` | `success` | 影响分析完整 | 强影响与弱影响维度均已覆盖。 |
| `degraded_target_resolution` | `warning` | 目标解析降级，部分影响未纳入 | 有执行动作的目标实体未能解析到图谱中，相关目标变更可能缺失。可核对执行动作的目标对象是否已入本体。 |
| `partial` | `warning` | 影响分析不完整 | 当前仅覆盖弱影响三类（下游决策、目标对象变化、协同证据决策）。强影响维度（事实失效清单、失效边遍历）依赖 ADR-074 落地，尚未纳入。**下游决策数为 0 不代表没有下游决策。** |

**最后一句是设计的关键**：`partial` 状态下"下游决策 0 条"极易被误读为"这件事没有影响"。必须显式否定这个误读。ADR-076 §9 也要求"invalidation 类边在图例中与确定性边视觉区分，避免误读"。

**图例视觉区分**：影响面板若渲染衍生决策图，失效类边用 `--odap-color-text-tertiary` 虚线，确定性边用 `--odap-color-border` 实线，图例文字明确写"虚线 = 失效/不确定关系"。**不用颜色区分强弱，用线型**——颜色已被状态占用，且线型对色觉障碍友好。

### 6.4 详情 `Descriptions` 字段（原 10 项 + 新增 7 行）

原 10 项（`DecisionIntelligencePage.tsx:90-113`）保留，新增 7 行：

| 新增字段 | 展示规则 |
|---|---|
| 可见状态 | `DecisionStatusTag`，取值 `toDisplayLabel(status, outcome)`（**双参**，§5.1.1），**不显示 `outcome` 原文** |
| 来源入口 | 7 值域（§4.4）；缺值"来源未标注" |
| 裁决人 / 裁决时间 | 同一格。`system` → `16px SafetyCertificateOutlined` + "系统（策略门禁）"；有 `by` → "张三 · 2026-10-22 14:30"；无 `by` 且 `status=pending` → "未处理"；历史数据 → "—"（**不写"未处理"**，§5.1.5） |
| 驳回理由 | `span={2}`；**仅 `已驳回` 状态渲染该行**，其他状态整行不渲染（不是显示"—"）。**内容按驳回来源分两种**，见 §6.4.2 |
| 执行动作 | `action_record_id` + 当前执行状态；无关联动作时"无关联执行动作" + 说明"该决策尚未派发执行"。**精确 8 态只在详情页出现**，见 §6.4.1 |
| 关联任务 ID | `task_id` + 16px `CopyOutlined`；**仅当决策由 Agent 链路产生时渲染该行**，其他来源整行不出现。不放进台账列（§3.5 末节） |
| 证据数 | `实体 N + 出处 M`，`M=0` 加 `WarningOutlined` + **可见文字**（不是仅 Tooltip，§6.6） |

**`推理摘要`（`reasoning`）**：`span={2}`，长文本 `Typography.Paragraph` + `ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}`，避免一屏被推理文本淹没。

### 6.4.1 执行动作的精确状态（8 态，只在此处展开）

台账"执行状态"列已降为 4 档（§4.6），**精确 8 态的唯一落点是详情页**。状态来源是后端 `ActionRequestStatus`（`apps/api/odap/biz/decision/action_service/schemas.py:6-14`），前端不推断。

| `ActionRequestStatus` | 详情页文案 | 语义 | 图标（`@ant-design/icons`，16px） | 色彩 Token |
|---|---|---|---|---|
| `pending` | 待派发 | 动作已创建，未进入校验 | `ClockCircleOutlined` | `--odap-color-text-tertiary` |
| `validating` | 校验中 | 策略门禁正在判定 | `SyncOutlined`（`spin`） | `--odap-color-info` |
| `approved` | 已批准，待执行 | 门禁通过，尚未开始 | `CheckCircleOutlined` | `--odap-color-info` |
| `rejected` | 已拒绝（门禁） | 门禁未通过 | `StopOutlined` | `--odap-color-error` |
| `executing` | 执行中 | 正在执行 | `SyncOutlined`（`spin`） | `--odap-color-info` |
| `completed` | 已完成 | 执行成功 | `CheckCircleOutlined` | `--odap-color-success` |
| `failed` | 执行失败 | 执行异常 | `CloseCircleOutlined` | `--odap-color-error` |
| `rolled_back` | 已回滚 | 执行后回滚 | `UndoOutlined` | `--odap-color-warning` |

**为什么 8 态必须给详情页、不能只给 4 档**：`pending` / `validating` / `approved` 三态在台账里合并成"未开始"，但用户在这三态下的**排查动作完全不同** —— `pending` 是"没人派发"（要催派发），`validating` 是"门禁在算"（等一下），`approved` 是"批了没跑"（要催执行）。把三者压成一格只在**列表浏览**时成立，一旦用户点进详情就是要排查，此时合并等于把答案藏掉。

**`Spin` 动画必须尊重 `prefers-reduced-motion`**：`global.css:780` 已有 reduce 媒体查询，`SyncOutlined spin` 在 reduce 下退化为静态图标 + 文案本身已含"中"字，不靠动画单独传达"进行中"。

**补一个第 9 个展示态「状态同步中」——只在本页（详情页）出现，列表不适用**（PM 裁定 E41 已改为"在详情页"并写明"台账列表不适用本条，不得由前端猜测"）：

`ActionRecord.status` 在 SQLite、`DecisionRecord.status` 在 Neo4j，**跨库不能同事务**。崩溃可能让决策停在 `executing` 而执行动作其实已结束。

**判据分三级。第一级看"两个信号是否不一致"，第三级才看时间——顺序不能颠倒**：

**「出口」不是超窗后的补救，是 `status=executing` 期间的常驻能力**（Spec 的 **AC-15** 就是这么锁的，比我原来的实现宽一格）：**任何 `executing` 的渲染，无论超没超窗、无论落到哪一支，都必须渲染「查看执行记录」入口。** 时间只决定**文案是否降级**，不决定**要不要给出路**。

| 级 | 条件（`status=executing` 前提下） | 文案（未超窗） | 文案（超窗后 > `SYNC_STALE_MINUTES`＝10 分钟） | **出口** | 依据性质 |
|---|---|---|---|---|---|
| ① | `outcome_details.action_status` 已是终态（`completed` / `failed` / `rolled_back`） | **「状态同步中」** + `SyncOutlined`，`--odap-color-text-tertiary`，Tooltip"执行结果已产出但决策状态尚未回写，系统会自动同步" | **改文案**：「状态可能未同步，请检查执行记录」 | **「查看执行记录」入口（全程必须有）** | **有证据**：两信号不一致 |
| ② | `action_status` 为进行中（`pending`/`validating`/`approved`/`executing`） | 正常「执行中」 | **文案不变**（仍「执行中」） | **「查看执行记录」入口（全程必须有）** | **有证据**：两信号一致 |
| ③ | `action_status` 拿不到**或取值不在 8 值枚举内**（不可解析＝无法判定） | **「执行中」**（不假装知道，见下方"为什么③不显示同步中"） | **改文案**：「状态可能未同步，请检查执行记录」 | **「查看执行记录」入口（全程必须有）** | **无证据**：承认不知道 |

**把「出口」从时间维度里解耦出来，是这张表的关键结构**：它是一列恒定值，不是某个时间点的补偿。这样写的直接好处是——**删掉 ① 的时候不会连 ② 的出口一起删**（team-lead 的原话："它不能挂靠在某一条分支的文案条款下，必须是独立的一条"）。

**这张表的"失败方向"是安全的——这是它虽然一半不可验收、却仍然可以放行的真正理由**（team-lead 的推理，我补进表下）：

`action_status` 是本期**不可验收半**依赖的字段（契约零结构承诺，字段缺失时断言静默通过）。看起来最危险的是：**唯一含"承诺"的 ①，恰好依赖这个最测不了的字段。** 但把降级规则代进去算一遍，结论是反的：

| `action_status` | 是否超窗 | 落到哪支 | "系统会自动同步"这句承诺是否被说出 |
|---|---|---|---|
| 终态 | 未超窗 | ① | **说出（未验证）** |
| 终态 | 超窗 | ③ | 不说 |
| 进行中 | 任意 | ② | 不说 |
| **缺失/不可解析** | 未超窗 | ②（保持"执行中"） | **不说** |
| **缺失/不可解析** | 超窗 | ③ | **不说** |

**字段缺失时 ① 根本渲染不出来 → 承诺永远说不出口。** 所以这个不可验收分支的**失败方向是"少承诺"，不是"多承诺"**：我们可能少说一句本该说的话，但**绝不会对用户承诺一件系统做不到的事**。

**这就是"不可验收"能被接受的判据**：不是"影响小"（影响可能不小），而是**失败时倒向安全的一侧**。反过来，如果某个不可验收分支失败时会多说一句假话，那它就不能放行——**同一份"不可验收"，风险方向不同，结论就不同。**

> 写这一段是因为：`verdict: pass` 旁边挂一条"不可验收"，评审的人会默认你在找借口。补上失败方向之后，它才是一个**有理由的取舍**；否则它就是一个**没查出来的洞被写成了设计决定**——这两者在文档上长得一模一样，只能靠把推理写出来区分。

### 这一节的核心原则（比文案细节重要）

> **任何一支都不允许存在"没有出口的长期状态"。三支的区别只在文案（有证据说实话、没证据说不知道），不在于要不要给出路。**

**② 为什么也要有出口——"有证据"不等于"可证伪"**（PM 补的一层，我原来漏了）：
② 是**有证据**的（两信号一致，它确实在跑）。但用户看到"执行中"十分钟，他能做的**仍然只有等**——他无法判断到底是"在跑"还是"卡住了"。**跑得久不是错误，"跑得久且查不到"才是。**
所以我原来只让 ③ 有出口是不够的：把 ② 当成"有证据所以安全"，等于假设"有依据"就等于"用户能自己确认"，这两件事不是一回事。

**为什么 ② 超窗后文案不变，而 ①③ 要改**——这条差别有依据，不是随手定的：
- **① 的文案里含一个承诺**："系统会自动同步"。**承诺有期限**——10 分钟还在承诺自动同步，就是在替系统背书一件它做不到的事。所以超窗后必须撤掉承诺，改说"可能未同步"。
- **② 的文案只是陈述**："执行中"。**陈述只要是真的就照说**，没有期限问题——它确实还在跑。所以文案不变，**补的是出口，不是措辞**。
- **③ 未超窗时的"执行中"是一个未被证伪的默认值，不是断言**；超窗后连默认值也不该维持，因为"一直停在执行中"本身就是需要解释的现象。

一句话记：**①超窗撤承诺，②超窗补出口，③超窗撤默认值。三件事不同，不要统一处理。**

**为什么 ③ 未超窗时显示"执行中"而不是"状态同步中"**（AC-14）：拿不到 `action_status` 就无从判断，此时显示"同步中"等于**凭空断言"系统出问题了"**。**没证据时不要给结论，只保留原状态。** 这一条同时保证了这个态不会在正常执行中误报——否则每一次拿不到字段的正常案例都会闪一下异常，告警就废了。

**① 是断言，③ 是承认。两者不能合并。** ①说"我知道结果出来了、只是没写回"（有 `action_status` 为凭）；③说"我不知道，你去看看"（没有任何凭据）。用同一句话表达这两件事，等于把"不确定"伪装成"确定"。

**为什么要给出口**（PM 加码 E41，架构落地 `SYNC_STALE_MINUTES`）：
- **无期限的「状态同步中」是用户无法自行证伪的状态**——他会一直等，因为界面始终在告诉他"系统在处理"。**这等于替系统永久兜住一次失败。**
- 给"请检查执行记录"+ 跳转，是把这个状态**变成可证伪的**：用户点进去，看到底跑没跑完，自己下结论。**出口的作用不是给出答案，是让用户能自己拿到答案。**

**④ 计时用 `updated_at`，不新增字段，且明确接受它不精确**（架构口径）：
- 字段表已锁 5 个，不为一个文案判断加存储；
- `updated_at` 会被编辑操作刷新，导致**提示被推迟**——只会"晚报"，不会"误报"；
- 这个判断**只影响文案**，不参与任何计数 / 排序 / SLA 计算，所以可以容忍不精确。**这句话是它可被接受的前提，若哪天它被用于计数，这个容忍立刻失效。**

**验收边界：这一档只有一半能测，必须说清是哪一半**（PM 把 E41 拆成两半，team-lead 据此改写 AC-14）：

| 半 | 内容 | 依赖字段 | 能不能验 |
|---|---|---|---|
| **可验收半**（Spec **AC-15**） | **任何** `status=executing` 的渲染（**含未超阈值**）都必须有「查看执行记录」入口；超窗只是文案降级（①③ 改、② 不改）。**实测到"executing 但没有任何入口"，即为未实现——不需要等到超窗才判失败** | **只依赖 `status` + `updated_at`**，零跨库、零新字段 | **能验，本期硬断言** |
| **不可验收半** | 窗口内那句「状态同步中」 | `outcome_details.action_status`（目前零结构承诺） | **本期不测**，字段声明到位后升级 |

**为什么要把"不能测"写出来，而不是留成一条"应该能验"的条款**：字段缺失时断言会**静默通过**（拿 `undefined` 和 `undefined` 比），看起来是绿的，实际什么都没验。**测试静默通过比测试失败更糟——失败会有人来看，静默通过没人看。** PM 的总结更准：*"一条验收若不能从契约明确承诺的字段推出来，写进 EARS 只是自我安慰——宁可明说不可测，不假装能验。"*

**注意可验收半才是真正防住"无限期显示执行中"的那一条**——它不依赖任何跨库信息，所以它**必须**本期做到。把注意力全放在"状态同步中"那半，反而会漏掉真正能兜底的那半。

> **三套时间轴不要混**（架构特意提醒，我复核了契约）：`sla_state` 按 `group` 取基准（`to_resolve` 用 `created_at`、`to_execute` 用 `resolution.at`），`waited_minutes` 恒取 `created_at`，`decided_waited_minutes` 取 `resolution.at`，而本节的同步窗口取 `updated_at`。**不要用 `sla_state` 或 `waited_minutes` 反推这个窗口**——混用会出现"等了 3 天，但状态同步中 2 分钟"这种自相矛盾的组合。同理，**SLA 徽标上的时长与本节窗口的时长是两件不同的事**，不互相印证。

**阈值是前端单点常量，不入契约**（架构口径）：`constants/decisionConfig.ts` 的 `SYNC_STALE_MINUTES`，默认 10。与 SLA 刻意不同——**SLA 决定"返回哪批记录"，改它就是漏数据**（所以必须服务端）；**同步窗口只决定"说哪句话"，改它不改变任何数据集合**（所以可以放前端）。这个差异用一句话记：**改了会让数据变的东西必须服务端，改了只让文案变的东西可以前端。**

> **`action_status` 的契约状态（已闭环，不再是缺口）**：我报的缺口（`api-spec.yaml:775-777` 的 `outcome_details` 是 `additionalProperties: true`、无结构承诺）已被 team-lead 与架构确认会显式声明。关键事实：**pipeline 的 `_backfill_decision_outcome` 本来就写 `action_record_id` / `action_status` / `feedback_pipeline` 三个键**——所以契约声明只是"把既有行为写实"，不扩能力。同时已要求后端确认 **`POST /{id}/execute` 路径也写这个字段**（流水线写了不代表执行端点写了，而本节的判据恰恰依赖后者）。
> team-lead 已把本文档第三级 `action_status` 不可得 → 保持原状 的做法立为 **AC-14「没证据时不给结论」**。字段声明到位后，本节三条判据都可写成可跑断言。

**为什么不直接用"执行中"**：它会让用户以为系统正常在跑，实际可能已经崩在中间，于是用户一直等、不报障。**诚实的"不知道"比虚假的"进行中"有用**——但前提是这个"不知道"有期限、有出口（③），否则它只是在骗人骗得更久。

**`rolled_back` 的明细展示（架构给足了字段，不需要新增契约）**：

列表口径一律"执行失败"（`failed` + `failure`），**但详情页可以把过程讲清楚**——`outcome_details` 里有 `action_status: "rolled_back"`、`achieved_items`、`rolled_back_items`：

> 已回滚：3 项中 2 项达成后撤销

渲染位置：执行动作区块底部，`--odap-color-text-secondary`，`--odap-font-size-xs`，**不加 Alert 底色、不用图标**——它是过程说明，不是告警。

**为什么列表只给"执行失败"而详情给明细**：列表标签是**终局结论**，明细是**过程**。把过程塞进列表标签，就会出现"按部分成功筛选却看到执行失败标签"这类筛选与展示对不上的问题（这正是 PM 与架构就矩阵争执的那个点）。**两个层级的信息放对位置，各自都不用妥协。**

**动作 ID 与关联任务 ID 是两个不同的键，不要合并展示**：

| 字段 | 是什么 | 展示位置 |
|---|---|---|
| `action_record_id` | 执行动作记录的主键（ADR-076 `Decision -[:TRIGGERED]-> ActionRecord`） | 执行动作区块标题右侧，`--odap-font-family-mono` + 16px `CopyOutlined` |
| `task_id` | Agent 链路关联的任务 ID | `Descriptions` 独立一行，仅 Agent 来源渲染 |

两者都可能出现"有 A 无 B"（人工裁决的决策有 `action_record_id` 但无 `task_id`；Agent 产生的决策在未派发时反之）。合并成一格会出现"到底是哪个 ID"的歧义。

### 6.4.2 门禁拒绝 vs 人工驳回：必须区分（PM 裁定，对应 PRD「驳回来源可区分」验收项）

同一个"已驳回"标签下藏着两种成因完全不同的事。**混在一起会让"我们的策略门禁是太严还是太松"这个复盘问题永远答不出来**——一个是规则问题（改策略），一个是判断问题（改人或改信息供给）。

| 驳回来源 | 判定依据 | 详情页展示 |
|---|---|---|
| **系统（策略门禁）** | `resolution.by = "system"` 或 `resolution.action` 由门禁写入 | 裁决人列显示 `SafetyCertificateOutlined` + "系统（策略门禁）"。驳回理由区展示**门禁判定摘要**：命中的规则名 + 判定结果 + 拒绝原因，取 `ActionRecord.opa_decision` / `validation_result`（`schemas.py:35-36` 已有该两字段）。**不展示"人工理由"占位框** |
| **人工驳回** | `resolution.by` 是真实用户 ID | 裁决人列显示"张三 · 时间"。驳回理由区展示 `resolution.reason` 原文 |
| 门禁拒绝但 `reason` 也为空 | 门禁未返回可读原因 | 展示"门禁未返回原因，请查看执行动作详情"+ 链接跳到执行动作区块，**不留空白** |

**排版要求**：两种摘要**用同一位置、同一字号、同一层级**，只在标签前缀上区分（"门禁判定：" / "驳回理由："）。**不要**给门禁摘要单独的底色或容器——它不是另一种卡片，它是同一个字段的另一种来源。

### 6.4.3 历史数据标注（无 `status` 的旧决策，按 PRD 历史数据要求）

历史数据在详情页必须有一句**可见**说明，不能只靠状态标签传达：

| 项 | 要求 |
|---|---|
| 文案 | "历史数据，流程状态未记录" |
| 位置 | 标题区状态标签**右侧**，同一行 |
| 样式 | `--odap-color-text-tertiary` + 16px `InfoCircleOutlined`；**无背景、无边框、不做胶囊** |
| 为什么不做胶囊 | 胶囊会被读成"一种状态"，而它不是状态，是**数据说明**。做成胶囊会让用户以为系统还有第七种状态（§2.2 已把状态限定为 5 类标签 / 4 色系，不得新增） |
| 完整说明 | **文案以 §5.1.5 为唯一源**（不允许两处各写一版）："这条决策创建于流程状态字段上线之前，当时只有结果记录。它的实际处理过程无法追溯。" |
| 状态标签 | 仍显示 `待定`（`outcome` 无法映射到具体结果时），但**不得进入待决策队列**（§5.1.5） |

### 6.5 详情页状态

| 场景 | 表现 |
|---|---|
| **加载中** | 左栏因果链区域骨架（420px 高的灰块 + 微光），右栏两个卡片骨架；顶部标题区显示 ID 但状态标签位显示 `Skeleton.Button` |
| **404 / 决策不存在或跨工作空间** | 整页空态：24px `PartitionOutlined` + "没有找到这条决策" + 副文案"它可能属于其他工作空间，或已被删除"+ 按钮"返回决策台账"。**跨工作空间必须返回 404 而非 403**——403 会泄露"这条决策存在、只是你没权限"，配合 §3.5 的 IDOR 上下文就是可枚举攻击面。前端两种情况用同一套文案，不区分措辞 |
| **403 / 同空间但无查看权限** | "你没有查看这条决策的权限" + "当前工作空间：{名称}"+ 按钮"返回决策台账"。**不显示决策内容**，不显示"部分内容"。仅当服务端能确认该决策属于当前空间时才走这一支 |
| **因果链为空但决策存在** | 图区域显示 `Empty` + "这条决策没有上游因果链记录"（现状 `DecisionChainGraph.tsx:136` 写的是"输入决策 ID 查看因果链"，已不适用——ID 不再是输入项，必须改文案） |
| **影响分析单独失败** | 影响卡片内显示 `Alert type="warning"` + "影响分析加载失败，可单独重试" + 小号"重试"按钮；**不阻断因果链与详情**（现状 `DecisionIntelligencePage.tsx:38-40` 是静默 `setImpact(null)`，用户看到的是一句"查看因果链后自动加载影响分析"——错误的降级文案，必须改） |
| **先例检索为空** | "未找到相似先例"+ 说明"换个说法或缩短描述再试"（现状已有，保留） |

### 6.6 证据展示规范（架构硬要求，三处共用）

| 规则 | 具体要求 | 为什么 |
|---|---|---|
| **实体/出处一律显示 `name`，绝不显示 UUID** | `/chain` 的 `evidence_entities` 已含 `name`（现状 `DecisionChainGraph.tsx:70` 已按 `e.name \|\| id` 处理，保留）。当 `name` 缺失时显示"未命名实体" + Tooltip 显示完整 UUID 供排查，**不把 UUID 当主标签** | PRD US-3 原话：本体工程师要看到"实体名称而不是一串 UUID"。UUID 对用户零信息量 |
| **`evidence_episodes` 为空必须显式标注"证据出处层不完整"** | 不允许留空区块，也不允许只给 Tooltip。做法：证据区固定显示两段计数 `实体 N` / `出处 M`；当 `M = 0` 时，在"出处 0"右侧**直接渲染** 16px `WarningOutlined` + 可见文字"证据出处层不完整"，`--odap-color-text-secondary`；点击展开一段说明"该决策的实体证据未经 add_episode 管线写入，无法追溯到原始数据源（覆盖率受限）" | ADR-076 §4.2/§10 已确认 Episode 层覆盖率受限是既知限制。**只给 Tooltip 等于隐藏**——鼠标悬停才知道的信息在截图、打印、键盘操作下全部丢失 |
| 计数为 0 时不能显示成"0 条证据" | 必须区分"没有证据"与"证据出处层缺失"两种零：`实体 0` = 真的没证据（此时提示"该决策未关联证据实体"）；`出处 0 且实体 > 0` = 出处层缺失 | 同一个 `0` 有两种完全不同的成因，用户对它们的行动完全不同（补证据 vs 查采集管线） |

**三处共用**：台账证据数列、队列卡片证据区、详情页证据区 —— 同一套组件 `EvidenceCount`，避免三处措辞不一致。

---

## 7. 关键状态矩阵

> 每个页面 × 5 态，全部给出具体表现，无"待补充"。

### 7.1 决策台账（`/decisions/ledger`）

| 态 | 具体表现 |
|---|---|
| **loading** | 表格骨架 8 行 × 10 列；筛选区正常可交互；计数位显示 `Skeleton.Input`；**不渲染空态** |
| **empty** | 分两种（§4.5）：本空间无决策 → "当前工作空间还没有决策记录" + "去问答发起第一个决策"；筛选后为空 → "当前筛选条件下没有决策" + "清除筛选" |
| **error** | 表格区替换为错误块 + 重试；筛选区保留；错误摘要不含堆栈 |
| **partial** | ① 列表成功、计数失败 → 计数显示"共 — 条"；② 某行派生字段（裁决人/来源）缺失 → 该格"未标注"置灰，全表正常；③ `total` 为估算 → "约 N 条（估算）"；④ 证据出处层缺失 → 该格 `WarningOutlined` + Tooltip，全表正常 |
| **permission-denied** | 页面正常渲染（台账为只读视图，任何登录用户可看本空间数据）；行内无裁决入口。**导出按钮本期不渲染**（P1），因此本态下也不需要导出权限文案——省掉一个"永远不显示"的分支 |

### 7.2 待决策队列（`/decisions/queue`）

| 态 | 具体表现 |
|---|---|
| **loading** | 3 张卡片骨架 + 计数条骨架 |
| **empty** | "待决策队列已清空" + "当前没有等你拍板的决策。"+ 链接"去台账看看最近的决策" |
| **error** | 整块错误 + 重试；计数条保留上次值 + "数据可能过期" |
| **partial** | ① 计数接口失败 → 计数位"—"，列表正常；② `to_execute` 段加载失败 → "待我拍板"段正常渲染，`to_execute` 段位置显示"待执行事项加载失败" + 局部重试；③ 单条先例预取失败 → 该卡片不显示先例勾选区，其余正常；④ `decided_waited_minutes` 缺失 → 该段**不显示任何等待时长标记**（不是显示 0，也不是用 `waited_minutes` 顶替，§11 第 21 条） |
| **permission-denied** | 队列可见、列表正常渲染；**采纳 / 驳回按钮 `disabled` + Tooltip"需要决策审批权限"**；批量操作条不出现（不渲染半残的批量条）；**整页不 403、不空白** |
| **历史数据不出现** | 无 `status` 的旧决策**不进本页任何一段**（§5.1.5）。若后端漏了过滤而前端收到，该条被丢弃并在 `console.warn` 一次，**不渲染成待办卡片**——否则用户会点进去发现没法处理，从此不信这个队列 |

### 7.3 决策详情（`/decisions/detail/:id`）

| 态 | 具体表现 |
|---|---|
| **loading** | 左栏图骨架 + 详情 `Descriptions` 骨架；右栏两卡骨架；顶部 ID 可见、状态标签骨架 |
| **empty** | 决策存在但无因果链 → 图区 `Empty`"这条决策没有上游因果链记录"；无先例 → "未找到相似先例"；无影响 → 影响面板 `Empty`"暂无可分析的下游影响" |
| **error** | 主体加载失败 → 整页错误 + 重试；**影响分析单独失败 → 局部 Alert + 局部重试，不阻断页面**（§6.5） |
| **executing-unsynced**（跨库残留，**仅本页**，三级） | **AC-15：任何 `executing` 渲染（含未超窗）都必须有「查看执行记录」入口**，这是恒定要求。文案：未超窗 → ① `action_status` 终态＝**「状态同步中」**（`--odap-color-text-tertiary` + `SyncOutlined`）、② 进行中＝**「执行中」**、③ 拿不到/不可解析＝**「执行中」**（不假装知道）；超窗（> `SYNC_STALE_MINUTES` 10 分钟）→ ①③ 改 **「状态可能未同步，请检查执行记录」**、② **文案不变**。**页面其余部分不降级**——它只是一个字段的展示态，不是整页异常。**台账与队列不适用本条**（§5.1.3 / §6.4.1） |
| **partial** | ① `impact_completeness=partial` → 黄色 Alert + 显式"下游决策数为 0 不代表没有下游决策"；② `degraded_target_resolution` → 黄色 Alert + 目标解析说明；③ 证据出处层为 0 → 证据数格 `WarningOutlined` + Tooltip；④ 因果链图渲染失败（G6 异常）→ 图区降级为文本树"上游决策 3 条 / 先例 2 条 / 证据实体 7 条"，页面其余部分不受影响 |
| **permission-denied** | 无查看权限 → 整页"你没有查看这条决策的权限" + 返回按钮，**不渲染任何决策字段**；有查看无裁决权限 → 页面完整，采纳/驳回 `disabled` + Tooltip |

### 7.4 组件级 5 态覆盖

| 组件 | loading | empty | error | populated | edge |
|---|---|---|---|---|---|
| `DecisionStatusTag` | `Skeleton.Button`(小) | 不适用（状态必有值；`status=null` 走历史数据分支，见下行） | 不适用 | `status` 6 值 × `outcome` 5 值经 `toDisplayLabel(status, outcome)` → 5 类标签（§5.1.1） | 未知枚举值 → 显示"状态未知"中性色，**不抛错不空白**；`status=null` → 显示"待定" + 历史数据标注（§6.4.3） |
| `DecisionChainGraph` | 加载中转圈（父级传入 `loading`） | "没有上游因果链记录" | 降级为文本树（§7.3） | G6 正常渲染 | 节点 >50 个 → 默认折叠证据实体层，提供"展开全部"；标签超 24 字截断（现状 `:70` 已 `slice(0,24)`，保留） |
| `PrecedentSearch` | 结果区骨架 3 条 | 初始"搜索后展示相似历史决策"；检索后无结果"未找到相似先例" | 卡片内 Alert + 重试 | 列表 | 结果 > 5 条 → 只显示前 5 + "查看全部在台账筛选"链接 |
| `ImpactPanel` | 卡片内骨架 | "暂无可分析的下游影响" | 局部 Alert + 局部重试 | 三段列表 | 任一段 > 20 条 → 折叠为"显示前 20 条"+ 计数 |
| 队列卡片 | 骨架 | 队列整体空态 | 整块错误 | 正常 | 问题文本超 2 行截断 + Tooltip；等待时长 > 999 小时显示"超过 41 天" |

---

## 8. 响应式断点

### 8.1 前置事实（必须承认的约束）

**项目外壳是桌面优先的硬约束：**
- `AdminLayout.tsx:700` → `<Layout className="odap-layout" style={{ minWidth: 1200 }}>`
- `AgentLayout.tsx:142` → 同样 `minWidth: 1200`
- `/decisions` 由 `AdminLayout` 包裹（`App.tsx:247-248`）

**因此 <1200px 时整个应用会出现横向滚动**，决策模块**无法单方面实现真正的移动端重排**。PRD §7 第 4 条也已把"移动端 / 企业微信内嵌审批"列为 Out-of-Scope。

**本设计的 `<768` 档是"模块内降级"，不是"移动端适配"**：目标是在外壳横向滚动的既成事实下，让决策模块自身的可用性不至于崩坏（不要出现 10 列硬挤、抽屉里套抽屉）。真正去掉 `minWidth: 1200` 属于全站议题，不在本期。

### 8.2 三档降级策略

| 断点 | 台账 | 队列 | 详情 |
|---|---|---|---|
| **≥1280（主目标，PRD §10 要求 1440×900 / 1920×1080 无横向截断）** | 10 列全显；`scroll.x=1580`，仅在 1280–1439 出现横向滚动；筛选区单行（RangePicker 240 + 结果 200 + 来源 180 + 置信度 280 + 复选 140 + 关键词 240 + 间距 ≈ 1330，故 **lg 断点折两行**）；`pageSize` 默认 20 | 单列卡片，最大宽度不限制（跟随容器）；右侧"置信度"与左侧状态同排；四行信息一行展开 | `Row`/`Col 14:10` 双栏；图高 420 |
| **768–1279** | **隐藏 3 列**：执行状态、裁决人、来源入口（收进"列设置"，`AdvancedTable` 已内置列设置能力 `:264`，用户可自行开）；保留 ID/问题/推荐方案/结果/置信度/证据数/创建时间 7 列；`scroll.x` 降至 900；筛选区两行；`pageSize` 默认 20 | 单列卡片，操作按钮换行到独立一行（右下 → 整行右侧）；第四行元信息允许折两行 | 双栏降为单栏纵向堆叠：因果链 → 详情 → 先例 → 影响；图高 320；影响面板不再限高 |
| **<768** | 表格 → **卡片列表**（每条一行卡片：状态 + 问题 + 置信度 + 时间，点击进详情）；表格组件整体不渲染（不是 CSS `overflow` 藏着）；筛选区收进底部 `Drawer`（`placement="bottom"`，高度 85vh），由吸顶"筛选"按钮唤起；`pageSize` 固定 20（不提供 size changer）；**不做横向滚动表格** | 卡片占满宽度；操作按钮改为整行三等分（详情/驳回/采纳），高度 ≥44px；批量操作条改为底部固定条 | 单栏；图高 260；`Descriptions` 由 `column={2}` 降为 `column={1}`；`Descriptions bordered` 在窄屏关掉边框（边框在窄屏吃宽度）；详情页顶部操作改为底部固定操作条（避免滚动到顶才能操作） |

### 8.3 触摸目标与键盘

| 项 | 要求 | 依据 |
|---|---|---|
| 最小点击区 | **44 × 44 px**（<768 档强制；桌面档可到 32px 高但宽度不小于 44px） | WCAG 2.5.5 |
| 按钮间距 | ≥ 8px（`--odap-spacing-sm`） | 防误触 |
| 表格键盘导航 | 行内"查看"按钮 `tabIndex=0`，`Enter` / `Space` 触发；整行 `onRow` 只做鼠标增强 | 不只靠点击 |
| 焦点可见 | 复用既有 `.advanced-table-toolbar-btn:focus-visible`（`AdvancedTable.css:63`）模式；决策模块新增可聚焦元素必须显式 `:focus-visible` 描边 `2px var(--odap-color-primary)` + `outline-offset: 2px` | 禁止移除 focus ring |
| 动效降级 | 依赖全局 `@media (prefers-reduced-motion: reduce)`（`global.css:780`）已覆盖 `animation-duration/transition-duration` → 决策模块**不新增自定义动画**，只用 150ms 过渡 | 已存在基础设施 |

---

## 9. 反模式自查

### 9.1 逐条声明

| # | 禁止项 | 声明 | 本设计的实际做法 |
|---|---|---|---|
| 1 | emoji 作功能图标 | **未使用** | 全部图标来自 `@ant-design/icons`（§1），16/20/24px 三档。文档内所有图标均以组件名表述，无 emoji |
| 2 | 紫→粉渐变 | **未使用** | 决策模块**零渐变**。背景用 `--odap-color-bg-primary/secondary/tertiary` 纯色；不使用 `--odap-gradient-brand` / `--odap-gradient-brand-hover` |
| 3 | 空洞占位文案 | **未使用** | 所有空态/错误态文案都指明"发生了什么 + 下一步做什么"（§4.5 / §5.6 / §6.5）。无 "Welcome to" / "Lorem ipsum" / "暂无数据" 裸文案 |
| 4 | 千篇一律 Hero | **未使用** | 三个视图都没 Hero。台账首屏是筛选区 + 表格；队列首屏是计数条 + 卡片流；详情首屏是面包屑 + 状态 + 因果链。**无大标题 + 副标题 + 居中 CTA** |
| 5 | 硬编码颜色 | **未使用** | 本文档 0 个色值字面量；组件层色值全部落 CSS 变量或 `theme.useToken()`（§2.6、§6.2） |
| 6 | 弹跳缓动 | **未使用** | 只用 `--odap-transition-fast`（150ms + `--odap-ease-out`）。**不使用 `--odap-ease-spring`**（见 §9.2 第 3 条） |
| 7 | 侧条纹边框（`border-left > 1px` 作强调） | **未使用** | 卡片强调靠 1px 全边框 + 状态标签，不用左侧色条 |
| 8 | 渐变文字（`background-clip: text`） | **未使用** | 层级靠字号 + 字重 + 颜色，不靠渐变 |
| 9 | 默认毛玻璃 | **未使用** | 不使用 `backdrop-filter`。浮层用 `--odap-shadow-md` + 不透明背景 |
| 10 | 相同卡片网格无限重复 | **未使用** | 台账是表格（非卡片网格）；队列卡片是纵向单列不等高（内容驱动高度），不是等尺寸网格阵列 |
| 11 | 每节都有小型大写追踪标签 | **未使用** | 无 "ABOUT / PROCESS / PRICING" 式节标签；无编号 section 标记 |
| 12 | 过度圆角（卡片 ≥24px） | **未使用** | 卡片 `--odap-radius-md`(8px)，最大 `--odap-radius-lg`(12px) |
| 13 | 每屏强调色 >2 处 | **已控制** | 台账：**1 处**（选中 Tab 指示）——导出降 P1 后台账是纯只读视图，**没有主按钮是对的**，不要为凑"一个主按钮"再造一个动作；队列：采纳按钮 + 选中 Tab = 2 处；详情：采纳按钮 + 选中 Tab = 2 处 |
| 14 | 幽灵卡片（1px 边框 + blur ≥16px 阴影同时出现） | **未使用** | 卡片只给 1px `--odap-color-border`，**无阴影**；阴影只用于浮层 |
| 15 | 纯黑 / 纯中性灰直接使用 | **未使用** | 全部走 `--odap-color-gray-*` 与 `--odap-color-text-*`（项目灰阶为冷色调派生，非中性灰） |
| 16 | 仅靠颜色传达含义 | **已规避** | 每个状态标签 = 图标 + 文字 + 颜色三重编码；置信度低 = 颜色 + "低"字；影响完整度差异 = 文案 + 图标 + 线型 |

### 9.2 勘查中发现的**存量**设计系统问题（不在本期范围，但必须上报）

> 以下问题**存在于现有代码**，不是本设计引入的。列出来是为了让架构师决定"本期顺手修 / 单独立项"，我未擅自修改。

| # | 问题 | 证据 | 影响 | 建议 |
|---|---|---|---|---|
| 1 | **决策因果链图硬编码 6 个色值** | `DecisionChainGraph.tsx:14-20`（`NODE_COLORS` 常量，antd 默认蓝/紫/青/绿/橙）+ `:108` 与 `:120` 的灰色回退字面量 | 违反"禁止硬编码颜色"；切 `colorTheme` 或深色模式时图不跟随（`useEffect` 依赖只有 `[chain]`，`:133` 不会重绘） | **本期必修**：§6.2 已给方案（`useToken()` + `nodeColors` prop + 依赖加 `nodeColors`） |
| 2 | **`OUTCOME_META` 用 antd 预设色名字符串** | `modules/decision/types.ts:68-74`（`color: 'green' \| 'lime' \| 'red' \| 'default' \| 'orange'`） | 绕过 Token 体系，不随主题切换；`lime` 与 `green` 语义几乎无差别（部分成功 vs 成功难以辨认）；`default` 表达"待定"没有语义 | **本期必修**：换 §2.6 的 `DecisionStatusTag`；`OUTCOME_META` 只保留 `label`，删除 `color` |
| 3 | **存在回弹缓动 token** | `global.css:125` → `--odap-ease-spring`（数值见该行；曲线第三参数大于 1，即存在超射回弹） | 属"弹跳缓动"禁止类；当前**全仓无使用点**（已 grep 确认） | 建议删除该 token 或改名并注明禁用；决策模块声明不使用 |
| 4 | **品牌渐变在 violet 调色板下落入禁色区间** | `colorThemeUtils.ts:142-147` 以 `primary-600 → accent-500` 拼装 `--odap-gradient-brand`；violet 调色板的 `primary-600` 与 `accent-500` 组合落在"靛紫 → 玫红"区间（具体字面量见该处代码） | 全站范围的 P0 风险，一旦有人在 violet 主题下用这个渐变就命中红线 | 建议：① 明确 `--odap-gradient-brand` 的使用白名单；② violet 调色板的 accent 换成非粉色的色相；③ 决策模块**已声明不使用该 token** |
| 5 | **两个 `ConfigProvider` 配置漂移** | `AdminLayout.tsx:653-690` 与 `AgentLayout.tsx:117-137` 各定义一份 `antdThemeConfig`；Admin 版含 `Menu` 组件配置、Agent 版没有，`Button/Input/Select` 两处重复 | 双份维护，未来改一处漏一处；`/decisions` 走 Admin 版，若 agent 模式进入则样式略有差异 | 建议抽 `useAntdThemeConfig()` 共用 hook，单独立项 |
| 6 | **事实描述与代码不符的过期文案** | `DecisionChainGraph.tsx:136` 空态写"输入决策 ID 查看因果链"——ID 输入框将被移除（§3.4） | 改版后会变成指向不存在交互的文案 | 本期顺手改为"没有上游因果链记录"（§7.4 已列） |
| 7 | **影响分析失败被静默降级** | `DecisionIntelligencePage.tsx:38-40` `catch { setImpact(null) }`，用户看到的是"查看因果链后自动加载影响分析" | 把"加载失败"伪装成"还没加载"，违反"不得静默空列表"（PRD §10） | 本期必修：§6.5 局部 Alert + 局部重试 |
| 8 | **Agent 决策链三个接口存在跨工作空间数据暴露 + IDOR** | 列表：`AgentPage.tsx:47-49` 传 `undefined` + `decision_routes.py:39-51` 无校验 + `decision_service.py:85` `if workspace_id:` 假值不过滤。单条与链详情：`decision_routes.py:13-23` / `:26-36` **连 workspace 参数都没有**，`decision_service.py:44-45` / `:60-61` 纯主键查字典。`get_decision` 返回体还带 `workspace_id`（`:54`），可反查归属 | IDOR：凭 ID 可读任意空间决策详情与推理步骤；列表为空上下文时返回全量；重启即丢数据。直接违反 PRD §10"全部接口走既有鉴权与工作空间隔离"。**PM 已升级为 PRD G6 / P0 缺口 E26** | **本期必修**（§3.5）：给三个端点加 `workspace_id: str = Depends(get_current_workspace)`（`workspace_access.py:154`，已有且 fail-closed 422），把 workspace 下推进 service 查询与主键校验。**不得以"前端补传 workspace"替代**——那只是把空上下文泄露换成伪造上下文泄露 |
| 9 | **`DecisionTimeline` 又一处 antd 预设色名** | `modules/agent/components/DecisionTimeline.tsx:25-30` → `PHASE_CONFIG` 用 `'blue' / 'orange' / 'green' / 'red'` 字符串，且四色无统一语义（observe=蓝 / orient=橙 / decide=绿 / act=红） | 同第 2 条问题；且 `act`（执行）用红色=错误色，语义误导——执行动作本身不是错误 | 随 §3.5 收敛时改为 token：`--odap-color-info` / `--odap-color-warning` / `--odap-color-success` / `--odap-color-primary`（act 用品牌色而非错误色） |
| 10 | **Agent Tab 文案是英文** | `AgentPage.tsx:131-136`：`Decisions` / `Decision Records` / `Refresh`，而全站中文 | 违反 PRD §10"文案走既有 i18n 机制" | 随 §3.5 收敛时一并改中文 |

### 9.3 与任务书的口径差异（上报 team-lead）

| 任务书表述 | PRD 口径 | 本设计采用 | 理由 |
|---|---|---|---|
| 裁决动作 4 个：采纳 / 改选备选 / 拒绝并填理由 / 转人工补充信息 | §5.4 三个：采纳 / 驳回 / 查看详情；§7 第 8 条排除"裁决时修改方案"，第 5 条排除"协作讨论/转人工" | **PRD 口径（3 个）** | PRD 是已锁定范围且经 RICE 评分，增加两个动作会引入"方案变更后置信度是否重算""证据链是否失效"的连带复杂度（PRD §7 第 8 条原话）。"转人工补充信息"的实际需求由"证据不完整标记 + 查看详情先看证据"路径覆盖 |
| `impact_completeness` 按 partial/full 两态 | 代码是 3 值（`types.ts:59`） | **3 态设计**（§2.3 / §6.3） | 按代码事实，两态表述会漏掉 `degraded_target_resolution`（目标解析降级），而后者的用户行动与 `partial` 不同（去查本体数据 vs 等 ADR-074） |
| 状态机 | 不新增枚举，由 `outcome` + 执行动作状态派生 | **改为按架构 Spec `DecisionStatus` 六值**（§5.1 已重写） | 架构已在 `api-spec.yaml:392-394` 定稿 `DecisionStatus` 枚举并让 `DecisionRecord` required 该字段，推翻 PRD §0 第 2 条的"派生"方案。我按契约实现（前端少一处推断更稳）。**我最初主张的"`status` 读时派生不落库"已作废并被架构否决**——`action_record_id` 全仓从未被赋值，"派生"的前置条件不成立，我当时没核实这一步；且 `status` 可空会让迁移守卫与 CAS 双双失真。现状是 `status` 落库 + 写侧矩阵 + 同语句原子写（§5.1.3 / §10.2.1 L） |
| （本设计初稿）结果标签 6 个、占 5 个色系，`待执行确认` 用 `--odap-color-info` | PM §三：**"不要新增第六种状态色系混乱，待定是一类，括号内是细分文案"** | **改为 5 类标签 / 4 色系**（§2.2 已修订） | PM 定调优先。改后"待定"内两细分靠图标 + 括号文字 + 队列分组区分，对色觉障碍更友好；`--odap-color-info` 退回只服务"执行状态"列（过程态），两个正交维度不混色 |
| （本设计初稿）`部分成功` 用 `--odap-color-warning` | PM §三 只给 5 个标签、限 4 色系 | **改为 `--odap-color-success`**（§2.2） | 部分成功是**已完成**的结果，归 success 语系；与"执行成功"靠图标区分。原方案与"待定"抢 warning 色，正是 PM 要避免的混乱 |
| （本设计初稿）台账"执行状态"列按动作状态直出 | PM：**降为 4 档，精确 8 态移到详情页** | **4 档列表 + 8 态详情**（§4.6 / §6.4.1） | 不是为了省列宽，而是因为 8 态里 `pending`/`validating`/`approved` 三态的**用户动作完全相同**（都是"等"），在列表里拆开只是把辨识负担转给用户。排查时才需要精度，而排查一定发生在详情页 |
| （本设计初稿）次队列只有"待裁定"+"待执行确认"两段 | PM：`decided` 与 `executing` 拆两档，前者可发起执行 | **三段**（§5.1.2） | `decided`（已裁决未执行）与 `executing`（执行中）混成一段无按钮的"处理中"，用户只看到一堆在跑，**看不到其中一部分根本没开始**。"采纳了却忘了执行"比"没人裁决"更隐蔽 |
| （本设计初稿）裁决人只有"人名"与"未处理"两值 | PM：新增第三值"系统（策略门禁）" | **三值 + 历史数据 `—`**（§4.8 / §6.4.2） | 门禁拒绝是**规则问题**（改策略），人工驳回是**判断问题**（改人或改信息供给）。混在一起，"我们的门禁是太严还是太松"这个问题永远答不出来。历史数据用 `—` 而非"未处理"，因为后者暗示"还在等" |
| （本设计初稿）旧数据无 `status` 视为异常数据 | PM（历史数据要求）：归"待定" + 轻量标注 + **不进主队列** | **§5.1.5 / §6.4.3** | 若塞进主队列，上线当天队列会被历史数据灌满假待办，用户点进去发现全是没法处理的东西，这个队列就废了。标注**不做胶囊**——胶囊会被读成"第七种状态" |
| （本设计初稿）"派生 6 态"由前端从 `outcome` 推导 | team-lead 裁定 B-2：改独立 `status` 6 值字段 | **`toDisplayLabel(status, outcome)` 双参**（§5.1.1） | `status` 六值**不含 `partial_success`**（该项只在 `outcome` 里），只吃 `status` 会丢掉"部分成功"这个 PRD 明确要求的标签。team-lead 已采纳，并要求"标签映射只允许一处实现"（§11 第 7 条） |

---

## 10. API 契约对齐（按 `api-spec.yaml` v1.4.0 复核）

> **本章已按 `api-spec.yaml` v1.5.0 复核（v1.1.0 时重写全章，后续版本增量核对）。**
> 我上一轮提的 A–S 共 19 条缺口，**除 1 条主动降为 P1 外全部关闭**。本章现在是"契约 → 设计"的对照表，不再是待办清单。
> **所有字段名均已 grep 核实过，不按消息转述写文档。**
> **v1.4.0+ 的增量只有一处影响设计：错误体接上了统一信封，但三套形状并存 → 新增 §10.6。** 其余（`entry_source` 单值、`sla_state` 服务端下发、`StepRejectDetail`）前几版已对齐。
> **§10.6 是按契约原文写的，不是按转述写的**——核对时发现转述与契约有两处不一致（`evidence_too_many` 的挂载位置、`details.field` 是否恒存在），均以契约为准，差异已在 §10.6 标注。

### 10.1 已对齐的部分（设计可直接实现）

| 能力 | 契约 | 设计侧用到的字段 |
|---|---|---|
| 台账列表 | `GET /api/decisions`（`:40-160`） | `items[]` / `total` / `total_is_estimate` / `page` / `page_size` / `has_more` |
| 台账导出 | ~~`GET /api/decisions/export.csv`~~ **本期不做（P1）**，`api-spec.yaml:22` 已明确移除 | 前端**不渲染按钮**。原设计（CSV UTF-8 BOM、>5000 行 422 不生成截断文件）留档，恢复时照此实现 |
| 待决策队列 | `GET /api/decisions/pending` | `items[]{decision, group, waited_minutes, decided_waited_minutes, sla_state, available_operations, executable}` / `total` / `counts.{to_resolve,to_execute,sla_warning,sla_breached}` / `has_more`。**`evidence_count` 已从 item 移除**（随证据数排序降 P1），卡片上的证据数只能从 `decision` 内的证据字段派生 |
| 裁决 | `POST /{id}/resolve` | `action ∈ {approve, reject}` / `reason`（`selected_option` 与 `expected_outcome` **均已删除**） |
| 批量裁决 | `POST /batch-resolve` | `BatchResolveRequest` / `BatchResolveItemResult` / `BatchResolveResult` |
| 执行 | `POST /{id}/execute` | `RecommendedAction` / `ActionRecord`（含 `opa_decision` / `validation_result`，供 §6.4.2 门禁摘要） |
| 推理步骤 | `GET\|POST /{id}/reasoning-steps`（契约在位） | **本期无消费方**（team-lead 裁定不实装，§3.5）。设计稿不引用；将来实装时详情页优先用 `/chain` 的 `reasoning_trace`，**不双拉**。<br>**备查（将来实装时必踩的坑）**：422 已带 `StepRejectDetail.reason_code`（`step_limit_reached` / `invalid_phase` / `description_too_long` / `evidence_too_many`），但取值路径是 **`res.data.reason_code`，不是 `res.data.detail.reason_code`**——架构为此专门做了扁平响应体（`DecisionApiError` + 专属 handler）。另：`step_limit_reached` 是**系统容量上限、不是用户错误**，文案不得写成"你输入有误"，已存在的 199 条也不得渲染成失败态 |
| 详情页三个只读端点 | `/chain`、`/impact`、`/similar`，**本期行为不变** | 因果链图 / 影响面板 / 先例列表照现状消费；`evidence_entities[].name` 稳定返回 |
| 裁决留痕 | `DecisionRecord.resolution` | `action` / **`actor_type`**（`system \| user`） / `by` / `at` / `reason` → §4.8 三值 + §6.4.2 两种摘要 |
| 状态 | `DecisionStatus` 6 值 + `DecisionOutcome` 5 值 | §5.1.1 **双参**映射；契约里已写死 `toDisplayLabel(status, outcome)` 签名 |
| 历史数据 | `DecisionRecord.status_assumed: boolean`（`:781-787`） | §5.1.5 标注 + **不进队列任何一段** + 不出裁决/执行按钮 |
| 来源入口 | `DecisionEntrySource` 7 值 | §4.4；`entry_source` 为**单值**参数，筛选做单选 |
| SLA | `sla_state: ok \| warning \| breached` + 两个 `*_waited_minutes` | §5.2 直接消费三档，**前端不算阈值** |

### 10.2 缺口清单：19 条已关 16 条，3 条主动降 P1

> 降 P1 的三条是 **E**（"仅看证据不完整"筛选，口径未定）、**G**（台账 `sort=evidence_count`）、**J** 的证据数部分（队列 `sort_by=evidence_count_asc`；同条的 `confidence_asc` 已关）。这三条的共同处置是**整项不渲染**，不是"先放着"。

#### 10.2.1 已关闭（逐条记结论，便于后来人核对）

| 原缺口 | 关闭方式 | 对我的影响 |
|---|---|---|
| **A** `outcome` 单值 | 改 array + explode（`:57-71`），`maxItems: 5` | 结果多选可直接做；后端 `n.outcome IN $outcomes`，前端不拼 OR |
| **B** `/pending` 恒空 | 改按待办域过滤（`pending\|decided\|executing`）再二分；`counts` 与 `grp` **同一表达式** | §5.1.2 三段分组定稿；新增验收：`counts.to_execute > 0` 时第 2/3 段不得为空 |
| **C** SLA 表达不了三档 | 改 `sla_state` 三档 + 删 `sla_minutes`/`stale_minutes`（阈值走服务端配置，**客户端不得自定义**） | §5.2 直接消费；**我的"补三档"诉求满足，但不是我建议的入参形式——架构和 team-lead 的做法更好**，入参会让人改前端就把"已超时 40 条"变成 0 条 |
| **D** 缺置信度区间 | 补 `min_confidence` / `max_confidence`（0–1，`min>max` **422 而非静默空集**） | 三档 Segmented 映射成 min/max 对，不要求后端加枚举 |
| **E** 缺证据不完整筛选 | **主动降 P1，本期不渲染** | §4.3 该控件直接删除，不加灰色占位 |
| **F** 缺 `agent_id` | 补参数 + 响应字段；明写"空间内收窄维度，不是租户边界" | E27 可做；且该注释正好防止有人把 `agent_id` 当隔离手段 |
| **G** `sort` 缺 `evidence_count` | **不再补，降 P1**（`api-spec.yaml:22` 明确本期不做） | "证据数"列**照常显示但不给排序**。原设计"列头可点击降序"作废——契约无此键，渲染排序标记就是假控件 |
| **H** `q` 搜 `reasoning` | **按 PRD 删掉**（`:120-126` 明写不含 reasoning，并给了性能理由） | 搜索结果噪音问题解决；我的 `q` 文案按"问题 + 推荐方案" |
| **I** `total` 无估算标记 | `total_is_estimate` 恒返回；`page` 上限 100、超出 422 | "约 N 条" + 禁用跳末页有依据了 |
| **J** `/pending` 排序缺项 | 补 `confidence_asc`；`evidence_count_asc` **降 P1 不补** | §5.2 排序切换**只剩"置信度"一项**，且只在第 1 段显示（第 2/3 段固定 `waited_desc`，不渲染切换器）。原"证据数排序"整项不渲染 |
| **K** `execute`/`retry` 无归属 | `available_operations` 改为"当前能做的操作"，由状态机**单点派生**，队列与详情页共用同一函数；`decided→[execute]`、`failed→[retry]` | §5.1.3/§5.1.4 定稿；`retry` 不是"无归属"，只是"不出现在队列" |
| **M** `selected_option` | **删除**（`Resolution` + `ResolveDecisionRequest` 两处），**没有留带开关的扩展字段** | 前端连只读回显都不需要；PM 同时升级为 E35「裁决不得改选」，合法替代路径是"驳回 + 理由里写建议方案" |
| **N** `expected_outcome` 语义未定义 | **一并删除** | 语义未定义的字段留着只会被猜着用，删对了 |
| **O** `available_actions` / `RecommendedAction` 撞名 | 前者改名 **`available_operations`** | 我全文已重命名（17 处）；TS 里再加 `type AvailableOperation` 别名，注释写明与 `RecommendedAction` 的区别 |
| **P** 三个只读端点未收录 | **确认行为不变**，仅被 `decision_hub` 复用 | 我的唯一硬阻塞解除；`DecisionChainGraph` 不加兼容分支 |
| **Q** 历史数据无法区分 | 补 **`status_assumed: boolean`**（**team-lead 裁定用已有字段，否决"`status` 可空"**） | 比我提的"`status` 可空"更好（理由见 §5.1.5）：`null` 只能表达"不知道"，`status_assumed` 能表达"已推定但不可信"；更关键的是可空会**破坏迁移守卫**（`WHERE n.status IS NULL` 二次运行非 0 行）并污染 CAS（`coalesce(n.status,'pending')`）。**我的原建议撤回。** 已加验收：这类记录不得出现在**队列 / `counts`** 两处（走不同查询路径，只验队列会漏）；导出随 B5 降 P1 本期不存在，恢复时补第三条 |
| **R** `decided` 档等待时长无字段 | 补 **`decided_waited_minutes`**（自 `resolution.at`；缺失时回落 `updated_at` 并打 warning，**不让前端拿 null 自己猜**）。**team-lead 确认本期做**（成本很低：`resolution.at` 已有，派生即可，零新增存储），并升级为 PRD 验收 E38 | §5.2 第 2 段 SLA 可做；处理方式值得记成惯例：**缺值由服务端兜并告警，而不是把不确定性丢给前端**。另：`sla_state` 的计时基准**按 `group` 取**（`to_resolve` 用 `created_at`、`to_execute` 用 `resolution.at`），不写死这条，实现的人会拿创建时间给所有行算 SLA |
| **S** 推理路径无读取能力 | 契约已补 `GET\|POST /{id}/reasoning-steps`，**但 team-lead 裁定本期不实装**（不在本批范围） | 详情页不渲染该区块、`DecisionTimeline` 不下沉、Tab 收敛只做内嵌台账表半边。**契约保留、无消费方**，设计稿不引用它 |
| **T** SLA 分档计数无字段 | 补 `counts.sla_warning` / `counts.sla_breached`，**全库口径、不受分页影响** | §5.5 四个计数全渲染；我原本要的 `overdue_count`/`stale_count` 命名不同但能力等价，**按契约名写** |

#### 10.2.2 仍开着的（1 条，且有明确降级方案）

| # | 缺口 | 现状 | 我的降级 | 何时再看 |
|---|---|---|---|---|
| **E** | "仅看证据不完整"筛选 | 口径未定（0 条实体？出处 0 且实体 > 0？少于 N 条？） | **本期不渲染该控件**，不留灰色占位、不加"暂不支持" | 口径定后加 `evidence_incomplete: boolean`，语义 = `evidence_episodes` 为空 |

#### 10.2.3 我新发现的两处契约限制（不阻塞，但设计已适配）

**① `entry_source` 是单值参数（`:72-75`），不是数组**

我的原设计是多选 `Select`——PRD §4.2 只写"来源入口"，没明说单选还是多选。**改为单选。**

这一条的理由改过两次，两次都留在这里——**因为第一次是错的，而错的那版已经流通过**，不写明它错在哪，读到旧版契约的人会继续传播。

- **错的理由（架构初版，已撤回）**："多选在语义上等价于不传（= 全部），只是把同一个结果写得更长。"
  **为什么错**：勾选 `manual + pipeline` 是一次**真实收窄**，不是全选。把它说成"等价于不传"，会让维护者以为这个控件本来就是装饰品，从而**在别的筛选器上套用同样的错误推理**。
- **真的理由（架构纠正后）**：
  1. **没有需求支撑**。`status` / `outcome` 必须多值，是因为界面存在"执行成功 + 部分成功"这类跨值域组合诉求；`entry_source` 的 7 个取值里流量集中在 `manual` / `pipeline`，真实用法是"看某一条链的产物"，一次一个来源。
  2. **不做不封路**。标量参数改成可重复参数是**向后兼容**扩展：将来真要加，后端加 `List[...]`、前端把单选换多选，旧请求不受影响。

**准确表述是"没有真实用法支撑，且扩展成本为零，所以现在不做"**——既不是"语义上不可能"，也不是"需求被否"。这正是它作为单值正确、而将来加了也不算推翻的原因。三种措辞的差别见 §10.2.4，那里有分类判据。

要看来源构成，用台账按来源分组统计，不该用多选筛选。契约已加注"前端用单选/下拉，不要实现多选框"。

**② `outcome_details.action_status` 曾无结构承诺（`:775-777` 是 `type: object` + `additionalProperties: true`）**

详情页的 `rolled_back` 明细与「状态同步中」判据都依赖它，但契约不保证字段存在、也不保证取值集合——**测试会静默通过**（拿 `undefined` 和 `undefined` 比）。

**已闭环**：team-lead 与架构确认会显式声明，且核实 **pipeline 的 `_backfill_decision_outcome` 本来就写 `action_record_id` / `action_status` / `feedback_pipeline` 三个键**——属"把既有行为写实"，不扩能力。同时已要求后端确认 **`POST /{id}/execute` 路径也写**（流水线写了不代表执行端点写了，而判据依赖后者；若不写，详情页"窗口内状态同步中"这一档在刚执行完的窗口里永远空着，反而制造更长的假状态）。

**设计侧在字段声明前按 AC-14 保守实现**：取不到就不显示该态，只保留"执行中"。

#### 10.2.4 "本期不做"的三种性质必须分开写（PM 立的组内纪律，本节最适用）

写"本期不做"的人很多，但**不做的原因不同，后续行为完全不同**：

| 性质 | 该怎么写 | 写错会怎样 | 本次属于此类的 |
|---|---|---|---|
| **语义上不可能** | 说明为什么不存在 | 写成"暂不支持"会留下一个**永远不该做**的待办 | 无 |
| **本期不做、将来会做** | 写 P1 + 保留需求与理由 | 写成"不可能"会让后来人**以为这条路封死了**，不再评估 | B5 导出、证据数排序 |
| **本期不做、也不需要将来做** | 写"没有真实用法支撑、扩展成本为零，现在不做，将来加了也不算推翻" | 写成"暂不支持"留下待办；写成"不可能"是**伪造依据** | `entry_source` 单选 |

**共同纪律：不准把后两类包装成第一类。** 把"当前不做"说成"不可能"是一种**伪造依据**——它让后来人失去重新评估的机会，而他们本可以用新信息推翻这个结论。

> 我之前正好犯了这一条：把 `entry_source` 的"没有需求 + 不封路"写成了"语义上不存在多值"。已改为准确表述（§10.2.3 ①）。


### 10.3 语义冲突：全部已裁决（记录结论与我的接受情况）

| # | 冲突 | 裁决 | 我的立场 |
|---|---|---|---|
| **L** | `status` 与 `outcome` 双真相源风险 | **`status` 落库** + 写侧合法性矩阵（**7 合法 / 23 非法**，`(failed, partial_success)` 已收窄为非法）+ 同一条 Cypher 原子写（非法组合返回 409）+ 测试断言（E33 状态矩阵服务端强制 / E34 写入原子） | **我原来的"读时派生不落库"被否，我接受且已改。** 我的主张不可行——`action_record_id` 全仓从未被赋值，"派生"前置条件不成立，我当时没核实这一步。PM 的区分也对：US-8 要消灭的是**跨入口不一致**，不是"记录内有多个字段"。**前端警示图标兜底已撤销**——写侧断言让矛盾态写不进去，保留一个永不可达的分支会让后来人以为矛盾是允许的（§5.1.3） |
| **M** | `selected_option` 隐含"改选备选" | **删字段**，同时 PRD 新增 E35「裁决不得改选」；唯一合法替代是"驳回 + 理由里写明建议方案" | **完全同意。** 我的原话是"字段能力不得先于产品决策存在"——能力留着前端一定做成下拉框，而置信度重算规则还没定。删字段是唯一可靠解法 |
| **N** | `expected_outcome` 语义未定义 | **删字段** | 同意。未定义语义的字段比没有更危险：它会被当"能用"而猜着实现 |
| **O** | 两个 "action" 撞名 | `available_operations` 改名 | 已全文重命名，并按建议在 TS 里加别名 + 注释 |
| **H** | `q` 是否搜 `reasoning` | **不搜**（按 PRD），契约加了性能理由 | 同意。PRD 与契约本来相反，现在是契约服从 PRD，方向正确 |

### 10.4 契约里做对、值得固化的五处（记录下来，避免以后被"简化"掉）

| 项 | 位置 | 为什么好 |
|---|---|---|
| SLA 阈值**不入参**，走服务端配置 | `:960-968` | 若入参，前端改一个数字就能把"已超时 40 条"变成 0，SLA 机制变成摆设。**约束放在客户端不设防的地方是不设防。** |
| `counts` 与 `items` **同条件、全库口径、不受分页影响** | `:1000-1010` | 页内算出来的计数会让用户以为"只有 3 条超时"。且 `to_execute` 与 `grp` 同表达式，从根上消除"计数有、分组空"的不一致 |
| `decided_waited_minutes` 缺值**由服务端回落 + warning**，不丢 null 给前端 | `:951-957` | 把不确定性在源头消化，而不是让每个前端各猜一遍。**这条值得成为团队惯例。** |
| `available_operations` 队列与详情页**共用同一派生函数** | `:969-984` | 我上一轮最担心的"两处各判一次"从根上消失 |
| `DecisionStatus` 的 description 里**写死了映射签名** `toDisplayLabel(status, outcome)` | `:631-641` | 把设计约束写进契约，比写在设计文档里更难被忽略 |

### 10.5 本次沉淀的三条团队规则（team-lead 认可，跨项目适用）

这三条不是本项目的局部约定，是判断"某个设计该不该做"以及"某个数字可不可信"的通用尺子。本次各自被反复用到，写在这里避免下一轮重新论证。

**R1｜缺值由服务端回落 + 告警，不把不确定性丢给前端。**
`decided_waited_minutes` 缺值时不丢 `null`，服务端回落到 `waited_minutes` 并打 warning——若丢 `null`，每个前端都会各猜一遍"用哪个数"，猜测之间必然不一致。
**反面形态**：契约把 `optional` 字段留给前端自行 `??` 兜底。

**R2｜前端只对它能证实的事情负责。**
前端拿不到的、证不了的，就明确不做，**不加安慰性兜底**。因为兜底的前提是"我知道真值应该是什么"，而前端恰恰不知道。
本次四处实例，判据完全一致：

| 场景 | 错误做法（都被删掉或拒绝） | 为什么"不做"更对 |
|---|---|---|
| `entry_source` 契约单值 | 做成多选 | 传上去只用第一个值，用户以为生效了 → 假控件 |
| 推理路径区块本期不做 | 渲染空壳并写"暂无" | "暂无"读作"这里坏了"，而事实是"本期不做" → 假内容 |
| 状态矛盾 | 前端加警示图标兜底 | 写侧断言让矛盾写不进去，该分支永不可达 → 后来人会以为矛盾是允许的 |
| 筛选结果可疑 | 前端加"结果看起来不对"提示 | 前端只拿到结果集，反推不出漏了谁 → 无法证实即无法负责 |

**一句话**：**能证实的才负责；证不了的说"不做"，不要说"尽力兜一下"。**

**R3｜在别人正在编辑的文件上，不报绝对数字。**
同一份 `architecture.md`，我在三段统计里得到 **40 / 41 / 42 张表**，架构师在同一时段报 **39**。差异不在判据，**在快照**——两边都觉得自己对，而且都对，只是对的是不同时刻的文件。
这比误报更隐蔽：**误报会被核对推翻，快照差异不会**，因为双方的数字各自都成立，谁都无法证明对方错。
**处置**：报数必须附 `sha256sum` 前 16 位（或 git commit）；先确认"看的是同一份"，再谈数字是否一致。**跨人核数字前先钉快照。**

这三条的共同点：**都是在防止"看起来对"被当成"确实对"**——R1 防"缺值被各猜一遍"，R2 防"证不了的被兜底掩盖"，R3 防"不同时刻的数字被当成同一事实"。

### 10.6 错误读取：三套形状并存，读取只允许一处封装（契约 1.5.0）

契约 1.5.0 起 `APIError` 接上了统一信封（**AC-17**：决策模块路由体内禁用 `HTTPException`），但**本域仍然三套形状并存，这是契约里的显式声明（`Unprocessable` / `ErrorEnvelope` 两处 description 都写了），不是没改完**。前端如果按"已经统一了"去写，会在 401 / 字段校验这两条最常走的路径上崩。

| 形状 | 谁用 | 长相 |
|---|---|---|
| **信封** | **403 `FORBIDDEN` / 404 `NOT_FOUND`** / 409 三个冲突码 / 本域显式 422 四码 / 500 | `{"error": {"type","code","message","request_id","path","details"}}` |
| **`detail` 字符串** | **401**（`HTTPException`，AC-17 例外一）、**422 缺 workspace 声明** | `{"detail": "未认证"}` |
| **`detail` 数组** | FastAPI 字段级校验 422（`page > 100` 等，AC-17 例外二） | `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` |

**注意 403 / 404 这轮从"`detail` 字符串"迁到了信封**，这正是 AC-17 的效果。**401 没有迁**——它是共享依赖产出的，没有 `code`。

#### 唯一允许的错误读取入口

```ts
// services/apiError.ts —— 全项目只此一处能碰 resp.error / resp.detail
parseApiError(resp): {
  status: number;                       // 必须带，理由见下
  code?: string;                        // 仅信封里有；不在 ErrorCodeCatalog 内 → 视为未知
  message: string;
  details?: Record<string, unknown> | null;
}
```

**调用点不得各写 `resp.error?.code ?? resp.detail`。** 三处各写一套的后果是：同一个 409，队列页显示「已被张三处理」、详情页显示「操作失败」——用户会以为是两个不同的问题。

**`status` 必须一起返回，不能只给 `code`。** 因为 **401 没有 `code`**（AC-17 例外一，`HTTPException` 直出 `{"detail": "..."}`），而 401 与 403 的处理动作完全不同：

| | 401 | 403 |
|---|---|---|
| 语义 | 没登录 / token 失效 | 登录了，但没这个权限 |
| 动作 | **跳登录页** | **就地提示，不跳转、不清空页面** |
| 有无 `code` | **无** | `FORBIDDEN` |

只靠 `code` 判，401 拿到 `undefined`，前端只能落到"未知原因"的通用提示——用户明明只是登录过期，却看到一句"操作失败"，而且**不会自动去登录**。所以 `status` 是判据的一部分，不是附加信息。

四条实现规则：

1. **信封优先**：有 `error` 就取 `error.code` / `error.message` / `error.details`。
2. **旧形状走降级，不崩**：`detail` 是**字符串** → 直接当 `message`；`detail` 是**数组** → 取 `detail[0].msg`。**直接把数组塞进 `Alert` 会渲染成 `[object Object]`**，这是最常见的翻车点。
3. **`code` 缺失 ≠ 成功**：只说明该分支没有机器可读原因（500 / `ValueError` / 裸 `HTTPException`），走通用文案 + 展示 `request_id`。**不得跳过提示，不得让 `undefined` 出现在界面上。**
4. **按 `code` 判断，不按文案**。文案匹配会在改一句话时静默失效，而且失效时**不会报错，只会让提示变成默认那条**——这正是最难发现的一类错。

#### `error.code` 与文案：**穷举源是契约的 `ErrorCodeCatalog`，不是这份表**

契约 `ErrorCodeCatalog` 列了本域 `error.code` 全集 **13 个**，并明写"新增码必须同时更新本表与前端 `parseApiError` 的映射"；**不在这张表里的码一律按"未知原因"处理（通用文案 + `request_id`），不得猜测、不得当成成功**。

所以前端的映射写成 `Record<ErrorCode, …>`，而 `ErrorCode` 是**从契约抄死的 TS union**。这样漏一个码会在编译期红，而不是在运行时静默落到通用文案。

| `code` | 状态码 | 场景 | 文案 | 挂载位置 |
|---|---|---|---|---|
| `illegal_transition` | 409 | 状态已被抢先改 / 当前状态不允许该动作 | 「该决策已被 {handler_name} 处理」，`handler_name` 为 `null` 时降级为「该决策已被他人处理」 | toast |
| `execute_in_progress` | 409 | 另一请求正在派发 | 「该决策正在执行中，无需重复发起」 | 卡片内 `Alert` |
| `concurrent_append_conflict` | 409 | 并发追加推理步骤撞车 | 「该决策刚被更新，请刷新后重试」 | 卡片内 `Alert` |
| `NOT_FOUND` | 404 | 不存在**或跨空间（两者不区分，不泄漏存在性）** | 「决策不存在，或你没有权限查看」——**不得写成"不存在"**，跨空间时那是一句假话；也**不得回显 `decision_id`** | 页级空态 |
| `FORBIDDEN` | 403 | 属于当前空间但无操作权限 | 「你没有该操作的权限」 | 就地提示，**不跳转、不清空页面**（§5.4 权限只读） |
| `missing_action_payload` | 422 | 执行请求缺载荷（body 与 `recommended_action` 均空） | 「该决策还没有可执行的方案，请先补充推荐动作」 | 表单整体 |
| `batch_empty` | 422 | `decision_ids` 为空 | 「请先选择要处理的决策」 | 批量操作条 |
| `batch_size_invalid` | 422 | `decision_ids` 超 50 条 | 「一次最多处理 50 条，当前 {n} 条」 | 批量操作条 |
| `reason_required` | 422 | `action=reject` 但 `reason` 缺失或 <5 字 | 「驳回需要填写理由（至少 5 字）」 | **驳回理由输入框**（用户改这个框就能过） |
| `step_limit_reached` | 422 | 推理步骤达 200 条上限（**系统容量，非用户输入错误**） | 「该决策的推理步骤已达上限（{limit} 条），无法继续追加」 | **表单整体**（`field=null`）。**已存在的步骤不得渲染成失败状态** |
| `invalid_phase` | 422 | `phase` 取值不合法 | 「阶段取值不合法」 | 按 `details.field` 定位到该表单项 |
| `description_too_long` | 422 | `description` 超 1000 字 | 「描述超出长度上限」 | 按 `details.field` 定位到该表单项 |
| `evidence_too_many` | 422 | `evidence` 超 20 条 | 「证据最多 {limit} 条」 | **按 `details.field` 定位到证据字段** |

**一律用 `{limit}` / `{step_count}` 插值，不写死数字**——契约里数字会变，文案写死就会在某次调阈值后变成假话。所有插值字段都要有 `null` 分支（同 §5.3「handler_name」）。

#### 一个必须照字面写的坑：13 个码里 **2 个大写、11 个 snake_case**

`NOT_FOUND` / `FORBIDDEN` 是全大写，其余 11 个是 `lower_snake_case`。这是**已落进契约的现实**，不是笔误可改的。

前端**按字面匹配，禁止做大小写归一化**：

```ts
// 错法：归一化
const key = err.code?.toLowerCase();          // NOT_FOUND → not_found
switch (key) { case 'not_found': ... }        // 若映射表按 catalog 原样写，这里永远不命中

// 正法：原样查表，键就用契约里的字面
const table: Record<ErrorCode, Msg> = { NOT_FOUND: ..., FORBIDDEN: ..., illegal_transition: ... };
```

为什么禁止归一化：**归一化会掩盖契约里的不一致**，等到后端某天把两个码统一成 snake_case（或反过来把其余 11 个改成大写），归一化那版**不会报错、只会静默失效**——因为它的键和值都归一化过，看起来永远匹配得上，实际业务映射已经错位。这正是本节开头那条「按 `code` 判断、不按文案」要防的同一类失败：**看起来在工作，实际在走默认分支。**

（这条已上报架构：风格不一致本身是契约问题，但前端不能靠"帮它抹平"来解决。）

#### `details` 的分支差异：409 没有 `field` 键，422 才有

架构师口述的「`error.details.field` 恒存在（不适用给 `null`）」**只在 422 成立**，409 不是这个形状。按契约的 schema 精确写：

| 分支 | `error.details` 形状 | `details` 本身可为 `null`？ |
|---|---|---|
| **422**（`StepRejectDetail`） | `{field, step_count, limit}` **三键恒存在**，不适用给 `null` | 否（契约明写三键恒存在） |
| **409 `illegal_transition`**（`ConflictDetail`） | `{handler_name, current_status}`，**没有 `field` 键**；`handler_name` 可为 `null` | 否 |
| **409 `execute_in_progress` / `concurrent_append_conflict`** | `{}` **空对象**，没有 `field` 也没有 `handler_name` | 否 |
| **任意错误（`ErrorInfo.details`）** | `type: object, nullable: true` | **是**——`details` 可能是 `null` |

所以读法必须分两层，而不是笼统"判 null"：

```ts
// 第一层：details 本身可能为 null（ErrorInfo 是 nullable: true）
const details = err.details ?? {};

// 第二层：422 分支用「值为 null」表达"不挂字段"；409 分支根本没有这个键
//         两种情况统一成同一句判断，才既不吃 null 也不吃 undefined
const field = (details as { field?: string | null }).field ?? null;
if (field) { 挂到该表单项 } else { 挂在表单整体 }
```

**这样写同时满足两边**：422 的 `field: null` → 挂整体；409 的键缺失 → `?? null` → 挂整体。而且**没有一处依赖"键在不在"**。

```ts
// 三个错法，都试过它们的后果：
if ('field' in details) { ... }        // 409 上永假、422 上永真 —— 结构恒定，判了等于没判
if (details.field !== undefined) { ... } // 409 上 undefined、422 上 null —— 两种"没值"两套行为
details.field                           // details 为 null 时直接 TypeError
```

**这与我第一次给 SLA 判据时犯的错同类**：拿"字段在不在"当语义判据。字段在不在是**结构事实**，业务含义在**值**里；结构恒定时判结构，等于没判。而且它不报错，只在某一条分支上悄悄走错。

#### 为什么 `request_id` 必须展示

500 类错误没有 `code`，用户唯一能提供给你排查的信息就是 `request_id`。它是**前端确实拿到了的值**（符合 R2：能证实的才负责），所以必须出现在错误提示里——写成可复制的等宽文本，不要藏在 tooltip 里。

## 11. 给前端的实现提示（交接要点）

1. **不要新建表格组件**，用 `@/modules/shared` 的 `AdvancedTable`（`AdvancedTable.tsx:610`）。参数对照见 §4.2；`search={false}` 已内置，筛选区自己写在表格上方。
2. **不要新建主题或改 `global.css`**。决策模块只消费 `--odap-*` 变量。需要新 token 时提给架构师，不在组件里写字面量。
3. **`OUTCOME_META` 的 `color` 字段要删**，改为 `DecisionStatusTag` 接收 `status` + `outcome`。删之前先 grep 使用点（`PrecedentSearch.tsx:64,74`、`DecisionIntelligencePage.tsx:53,92`）并一并改。**新建单一映射点 `DecisionStatusTag.tsx`，`displayStatus.ts` 里只放纯函数、不放色值**——组件负责渲染，纯函数负责判档，两者都不许有第二份。
4. **`DecisionChainGraph` 的 `useEffect` 依赖必须加 `nodeColors`**，否则主题切换图不重绘。
5. **详情页路由用 `/decisions/detail/:decisionId`**，不要用 `/decisions/:decisionId`——否则与 `/decisions/ledger`、`/decisions/queue` 的静态段产生匹配歧义（虽然 react-router v7 静态优先，但显式加 `detail/` 段更可读、更安全）。
6. **筛选条件写 URL query**，不要只依赖 `KeepAliveOutlet` 的组件缓存（缓存是内存态，刷新即失）。
7. **状态映射必须是纯函数 `toDisplayLabel(status, outcome)`**，放 `modules/decision/utils/displayStatus.ts`，台账/队列/详情/队列卡片四处共用。**必须同时吃 `status` 和 `outcome`**——因为 `status` 只有 `executed`，没有 `partial_success`，只按 `status` 渲染会丢掉"部分成功"这个 PRD 明确要求的标签。原设计的 `deriveVisibleStatus(record, action)` 已取消（后端直接给 `status`）。**这条 team-lead 特别点名过：标签映射只允许一处实现，严禁任何组件内再判一次**（`status === 'executed' && outcome === 'partial_success'` 这种判断写在组件里就是第二个真相源，改一次要改四处，且必然漏一处）。契约 `DecisionStatus` 的 description 里已写死这个签名，可以直接引给评审看。

   **反向的映射 `toLedgerQuery(displayStatuses)` 必须与它同文件、成对维护**（§4.3）——正向是人话←数据，反向是人话→查询参数，只改一个必然对不上。
8. **批量裁决只有第 1 段可勾选**（`available_operations` 含 `approve`）。第 2 段（`decided`）不显示 Checkbox——它的主操作是"发起执行"，批量执行不在 PRD §5.5 范围内，不要顺手扩。上限判断前端做一次（禁用 + 内联提示）后端再做一次（硬拒）。
9. **不要给 `<768` 档写横向滚动的表格**，直接换卡片列表（§8.2）。
10. **图标只从 `@ant-design/icons` 里取**，按下表 §1 的语义映射，尺寸 16/20/24，不要 `fontSize` 随手写。
11. **台账必须拆成「页面壳 + 可复用表」两层**（§3.5）：`DecisionLedgerTable` / `DecisionFilterBar` 是纯组件，`DecisionLedgerPage` 才是路由页面。Agent 页 Tab 要嵌同一个表，写成页面就复用不了。**A1 一开始就得按可复用写**，不要先写页面再回头拆。
12. **结果标签只有 5 类文案、4 个色系**（§2.2 / PRD §4.1.1）：`待定（待裁定）` 与 `待定（待执行确认）` 同色，靠图标 + 括号文字 + 队列分组区分。**不要给"待执行确认"单独配色**——PRD 已把这条写成验收口径。
13. **不要用"前端补传 workspace_id"去修 Agent 决策链的越权问题**（§3.5 / PRD E26）。那只是把"空上下文返回全量"换成"伪造上下文读别人空间"。修法在服务端：给三个端点加 `workspace_id: str = Depends(get_current_workspace)`（`odap/infra/security/workspace_access.py:154` 已有，fail-closed 422），并把 workspace 下推给 service 做过滤与主键归属校验。前端这边只需**不再自己传** workspace。
14. **`embedded` 模式必须显示过滤语境标签**（§4.3 末节）：Agent Tab 里表格被 `agentId` 隐式过滤，界面必须有一枚"当前仅显示 {Agent 名} 产生的决策"提示，否则用户会以为台账漏数据。**隐藏的是控件，不是状态。**
15. **详情页 404 与 403 要分开**（§6.5）：跨工作空间一律 404（不泄露存在性），只有能确认属于当前空间但无权限时才 403。
16. **队列分组与可用动作都用后端字段，不要自己判**（§5.1.2）：`group` 直接用，不要从 `status` 反推；按钮由 `available_operations` 数组驱动，不要按 `status` 硬编码按钮组合。后端改了状态机，前端不该跟着改。
17. **`available_operations` 为空时不要渲染禁用按钮**（§5.1.4）：`to_execute` 组渲染两个灰按钮会让用户误判成"我缺权限"。空数组 → 整组不渲染，换成进度说明文字。**禁用态只用于"你没权限"，不用于"这个动作对谁都不存在"。**
18. **裁决留痕从 `decision.resolution` 取**（`{action, actor_type, by, at, reason}`）。**判来源用 `actor_type`，不要用 `by` 的字符串或空值反推**（§4.8）：`actor_type === 'system'` → "系统（策略门禁）"+ `SafetyCertificateOutlined`；`actor_type === 'user'` → "张三 · 时间"；`resolution` 为 null 且 `status === 'pending'` → "未处理"；`status_assumed === true` → "—"。**"未处理"不能被历史数据复用**——它暗示"还在等人处理"，而历史数据是"根本没记录过流程状态"。**也不要用 `by === 'system'` 判门禁** —— 那是拿显示名当语义判据，改一次显示名就全错。
19. **门禁拒绝与人工驳回的摘要用同一位置同一字号，只在标签前缀区分**（§6.4.2）："门禁判定：" / "驳回理由："。**不要给门禁摘要单独的底色或容器**——它是同一字段的另一种来源，不是另一种卡片。混在一起会让"策略门禁太严还是太松"永远答不出来。
20. **执行状态：台账 4 档 / 详情 8 态，两套映射都要有唯一实现点**（§4.6 / §6.4.1）。台账 `toExecutionTier(actionStatus)`、详情 `toExecutionLabel(actionStatus)`，都放 `displayStatus.ts`。**「无动作」不是第 5 档，是这一列的空态**（`action_record_id` 为空）：前者是动作已派发但没启动，后者是决策根本还没派发执行，用户下一步动作完全不同（催执行 vs 催裁决）。**把两者并成一格，"已裁决未执行"在列表里就会看起来和"正在校验"一样。**
21. **不要用 `waited_minutes` 算 `decided` 档的等待时长**（§5.2）：它是自**创建**起算的。`decided` / `executing` 档要用 `decided_waited_minutes`（自**裁决**起算）。用错会把"昨天裁决的"显示成"等了 5 天"，这类数字一旦错，用户对整个 SLA 机制就失去信任，且不会有人报障——他们只会不再看这个标记。契约已补该字段（`:951-957`），缺值时服务端会回落并告警，**前端不要拿 null 自己猜、也不要顶替**。
    **SLA 三档直接消费 `sla_state`，不要自己比时间算阈值**——阈值走服务端配置，契约明写"客户端不得自定义 SLA 口径"。
22. **队列是三段不是两段**（§5.1.2）：`to_resolve` 段（`status=pending`）、`to_execute` 段再按 `status` 拆成 `decided`（有 `execute` 按钮）与 `executing`（只读）。**不要把 `decided` 和 `executing` 混成一段无按钮的"处理中"**——那样用户只看到一堆"在跑"，不会注意到其中一部分根本没开始。
23. **历史数据（`status_assumed === true`）不进队列任何一段**（§5.1.5 / §6.4.3）：一律归"待定"、标注"历史数据，流程状态未记录"、**不出任何裁决/执行按钮**。否则队列上线当天会被历史数据灌满假待办，用户点进去发现全是没法处理的东西，这个队列就废了。标注样式：`--odap-color-text-tertiary` + `InfoCircleOutlined`，**不做胶囊、不加底色**（胶囊会被读成"第七种状态"）。
    **标注必须是页面可见文字，不能只放 Tooltip**——截图、打印、键盘操作、屏幕阅读器快速浏览四种场景下 Tooltip 全丢。这条是架构明确要求的，不要为省空间改成 hover。
24. **契约缺口未补齐前不要造假功能**（§10.2）。当前**三项本期不渲染**，全部"整块不渲染、灰色占位和暂不支持文案都不要"：
    - **导出按钮**（B5，降 P1）：契约 `api-spec.yaml:22` 已移除 `/export.csv`。按钮不渲染，`permission-denied` 态下也不需要导出权限文案。
    - **"仅看证据不完整"筛选**（E）：口径未定，三个候选口径筛出来的集合完全不同。
    **为什么"灰色占位"比"不渲染"糟**（PM 的论证，比"规范要求"硬）：灰色占位告诉用户"**这里有功能，只是不给你用**"，用户会去找权限、找设置、问管理员；不渲染告诉用户"**这一期没有这个功能**"，用户会接受。同一份代码，两种说法的用户行为完全不同——**前者制造无效动作，而无效动作比缺失更消耗信任**。这条适用于所有降 P1 项，不只这一处。
    - **证据数排序**（G/J，降 P1）：台账表头不给排序标记、队列排序切换器只剩"置信度"一项。**但"证据数"列照常显示**——不排序 ≠ 不显示，这两件事别混。
    其余（`agent_id` / `outcome` 多选 / SLA 三档 / 置信度区间 / `decided_waited_minutes` / `status_assumed`）**契约都已到位，可以直接接**。`reasoning-steps` 契约也在位，**但 team-lead 裁定本期不实装**，所以不要接——"契约有"不等于"该做"。
    **通用规则（team-lead 要求写进交接，作为今后遇到契约缺口的统一处理方式）**：渲染一个点了没反应的筛选器，比不渲染更伤信任——用户会开始怀疑整个页面的数据是否可信。**宁可不渲染，不留空壳控件，也不加"暂不支持"的灰色占位**。需要说明时在文档/注释里写，不占界面。
25. **`entry_source` 是单值参数**（§4.4 / §10.2.3）：筛选做**单选** `Select`，不要做多选。做了多选就是假控件——传上去只会用第一个值，用户还以为多选生效了。
26. **`q` 不搜 `reasoning`**（§10.2.1 H）：契约已按 PRD 删掉 reasoning，搜索范围为 `context_summary` + `recommended_option`。占位文案也据此写，不要写"搜索问题、方案或推理过程"。
27. **详情页不做推理路径区块**（§3.5）：team-lead 已裁定本期不实装，**整块不渲染、不写"暂无"、不留占位**。`reasoning-steps` 契约虽在，本期无消费方。将来实装时记住一条：已拉 `/chain` 就用响应里的 `reasoning_trace`，**不要双拉**。
28. **`counts.to_execute > 0` 时第 2/3 段不得为空**（§5.5）——这是防"次队列恒空"复发的回归断言，team-lead 会让 QA 按这条测。造 3 条 `decided` 验有、造 0 条验空，两遍都要跑。**计数与分组必须来自同一条查询的同一个 `grp` 表达式**，不是两条同条件查询；分开写迟早漂。
29. **「状态同步中」只在详情页，判据三级，且三支都必须有出口**（§5.1.3 / §6.4.1 / §7.3，PM E41 + 架构落地）：
    - **出口是恒定列**（Spec **AC-15**）：**任何 `status=executing` 渲染，含未超阈值，都必须渲染「查看执行记录」入口**。**不要把它写成"超窗后的补救"**——那样删掉 ① 时会连 ② 的出口一起删。
    - 文案分三支：未超窗 → ① `action_status` 终态＝「状态同步中」、② 进行中＝「执行中」、③ 拿不到/不可解析＝「执行中」（AC-14：没证据不给结论）；超窗（`SYNC_STALE_MINUTES` = `constants/decisionConfig.ts` 默认 10 分钟，依据 `updated_at`）→ ①③ 改「状态可能未同步，请检查执行记录」、**② 文案不变**。
    **核心原则**：任何一支都不允许存在"没有出口的长期状态"，**区别只在文案，不在要不要给出路**。
    **② 也要给出口的理由**（PM 补的，我原来漏了）：② 有证据，但**"有证据"不等于"可证伪"**——用户看到"执行中"十分钟，能做的仍然只有等。**跑得久不是错误，"跑得久且查不到"才是。**
    **三支超窗后处理不同**：①超窗**撤承诺**（原文案"会自动同步"有期限）；②超窗**补出口**（"执行中"是陈述，仍真就照说）；③超窗**撤默认值**（未超窗的"执行中"是未被证伪的默认值，不是断言）。
    另：`sla_state` 只有 `/pending` 有（`:903/935`），**我原写"超 SLA 即同步中"是字段用错 + 信号偷换**（SLA 档位≠回写完成度，会让每次正常执行都闪异常）。**四套时间轴（`created_at` / `resolution.at` / `updated_at` / `sla_state` 按 group 取基准）不得混用**。
30. **`idempotent_replay=true` 时文案必须变**（§5.3）：toast 写「已按当前执行状态同步」，**不能写"已发起执行"**。用户没做新动作，界面不该让他以为自己做了。这个判断只能靠响应标记，前端不能猜。
31. **`toDisplayLabel` 现在是一张 7 行纯查表，不要加默认分支**（§5.1.1）：矩阵已收窄到 7 合法 / 23 非法，非法组合返回 409、写不进去。所以**不需要** `if (status === 'failed' && outcome === 'partial_success')` 这类兜底——那种行不存在。加了反而会让后来人以为矛盾是允许的。
32. **`status_assumed=true` 的排除要验两处，且都要验**（§5.1.5）：队列 `items` 与顶部 `counts`——**走不同查询路径**（分页查 vs 聚合查），只验队列会出现"列表干净但计数还带着"。team-lead 原来要求验三处，第三处 CSV 导出随 B5 降 P1 **本期不存在**；**恢复导出时必须把排除条件补回第三条查询**（导出走独立路径，最容易漏）。
33. **执行类操作的三条硬约束**（§5.1.6，对应 E36 执行幂等与失败回写）：① `decided → executing` 成功后卡片必须移出第 2 段，不能留原地变灰；② `status !== 'decided'` 时**忽略** `available_operations` 里的 `execute` 并 `console.warn`（防后端误传）；③ 重复发起必须幂等，按钮提交后到响应返回前**不解除 loading**，成功后按返回的 `action_record_id` 更新，不做乐观递增。
34. **筛选结果与标签必须一致——这是 QA 的断言，不是观感检查**（§4.3 必读前提）：对同一份种子数据，6 个人话选项各筛一次，逐条比对「返回记录的 `toDisplayLabel()` 结果」与「所选选项」，**双向都要验**（返回集内无他项 / 他项集内无返回项）。这条不通过说明后端矩阵（E33 状态矩阵服务端强制）或前端翻译表有一处失效，**且失效时页面不报错、只是结果错**，人眼抽查容易放过。team-lead 已按 AC-09 反向一致性收录。
35. **前端无法自证筛错了**（§4.3）：不要试图在前端加"结果看起来不对"的兜底——前端只拿到结果集，反推不出自己漏了谁。这是团队规则 **R2「前端只对它能证实的事情负责」** 的一次应用（§10.5），与"不渲染假控件""不写暂无占位""不做前端自审"同一条判据：**做不到的事就明确不做，不做半吊子补救**。
36. **错误只能从 `parseApiError()` 读，全项目一处**（§10.6，契约 1.5.0 / AC-17）：本域**三套错误形状并存**（`{error:{...}}` / `{detail:"str"}` / `{detail:[...]}`），这是契约显式声明不是没改完。AC-17 把 **403 / 404 也迁进了信封**，但 **401 没迁**（共享依赖，无 `code`）。五条最容易翻车的：① `detail` 是**数组**时直接塞进 `Alert` 会渲染成 `[object Object]`，必须取 `detail[0].msg`；② **按 `code` 判断，不按文案**，文案匹配失效时不报错、只会静默落到默认提示；③ **`code` 缺失 ≠ 成功**，走通用文案 + 展示 `request_id`，不得让 `undefined` 出现在界面上；④ **返回值必须带 `status`**——401 没有 `code`，而 401（跳登录页）与 403（就地提示不跳转）的动作完全不同，只靠 `code` 判的话登录过期会被当"未知原因"；⑤ **`ErrorCode` 用契约 `ErrorCodeCatalog` 的 13 个字面量做 TS union，漏一个编译期红**，不在表里的码归"未知原因"，不得猜测、不得当成功。
    另：**13 个码里 `NOT_FOUND` / `FORBIDDEN` 是全大写、其余 11 个是 snake_case，按字面匹配、禁止大小写归一化**——归一化能"抹平"当下，但后端哪天统一风格时它不会报错、只会静默错位。
37. **`details` 分两层读，且一处都不判"键在不在"**（§10.6）：① `error.details` 本身**可为 `null`**（`ErrorInfo.details` 是 `nullable: true`），先 `?? {}`；② **422** 的 `details` 三键恒存在、用 `field: null` 表达"不挂字段"；**409 根本没有 `field` 键**（`illegal_transition` 是 `{handler_name, current_status}`，另两个 409 是 `{}`）。统一写 `const field = details.field ?? null`，两种"没值"收敛成同一行为。**`'field' in details` / `!== undefined` / 裸 `details.field` 三个错法各错在不同分支上，且都不报错。**
    另：**`evidence_too_many` 必须指到证据字段，不能挂表单整体**——用户删几条就能过。契约 `Unprocessable` 把它和 `invalid_phase` / `description_too_long` 归为同一类（用户输入问题，按 `field` 定位），只有 `step_limit_reached`（200 条上限）是 `field=null`。**提示存在但不指向动作，用户只能放弃。**

### 11.1 改动落点清单（谁改哪个文件）

架构师给过一份归属表，我按最新团队构成补一条意见：**团队现在已有专职前端（`mvp-dev-expert-team-frontend`），代码归属应给到他，我的交付物是规格与判据，不是 diff。** 理由：我写的代码没人做 code review 承接，而前端有。下面是"改什么 + 判据在哪"，可直接当任务卡用。

| 文件 | 改什么 | 判据 |
|---|---|---|
| `modules/decision/components/DecisionStatusTag.tsx`（新建） | 唯一渲染点：吃 `status` + `outcome`，调 `toDisplayLabel` | §2.2 / §5.1.1 / §2.6 |
| `modules/decision/utils/displayStatus.ts`（新建） | 四个纯函数，**零色值**：`toDisplayLabel(status, outcome)` / `toLedgerQuery(filters)` / `toExecutionTier(status)` / `toExecutionLabel(status)`。架构另提了 `toStatusToken(status)`，若要保留，**它只能返回语义等级**（`warning` / `success` / `error` / `neutral`），由 `DecisionStatusTag` 经 `theme.useToken()` 映射成 `--odap-*`——**纯函数不接触颜色体系**，否则"零色值"这条守不住。**`toExecutionTier`（台账 4 档）与 `toExecutionLabel`（详情 8 态）必须是两个函数，不能合并**——合并就意味着台账显示 8 态或详情只剩 4 档，这正是 §4.6 开头"为什么详情页必须给 8 态"要解决的问题 | §4.3 / §5.1.1 / §4.6 / §6.4.1 / §11 第 20 条 |
| `modules/decision/constants/decisionConfig.ts`（新建） | `SYNC_STALE_MINUTES = 10`（状态同步窗口）。**前端单点常量，不入契约**——它只决定"说哪句话"，不改变任何数据集合 | §6.4.1 / §11 第 29 条 |
| `modules/shared/services/apiError.ts`（新建，**全项目共用**） | `parseApiError(resp) → {code?, message, details?}`。**唯一允许读 `resp.error` / `resp.detail` 的地方**；三套形状（信封 / `detail` 字符串 / `detail` 数组）在这里收敛。**不要把决策域专用的 `error.code → 文案` 表塞进去**——那是决策域的，放 `modules/decision/utils/errorMessages.ts`，`apiError.ts` 只负责"把任意形状读成 `{code, message, details}`" | §10.6 / §11 第 36-37 条 |
| `modules/decision/utils/errorMessages.ts`（新建） | `code → 文案` 映射，**键类型是 `ErrorCode`（从契约 `ErrorCodeCatalog` 抄死的 13 个字面量 union），写成 `Record<ErrorCode, …>` 让漏项在编译期红**；另加 `status === 401 → 跳登录` 的分支（401 无 `code`）。插值字段（`handler_name` / `step_count` / `limit` / `n`）全部带 `null` 分支。**按 `code` 原样查表，不做 `.toLowerCase()` 归一化**（`NOT_FOUND` / `FORBIDDEN` 是大写） | §10.6 的 13 行文案表 / §11 第 36 条 |
| `modules/decision/types.ts:68-74` | 删 `OUTCOME_META` 的 `color` 字段（保留 label 或整体下线） | §11 第 3 条 |
| `modules/decision/components/PrecedentSearch.tsx:64,74` | 改用 `DecisionStatusTag` | 同上 |
| `modules/decision/pages/DecisionIntelligencePage.tsx:53,92` | 两处 `OUTCOME_META` 替换为 `DecisionStatusTag` | 同上 |
| `modules/decision/components/DecisionChainGraph.tsx` | 加 `nodeColors?: Record<string,string>` prop + `useEffect` 依赖补 `nodeColors` + 空态文案改"没有上游因果链记录" | §6.2 / §7.4 |
| `modules/decision/components/ImpactPanel.tsx` | `partial` 文案补"下游决策数为 0 不代表没有下游决策" | §6.3 |
| `modules/decision/utils/ledgerQuery.ts` | **删掉 `LedgerSort` 里的 `'evidence_count'`**（PM 核过：类型还在，会有人接上去） | §4.2 / §10.2.1 G |
| `modules/decision/components/ledgerColumns.tsx` | `evidence_count` 列**去掉可排序标记**，列保留 | §4.2 / §10.2.1 G |
| 台账工具栏 | **删除导出按钮**（不是 `disabled`、不是留位）；`permission-denied` 分支里的导出权限文案一并删除 | §10.1 / §11 第 24 条 |
| 队列卡片证据区 | 去掉 `?? 0`，派生不出时显示"证据数未知" | §5.2 证据行 |
| 队列排序切换器 | 删掉"证据数"选项，只剩"置信度"；第 2/3 段不渲染切换器 | §5.2 排序切换器 / §10.2.1 J |
| 详情页执行状态位 | **AC-15：`status=executing` 的任何渲染（含未超阈值）都必须有「查看执行记录」入口** —— 这是恒定要求，不是超窗补偿。文案：未超窗 终态→"状态同步中"、进行中→"执行中"、拿不到→"执行中"；超窗后终态/拿不到改"状态可能未同步"、**进行中不变**。**验收判据："executing 但没有任何入口"即失败，不需等到超窗** | §6.4.1 / §7.3 / §11 第 29 条 / Spec AC-15 |

**顺序建议**：`displayStatus.ts` + `DecisionStatusTag.tsx` 先行（它们是所有页面的依赖），然后再做台账 → 队列 → 详情。**不要先写页面再回头抽映射**，那样一定会写出第二份映射。

---

## 12. 交付清单核对

| 要求 | 位置 | 状态 |
|---|---|---|
| 图标库锁定 + 证据 | §1 | 完成（`@ant-design/icons`，187 文件，无混用） |
| Design Token 引用表 | §2（2.2 决策状态 / 2.3 完整度 / 2.4 通用） | 完成（0 色值字面量） |
| 信息架构 + 与现有页面关系 | §3（结论：改造 + 2 子路由；拆解复用） | 完成 |
| PM §13 Q3（台账/队列一页两 Tab 还是两个菜单） | §3.1-3.3 | 完成（采纳 PM 倾向，且进一步做到子路由：一页两视图 + 详情独立路由） |
| PM §13 Q4（详情独立路由还是抽屉） | §3.3 / §4.7 | 完成（独立路由，理由与 PM 一致，另补三条可行性证据） |
| PM §13 Q5（Agent 页决策 Tab 换数据源） | **§3.5** | 完成（含新发现的跨工作空间数据暴露 + IDOR；PM 已升级为 PRD G6 / E26） |
| PM §13 Q8（按 Agent 过滤是否做可见筛选器） | §4.3 末节 | 完成（隐藏参数 + 内嵌时语境标签可见） |
| 台账：列定义/筛选/四态/超大分页/行跳转结论 | §4.1-4.7 | 完成（整页跳转；执行状态列 4 档、裁决人 3 值） |
| 队列：卡片字段/裁决流程/批量限制 | §5.1-5.5 | 完成（3 动作按 PRD；三段分组；历史数据不进主队列） |
| 详情：三块布局 + 复用 + props 改动 + partial 文案 | §6.1-6.5 | 完成（3 态文案 + `task_id` 落位 + 执行动作 8 态 + 门禁/人工驳回区分） |
| 状态模型变更（PM：独立 `status` 6 值 / 三段队列 / 4 档执行列 / 裁决人 3 值 / 历史数据） | §4.6 / §4.8 / §5.1.1-5.1.6 / §6.4.1-6.4.3 | 完成（`toDisplayLabel(status, outcome)` 双参单点实现） |
| 中间态裁定（team-lead：Tab 直接隐藏，不做维护态页） | §3.5 末节「落地时序」 | 完成（减法：不产出维护态设计，并记录不做的理由） |
| 推理路径区块本期不做（team-lead 裁定，否决实装） | §3.5「推理路径区块：本期不做」/ §6.1 | 完成（整块不渲染、`DecisionTimeline` 不下沉、Tab 收敛只做内嵌台账表；不写"暂无"、不留占位） |
| 「无动作」= 空态而非第 5 档（team-lead 通过） | §4.6 / §11 第 20 条 | 完成（4 档 + 1 空态；PM 已据此改 PRD §4.1 并留痕记录原口径错在哪） |
| 历史数据排除（队列 / counts **两处**） | §5.1.5 / §11 第 32 条 | 完成（数据层排除，前端丢弃 + warn 仅作防御；导出随 P1 移除，恢复时补第三条） |
| 跨库残留期「状态同步中」**收窄到详情页** | §5.1.3 / §6.4.1 / §7.3 / §11 第 29 条 | 完成（PM 裁定；判据改为"两信号不一致"，**原 `sla_state` 判定是字段用错 + 信号偷换**，已作废） |
| 「状态同步中」**三级文案 + 恒定出口**（Spec AC-15 / AC-14） | §6.4.1 / §7.3 / §11 第 29 条 / §11.1 | 完成（**出口是恒定列：任何 executing 渲染含未超窗都必须有入口**；文案未超窗 ①同步中/②执行中/③执行中，超窗 ①③降级、②不变） |
| 「不可验收」须附**失败方向**分析 | §6.4.1 | 完成（字段缺失时 ① 渲染不出→承诺永不说出，**失败方向是"少承诺"不是"多承诺"**；这是"不可验收"能被接受的判据） |
| 跨文档引用核实（§0/§13 → prd.md） | 文末门禁 | 完成（真断链 **0**；§0、§13 均存在于 `prd.md`，**行号由门禁现读、不在此钉死**——协作期间 `## 13.` 已从 807 漂到 806，钉死就会立刻过期。原检查器只扫本文档标题，误报为 broken） |
| **门禁自身可信度：先自检、再他检** | `check_doc.py` `self_check()` / `check_doc_selftest.py` | 完成（**`main()` 第一件事跑自检，不通过就 EXIT=2 且拒绝出报告**——`--all` 同样被拦，一个能绕过的闸门等于没有闸门。用例 13 例：8 例已知缺陷必抓（含 PM 的"表头 3 列 / 7 行只有 2 格"）+ 5 例正常写法必不报（含 ASCII 流程图）；另 **2 例盲区断言"确实抓不到"**，抓到了反而报错并提示更新盲区清单。`--mutate` **11 个变异体全部被杀死**。**没有红样例的 0，等于没有 0**） |
| 门禁用例**单一来源** | `check_doc.py` `SELF_CHECK` / `BLIND_SPOTS` | 完成（`check_doc_selftest.py` **不另抄一份用例**，只做变异测试与转义保护。理由：同一份内容写两处，早晚改一处忘另一处——本项目已因此发生过两次。**砍用例砍过头的实测教训**：精简 `SELF_CHECK` 时漏掉 `glued` / `spilled_weak` 两条，变异测试立刻报 `SURVIVED`——没有用例的检测器就是没人看着的检测器，它报 0 只是因为它没在跑） |
| 表格判据的两条误报防线 | `check_doc.py` `fenced_mask()` / `odd_backtick_cell()` | 完成（① **跳过 fenced code block**：`prd.md` §3.1 的 ASCII 流程图有 7 行 `\|` 被旧判据报成"表格列数不一致"，照它改会把一张正确的图改坏；② **单元格内反引号奇数 = 行内代码被 `\|` 切断**：反引号不保护 `\|`，`decided\|failed` 会切两列、末列被静默丢弃。**为什么误报必须消灭而不是容忍**：一次误报让人改坏正确的东西；反复误报**训练人忽略整类告警**——那时它连"没有门禁"都不如，因为你还以为自己有） |
| 已知**不可判**类别 + 对应写作规范 | §12 本行 / `check_doc.py` `check_tables()` docstring | 完成（**反引号成对、裸管道在反引号外**（如 `状态: decided \| failed`）：裸管道与真分隔符在字节层等价，两处错误可互相抵消使 cells 数恰好正确 → **计数层面不可判，不是难判**。故不进门禁，改立写作规范：**单元格内需字面管道一律写 `\|`；表达"或"用 `/` 或顿号，不写 `A \| B`**。真要判只能渲染成 HTML 比对 DOM 单元格数——但它的失败模式**不是误报，是漂移**：判据的真相源变成一个会升级的第三方，"昨天 0、今天 3"可能只是渲染器换了行为、跟文档无关。**要么钉住版本，要么钉住规范（GFM 文本）；钉不住就别把它当门禁，只能当一次性审计。** 故记录不实现） |
| **孤立表格行**（`TABLE_ORPHAN_ROW`，PM 补的第 5 类） | `check_doc.py` `check_tables()` F 分支 | 完成（以 `\|` 开头但块内**没有分隔行** → 按 GFM 不成表，整块渲染成裸文本、`\|` 直接显示在页面上。**必须报，不能跳**：跳过等于把它从"被检查的集合"里剔除，而它几乎总是"想写表、漏了表头/分隔行"的手误——**跳过之后它永远不会被修掉，因为没有任何检查知道它存在**。实证两处：`uiux.md` 原 L1032（两行组件表裸奔，已补表头）、`spec.md` L163 起 8 条 AC 被一段引用块切断） |
| **集合与结论分开报** | `check_doc.py` `scan_all()` 输出 | 完成（输出改为「比对 N ｜ 跳过 K（无分隔行 / 代码块内）｜ 缺陷 M」。只报"比对 73 张 / 0 缺陷"，读者会以为压根没有第 74 个块——**而缺陷常常就在被跳过的那个里**。`spec.md` 那处就是这样活过三轮检查的：从未进入被检查集合，不是"通过了"） |
| 门禁**能力边界**（写下来防止高估） | `check_doc.py` `check_tables()` docstring | 写明**列数检查抓不到「内容错位」**：表头 4 列、某行也是 4 个单元格、内容整体左移一列时，列数完全正确、语义全错。`prd.md` §2.1 即此形态，本门禁报 0。**`TABLE_* 全绿` ≠ 表格内容全对**——脚本没有语义判断力，这部分只能靠表头与内容的人工核对 |
| `action_status` 契约缺口**已闭环，execute 路径确定为必做** | §6.4.1 / §10.2.3 | 完成（`pipeline` 本来就写；架构已定 `POST /{id}/execute` 的**同一次** `StatusOutcomePatch` 写 `outcome_details` 完整快照 `{action_record_id, action_status}`，零额外往返。**约束**：`outcome_details` 是整体 JSON 串、`SET` 是替换不是合并，每个写点必须写"当次完整快照"，禁止只写一个键——否则先写的键会被静默抹掉，Cypher 里看不出来） |
| 错误读取单点封装（契约 1.5.0 / **AC-17** / 按 `error.code` 分流） | **§10.6** / §5.3 并发冲突 / §5.4 权限只读 / §11 第 36-37 条 / §11.1 | 完成（**403 `FORBIDDEN` / 404 `NOT_FOUND` 本轮迁进信封**，401 未迁（共享依赖、无 `code`）→ `parseApiError` 必须**连 `status` 一起返回**，否则登录过期会被当"未知原因"且不跳登录页；文案表按 `ErrorCodeCatalog` **全 13 码**列全，`ErrorCode` 用其字面量做 TS union 让漏项编译期红；`details` **分两层读**（先 `?? {}` 再接 `field ?? null`）；`evidence_too_many` 指证据字段，`step_limit_reached` 挂整体；**13 码里 `NOT_FOUND`/`FORBIDDEN` 是大写，禁止大小写归一化**。**核对时发现转述与契约三处不一致，一律以契约为准**） |
| `entry_source` 单选理由修正 | §10.2.3 | 完成（从"本期不做"改为"语义上不存在多值"——写成本期不做会被当 TODO 捡起来） |
| 导出按钮本期不渲染（B5 降 P1） | §1 / §3.3 / §7.1 / §10.1 / §11 第 24 条 | 完成（6 处同步；台账强调色从 2 处降到 1 处，不再有主按钮） |
| 证据数排序整项不渲染（G/J 降 P1） | §4.2 / §5.2 / §10.2.1 / §11 第 24 条 | 完成（列仍显示、表头不可点；队列切换器只剩置信度；DTO 已无 `evidence_count`） |
| 证据数"未知"不渲染成"零" | §5.2 证据行 | 完成（派生不出即显示"证据数未知"） |
| `idempotent_replay` 文案区分 | §5.3 | 完成（"已按当前执行状态同步" ≠ "已发起执行"） |
| 矩阵收窄 7/23 后的映射简化 | §5.1.1 / §11 第 31 条 | 完成（7 行纯查表、无默认分支、无异常标记） |
| 编号纪律「编号作辅助、名称作主键」 | 文首编号口径 / §11 第 33 条 | 完成（六条保留编号项每处均带名称，已全量核对零裸引用） |
| 沉淀两条团队规则 R1/R2 | §10.5 / §11 第 34–35 条 | 完成（R1 缺值服务端回落；R2 前端只对能证实的事负责，含四处实例对照） |
| 筛选翻译强依赖矩阵 + 可测断言 | §4.3 必读前提 / §11 第 34–35 条 | 完成（QA 按第 34 条测"筛选结果与标签双向一致"） |
| 状态矩阵（5 页 × 5 态） | §7 | 完成（无"待补充"；404/403 已按不泄露存在性拆分） |
| 响应式三档 | §8 | 完成（含外壳 `minWidth: 1200` 约束声明） |
| 反模式自查 | §9.1（16 条） | 完成 |
| 存量违规上报 | §9.2（10 条） | 完成 |
| 口径差异上报 | §9.3（10 条） | 完成 |
| 后端阻塞项 | §10 | 完成（**已按 api-spec.yaml v1.1.0 重写**：10.1 已对齐 13 项 / 10.2.1 已关闭 18 条 / 10.2.2 仍开 1 条（E，P1）/ 10.2.3 新发现契约限制 1 条 / 10.3 语义冲突全部裁决 / 10.4 做对的 5 处） |
| 与 api-spec.yaml v1.1.0 对齐 | §4.3 / §4.4 / §5.1 / §5.2 / §5.5 / §10 | 完成（字段名全部 grep 核实：`available_operations` / `sla_state` / `status_assumed` / `actor_type` / `decided_waited_minutes` / `counts.*` / `min_confidence` / `max_confidence` / `reasoning-steps`；`selected_option` 与 `expected_outcome` 已确认删除、无残留） |
| 契约字段重命名同步 | §5.1.3 / §5.1.4 / §10.3 O / §11 | 完成（`available_actions` → `available_operations`，全文 17 处） |
| 筛选翻译规则（6 人话选项 → `status[]`+`outcome[]`） | §4.3 | 完成（含"依赖合法性矩阵才正确"的隐藏前提说明） |
| 队列四计数 | §5.5 | 完成（全库口径 + "`counts.to_execute>0` 时分组不得为空"写成验收） |
| 与 PRD §4.1.1 对齐 | §2.2 / §2.6 / §4.2 / §5.1 | 已核对一致（5 类标签 / 4 色系 / 6 派生筛选项 / 映射单点） |
| 图标库与 G6 配色 | §1 / §6.2 | 已按架构锁定（`@ant-design/icons@6.1.1`；G6 用 `useToken()` 由父级传值，只给 token 名不给色值） |
| 契约缺口「不造假功能」通用规则 | §11 第 24 条 | 完成（team-lead 要求写进交接，作为今后统一处理方式） |
