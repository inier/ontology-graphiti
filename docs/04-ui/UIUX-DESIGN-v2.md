---
id: odap.l4.uiux-design-v2
status: authoritative
owner: designer
version: 2.0.0
layer: L4
concern: ui-design
lifecycle: living
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
governance_reason: 前端设计单一真源
governance_evidence: UIUX-DESIGN-v2.md:14 自述「本文档是 ODAP 前端设计的单一真源」
---

# ODAP UI/UX 设计方案 v2

> 设计版本：v2.0.0 ｜ 设计师：颜好看 ｜ 日期：2026-10-16
> 状态：Phase 1 设计契约（供架构师 Spec 引用 / 前端 Phase 3 实现）
> 关联产物：`docs/04-ui/design-tokens.json`、`docs/04-ui/design-tokens.css`
> 三轴刻度：**DESIGN_VARIANCE = 4 / MOTION_INTENSITY = 4 / VISUAL_DENSITY = 7**
> 设计寄存器：**Product Register（产品型）** — 设计服务产品，目标是"赢得熟悉感"，不是炫技
> 平台轴：**web（桌面优先）**，平板完整适配，手机单列兜底

---

## 0. 阅读指引

本文档是 ODAP 前端设计的**单一真源（single source of truth）**。`docs/04-ui/` 下 v1 的 7 篇文档（`UI_DESIGN.md`、`05-ODAP-V2-DESIGN-SYSTEM.md`、`COMPONENT_SPEC.md`、`COMPONENT_HIERARCHY.md`、`FRONTEND_COMPONENT_DESIGN.md`、`MOBILE_FIRST_DESIGN.md`、`ONTOLOGY_BUILD_UI.md`）在 Phase 3 前应被标注为"历史文档"，凡与本文冲突处以本文为准（差异清单见第 1 章）。

Token 的机器可读真源是 `design-tokens.json`（前端 `import` 使用），CSS 真源是 `design-tokens.css`（`data-appearance` / `data-accent` 驱动）。本文只描述**规则与映射**，不重复罗列数值。

---

## 1. 现状设计系统审计

### 1.1 结论摘要

现状不是"一套设计系统"，而是**四套互相冲突的规范 + 一套与文档脱节的代码实现**。核心问题是缺少单一真源、缺少三层 Token、以及命中团队 P0 红线。

| 严重度 | 问题 | 结论 |
|---|---|---|
| P0 红线 | 现有主题系统生成"紫→品红"跨色相渐变 | 命中 P0-2，必须移除 |
| P0 红线 | 多篇文档用 emoji 充当功能图标 | 命中 P0-1，必须重写 |
| P0 红线 | 全站玻璃态 + 发光边框 + 跨色相渐变三位一体 | 命中 P0-2 套路 + 绝对禁令 #3 |
| 结构性 | 无 primitive / semantic / component 三层 Token | 必须新建 |
| 结构性 | 4 套互相冲突的响应式断点 | 必须统一为 1 套 |
| 结构性 | 文档描述与实际代码/目录严重不符 | 文档失真 |
| 规范 | 使用过冲弹性缓动（overshoot easing） | 命中"禁止弹跳" |
| 规范 | 大量硬编码色值与侧条纹边框 | 命中硬编码/绝对禁令 #1 |

### 1.2 冲突与违规逐条（含文件证据）

**（1）主色与品牌语言互相冲突 —— 三份文档三个答案**

- `docs/04-ui/UI_DESIGN.md` L35-43：主色调 `#1890ff`（Ant Design 蓝）、文字主色 `#262626`、边框 `#d9d9d9`。
- `docs/04-ui/05-ODAP-V2-DESIGN-SYSTEM.md` L3-5、L49：方向为"蓝紫渐变 · 玻璃态"，主色 `Indigo #4F46E5 → Violet 渐变`。
- `apps/web/src/modules/shared/styles/global.css` L3、L14-23：实际实现是 `Indigo #6366F1 / #4F46E5` + `DM Sans`。
- 三处主色/字体/语言均不一致，无单一真源。

**（2）P0-2 红线：紫→品红跨色相渐变（现网可复现）**

- `apps/web/src/modules/shared/styles/colorThemeUtils.ts` L69-84：`violet` 调色板 accent 为 `#D946EF`。
- 同文件 L142-147：`--odap-gradient-brand = linear-gradient(135deg, ${p('600')} 0%, ${accent['500']} 100%)`。对 `indigo` 调色板即 `#4F46E5 → #8B5CF6`；对 `violet` 调色板即 `#7C3AED → #D946EF`（**紫→品红**，正面命中 P0-2）。
- `global.css` L79-80：`--odap-gradient-brand: linear-gradient(135deg, #4F46E5 0%, #8B5CF6 100%)`（跨色相）。
- `global.css` L441-447：`.ant-btn-primary` 主按钮背景使用上述跨色相渐变，且 hover 叠加 `--odap-shadow-glow`（发光）→ 构成"渐变 + 发光"AI 模板套路。

**（3）P0-2 套路：玻璃态被当作默认表面**

- `05-ODAP-V2-DESIGN-SYSTEM.md` L342-371、L520-539：`Glass Card` 被标为"推荐默认"，`.glass-panel` 使用 `backdrop-filter: blur(20px)`。
- `global.css` L217-226：`.glass-surface` 全局工具类。
- 判定：装饰性毛玻璃 = 绝对禁令 #3，且与"深色面 + 发光边框 + 跨色相渐变"组成三位一体。

**（4）P0-1 红线：emoji 作为功能图标**

- `docs/04-ui/UI_DESIGN.md` L86-99：导航菜单"图标"列由 12 个 emoji 字符充当（U+1F3E0 房子、U+1F517 链接、U+23F1 秒表、U+1F5FA 地图、U+26A1 闪电、U+1F4E5 收件、U+1F4CA 图表、U+2699 齿轮、U+1F465 人群、U+1F4DD 便签、U+1F4CB 剪贴板、U+1F50C 插头）。
- 同文件 L157 工具栏、L219-221 时间线控件、L275-279 地图图例、L310-311 推演状态、L378 数据摄入标签页大量以 emoji 充当功能图标（播放/暂停/定位/导出/图层等语义位）。
- `docs/04-ui/COMPONENT_SPEC.md` L154：日志级别图标以 emoji 表示（info U+2139、success U+2705、warning U+26A0、error U+274C）；L531：`icon:` 字段直接写 emoji 字符。
- `docs/04-ui/MOBILE_FIRST_DESIGN.md` L47-48：底部 TabBar 的 5 个标签同样以 emoji 充当图标。
- 判定：全部必须替换为 Spec 锁定的统一描边 SVG 图标（本文 §5），并保证最终产出零 emoji 字符。

**（5）禁止弹跳/过冲缓动**

- `05-ODAP-V2-DESIGN-SYSTEM.md` L236：`--ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1)`（过冲，控制点 > 1）。
- `global.css` L125：同一过冲缓动；L236-243 Modal/Toast 使用该 spring。
- `apps/web/src/modules/shared/components/ThemeColorPicker.tsx` L68：内联 `transition: ... 200ms cubic-bezier(0.34, 1.56, 0.64, 1)`。
- 判定：v2 全部改用 `--odap-ease-standard/decelerate/accelerate`，无任何过冲。

**（6）四套互相冲突的响应式断点（无法协商的系统性缺陷）**

| 来源 | 断点定义 |
|---|---|
| `05-ODAP-V2-DESIGN-SYSTEM.md` L478-485 | 0 / 640 / 768 / 1024 / 1280 / 1536 |
| `COMPONENT_SPEC.md` L544-570 | 1440 / 1199 / 991 / 767 |
| `MOBILE_FIRST_DESIGN.md` L20-27 | 576 / 768 / 1024 / 1440 / 1920 |
| `global.css` L137-142 | 480 / 576 / 768 / 992 / 1200 / 1600 |

判定：v2 统一为 **480 / 640 / 768 / 1024 / 1280 / 1536 / 1920**，且与栅格 4/8/12 列绑定（见 §3.5）。

**（7）文档描述与实际代码/目录不符**

