---
id: odap.l4.token-migration-map
status: active
owner: designer
version: ''
layer: L4
concern: token-migration
lifecycle: living
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
governance_reason: Token 双写协议与迁移映射，W0-1 交付物
---

# Token 迁移映射表（W0-1）

> 真源：`docs/04-ui/design-tokens.css`（唯一）
> 运行时镜像：`apps/web/src/modules/shared/styles/design-tokens.css`
> 迁移桥（别名层）：`apps/web/src/modules/shared/styles/global.css` 第 1 节

---

## 1. 双写协议（先读这一节）

`docs/04-ui/design-tokens.css` 是**唯一真源**。前端为了能被打包器引入，必须存在一份字节级镜像：

| 位置 | 角色 | 谁改 |
|---|---|---|
| `docs/04-ui/design-tokens.css` | 真源（设计侧与前端共同评审） | 设计师提出 → 评审通过后写入 |
| `apps/web/src/modules/shared/styles/design-tokens.css` | 镜像（仅加文件头注释，其余逐字一致） | 由真源复制，**不得单独编辑** |

改动流程（三步，缺一即视为未完成）：

1. 改真源 `docs/04-ui/design-tokens.css`
2. 同步镜像：把真源内容整段复制过去，只保留镜像文件顶部的「镜像说明」注释块
3. 校验一致性（CI 与本地都必须通过）：

```bash
diff docs/04-ui/design-tokens.css \
     apps/web/src/modules/shared/styles/design-tokens.css
```

> 已知差异只有镜像文件顶部的注释块，`diff` 输出应当**只有**该段。若出现其他差异，说明有人直接改了镜像。

引入顺序（`apps/web/src/main.tsx`）：`design-tokens.css` → `index.css` → `global.css`。
别名层必须在真源之后加载，否则 `var()` 会解析为空。

---

## 2. 主题怎么被驱动（不再有内联渐变）

旧实现（v1）在 `colorThemeUtils.ts` 里用 JS 写内联变量，把紫色→品红渐变注入 `--odap-gradient-brand`，命中团队 P0 红线。v2 起**只有一个切换点**：

```html
<html data-appearance="luminous|nebula" data-accent="cobalt|teal|indigo|graphite">
```

| 轴 | 取值 | 含义 | 由谁写 |
|---|---|---|---|
| `data-appearance` | `luminous` / `nebula` | 亮面 / 暗面（亮度递进表达层级，不靠阴影） | `applyColorTheme()`（`colorThemeUtils.ts`） |
| `data-accent` | `cobalt` / `teal` / `indigo` / `graphite` | 4 个纯色强调色相族 | 同上 |

旧 store 的 `colorTheme`（`indigo/blue/green/violet/amber`）与 `isDark` 仍在，但只作为"旧取值域"被翻译：

| 旧 store 值 | 新 `data-accent` | 说明 |
|---|---|---|
| `indigo` | `indigo` | 同名直映 |
| `blue` | `cobalt` | 语义最近的纯色族 |
| `green` | `teal` | 语义最近的纯色族 |
| `amber` | `graphite` | 语义最近的纯色族 |
| `violet` | `indigo` | **已退役**（渐变来源色相），降级为纯色 |
| 其他/脏值 | `cobalt` | 兜底，避免"没有强调色" |

组件层取色统一走 `useThemeRuntime()`：它把 CSS 变量读成 Ant Design 6 的 `ConfigProvider.token`，因此**主题色不需要在 JS 里再定义一份调色板**。

---

## 3. 旧 Token → 新 Token 映射

旧代码里 300+ 处 `--odap-*` 引用没有一次性删除，而是通过 `global.css` 的别名层桥接。别名层只允许出现 `var()`，**零字面色值**。

### 3.1 主色阶 / 强调色阶

| 旧 Token | 新 Token |
|---|---|
| `--odap-color-primary-50…900` | `--odap-accent-50…900`（插槽，随 `data-accent` 变） |
| `--odap-color-primary` | `--odap-color-accent` |
| `--odap-color-accent-50…600` | `--odap-accent-50…600` |
| `--odap-color-highlight` | `--odap-color-accent-subtle` |

### 3.2 文本 / 表面 / 描边

