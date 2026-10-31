---
id: odap.l7.adr-093-design-token-theming
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

# ADR-093: Design Token 分层与多主题切换机制

## Status

**已接受（2026-10-17）**。本轮确认 primitive → semantic → component 三层 Token 体系，消除 P0-2 违规，并与设计侧 Token 真源对齐。

---

## Background

关联铁律：团队级 P0-2 ——「禁止紫色→粉色/品红渐变主视觉（含调色板定义）」；P0-3 ——「禁止硬编码颜色（除 #fff/#000）」。

**现状（文件:行证据）**：

- 现网 `apps/web/src/modules/shared/styles/colorThemeUtils.ts:12-18` 的 `ColorPalette` 仅含 `primary/accent/glowRgba/sidebar/logoAccent`，**无三层 Token 结构**。
- **P0-2 违规实锤**：`:69-84` `violet` 调色板 `primary['600']='#7C3AED'`（`:73`）+ `accent['500']='#D946EF'`（`:78`）；`:142-144` 生成 `--odap-gradient-brand: linear-gradient(135deg, #7C3AED 0%, #D946EF 100%)`（紫→品红）。
- 同类违规（设计侧已定位，`docs/04-ui/UIUX-DESIGN-v2.md` §7.4）：`global.css` L79-80 跨色相渐变 `#4F46E5→#8B5CF6`；L441-447 `.ant-btn-primary` 渐变+发光；L125 过冲缓动；L375/L649 `border-left` 侧条纹；L113/L608 等裸色值。
- 全项目硬编码 hex（排除 #fff/#000）**1044 处**。

**设计侧已交付 Token 真源**（本轮以此为唯一真源，不另起炉灶）：
- `docs/04-ui/design-tokens.css`（CSS 真源）+ `docs/04-ui/design-tokens.json`（机器可读真源），二者须完全一致。
- 命名前缀 `--odap-*`；三层结构；外观 `data-appearance="luminous|nebula"`；强调色 `data-accent="cobalt|teal|indigo|graphite"`。
- 关键 token：`--odap-size-icon-stroke:1.5`（`:237`）、`--odap-size-icon-inline/button/standalone:16/20/24`（`:234-236`）、`--odap-graph-*`（`:521-553`）、`--odap-chart-*`（`:555-572`）。

---

## Decision

1. **Token 三层结构**（对齐 `references/design-systems/token-standard.md`，落 `docs/04-ui/design-tokens.css`）：
   - `Primitive`（原始值，全项目唯一允许出现 hex 的层）：`--odap-primitive-{neutral|ink|cobalt|teal|indigo|graphite|...}-{50..900}`。
   - `Semantic`（语义别名，主题切换点）：`--odap-color-{bg|surface|fg|border|accent|success|warn|danger|info}`、`--odap-accent-*`。
   - `Component`（组件专用）：`--odap-button-*`、`--odap-input-*`、`--odap-graph-*`、`--odap-chart-*`。
2. **Token 真源**：以 `docs/04-ui/design-tokens.css` + `design-tokens.json` 为唯一真源；移除 `apps/web/src/modules/shared/styles/colorThemeUtils.ts` 的行内注入模式（`applyColorTheme`）。前端 `import` `design-tokens.json` 供 TS 使用，CSS 侧由 `data-*` 驱动。
3. **P0-2 消除**：
   - 删除 `colorThemeUtils.ts:142-147` 跨色相渐变生成逻辑；`--odap-gradient-brand` 不再存在。
   - 删除 `global.css` L79-80、L441-447 的跨色相渐变主按钮（改纯色 `--odap-color-accent-solid`）。
   - `violet` 仅保留为**图表/图谱分类纯色**（`--odap-primitive-violet-500`，`:118`），不再参与品牌渐变；如需渐变只允许同色相深浅（`accent ↔ accent-hover`）。
4. **多主题/风格切换**：`<html data-appearance="luminous|nebula" data-accent="cobalt|teal|indigo|graphite">`；`[data-appearance]`/`[data-accent]` 只切换 semantic 层；由 `useThemeRuntime` 写入属性并持久化。
5. **与 AntD 6 ConfigProvider 对接**（沿用设计侧 §3.6 唯一路径）：`CSS 变量 → html[data-*] → ConfigProvider.token + ConfigProvider.components`；用 `getComputedStyle(document.documentElement).getPropertyValue(name)` 实时读 CSS 真源，保证与 CSS 一致（`AdminLayout.tsx:655-691` 的 `ConfigProvider` 用法正确，v2 在其上扩展而非推翻）。
6. **禁硬编码**：组件代码只用 `var(--odap-*)` 或 AntD token；现存 1044 处按模块清理，清理率进 Phase 3 质量门禁。
7. **动效约束**：统一 `--odap-duration-*`/`--odap-ease-*`（无 spring/overshoot），删除 `global.css` L125 过冲缓动。

---

## Consequences

**正面**：
- 消除 P0-2 违规；主题/风格切换只改 semantic 层，组件零感知。
- 与设计侧 Token 真源单一来源，设计与工程同一契约。
- 硬编码颜色收敛，多主题一致性可保证。

**负面**：
- 1044 处硬编码清理工作量大，须分批 + 灰度。
- Token 真源需设计/工程同步维护，引入额外维护面。
- `violet` 品牌渐变移除属视觉破坏性变更，依赖它的既有页面须回归。

---

## Related ADRs

- ADR-007（前端 React + Ant Design 技术栈）
- ADR-091（图谱渲染栈；消费 `--odap-graph-*`/`--odap-chart-*`）
- ADR-092（图标库；消费 `--odap-size-icon-*` 与 `--odap-color-*`）