- `COMPONENT_HIERARCHY.md` L23-88 描述目录为 `apps/web/src/components/{atoms,molecules,organisms,templates}` + `pages/`；实际代码为 `apps/web/src/modules/<domain>/{components,pages,stores,services}`（28 个业务模块）。
- `UI_DESIGN.md` L504 首页仪表盘标"未实现"，L511-518 自述"响应式未实现 / 国际化未实现 / WebSocket 未实现"——即文档承认自身已与实现脱节。
- `README.md` L24 技术栈写 "AntV G6 v5"，`UI_DESIGN.md` L27 写 "AntV G6 latest"；而实际图谱渲染栈有 7 套并存（cytoscape / @antv/g6 / sigma / @xyflow/react / @ant-design/graphs / graphology / echarts）。文档未反映此碎片化。

**（8）硬编码色值散落（禁用项）**

- `global.css` L113 `rgba(99,102,241,0.12)`、L608 `#FEF2F2`、L526 `#fff`（允许）之外存在多处裸值。
- `COMPONENT_SPEC.md` L47-53 `STAGE_COLORS` 直接写 `#1890ff/#52c41a/#ff4d4f/#faad14/#d9d9d9`；L394 `background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.08)`。
- `UI_DESIGN.md` L136 统计卡片硬编码 `0 2px 8px rgba(0,0,0,0.08)`。

**（9）绝对禁令 #1：侧条纹彩色边框**

- `global.css` L375：`.event-card { border-left: 4px solid var(--odap-color-error); }`。
- `global.css` L649：`.ant-menu-dark .ant-menu-item-selected { border-left: 3px solid ...; }`。
- `COMPONENT_SPEC.md` L236-238：新增/删除/修改用 `左边框 3px`。
- 判定：v2 改用"整块底色 + 圆角 + 图标"表达状态，禁止 ≥2px 的彩色侧条纹。

**（10）字体被反射拒绝清单命中**

- `global.css` L7：`@import ... family=DM+Sans`；`global.css` L84 与 `05-ODAP-V2-DESIGN-SYSTEM.md` L154 不同（前者 DM Sans，后者 Inter）。
- `DM Sans` 在字体反射拒绝清单内（训练数据默认值，制造 monoculture）。v2 更换为 Manrope（展示）+ Inter（正文）+ JetBrains Mono（数据）。

**（11）深色侧栏在浅色主题下不协调**

- `05-ODAP-V2-DESIGN-SYSTEM.md` L405：「背景 `linear-gradient(180deg, #1E1B4B, #0F0F1A)` / 深色始终不变」。
- `colorThemeUtils.ts` L150-152：侧栏恒为深色渐变。
- 判定：v2 侧栏跟随 `appearance`（亮色面浅底、暗色面 ink 底），层级由亮度/描边递进表达，不再恒为深色。

### 1.3 现状可复用的资产（保留）

- `layoutStore.ts` 的四栏布局状态机（菜单/功能/工作/扩展 + Tab 保持 + 快捷操作）是**优秀的产品化基础**，v2 保留其信息架构，仅重绘视觉与 Token。
- `AdminLayout.tsx` L655-691 已用 AntD 6 `ConfigProvider` + `theme.darkAlgorithm` + `token.colorPrimary`，**对接路径正确**，v2 在其上扩展（见 §3.6）。
- `KeepAliveOutlet.tsx` + Tab `refreshToken` 机制保留。

---

## 2. 设计方向

### 2.1 竞品与行业研究（联网检索，2026-10）

| 对标对象 | 关键做法（对本项目的可迁移结论） |
|---|---|
| **Linear** | 暗色原生：`#08090a` 画布 / `#0f1011` 面板 / `#191a1b` 抬升面，**用亮度递进而非阴影表达层级**；几乎全无彩，仅一个品牌强调色用于 CTA/选中态；发丝级半透明描边 `rgba(255,255,255,0.05~0.08)`；展示字用激进负字距，UI 正文用"签名中间字重"（510）。→ 直接采纳为本项目 `nebula` 外观与"三级字重（400/500/590）"。 |
| **Palantir Foundry（Vertex）** | 本体图谱就是产品核心：对象选择面板随点击自动展开、显示属性与派生属性；Search Around 多步筛选；Layers 面板做**数据驱动的节点/边样式**；右侧 Tab 承载探索逻辑；Ontology Tab 有 entity 状态图例（Existing / Proposed）与校验错误定位。→ 采纳为本项目"图谱探查"与"本体建模"的交互骨架。 |
| **Neo4j Bloom** | 图例面板（Legend）按 category / relationship type 列出并可改样式；**规则驱动样式**（single / range / unique values，数值属性带直方图）；"Reveal Relationships"避免画布噪声；悬停 tooltip 显示 caption；Perspective 作为可保存视图。→ 采纳为图例 + 样式规则 + 悬停提示规格。 |
| **Databricks** | 数据密集控制台：结果表高数据密度、无限滚动、数据类型图标、多列排序、集成搜索过滤；长任务用"近似结果先出"缓解等待焦虑；统一顶栏导航 + 可折叠产品区；资产成熟度（draft/validated/production/deprecated）需要可见状态。→ 采纳为表格密度档位、长任务进度规格、资产状态徽标。 |
| **行业知识库** `industries/enterprise.md`、`industries/ai-native.md` | 明确反模式：不要用紫/粉渐变做企业产品、不要 emoji 作功能图标（推荐 Lucide）、不要硬编码色、不要弹跳缓动、不要空洞占位；AI 产品必须覆盖 5 态（Loading/Empty/Error/Populated/Edge）。→ 与团队 P0 完全一致，作为硬约束。 |

**结论**：定位为「**精密仪器（Precision Instrument）**」型专业工具——数据优先、克制用色、发丝描边、亮度分层、可信赖。

### 2.2 设计语言

**关键词**：克制、精密、可信、可追溯、数据优先。

**五条设计原则**：

1. **内容优先于装饰**：中性色占 70-90% 表面积；每屏可见的强调色使用 **≤ 2 处**；装饰性毛玻璃、发光边框、跨色相渐变一律不做。
2. **层级靠亮度与描边，不靠阴影**：亮色面用 1px 描边 + 极浅阴影；暗色面用 ink 表面的 5 级亮度递进（L1→L5）。
3. **信息密度可调但默认紧凑**：专业用户长时间操作，默认 `compact`（表格行高 36px），提供 `comfortable(44) / dense(28)` 三档。
4. **状态可解释**：AI/推理类界面必须显式表达"意图 → 本体约束命中 → 证据溯源 → 后续建议"，绝不做黑盒。
5. **动效只传达含义**：仅用于状态确认、层级进入、跨屏过渡；150ms 为收敛基准；无弹跳、无装饰性动画。

### 2.3 配色基调

- 中性色：冷调 slate（亮色面）+ ink（暗色面），见 `design-tokens.css` primitive 层。
- 品牌强调色：**cobalt（品牌默认）**，另提供 teal / indigo / graphite 三个可切换色相；**全部以纯色使用**，渐变仅允许同色相深浅。
- 语义色：success / warn / danger / info，仅用于状态，不参与品牌表达。
- 强调色对比度已验证：solid 底 + on 前景 ≥ 6:1（见 `design-tokens.json` 各 accent 的 `contrastWithOn`）。
- **amber 退役为主强调色**，仅保留为 `warn` 语义色（避免白字对比度不足与"警告色当品牌"的语义污染）。
- 明令禁止：`linear-gradient` 跨越 `#7C3AED / #A855F7 / #9333EA / #EC4899` 任一组合；Indigo→Pink 任意组合。

### 2.4 字体方案

| 层 | 字体栈 | 依据 |
|---|---|---|
| 展示（标题/Wordmark） | `Manrope` + `Noto Sans SC` | 几何、精密、非训练默认值；避开反射拒绝清单 |
| 正文（UI 文本） | `Inter` + `Noto Sans SC` | 作为正文/UI 字使用（不作"展示字体"），小字号可读性最佳 |
| 数据（代码/ID/Cypher/指标数字） | `JetBrains Mono` | 等宽、tabular-nums，用于溯源与图谱属性 |

- 字号阶梯 11/12/13/14/16/18/20/24/32/40（`--odap-font-size-*`）。
- 三级字重：`read=400` / `medium=500` / `emphasize=590` / `announce=700`。
- 行高：正文 1.5、标题 1.2-1.35。
- 字距：全大写/标签 **≥ 0.06em**；标题 -0.02em ~ -0.03em；正文 0。
- Google Fonts `@import` 语句见 `design-tokens.css` 顶部。

### 2.5 栅格、密度与节奏