| 旧 Token | 新 Token |
|---|---|
| `--odap-color-text-primary` | `--odap-color-fg` |
| `--odap-color-text-secondary` | `--odap-color-fg-secondary` |
| `--odap-color-text-tertiary` | `--odap-color-fg-muted` |
| `--odap-color-text-disabled` | `--odap-color-fg-disabled` |
| `--odap-color-bg-primary` | `--odap-color-surface` |
| `--odap-color-bg-secondary` | `--odap-color-bg` |
| `--odap-color-bg-tertiary` | `--odap-color-bg-subtle` |
| `--odap-color-bg-glass` | `--odap-color-surface`（玻璃态退役，退化为实体表面） |
| `--odap-color-border-light` | `--odap-color-border-subtle` |

### 3.3 中性灰（不再自带色相语义）

| 旧 Token | 新 Token |
|---|---|
| `--odap-color-gray-50…900` | `--odap-primitive-neutral-50…900` |

### 3.4 语义色 / 标签色

| 旧 Token | 新 Token |
|---|---|
| `--odap-color-warning` | `--odap-color-warn` |
| `--odap-color-error` | `--odap-color-danger` |
| `--odap-color-tag-blue` / `tag-purple` | `--odap-color-accent` |
| `--odap-color-tag-green` | `--odap-color-success` |
| `--odap-color-tag-orange` | `--odap-color-warn` |
| `--odap-color-tag-red` | `--odap-color-danger` |
| `--odap-color-tag-cyan` | `--odap-color-info` |

### 3.5 字体 / 间距 / 圆角 / 阴影

| 旧 Token | 新 Token |
|---|---|
| `--odap-font-family` | `--odap-font-body` |
| `--odap-font-family-mono` | `--odap-font-mono` |
| `--odap-font-size-xs/sm/base/lg/xl` | 同名 `--odap-font-size-*`（真源已有，无需别名） |
| `--odap-spacing-xs/sm/md/lg/xl` | `--odap-space-1/2/4/6/8` |
| `--odap-radius-sm/md/lg` | 同名 `--odap-radius-*`（真源四级体系） |
| `--odap-radius-round` | `--odap-radius-pill` |
| `--odap-shadow-xs…xl` | `--odap-elevation-xs…xl` |
| `--odap-shadow-glow` | `--odap-focus-ring`（装饰性光晕 → 焦点环） |

### 3.6 骨架 / 动效 / 层级 / 断点

| 旧 Token | 新 Token |
|---|---|
| `--odap-sidebar-width` | `--odap-nav-width` |
| `--odap-sidebar-collapsed` | `--odap-nav-collapsed-width` |
| `--odap-sidebar-bg` | `--odap-nav-bg`（跟随外观，不再恒为深色） |
| `--odap-sidebar-border` | `1px solid var(--odap-color-border)` |
| `--odap-sidebar-border-strong` | `1px solid var(--odap-color-border-strong)` |
| `--odap-sidebar-text` | `--odap-color-fg-muted` |
| `--odap-sidebar-text-hover` | `--odap-color-fg` |
| `--odap-sidebar-logo-color` | `--odap-color-accent` |
| `--odap-ease-out` | `--odap-ease-decelerate` |
| `--odap-ease-in-out` | `--odap-ease-standard` |
| `--odap-transition-fast/normal/slow` | `--odap-duration-fast/base/slow` + `--odap-ease-standard` |
| `--odap-z-dropdown/drawer/modal/tooltip` | `--odap-z-dropdown` / `--odap-z-drawer` / `--odap-z-modal` / `--odap-z-tooltip`（真源已有完整 9 级） |
| `--odap-breakpoint-xs…2xl` | `--odap-bp-xs…2xl`（别名保留） |
| `--odap-page-padding` | `var(--odap-space-4) var(--odap-space-6)` |

---

## 4. 已彻底删除的 Token（无别名，出现即视为回退）

| 已删除 | 原因 | 替代做法 |
|---|---|---|
| `--odap-gradient-brand` | 跨色相紫→品红渐变（P0-2 红线） | 纯色 `--odap-color-accent`；需要层次用字重/尺寸/表面色 |
| `--odap-gradient-brand-hover` | 同上 | 悬停改 `--odap-color-accent-hover` 或表面色变化 |
| `--odap-gradient-sidebar` | 侧栏渐变 | `--odap-nav-bg` 纯色 |
| `--odap-ease-spring` (`cubic-bezier(0.34,1.56,0.64,1)`) | 过冲缓动（团队 P0） | `--odap-ease-standard` / `--odap-ease-decelerate` |
| `backdrop-filter: blur()` 玻璃面板 | 装饰性毛玻璃 | 实体表面 `--odap-color-surface` + 描边 |
| `border-left: 3px solid <语义色>` | 彩色侧条纹 | 整块底色 `--odap-color-{success,warn,danger}-bg` + 图标 |