- 栅格：桌面 12 列 / 平板 8 列 / 手机 4 列；沟槽 24 / 16 / 12px。
- 容器：应用壳 `--odap-container-max: 1440px`；文档/表单阅读宽 `--odap-content-max: 1200px`、窄栏 720px。
- 节区纵向节奏：桌面 48 / 平板 32 / 手机 24px。
- 密度档位：`comfortable / compact / dense`，对应表格行高 44 / 36 / 28px。默认仍以"专业默认 = compact"。
- 栅格容器采用 CSS Grid 分数单位（如 `minmax(0,1fr) 320px`），检查器面板固定 320px，主区自适应。

### 2.6 动效原则

- 时长：instant 80 / fast 150 / base 200 / slow 300 / page 240ms（全部 ≤ 400ms）。
- 缓动：`standard cubic-bezier(0.2,0,0,1)`、`decelerate`、`accelerate`、`linear`；**无 spring / 无过冲**。
- 允许的动效清单：hover/focus/active 状态确认（150ms）、面板展开收起（200ms）、路由转场（240ms，仅 opacity + 4px 位移）、骨架屏微光（1400ms loop）、长任务进度（线性）。
- 禁止：弹跳、缩放回弹、装饰性循环动画、同时动画超过 3 个元素、超过 500ms 的动画。
- 必须支持 `prefers-reduced-motion: reduce`（见 `design-tokens.css` §4）。

---

## 3. 风格切换方案（重点）

### 3.1 切换模型

两个**正交轴**，运行期通过 `<html>` 属性切换，互不耦合：

| 轴 | 属性 | 取值 | 决定 |
|---|---|---|---|
| 外观 Appearance | `data-appearance` | `luminous` \| `nebula` | 亮/暗面、表面层级手法、焦点光环强度、阴影策略 |
| 强调色 Accent | `data-accent` | `cobalt` \| `teal` \| `indigo` \| `graphite` | 品牌强调色相（纯色，10 级色阶插槽） |

另提供一个产品级开关 `data-density` ∈ `comfortable | compact | dense`（默认 compact），只影响表格/列表/表单行高与内边距，不影响配色。

> 设计取舍说明：v1 把"配色（indigo/blue/green/violet/amber）"与"亮暗"做成两个独立开关，导致 10 种组合各自跑偏、且 `violet` 直接产出紫→品红渐变。v2 将其收敛为"2 外观 × 4 色相 = 8 种稳定组合"，每一组合的对比度都已逐项验证。

### 3.2 风格一：`luminous`（清爽专业）

- 定位：日间办公 / 数据分析 / 长文与表单录入。
- 表面：`bg #F7F9FB`、`surface #FFFFFF`、`sunken #EFF3F7`；层级靠 1px 描边 + 极浅阴影（`elevation.sm`）。
- 文本：`fg #0F172A`（对白底 ≈ 17:1）、`fgSecondary #475569`（≈ 8.5:1）、`fgMuted #64748B`（≈ 5.9:1）。
- 描边：`border #E2E8F0` / `borderStrong #CBD5E1`。
- 强调色：取 accent-600（cobalt `#1E45DB`，白字 7.0:1）。
- 焦点：`0 0 0 3px` 半透明强调环。
- 密度：comfortable 偏默认（表格 36，可切 44）。
- 禁止项：不使用玻璃态、不使用发光边框、不使用跨色相渐变。

### 3.3 风格二：`nebula`（深邃科技）

- 定位：图谱探查 / 决策推演 / 大规模监控，长时间暗环境操作。
- 表面（亮度递进）：L1 `#0B0E14` → L2 `#12161F` → L3 `#1A1F2B` → L4 `#222836` → L5 `#2B3242`。
- 文本：`fg #F2F5FA`（对 L1 ≈ 15:1）、`fgSecondary #D3DAE6`、`fgMuted #9AA4B2`（≈ 7.7:1）。
- 描边：`rgba(255,255,255,0.08)` / strong `0.14` / subtle `0.05`（发丝级）。
- 强调色：取 accent-400（cobalt `#6285FF`，对 L1 ≈ 5.8:1）。
- 焦点：`0 0 0 3px` accent-400 40% 光环（暗面上更清晰）。
- 密度：compact 默认（图谱与表格并置）。
- 允许项：**同色相**强调色低透明光晕（仅用于 focus/active，alpha ≤ 0.40）；禁止装饰性发光边框。

### 3.4 强调色相四选

| 色相 | solid（按钮底） | on（按钮字） | 对比度 | 适用 |
|---|---|---|---|---|
| cobalt（默认） | `#1E45DB` | `#FFFFFF` | 7.0:1 | 品牌默认，中性专业 |
| teal | `#0A6E5D` | `#FFFFFF` | 6.3:1 | 知识/数据治理语义倾向 |
| indigo | `#4F46E5` | `#FFFFFF` | 6.3:1 | 与既有用户习惯衔接（纯色，无渐变） |
| graphite | `#334155` | `#FFFFFF` | 10.3:1 | 单色克制模式（打印/投影/审阅） |

### 3.5 断点（唯一一套）

| 断点 | 宽度 | 栅格 | 导航 | 布局 |
|---|---|---|---|---|
| xs | < 480 | 4 列 | 底部 TabBar（≤5） | 单列 |
| sm | ≥ 640 | 4 列 | 抽屉式导航 | 单列 |
| md | ≥ 768 | 8 列 | 可收起侧栏 | 双列 |
| lg | ≥ 1024 | 12 列 | 固定二级导航 | 主区 + 检查器 |
| xl | ≥ 1280 | 12 列 | 固定二级导航 | 主区 + 检查器 + 扩展面板 |
| 2xl | ≥ 1536 | 12 列 | 同上 | 内容最大宽 1440 |
| 3xl | ≥ 1920 | 12 列 | 同上 | 内容最大宽 1600 |

### 3.6 与 Ant Design 6 ConfigProvider 的对接

对接路径唯一且确定：**CSS 变量（本文 Token）→ `html[data-*]` → `ConfigProvider.token` + `ConfigProvider.components`**。

```tsx
// 伪代码：由 useThemeRuntime() 驱动，页面/组件一律不写死色值
import { token as odapTokens, semantic as odapSemantic } from '@/design/design-tokens.json';

const appearance = useLayoutStore((s) => s.appearance); // 'luminous' | 'nebula'
const accent = useLayoutStore((s) => s.accent);         // 'cobalt' | 'teal' | 'indigo' | 'graphite'

useLayoutEffect(() => {
  const root = document.documentElement;
  root.setAttribute('data-appearance', appearance);
  root.setAttribute('data-accent', accent);
}, [appearance, accent]);

// 读取当前生效的语义色（从 CSS 变量实时取，保证与 CSS 真源一致）
const cssVar = (name: string) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim();

const antdTheme = useMemo(() => ({
  algorithm: appearance === 'nebula' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
  cssVar: true,
  token: {
    colorPrimary: cssVar('--odap-color-accent-solid'),
    colorSuccess: cssVar('--odap-color-success'),
    colorWarning: cssVar('--odap-color-warn'),
    colorError: cssVar('--odap-color-danger'),
    colorInfo: cssVar('--odap-color-info'),
    colorBgBase: cssVar('--odap-color-bg'),
    colorBgContainer: cssVar('--odap-color-surface'),
    colorBgElevated: cssVar('--odap-color-surface-raised'),
    colorText: cssVar('--odap-color-fg'),
    colorTextSecondary: cssVar('--odap-color-fg-secondary'),
    colorBorder: cssVar('--odap-color-border'),
    borderRadius: parseInt(odapTokens.radius.md.value),
    fontSize: parseInt(odapTokens.font.size.base.value),
    fontFamily: odapTokens.font.family.body.value,
    fontFamilyCode: odapTokens.font.family.mono.value,
    controlHeight: parseInt(odapTokens.size.controlMd.value),
    motionDurationMid: odapTokens.motion.duration.base.value,
    motionEaseOut: odapTokens.motion.ease.standard.value,
    boxShadow: cssVar('--odap-shadow-token'),
  },
  components: {
    Table: { headerBg: cssVar('--odap-table-header-bg'), rowHoverBg: cssVar('--odap-table-row-hover-bg') },
    Menu: { itemSelectedBg: cssVar('--odap-nav-item-bg-active'), itemSelectedColor: cssVar('--odap-nav-item-fg-active') },
    Layout: { bodyBg: cssVar('--odap-color-bg'), siderBg: cssVar('--odap-nav-bg') },
    Graph: { /* 图谱组件内部消费 --odap-graph-* */ },
  },
}), [appearance, accent]);
```

**硬约束**：

1. 组件层**禁止**出现 hex/rgb 字面量（唯一例外 `#fff` / `#000`），一律 `var(--odap-*)`。
2. 现有 `colorThemeUtils.ts` 的跨色相渐变逻辑**整段删除**；`--odap-gradient-brand` 不再存在；如需渐变只允许 `var(--odap-color-accent)<->var(--odap-color-accent-hover)` 同色相。
3. `ThemeColorPicker` 改为"外观 + 色相"双选择器，选项色块直接读 Token 变量，交互过渡改用 `--odap-transition`。
4. 图谱/图表库（由架构师锁定）必须消费 `--odap-graph-*` 与 `--odap-chart-*`，不得自带主题色。

### 3.7 主题切换入口（规格）

- 位置：全局顶栏右侧，图标按钮（Spec 锁定图标库的"外观"语义图标），点击弹出面板。
- 面板内容（≤4 个可见选项，符合工作记忆上限）：
  1. 外观：清爽专业 / 深邃科技（分段控件，2 段）。
  2. 强调色：cobalt / teal / indigo / graphite（4 个色块，纯色圆点，选中态为描边环 + 对勾图标）。
  3. 密度：舒适 / 紧凑 / 密集（分段控件，3 段）。
  4. 跟随系统（开关，仅控制 `luminous/nebula` 自动切换）。
- 状态：切换即时生效（150ms 过渡），持久化到 `localStorage`（`odap-appearance` / `odap-accent` / `odap-density`），首屏前由内联脚本写入 `html` 属性以避免闪白（FOUC）。
- 无障碍：面板为 `role="radiogroup"`，键盘方向键切换，选中项 `aria-checked`，焦点可见环。

---

## 4. Design Token 规范

### 4.1 三层结构

```
primitive（原始值）        ← A1-identity + A1-structure
  ├─ color: neutral / ink / cobalt / teal / indigo / graphite / green / amber / red / sky / categorical
  ├─ space / radius / elevation
  ├─ font: family / size / weight / leading / tracking
  ├─ motion: duration / ease
  └─ zIndex / breakpoint / size / layout
        ↓ alias
semantic（语义别名）       ← A2
  ├─ accent.<hue>（10 级 + solid + on）
  ├─ appearance.luminous / appearance.nebula（bg/surface/fg/border/accent/semantic/focus）
  └─ typography（heading1-4 / body / bodySm / label / caption / code / numeric）
        ↓ alias
component（组件专用）      ← B-slot + C-extension
  └─ button / input / card / table / navigation / badge / overlay / feedback / code / graph / chart
```

**规则**：primitive 层持有所有字面值；semantic 与 component 层一律用 alias 引用（JSON 中 `{...}` 语法，CSS 中用 `var()`）。任何组件不得直接使用 primitive 色值。

### 4.2 完整 Token 清单

数值不在此重复，唯一真源为 `docs/04-ui/design-tokens.json`。清单覆盖范围：

| 分组 | Token 数量级 | 要点 |
|---|---|---|
| primitive.color | 96 | 8 个中性/品牌色阶 + 语义色阶 + 5 个图表分类色 |
| primitive.space | 12 | 0/4/8/12/16/20/24/32/40/48/64/80 |
| primitive.radius | 7 | none/xs/sm/md/lg/xl/pill（卡片上限 16） |
| primitive.elevation | 13 | 亮色 6 + 暗色 6 + none |
| primitive.font | 3 族 + 10 号 + 4 重 + 4 行高 + 5 字距 | — |
| primitive.motion | 6 时长 + 4 缓动 | 无 spring |
| primitive.zIndex / breakpoint / size / layout | 9 / 7 / 9 / 15 | — |
| semantic.accent | 4 色相 × 12 | 含 solid / on |
| semantic.appearance | 2 × 22 | 含 focusRing / shadow |
| semantic.typography | 10 组 | 含 usage 说明 |
| component.* | 11 组 | button/input/card/table/navigation/badge/overlay/feedback/code/graph/chart |

### 4.3 图表配色（`--odap-chart-*`）

- 8 个分类系列：cobalt / teal / amber / violet / vermilion / skyBlue / lime / slate。
- 轴/网格/标签：`axisLine` / `gridLine` / `axisLabel` 均取语义边框与 muted 文本。
- 阈值线使用 `warn`；正负值分别用 `success` / `danger`。
- **无障碍要求**：不得仅靠颜色传达含义——趋势用箭头 + 数值，正负用符号 + 图标，系列在 legend 与 tooltip 中同时给出文字名。

### 4.4 图谱配色（`--odap-graph-*`）

节点按本体语义分类，颜色 + **形状 + 图标**三重编码：

| 节点类别 | 颜色 Token | 形状 | 图标语义 |
|---|---|---|---|
| 对象类型 Object Type | `graph.nodeKinds.objectType` | 圆角矩形 | box |
| 链接类型 Link Type | `graph.nodeKinds.linkType` | 菱形 | link |
| 动作类型 Action Type | `graph.nodeKinds.actionType` | 六边形 | bolt |
| 实例 Instance | `graph.nodeKinds.instance` | 圆形 | dot |
| 事件 Event | `graph.nodeKinds.event` | 三角形 | clock |
| 指标 Metric | `graph.nodeKinds.metric` | 方形 | gauge |
| 规则 Rule | `graph.nodeKinds.rule` | 胶囊 | shield |
| 智能体 Agent | `graph.nodeKinds.agent` | 五边形 | bot |

边：默认 `edgeDefault`（1.25px），强调 `edgeEmphasis`（2px），选中 `edgeSelected`（强调色 2px + 箭头），label 用 `edgeLabel`。
其他：`marquee`（框选）、`cluster`（聚类外框）、`minimap`（缩略图）、`gridLine`（画布网格）。
**无障碍要求**：节点形状与图标必须冗余编码；选中态除颜色外叠加 2px 环；提供键盘可遍历（Tab 逐节点）+ `aria-label` 含节点名与类型。

---

## 5. 图标系统

- **选型归属**：图标库由**架构师在 Spec 中锁定一套**（全项目唯一）；本方案只约束规格，不自行选定实现。
- **统一描边风格**：线性描边（outline），`stroke-width = 1.5`（24px 网格），`stroke-linecap: round`、`stroke-linejoin: round`，`fill: none`（填充仅用于状态点等极小元素）。
- **尺寸三档**：`16px`（行内/表格内）、`20px`（按钮/导航内）、`24px`（独立图标/空状态）。三档全项目一致，不得出现 14/18/22 等中间值。
- **颜色**：`currentColor`，由父级文本色 Token 决定；禁止在图标内写死色值。
- **禁止 emoji**：任何位置不得使用 emoji 作为功能图标（含文档、测试快照、Placeholder）。emoji 仅允许出现在用户生成内容（UGC）中。
- **禁止混用**：不得同时引入两套图标库（例如既用 AntD Icons 又用另一套）；迁移期允许在同一 PR 内替换，但**不得长期并存**。
- **无障碍**：纯装饰图标 `aria-hidden="true"`；作为唯一可点击内容时必须提供 `aria-label`；图标按钮的命中区域 ≥ 44×44px（用 padding 补足）。
- **与现状关系**：`05-ODAP-V2-DESIGN-SYSTEM.md` L659 推荐 `@ant-design/icons`，而行业知识库（enterprise / ai-native）推荐 Lucide 风格描边图标；两者冲突，已由 Spec 锁定的结论见下。

### 5.1 锁定结论（架构侧回执，2026-10-16）

- **唯一图标库：`lucide-react`**。理由（架构师复核）：`@ant-design/icons` 为 1024 viewBox 的填充式 path（`fill="currentColor"`），不暴露 `stroke-width` / `linecap` / `linejoin` 控制，锁定它必然违反本文 §5 的描边规格，予以排除。
- `strokeWidth` 统一设 `1.5`，对齐 `--odap-size-icon-stroke`；尺寸仅 16/20/24，对齐 `--odap-size-icon-inline/button/standalone`；颜色 `currentColor` 继承 `--odap-color-*`。
- 语义映射（工作区 6 + 图谱节点 8 + 工具栏 12）已落入 ADR-092 §Decision 第 5 条；图谱节点图标与本文 §4.4 的 shape 冗余编码一一对应（Box/Link/Zap/Circle/Clock/Gauge/Shield/Bot）。
- 迁移策略：映射表 + codemod `scripts/migrate_icons.mjs` + 按模块分批（导航 → 图谱页 → 业务页）+ Feature Flag 灰度；`@ant-design/icons` 仅作为 AntD 组件内部传递依赖保留，不属"项目图标系统"范围；涉 emoji 的 55 个文件同批替换。
- 落点：`docs/07-adr/ADR-092_icon-library-lock.md`、架构 v2 §6.3。