动作/状态类过渡统一 `150ms`（`--odap-duration-fast`），不写 `transition: all`。

---

## 5. 自查命令

```bash
cd apps/web

# 1) 真源与镜像一致：diff 只应输出镜像头部注释那一段
diff ../../docs/04-ui/design-tokens.css src/modules/shared/styles/design-tokens.css

# 2) 本轮改写范围必须零硬编码颜色（#fff / #000 白名单除外）
grep -rEn "#[0-9a-fA-F]{3,8}\b" \
  src/modules/wiki src/routes \
  src/modules/shared/components/Icon.tsx src/modules/shared/components/iconRegistry.ts \
  src/modules/shared/components/WorkspaceRail.tsx src/modules/shared/components/ThemeColorPicker.tsx \
  src/modules/shared/styles/global.css src/modules/shared/styles/colorThemeUtils.ts \
  src/modules/shared/styles/useThemeRuntime.ts src/modules/shared/components/OdapLayout.css \
  src/modules/shared/navigation src/modules/shared/utils \
  --include='*.css' --include='*.ts' --include='*.tsx' \
  | grep -vE "#fff\b|#FFF\b|#ffffff\b|#000\b|#000000\b"
# 期望：空输出

# 3) 已删除 Token 的残留引用（注释/清理清单/测试除外）
grep -rn "gradient-brand\|gradient-sidebar\|ease-spring" src
# 期望：只出现在 colorThemeUtils.ts 的清理清单、global.css 的说明注释、对应单测

# 4) 本轮改写文件不得出现渐变 / 毛玻璃 / 彩色侧条纹
grep -rn "linear-gradient\|backdrop-filter" src/modules/shared/styles src/modules/wiki src/modules/shared/components/OdapLayout.css
grep -rn "border-left: *[2-9]px" src --include='*.css'
# 期望：唯一允许的命中是「骨架 shimmer」——由 --odap-skeleton-bg / --odap-skeleton-highlight
#       组成的同灰度功能性渐变（global.css 的 .ant-skeleton、wiki.css 的 .wiki-skeleton）。
#       任何引用品牌色/强调色的渐变都必须为 0。
```

### 5.1 遗留债务（如实记录，不在 W0-1 范围内）

`--odap-*` 别名层只保证「新代码不再产生字面色值」，不负责清理历史页面。仓库级的硬编码色值现状（命令：`grep -rEn "#[0-9a-fA-F]{3,8}\b" src --include='*.tsx' --include='*.ts' --include='*.css'`）：

| 指标 | W0-1 之前（HEAD） | W0-1 之后 |
|---|---|---|
| 硬编码颜色行数（不含 `#fff`/`#000`） | 1000 | 924 |
| 主要分布 | `shared/styles`、`OdapLayout.css`、`ontology`、`agent`、`ai-assistant` 等页面内联样式 | 同上，`shared/styles` 与 `OdapLayout.css` 已清零 |

清零路径（建议排入后续批次，逐页替换为 semantic token，不要一次性动 → 会踩到 AntD 覆盖优先级）：

1. `src/modules/shared/styles/*`、`OdapLayout.css`：**已完成**（另删除死代码 `colors.ts` —— 内含 `linear-gradient(135deg,#4F46E5,#8B5CF6)` 品牌渐变，全仓零引用）
2. `src/modules/wiki/*`、`src/routes/*`、`WorkspaceRail`、`ThemeColorPicker`、`Icon`：**已完成**
3. 剩余页面（`ontology` / `agent` / `ai-assistant` / `business` 等）逐模块替换，每模块单独 PR + 截图回归


---

## 6. 新增颜色的正确姿势

1. 判断属于哪一层：primitive（色阶）→ semantic（语义）→ component（组件插槽）
2. 只往**真源**加，然后同步镜像（第 1 节三步）
3. 业务代码只允许引用 semantic / component 层，**不允许**直接引用 `--odap-primitive-*`（图标/图表的极少数例外已在 `ThemeColorPicker` 中标注）
4. 强调色每屏 ≤2 处；新增语义色前先确认现有 `success/warn/danger/info` 不能表达