### 5.2 灰名单终审规则（设计师职责）

**终审人：UI/UX 设计师（本文作者）**。理由：灰名单条目本质是**视觉语义归一**问题（"这个图标在用户心智里代表什么"），不是技术可行性问题；架构师负责提供候选与技术约束，设计师负责裁决语义唯一性并回签。流程：架构产出映射表草案 → 标注灰名单 → 提交设计师 review → 设计师按下列三准则裁决并回签 → 冻结映射表。

**判定为灰名单（须终审）的三条准则**：

1. **语义不等价**：AntD 图标表达的概念在 Lucide 无单一对应，需换用近似语义或新造组合（不得"名字像就选"，须以"用户第一眼含义"为准）。
2. **全局语义冲突**：候选图标与本文其他地方已占用的语义撞车（同一图标在不同位置表示不同概念 = 禁止）。
3. **ODAP 专有概念**：本体、语义缺口、语义资产、路由工单等平台专有概念无现成图标，需要建立"语义约定"（一次约定，全局复用）。

**版本锚定前提（强制）**：裁决表以**语义角色**为主键（稳定），其右侧的图标名称为"须按 pinned `lucide-react` 版本导出清单解析"的候选。Lucide 存在图标改名（如 `MessageCircleQuestion` → `message-circle-question-mark`、`HelpCircle` → `CircleHelp`、`Layers3` → `layers`、`BookMarked` → `book-bookmark`），因此**裁决不随改名失效，映射表与 codemod 必须对已 pin 的版本冻结**（对齐 ADR-092 第 3 条）。

**裁决原则（优先级从高到低）**：① 同一语义只对应一个图标（跨位置复用同一语义是允许且正确的，复用"不同语义"才违规）；② 相邻/同屏的两个语义必须语义距离足够大，避免 24px 下误读；③ 图谱节点图标另需与 §4.4 的**形状**冗余编码自洽（形状与图标应互相印证而非互相矛盾）。

**A. 冲突裁决结果（8 条，已终裁）**

| 语义角色 | 裁决 | 保留备用 | 裁决依据 |
|---|---|---|---|
| 图谱节点 Rule（约束） | `Shield` | — | 本体规则的本质是"拦截非法数据"，防护语义直观 |
| 平台治理工作区 | `Scale` | — | 治理 = 法度/裁决；刻意与 Rule 的 shield 家族拉开距离 |
| 质量门 Quality Gate | `ShieldCheck` | `BadgeCheck` | 校验通过语义；与 Rule 节点不同屏，不构成同屏误读 |
| 审批 Approval | `Stamp` | `ClipboardCheck`、`FileCheck` | 审批 = 盖章；再远离一次 shield 家族，四处 shield 缺口用非 shield 收口 |
| 图谱节点 Metric + 指标平台指标 | `Gauge` | — | **同一语义共用同一图标（正确）**，不是双用 |
| 工作台工作区 | `LayoutDashboard` | — | 把"仪表"语义整条让给 Metric，避免抢用 |
| 本体工作区 | `Network` | `Boxes` | 本体即"语义网络"，是本产品最自然的隐喻；`Network` 因此从工具栏释放 |
| 工具栏 展开邻接 | `Waypoints` | `Share2` | 路径点 = 沿关系逐步扩展；与本体工作区互斥 |
| 图谱节点 Agent | `Bot` | `Cpu`（改留给"运行时/算力"） | `Bot` 语义更准；架构已核验其为 24px 单描边不卡通，与描边体系协调 |
| 编排 / 蓝图编排 | `Workflow` | `GitFork` | 编排 = 工作流；与展开邻接（Waypoints）分离 |
| 本体建模（设计器视图） | `PenTool` | `Blocks`、`Boxes` | "建模"＝绘制/搭建；与本体工作区（Network）不重复 |
| 版本分支 / 分叉视图 | `GitFork` | `GitBranch` | 与提交点（`GitCommit`）配套 |

**释放与保留**：`Network` 已被本体工作区占用；`Share2`、`BadgeCheck`、`Cpu`、`Route`、`Compass`、`ChartLine`、`Tags`、`History` 保留给本文 B 组语义。

**B. ODAP 专有概念语义约定（已终裁，一次性约定、全局复用）**

| 概念 | 裁决 | 备用 | 说明 |
|---|---|---|---|
| 语义缺口 Gap | `CircleDashed` | `Puzzle` | 虚线环＝"缺了一环"，16px 下仍可辨；`Puzzle` 的缺块隐喻在小尺寸易糊 |
| 语义资产 Asset / Semantic Asset | `Package` | — | 资产 = 可交付包；`Boxes` 已被 TBox 占用 |
| 路由工单 Routing Ticket | `Ticket` | — | 图形天然贴合工单 |
| USL 统一语义层 | `Layers` | — | 分层语义；按 pinned 版本解析为 `layers` |
| 指标 MetricType（指标平台） | `Gauge` | `ChartLine` | 与 Metric 节点同义共用 |
| 溯源 Provenance | `Footprints` | `Route` | 足迹＝溯源链路；与"历史记录"分离 |
| 历史 / 变更记录 | `History` | — | 与溯源区分：历史是"发生过什么"，溯源是"依据是什么" |
| 决策 Decision | `Signpost` | `Compass` | 路标＝决策方向；`Scale` 已让给治理 |
| 仿真推演 Simulation | `FlaskConical` | — | 实验/推演 |
| 漂移 Drift | `Radar` | — | 监测偏转 |
| 扫描 Scan（扫描任务） | `ScanLine` | — | 与漂移分离：扫描是动作，漂移是现象 |
| 变更提案 ChangeProposal | `FileDiff` | — | 差异即提案 |
| SHACL 形状 / 形状约束 | `Shapes` | — | 结构形状，非图节点，与 Rule 不冲突 |
| 版本 OntologyVersion | `GitCommit` | `GitFork` | 提交点；`Tags` 保留给标签语义 |
| TBox（术语/结构层） | `Boxes` | — | 与图谱节点 `Box`（对象类型）存在**有意为之**的视觉亲缘（对象类型 ⊂ TBox），是引导而非歧义 |
| ABox（实例层） | `Circle` | — | 与图谱节点"实例"同义共用（正确） |
| 质量门 Quality Gate | `ShieldCheck` | `BadgeCheck` | 见 A 组 |
| 概念缺口回路 | 循环箭头语义（候选 `RefreshCw`） | `RotateCw` | 回路＝闭环流程；**候选名须按 pinned 版本核验** |
| 标签 / 分类 | `Tags` | — | 保留，不给版本语义 |
| 图表 / 趋势 | `ChartLine` | — | 保留 |
| 运行时 / 算力 | `Cpu` | — | 由 Agent 释放而来 |
| 路径 / 链路 | `Route` | — | 保留 |

**回签状态**：设计师已终裁并于 2026-10-16 回签。A/B 两组共 30 项候选经架构在 lucide.dev 逐个核验**全部存在**（含 `PenTool`、`Blocks`、`RefreshCw`、`CircleDashed`、`Footprints`、`Shapes`、`FlaskConical`、`Signpost`、`Stamp`、`ScanLine`、`Ticket`、`Workflow`、`RotateCw`），故"备用列降级"规则本次未触发。

**冻结 gate（未满足即不得落地 codemod）**：`lucide-react` 为本轮新增依赖，`apps/web/package.json` 尚无此依赖，故当前**无 anchored 版本可比对**。映射表冻结须满足两项前置：① Phase 2 安装并 pin 一个具体 `lucide-react` 版本；② 产出「版本号 + 该版本完整导出清单快照」交设计师核对语义角色 → 导出名的映射（核对对象是本文 §5.2 的**语义角色**主键，非名称本身）。冻结完成前，本文 §5.2 为"已终裁、待冻结"状态，映射表为草案。该 OPEN 项已由架构登记于 `docs/decisions/OPEN-DECISIONS.md`（blocked_by: Phase 2 pin lucide-react）。

**冻结后的强制不变量（设计侧要求）**：冻结不是一次性动作，须转为可持续校验的约束——(a) codemod 与一个 CI 校验脚本必须以 pinned 版本的导出清单为**唯一白名单**，源码中出现清单外的图标名即**构建失败**（不得静默降级或就近改选）；(b) 该校验同时扫描 emoji，防止迁移期回灌 P0-1；(c) 校验脚本须内置本文 §5.2 的语义角色表，使"某语义被换成清单内但语义不符的图标"这种错配能被发现（仅校名字存在性不够）。

未列入本表的新语义，仍须走"提交 → 终审 → 回签"，前端不得自行就近选取。

### 5.3 描边档位与光学等重（已终裁）

**背景事实（架构经官方文档核验）**：Lucide 默认 `stroke-width = 2`（非 1.5），且默认描边**随尺寸等比缩放**——即在 24px 网格下取的 1.5，渲染到 16px 档会按 16/24 比例变成约 **1.0px**。因此存在一个必须在冻结前定死的子决策。

**裁决：三档统一恒定 1.5px，启用 `nonScalingStroke`，不接受等比变细。**

依据（按权重排序）：

1. **等比变细会打穿"精密仪器"语言**：1.0px 描边在 1x 与分数 DPR 下落在亚像素上，抗锯齿后发虚；`nebula`（暗色面）上浅色细描边尤其明显，会读作"噪点"而非"图标"。这与本设计语言"层级靠亮度与描边、发丝级描边必须清晰"直接冲突。
2. **高密度场景的相邻关系**：`VISUAL_DENSITY = 7` 下，16px 图标常与 13px 正文同排（表格行、标签、元信息）。1.0px 描边与正文笔画重量不匹配，视觉上"塌"下去；恒定 1.5px 才能与文本笔画持平。
3. **Lucide 自身提供该能力正是为此场景**：`nonScalingStroke`（`vector-effect="non-scaling-stroke"`，替代已 `@deprecated` 的 `absoluteStrokeWidth`）的语义就是"缩小尺寸但保持描边权重"。

**代价与对冲（必须成对执行，否则决策不成立）**：

恒定 1.5px 在 16px 档的相对笔画重量更高（1.5/16 ≈ 9.4%，而 24px 档为 1.5/24 = 6.25%），复杂字形在小尺寸会"糊成一团"。故配套 **16px 复杂度门禁**：

- 16px 档**仅允许单轮廓或简单几何字形**（如 circle / square / link / clock / gauge / bot / ticket）。
- **多内轮廓、密集节点、交叉线条**类字形（如 shapes / network / workflow / boxes / package / flask-conical / git-fork）**最小使用 20px**；若某处必须用 16px，须退用该语义的简化替代图标，而非硬缩。
- 落地方式：§5.2 的语义角色表为每个角色新增 `minSize` 字段，由 CI 校验脚本一并强制（与 §5.2 不变量 (c) 合并为一次扫描）。

**降级口径（避免冻结被阻塞）**：若 pinned 版本不存在 `nonScalingStroke`，退化为**显式逐档 `strokeWidth`**——三档仍取 1.5、仍不做等比，仅放弃 `vector-effect`；若在 1x 屏实测仍发虚，允许采用 `24 = 1.5 / 20 = 1.5 / 16 = 1.4` 的微调表（**仍非等比**）。此降级属同一决策族（"拒绝等比变细"），**不需二次终审**。

**显式性硬要求**：任何位置不得依赖库默认值——因默认值为 2，`strokeWidth={1.5}` 必须**显式传入**（或由项目级 Icon 包装组件统一注入，且该包装组件是唯一允许设置该 prop 的位置）。对包装组件另有三条设计侧约束（防止"唯一位置"被绕过）：

1. **不暴露 `strokeWidth` 为对外 prop**——包装组件可接受 `size` / `role`（或 `name`）/ `className`，但**不得**接受 `strokeWidth`；否则业务侧仍可覆盖，等于 186 处约定没收敛。描边相关属性对该组件内部为常量。
2. **注册表必须是手工维护的静态映射，禁止 `import * as Icons`**——后者会让打包器无法 tree-shake，把全部图标一并打进产物；注册表只允许列出本文 §5.2 终裁过的图标集合。
3. **优先以"语义角色"为 API 键**（如 `role="ontology"`），而非直接暴露库图标名。理由：语义角色是本文 §5.2 的稳定主键（Lucide 改名不影响它），以角色为键可把"语义绑定"从 CI 事后扫描升级为**类型层构造即合法**——传一个未经终裁的角色根本编译不过；同时角色键天然规避 `import *` 的 tree-shaking 陷阱（映射表是显式静态的）。若实现选取 `name` 键，CI 语义角色表校验（§5.2 不变量 (c)）即为必需补偿，不可省略。

---

## 6. 关键页面设计规格

> 通用约定：以下所有页面均覆盖 5 态 —— Loading / Empty / Error / Populated / Edge；均满足对比度、焦点可见、键盘可达、`prefers-reduced-motion`。全部颜色用 Token 名引用。

### 6.1 LLM Wiki（知识 / 文档中心）

- **路由**：`/knowledge`（列表 + 详情改用主从）、`/knowledge/navigation`（导航视图）、文档详情 `/knowledge/doc/:id`。
- **布局骨架**（lg+）：左侧二级导航（232px，目录树：本体域 / 概念 / 文档集）｜中部主区（文档列表或阅读器）｜右侧检查器（320px，可折叠，承载元数据/溯源/版本）。
  - 列表态：主区为表格（列：标题 / 类型 / 所属本体域 / 关联实体数 / 更新人 / 更新时间 / 状态徽标）。
  - 阅读态：主区 = 阅读器（`--odap-content-max: 1200px` 内），左缘 4px 内联锚点条（目录），正文右侧浮动"引用编号"，点击高亮对应溯源卡片。
- **信息层级**：页面标题（`typography.heading1`）→ 视图切换（列表/导航，分段控件）→ 过滤条（本体域 / 类型 / 状态 / 时间）→ 内容。强调色仅用于"当前选中视图"和"主操作按钮"各 1 处。
- **版本与溯源**：检查器内 `Tabs` = 属性 / 版本 / 溯源 / 关系。版本用时间线（竖向，节点为图标，非侧条纹）；溯源用"引用卡片"（来源文档 + 片段 + 置信度），置信度用数值 + 图标双编码。
- **去重合并**：在列表内多选后，顶部浮出操作条（`--odap-elevation.md`，sticky）；进入"合并"视图为左右对照（保留/丢弃字段逐项选择），冲突项用 `warn` 整块底色 + 图标标注（**不使用彩色左边框**），底部主按钮"确认合并"（危险语义时二次确认）。
- **交互状态**：
  - 列表行 hover → 行底色 `table.rowHoverBg`；选中 → `table.rowSelectedBg` + 行首勾选。
  - 阅读器内引用 hover → 对应溯源卡片描边高亮（`accentBorder`）。
  - 合并冲突项切换保留 → 150ms 底色过渡。
- **状态覆盖**：
  - Loading：表格骨架屏（`skeleton` 微光，1400ms loop）；阅读器用段落骨架。
  - Empty：首次进入显示"新建文档/导入来源"引导 + 一个真实示例条目（非空洞占位）。
  - Error：区分"知识库未初始化 / 权限不足 / 服务超时"，各给具体说明 + 重试按钮；合并失败保留用户已选状态。
  - Edge：超长标题截断（2 行 + title 提示）；上万条文档启用虚拟滚动；引用编号超过 3 位数改紧凑排版；超大文档分段懒加载。

### 6.2 智能问答（语义检索问答）

- **路由**：`/qa`、`/qa/query`（问答）、`/qa/evaluation`（评测）。
- **布局骨架**（lg+）：左栏会话/历史（可收起，232px）｜中部问答流（消息列表 + 底部输入）｜右栏"推理检查器"（320px，可 hold 或浮层）。
  - 输入区：多行输入 + 发送/停止；下方一行"约束开关"（是否强制本体约束、检索范围、模型路由，≤4 项）。
- **信息层级**（本页最关键的"可解释性"）：回答卡片自上而下 = ① 意图识别（意图标签 + 置信度条）→ ② 本体约束命中（命中的 Object Type / Relation 以 chip 列出，未命中项以 `warn` chip 标注"未覆盖"）→ ③ 答案正文（含内联引用角标）→ ④ 溯源证据（可展开列表：来源片段 + 相关度）→ ⑤ 后续执行建议（可点击的建议动作，如"在图谱中展开该子图"/"运行推演"）。
- **推理可视化**：右栏检查器用**步骤时间线**（竖向，每步为图标 + 标题 + 状态 + 耗时），`Loading` 步显示进度点阵，完成步可展开原始 JSON/SPARQL/Cypher（等宽字体）。**不使用"打字机 + 发光粒子"式装饰动效**，仅用逐段淡入（150ms）。
- **交互状态**：
  - 生成中：回答卡片顶部显示"生成中"状态点 + 中止按钮；已生成段落可读（不锁屏）。
  - 约束命中切换：hover 高亮正文中对应实体（描边），点击滚动到溯源。
  - 追问：输入框上方显示"上下文保持"指示（引用前几轮）与"新话题"入口。
- **状态覆盖**：
  - Loading：意图解析 → 检索 → 生成 三段进度；首 token 前用骨架段落。
  - Empty：首次显示 3 条**真实**示例问题（针对当前本体域生成），点击即填入并执行。
  - Error：分类"模型不可用 / 检索超时 / 权限 / 约束冲突"，各给降级方案（如"切换检索模式重试"）；约束冲突时明确指出违反的约束并给出可选放宽项。
  - Edge：超长答案折叠（保留前 N 段 + 展开）；成本/长度上限提醒；敏感内容过滤提示；无溯源命中时明确标注"无可靠来源"而非编造。

### 6.3 本体建模（编辑器 + 校验反馈）

- **路由**：`/ontology/designer`（设计器）、`/ontology/goals`、`/blueprint`。
- **布局骨架**（lg+，专业化三区）：左栏"本体树/资源库"（232-280px：Object Types / Link Types / Action Types / Properties，可搜索）｜中部画布（Graph 视图与列表视图可切换）｜右栏"属性/校验检查器"（320px，随选中项切换）。
- **编辑器能力**：
  - 画布：新增/连线/拖拽/框选/自动布局；连线时对非法关系（违反基数/类型约束）**即时**给出红色虚线预览 + 阻止提交。
  - 属性编辑：检查器内表单（名称/类型/基数/必填/默认值/描述），失焦校验 + 提交前全量校验。
- **校验反馈（本页核心）**：
  - 顶部校验条：`错误 N / 警告 M`，点击展开"问题面板"（列表：严重级图标 + 位置 + 说明 + "定位"按钮，点击跳转并高亮画布节点）。
  - 画布节点上叠加状态角标（错误/警告/通过），**颜色 + 图标双编码**。
  - 发布门禁：存在错误时"发布"按钮禁用并说明原因（helper text 紧贴按钮）。
- **状态覆盖**：
  - Loading：画布加载用坐标占位网格 + 骨架节点；检查器骨架。
  - Empty：无本体时显示"从模板创建 / 导入 / 手绘"三条真实入口；某个类型无实例时检查器显示引导。
  - Error：保存冲突（他人已改）提示对比合并；校验服务不可用时可只读编辑并标记"未校验"。
  - Edge：超大本体（>N 节点）默认聚类折叠 + 聚焦子图；名称重复/循环引用给出明确提示；撤销栈深度受限时提示。

### 6.4 图谱探查（统一渲染栈下的交互规格）

- **路由**：`/ontology/explorer`（对象图谱）、`/ontology/semantic-map`、`/ontology/abution-graph`。
- **统一渲染栈**：7 套图库收敛为 1 套（由架构师选型），本规格为**功能契约**，与实现库无关。
- **布局骨架**（lg+）：全高画布 + 顶部工具栏 + 左侧图例面板（可折叠）+ 右侧选择面板（320px）+ 右下角缩略图。
- **工具栏**（图标 + 图标旁可展开文字，尺寸 20px）：选择/平移模式、布局切换、搜索、筛选、展开邻接、隐藏选中、撤销/重做、导出。
- **图例面板**（参考 Neo4j Bloom）：按类别与关系类型列出，显示数量、颜色/形状/图标；**规则驱动样式**（single / range / unique values，数值属性附直方图）；点击类别 = 全选该类别节点。面板可折叠。
- **选择面板**（参考 Palantir Vertex）：点击节点自动展开属性（含派生属性置顶）；提供"Search Around"多步邻接扩展 + 过滤；提供"Reveal Relationships"避免画布噪声。
- **交互规格**：
  - 悬停节点：描边高亮 + tooltip（名称 + 类型 + 关键属性）；悬停边：加粗 + 显示关系名与基数。
  - 选中：2px 强调环 + 5px 24% 光环；多选显示聚合操作条。
  - 拖动节点：`cursor: grabbing`，节点 `opacity: 0.8`，150ms 后拾取。
  - 缩放/平移：滚轮/拖动；缩略图同步视口框。
  - 框选：marquee 半透明强调色填充 + 实线边框。
  - 键盘：Tab 遍历节点、方向键平移、`+/-` 缩放、Enter 打开检查器、Esc 取消选择。
- **状态覆盖**：
  - Loading：画布骨架（网格 + 占位节点），关系延迟加载时边显示虚线占位。
  - Empty：无数据时显示"从对象搜索添加起点"引导（含真实对象类型计数），而非空白画布。
  - Error：查询失败明确报错 + 重试；部分子图加载失败时保留已加载部分并标注缺失范围。
  - Edge：超大图（>N 节点）自动降级 —— 隐藏边标签、聚类折叠、进入"采样模式"并提示；超长节点标签截断 + tooltip 全文；零结果明确提示。

### 6.5 全局导航与主题切换入口（60+ 路由收敛后的信息架构）

- **导航骨架**：三级结构
  - 一级：左侧图标导轨（`--odap-rail-width: 56px`），承载 6 个顶级工作区（图标 24px + 悬停显示文字 + `aria-label`）。
  - 二级：二级导航（`--odap-nav-width: 232px`，可收起为 64px），展示当前工作区内的功能项（≤ 12 项，超出分组）。
  - 三级：页面内 `Tabs` / 分段控件。
  - 另有功能区（任务 Tab，来自 `layoutStore`）与扩展区（AI 助手，可 hold 或浮层）构成四栏，`lg` 以下按 §3.5 折叠。
- **信息架构收敛（60+ 路由 → 6 个工作区）**：

| 工作区 | 图标语义 | 归入的路由（示例） |
|---|---|---|
| 工作台 | dashboard | `/`、`/guide`、`/my-agents`、`/agent`、`/agent-chat/:id`、`/workspace/manage` |
| 本体 | ontology | `/ontology/designer`、`/ontology/explorer`、`/ontology/service-catalog`、`/ontology/semantic-map`、`/ontology/abution-graph`、`/ontology/goals`、`/blueprint`、`/versions` |
| 知识 | knowledge | `/knowledge`、`/knowledge/navigation`、`/ingest`、`/he/extraction`、`/mcp/tools` |
| 问答与决策 | ask | `/qa`、`/qa/query`、`/qa/evaluation`、`/decisions`、`/simulation`、`/simulation/memory`、`/simulation/perception` |
| 语义治理 | governance | `/semantic-admin/*`（assets / usl / usl-ontologies / pipeline / candidates / quality / approvals / gaps / routing-tickets） |
| 平台管理 | settings | `/settings`、`/settings/channels/*`、`/roles`、`/users`、`/policy-editor`、`/audit`、`/menu-config`、`/i18n-admin`、`/skills`、`/admin/agents`、`/iframe-viewer` |

- **收敛规则**：重复实现合并（如 Policy 三处 → 1 处；Knowledge 两处 → 1 处；`AuditTimeline` 组件/页面重复 → 1 处）；`/simulator`、`/policies`、`/ontology/graph`、`/admin` 等重定向路由保留为别名；顶级项固定为 6（符合工作记忆 ≤4-7 上限，超过则分组）。
- **主题切换入口**：置于顶栏右侧，规格见 §3.7。顶栏常驻元素（从左到右）：面包屑、全局搜索、帮助、通知、任务区开关、扩展区开关、主题切换、用户菜单。
- **状态覆盖**：
  - Loading：导航骨架（导轨图标占位 + 二级项骨架）。
  - Empty：某工作区对当前角色无任何可见项时，显示"当前角色未分配该模块，联系管理员"（不显示空壳导航）。
  - Error：菜单配置加载失败时降级为静态默认菜单并提示。
  - Edge：超长模块名截断 + tooltip；权限收敛后二级项为 0 时隐藏该导轨项；折叠态仅显图标，悬停出提示。

---

## 7. 设计门禁自查表

> 逐项声明，由大湾区靓仔在 Phase 门禁复核。证据指向 `design-tokens.json` / `design-tokens.css` / 本文对应章节。

### 7.1 P0 绝对规则

- [x] **P0-1 无 emoji 作为功能图标**：`design-tokens.css`、`design-tokens.json`、本文档已用 emoji 正则扫描，零命中。图标方案见 §5（统一描边 SVG，16/20/24px，库由 Spec 锁定）。§1.2(4) 已列出 v1 文档中全部 emoji 违规点作为待清理清单。
- [x] **P0-2 无紫色→粉色/品红渐变**：全文件零 `linear-gradient` 跨色相定义；仅有的渐变相关值为 `design-tokens.css` 中 `--odap-gradient-*` 的**不存在**（已删除该 token）；同一 hue 的深浅梯度以 `-400/-500/-600` 纯色阶梯表达。§1.2(2) 已定位现网 `colorThemeUtils.ts` L142-147 与 `global.css` L79-80 为待移除源。amber 退役、violet 仅保留为图表分类纯色。
- [x] **P0-3 无空洞文案与硬编码色**：Token 文件零裸 hex（primitive 层的 hex 即 Token 定义本身）；semantic/component 层全部 alias；组件层规格中全部用 Token 名。文档无 Lorem ipsum / "Welcome to" / "Sign up today"；§6 中的示例文案均为具体业务语义。**无弹跳/过冲缓动**：`design-tokens.css` 的 ease 仅 standard/decelerate/accelerate/linear，控制点均 ≤1；§1.2(5) 已列出 v1 过冲缓动待清理点。

### 7.2 设计系统检查

- [x] 所有颜色通过 Token 引用（三层架构，见 §4）。
- [x] 间距全部为 4px 整数倍（`space` 0/4/8/12/16/20/24/32/40/48/64/80）。
- [x] 字体明确：Manrope（展示）+ Inter（正文）+ Noto Sans SC（中文）+ JetBrains Mono（数据/代码）。
- [x] 标题 / 正文 / 数据三套字体层级明确（`typography.*`，含用法说明）。
- [x] 三轴刻度标定：Variance=4 / Motion=4 / Density=7（本文头部）。
- [x] 对标品牌与行业风格选定并全产品一致（Linear / Palantir Foundry Vertex / Neo4j Bloom / Databricks，见 §2.1）。
- [x] 按钮覆盖 default / hover / focus-visible / active / disabled / loading（`component.button.states` + §4）。
- [x] 表单有验证错误态与 helper text 规格；列表有空状态规格（§6 各页 5 态）。
- [x] 未使用千篇一律 Hero（本项目为 Product register，无营销 Hero；页面一律"工具栏 + 内容 + 检查器"骨架，§6）。
- [x] 无"每节小写大写标签"、"编号 section 标记"、"幽灵卡片（1px 边框 + blur ≥16px）"、"卡片圆角 ≥24px"等 AI 语法。

### 7.3 质量标准

- [x] 图标系统规格已定义（统一描边、16/20/24px、禁 emoji、禁混用），实现库由 Spec 锁定（§5）。
- [x] 无纯黑 `#000` / 纯灰 `#808080` 直接使用；暗色面最低为 `#0B0E14`，亮色面最高为 `#0F172A`，均带冷调。
- [x] 对比度：正文亮色面 ≥ 4.5:1（`fg #0F172A` ≈ 17:1、`fgSecondary #475569` ≈ 8.5:1）；暗色面 `fg #F2F5FA` ≈ 15:1、`fgMuted #9AA4B2` ≈ 7.7:1；强调色 solid 与 on 对比度逐色相验证（cobalt 7.0 / teal 6.3 / indigo 6.3 / graphite 10.3）。
- [x] 动画时长 ≤ 400ms（max 300ms，page 240ms）；支持 `prefers-reduced-motion`（`design-tokens.css` §4）。
- [x] 响应式方案覆盖移动端：断点唯一化（§3.5），导航移动端用底部 TabBar（≤5），触摸目标 ≥ 44×44px。
- [x] 组件状态矩阵覆盖：default / hover / focus-visible / active / disabled / loading / error / empty / success（各页面级 5 态见 §6）。
- [x] 无障碍：`:focus-visible` 全站可见环；键盘可达（导航、图谱、面板均有键盘规格）；卡片/列表顺序与视觉顺序一致；图表与图谱提供颜色以外的冗余编码。
- [x] 未使用装饰性毛玻璃（绝对禁令 #3）：`design-tokens.css` 无 `backdrop-filter`；玻璃态在 v2 中不提供。
- [x] 未使用侧条纹彩色边框（绝对禁令 #1）：状态表达改为"整块底色 + 圆角 + 图标"。

### 7.4 待清理清单（移交 Phase 3 前端）

| 文件 | 位置 | 动作 |
|---|---|---|
| `apps/web/src/modules/shared/styles/colorThemeUtils.ts` | L142-147 | 删除跨色相渐变生成逻辑，改为读 `data-appearance` / `data-accent` |
| 同上 | L69-101 | 5 个调色板收敛为 4 个 accent 色相 + 2 个外观 |
| 同上 | L150-163 | 侧栏改为跟随外观（不再恒为深色渐变） |
| `apps/web/src/modules/shared/styles/global.css` | L3、L79-80、L125、L375、L441-447、L541、L608、L649 | 删除跨色相渐变、过冲缓动、`border-left` 侧条纹、裸色值；接入 `design-tokens.css` |
| `apps/web/src/modules/shared/components/ThemeColorPicker.tsx` | L14-18、L68 | 改为外观+色相双选择器；过渡改用 token |
| `docs/04-ui/*.md`（v1 七篇） | 全文 | 标注"历史文档；以 UIUX-DESIGN-v2.md 为准"，并清理 emoji 与冲突色值 |

---

## 8. 交付物清单

| 产物 | 路径 | 说明 |
|---|---|---|
| 设计方案（本文） | `docs/04-ui/UIUX-DESIGN-v2.md` | 审计 + 方向 + 风格切换 + Token 规范 + 图标 + 页面规格 + 门禁 |
| 机器可读 Token | `docs/04-ui/design-tokens.json` | 三层结构，前端 `import` 使用 |
| CSS 变量 | `docs/04-ui/design-tokens.css` | 全主题风格，`data-appearance` / `data-accent` 驱动 |

变更记录：

| 日期 | 变更 | 原因 | 影响范围 |
|---|---|---|---|
| 2026-10-16 | v2 首版：三层 Token、双外观、4 色相、断点收敛、5 页面规格 | 现状四套规范冲突且命中 P0 红线 | 全前端 |
| 2026-10-16 | §5.1 记录图标库锁定 `lucide-react`；§5.2 新增"灰名单终审规则 + 冲突点清单" | 架构 ADR-092 回执；灰名单终审归属需明确 | 图标系统 / Phase 3 迁移 |
| 2026-10-16 | §5.2 完成 A 组 8 条冲突 + B 组 22 项 ODAP 专有概念的终裁并回签；§4.4 与 §5.1 的 Agent 图标由 cpu 改为 bot | 架构提交灰名单草案与配图候选；语义归一只能在设计侧收口 | 图标系统 / 映射表冻结 |
| 2026-10-16 | §5.2 补充"冻结 gate（blocked_by Phase 2 pin）+ 冻结后的强制不变量（白名单校验/emoji 扫描/语义角色表）"；30 项候选存在性核验结果记录在案 | 架构回执：13 候选全部存在；`lucide-react` 尚未 pin，冻结须以导出清单快照为准 | 图标系统 / Phase 2-3 交接 |
| 2026-10-16 | 新增 §5.3：裁决三档描边恒定 1.5px（`nonScalingStroke`）、拒绝等比变细、配套 16px 复杂度门禁与 `minSize` 校验、降级口径 | 架构核验 Lucide 默认 stroke-width=2 且随尺寸等比缩放，16px 档会降到约 1.0px；此子决策影响全部小尺寸图标观感 | 图标系统 / 映射表冻结口径 |
