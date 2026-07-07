# ODAP v2 — UI Design System

> **设计版本**: v2.0  
> **设计方向**: 科技现代（Tech-Modern）  
> **核心理念**: 蓝紫渐变 · 玻璃态 · 微交互 · 暗色双主题  
> **设计日期**: 2026-06-15  
> **UI Designer**: ODAP Design Team

---

## 目录

1. [设计理念](#1-设计理念)
2. [Design Token 体系](#2-design-token-体系)
3. [组件库规格](#3-组件库规格)
4. [布局与响应式系统](#4-布局与响应式系统)
5. [交互与动效规范](#5-交互与动效规范)
6. [可访问性标准](#6-可访问性标准)
7. [开发者交付规范](#7-开发者交付规范)

---

## 1. 设计理念

### 1.1 核心设计原则

| 原则 | 描述 | 设计体现 |
|------|------|----------|
| **深度感知** | 通过阴影、模糊、透明度创造空间层次 | 玻璃态面板、多层阴影系统、悬浮抬升 |
| **流动连贯** | 蓝紫渐变贯穿全平台，统一视觉语言 | 渐变色按钮、选中态、图表配色、图标系统 |
| **即时反馈** | 每个操作都有细腻的视觉响应 | 150ms 过渡动画、hover 抬升、ripple 波纹 |
| **克制表达** | 减少装饰元素，聚焦内容和数据 | 大量留白、单色图标、无衬线字体 |
| **暗色优先** | 深色模式作为一等公民设计 | 完整的暗色 Token 体系、自动跟随系统 |

### 1.2 视觉风格关键词

```
科技感 ── 深色背景 + 蓝紫渐变 + 发光边框
轻盈感 ── 玻璃态模糊 + 半透明表面 + 细腻阴影
精准感 ── 等宽数字 + 对齐网格 + 清晰层级
现代感 ── 圆角卡片 + 微交互 + 流畅过渡
专业感 ── Inter 字体 + 克制用色 + 信息密度适中
```

### 1.3 与 v1 的核心变化

| 维度 | v1 (当前) | v2 (升级) |
|------|-----------|-----------|
| 主色调 | Ant Design Blue #1677ff | Indigo #4F46E5 → Violet 渐变 |
| 侧边栏 | 纯黑 #001529 | 深灰半透明 + 玻璃态 |
| 卡片 | 纯白 + 标准阴影 | 玻璃态 + 悬浮抬升 |
| 圆角 | 2px / 8px 混用 | 统一的 8px-12px-16px 体系 |
| 字体 | 系统默认 | Inter 定制 + 等宽数字 |
| 暗色模式 | 基础适配 | 完整暗色 Token + 独立设计 |
| 微交互 | 基本无 | 全面的 hover/active/focus 状态 |

---

## 2. Design Token 体系

### 2.1 色彩系统

#### 主色系 — Indigo（靛蓝）

| Token | 色值 | 用途 |
|-------|------|------|
| `--color-primary-50` | `#EEF2FF` | 最浅背景、选中态底色 |
| `--color-primary-100` | `#E0E7FF` | 标签背景、hover 态底色 |
| `--color-primary-200` | `#C7D2FE` | 次要背景、禁用态 |
| `--color-primary-300` | `#A5B4FC` | 边框高亮、进度条 |
| `--color-primary-400` | `#818CF8` | 次要按钮、链接文字 |
| `--color-primary-500` | `#6366F1` | **主按钮、主图标、选中态（默认）** |
| `--color-primary-600` | `#4F46E5` | 主按钮 hover、强调色 |
| `--color-primary-700` | `#4338CA` | 主按钮 active、深色强调 |
| `--color-primary-800` | `#3730A3` | 深色背景上的文字 |
| `--color-primary-900` | `#312E81` | 最深色、暗色文字 |

#### 强调色系 — Violet（紫罗兰）

| Token | 色值 | 用途 |
|-------|------|------|
| `--color-accent-50` | `#F5F3FF` | 高亮背景 |
| `--color-accent-100` | `#EDE9FE` | 标签背景 |
| `--color-accent-300` | `#C4B5FD` | 边框高亮 |
| `--color-accent-500` | `#8B5CF6` | **强调按钮、特殊标记** |
| `--color-accent-700` | `#6D28D9` | 强调 hover |

#### 语义色彩

| Token | 色值 | 含义 |
|-------|------|------|
| `--color-success` | `#10B981` | 成功、通过、完成 |
| `--color-warning` | `#F59E0B` | 警告、注意、待处理 |
| `--color-error` | `#EF4444` | 错误、失败、危险 |
| `--color-info` | `#06B6D4` | 信息、提示、帮助 |

#### 中性色系

| Token | 色值 | 用途（Light） |
|-------|------|---------------|
| `--color-gray-50` | `#F9FAFB` | 页面背景 |
| `--color-gray-100` | `#F3F4F6` | 卡片背景、次要表面 |
| `--color-gray-200` | `#E5E7EB` | 分割线、边框 |
| `--color-gray-300` | `#D1D5DB` | 禁用态边框 |
| `--color-gray-400` | `#9CA3AF` | 占位文字 |
| `--color-gray-500` | `#6B7280` | 次要文字 |
| `--color-gray-700` | `#374151` | 正文文字 |
| `--color-gray-900` | `#111827` | 标题、强调文字 |

#### 渐变色系

```css
/* 品牌渐变 — 用于 Hero 区域、大按钮、图表 */
--gradient-brand: linear-gradient(135deg, #4F46E5 0%, #8B5CF6 100%);
--gradient-brand-hover: linear-gradient(135deg, #4338CA 0%, #7C3AED 100%);

/* 玻璃态渐变 — 用于 Glass Panel */
--gradient-glass: linear-gradient(135deg, rgba(255,255,255,0.9) 0%, rgba(255,255,255,0.7) 100%);
--gradient-glass-dark: linear-gradient(135deg, rgba(30,30,40,0.9) 0%, rgba(30,30,40,0.7) 100%);

/* 发光渐变 — 用于图表数据系列 */
--gradient-glow-blue: linear-gradient(180deg, #6366F1 0%, #312E81 100%);
--gradient-glow-purple: linear-gradient(180deg, #8B5CF6 0%, #5B21B6 100%);
```

#### 暗色主题

```css
[data-theme="dark"] {
  --color-bg-primary: #0F0F1A;      /* 最深背景 */
  --color-bg-secondary: #1A1A2E;    /* 卡片背景 */
  --color-bg-tertiary: #252540;     /* 悬浮表面 */
  --color-bg-glass: rgba(26,26,46,0.8); /* 玻璃态背景 */

  --color-text-primary: #F3F4F6;
  --color-text-secondary: #9CA3AF;
  --color-text-tertiary: #6B7280;

  --color-border-primary: #2D2D4A;
  --color-border-secondary: #1F1F38;

  /* 暗色下主色微调 — 更亮以保持对比度 */
  --color-primary-500: #818CF8;
  --color-primary-600: #6366F1;
  --color-accent-500: #A78BFA;
}
```

### 2.2 排版体系

#### 字体族

```css
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
--font-display: 'Inter', system-ui, sans-serif;  /* 大标题专用 */
```

#### 字号层级（Major Third 音阶：1.25）

| Token | 字号 | 行高 | 字重 | 用途 |
|-------|------|------|------|------|
| `--text-xs` | 11px | 1.4 | 400 | 极小标注、徽标数字 |
| `--text-sm` | 12px | 1.5 | 400 | 辅助说明、标签、时间戳 |
| `--text-base` | 14px | 1.6 | 400 | 正文、表格内容、菜单项 |
| `--text-lg` | 16px | 1.5 | 500 | 卡片标题、强调段落 |
| `--text-xl` | 20px | 1.4 | 600 | 页面小标题、Modal 标题 |
| `--text-2xl` | 24px | 1.3 | 600 | 页面主标题 |
| `--text-3xl` | 32px | 1.2 | 700 | Hero 标题、Landing |
| `--text-4xl` | 40px | 1.1 | 700 | 超大标题（仅 Landing） |

#### 字重对照

| Token | 值 | 使用场景 |
|-------|-----|----------|
| `--font-normal` | 400 | 正文、标签、辅助文字 |
| `--font-medium` | 500 | 卡片标题、按钮、菜单 |
| `--font-semibold` | 600 | 页面标题、Modal 标题 |
| `--font-bold` | 700 | Hero 标题、数字指标 |

### 2.3 间距系统（4px 基准）

| Token | 值 | 用途 |
|-------|-----|------|
| `--space-0` | 0 | 无边距 |
| `--space-1` | 4px | 图标间距、密排元素 |
| `--space-2` | 8px | 表单标签间距、小间距 |
| `--space-3` | 12px | 卡片内间距、按钮内边距 |
| `--space-4` | 16px | **默认间距**、卡片 padding |
| `--space-5` | 20px | 段落间距 |
| `--space-6` | 24px | **页面区块间距** |
| `--space-8` | 32px | 大区块间距、页面 padding |
| `--space-10` | 40px | 页面内主要分隔 |
| `--space-12` | 48px | 页面间分隔 |
| `--space-16` | 64px | Hero 区域间距 |

### 2.4 圆角系统

| Token | 值 | 用途 |
|-------|-----|------|
| `--radius-sm` | 6px | 小按钮、输入框、标签、徽标 |
| `--radius-md` | 8px | **默认圆角**、卡片、面板、下拉菜单 |
| `--radius-lg` | 12px | 大卡片、Modal、抽屉 |
| `--radius-xl` | 16px | 特大容器、图表容器 |
| `--radius-full` | 9999px | 药丸按钮、头像、圆形徽标 |

### 2.5 阴影系统

```css
/* 基础阴影 — 微弱抬升 */
--shadow-xs: 0 1px 2px rgba(0,0,0,0.04);

/* 卡片阴影 — 默认表面 */
--shadow-sm: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);

/* 悬浮阴影 — hover 态 */
--shadow-md: 0 4px 6px -1px rgba(0,0,0,0.06), 0 2px 4px -2px rgba(0,0,0,0.05);

/* 弹出阴影 — Dropdown/Modal */
--shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -4px rgba(0,0,0,0.04);

/* 模态阴影 — Modal/抽屉 */
--shadow-xl: 0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.05);

/* 发光阴影 — 用于主按钮、品牌元素 */
--shadow-glow-sm: 0 0 0 3px rgba(99,102,241,0.15);
--shadow-glow-md: 0 0 0 4px rgba(99,102,241,0.2);
--shadow-glow-lg: 0 4px 14px rgba(99,102,241,0.25);
```

### 2.6 动效 Token

```css
--ease-out: cubic-bezier(0.16, 1, 0.3, 1);     /* 标准缓出 */
--ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);  /* 标准缓入缓出 */
--ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1); /* 弹性 */

--duration-instant: 100ms;   /* 即时反馈 */
--duration-fast: 150ms;      /* 快速过渡 — hover、focus */
--duration-normal: 250ms;    /* 标准过渡 — 展开、切换 */
--duration-slow: 400ms;      /* 慢速过渡 — 页面切换、Modal */
--duration-very-slow: 600ms; /* 入场动画 */
```

### 2.7 Z-Index 层级

```css
--z-base: 0;          /* 默认内容 */
--z-dropdown: 1000;   /* 下拉菜单 */
--z-sticky: 1020;     /* 吸顶元素 */
--z-overlay: 1040;    /* 遮罩层 */
--z-modal: 1060;      /* 模态框 */
--z-popover: 1070;    /* 弹出提示 */
--z-tooltip: 1080;    /* 工具提示 */
--z-toast: 1100;      /* 全局通知 */
```

---

## 3. 组件库规格

### 3.1 按钮 Button

#### 变体

| 变体 | 背景 | 文字色 | 边框 | 使用场景 |
|------|------|--------|------|----------|
| Primary | `--gradient-brand` | `#FFF` | none | 主要操作 |
| Secondary | `--color-primary-50` | `--color-primary-700` | `--color-primary-200` | 次要操作 |
| Outline | transparent | `--color-primary-600` | `--color-primary-300` | 三级操作 |
| Ghost | transparent | `--color-gray-500` | none | 最低优先级 |
| Danger | `--color-error` | `#FFF` | none | 危险操作 |

#### 尺寸

| 尺寸 | 高度 | Padding X | 字号 | 圆角 | 最小宽度 |
|------|------|-----------|------|------|----------|
| xs | 28px | 10px | 12px | 6px | 56px |
| sm | 32px | 14px | 13px | 6px | 64px |
| md | 36px | 18px | 14px | 8px | 80px |
| lg | 42px | 22px | 15px | 8px | 100px |
| xl | 48px | 28px | 16px | 10px | 120px |

#### 状态规格

```css
/* Primary 按钮状态 */
.btn-primary {
  background: var(--gradient-brand);
  box-shadow: var(--shadow-sm);
  transition: all var(--duration-fast) var(--ease-out);
}
.btn-primary:hover {
  background: var(--gradient-brand-hover);
  box-shadow: var(--shadow-md), var(--shadow-glow-sm);
  transform: translateY(-1px);
}
.btn-primary:active {
  transform: translateY(0);
  box-shadow: var(--shadow-sm);
}
.btn-primary:focus-visible {
  outline: 2px solid var(--color-primary-500);
  outline-offset: 2px;
}
.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}
```

### 3.2 输入框 Input

```css
.input {
  height: 36px;
  padding: 0 12px;
  border: 1px solid var(--color-gray-200);
  border-radius: var(--radius-sm);
  background: var(--color-bg-primary);
  font-size: var(--text-base);
  color: var(--color-text-primary);
  transition: all var(--duration-fast) var(--ease-out);
}
.input:hover { border-color: var(--color-gray-300); }
.input:focus {
  outline: none;
  border-color: var(--color-primary-500);
  box-shadow: 0 0 0 3px rgba(99,102,241,0.1);
}
.input::placeholder { color: var(--color-gray-400); }
.input.error {
  border-color: var(--color-error);
  box-shadow: 0 0 0 3px rgba(239,68,68,0.1);
}
```

### 3.3 卡片 Card

#### Glass Card（推荐默认）

```css
.card-glass {
  background: rgba(255,255,255,0.8);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255,255,255,0.3);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  transition: all var(--duration-normal) var(--ease-out);
}
.card-glass:hover {
  box-shadow: var(--shadow-md);
  border-color: rgba(99,102,241,0.2);
  transform: translateY(-1px);
}
```

#### 深色 Glass Card

```css
[data-theme="dark"] .card-glass {
  background: rgba(26,26,46,0.8);
  border-color: rgba(255,255,255,0.06);
}
[data-theme="dark"] .card-glass:hover {
  border-color: rgba(129,140,248,0.3);
}
```

#### Solid Card（数据密集型场景）

```css
.card-solid {
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border-primary);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-xs);
}
```

### 3.4 数据表格 Table

| 元素 | 规格 |
|------|------|
| 表头高度 | 40px |
| 行高度 | 44px（默认）、36px（紧凑） |
| 表头背景 | `--color-gray-50` |
| 表头字重 | `--font-medium` (500) |
| 行 hover 背景 | `--color-primary-50` |
| 选中行背景 | `--color-primary-50` + 左边框 `--color-primary-500` |
| 分割线 | `1px solid var(--color-gray-100)` |
| 圆角 | `--radius-md` (8px) |
| 阴影 | `--shadow-sm` |

### 3.5 导航 Navigation

#### 一级侧边栏（深色固定）

| 属性 | Light | Dark |
|------|-------|------|
| 宽度 | 64px（收起）/ 200px（展开） | 同 |
| 背景 | `linear-gradient(180deg, #1E1B4B, #0F0F1A)` | 同（深色始终不变） |
| 图标色 | `rgba(255,255,255,0.65)` | 同 |
| 选中态 | `rgba(99,102,241,0.3)` + 左边框 3px `#818CF8` | 同 |
| 文字色 | `rgba(255,255,255,0.85)` | 同 |
| Logo 区域 | 渐变品牌色 `--gradient-brand` | 同 |

#### 二级子菜单（白色/深色面板）

| 属性 | Light | Dark |
|------|-------|------|
| 宽度 | 200px | 同 |
| 背景 | `rgba(255,255,255,0.95)` | `rgba(26,26,46,0.95)` |
| 选中态 | `--color-primary-50` | `rgba(99,102,241,0.15)` |
| 边框 | `1px solid var(--color-gray-100)` | `1px solid var(--color-border-primary)` |

### 3.6 图表配色（Chart.js / ECharts）

```
数据系列颜色（最多8个）：
  #6366F1  Indigo   — 主数据
  #8B5CF6  Violet   — 对比数据
  #06B6D4  Cyan     — 辅助数据
  #10B981  Emerald  — 正向数据
  #F59E0B  Amber    — 警示数据
  #EF4444  Red      — 异常数据
  #EC4899  Pink     — 特殊标注
  #6B7280  Gray     — 背景/参考线
```

### 3.7 状态徽标 Badge

```css
.badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  gap: 4px;
}
```

---

## 4. 布局与响应式系统

### 4.1 核心布局：三栏式

```
┌──────────┬────────────┬──────────────────────────┬───────────┐
│ Primary  │ Secondary  │     Content Area         │  Right    │
│ Sidebar  │ Sidebar    │                          │  Panel    │
│          │            │                          │           │
│ 64-200px │  200px     │    flex: 1               │  0-320px  │
│  dark    │  light     │    scroll                │  overlay  │
│  fixed   │  fixed     │                          │  fixed    │
└──────────┴────────────┴──────────────────────────┴───────────┘
```

### 4.2 页面模板

| 模板 | 用途 | 结构 |
|------|------|------|
| **Dashboard** | 概览仪表盘 | 顶部统计卡片行 + 图表网格 |
| **Master-Detail** | 列表-详情 | 左侧列表（320px）+ 右侧详情 |
| **Full Canvas** | 图谱/蓝图 | 全宽工具栏 + 全高画布 |
| **Form Page** | 表单编辑 | 居中表单（max-w: 720px） |
| **Chat Panel** | 对话界面 | 消息列表 + 底部输入框 |

### 4.3 响应式断点

| 断点 | 最小宽度 | 布局策略 |
|------|----------|----------|
| `xs` | 0 | 单列，侧边栏隐藏为抽屉 |
| `sm` | 640px | 双列网格，侧边栏折叠 |
| `md` | 768px | 侧边栏可选展开 |
| `lg` | 1024px | **默认布局**，完整三栏 |
| `xl` | 1280px | 内容区最大宽度 1200px |
| `2xl` | 1536px | 内容区最大宽度 1400px |

### 4.4 内容区最大宽度

```css
.content-container {
  max-width: 1200px;  /* lg 及以上 */
  margin: 0 auto;
  padding: 0 var(--space-6);
}

@media (min-width: 1536px) {
  .content-container { max-width: 1400px; }
}
```

---

## 5. 交互与动效规范

### 5.1 微交互清单

| 交互 | 效果 | 时长 | 缓动 |
|------|------|------|------|
| 按钮 hover | 上浮 1px + 阴影加深 + 发光 | 150ms | ease-out |
| 按钮 active | 下沉归位 | 100ms | ease-out |
| 卡片 hover | 上浮 2px + 阴影加深 | 250ms | ease-out |
| 输入框 focus | 边框变色 + 外发光 | 150ms | ease-out |
| 菜单展开 | 从上方滑入 + 透明度 | 200ms | ease-out |
| Modal 打开 | 缩放 0.95→1 + 透明度 | 250ms | spring |
| 页面切换 | 透明度过渡 | 200ms | ease-in-out |
| 加载骨架屏 | 从左到右 shimmer | 1.5s | linear infinite |
| Toast 通知 | 从右侧滑入 | 300ms | spring |
| 数字跳动 | count-up 动画 | 600ms | ease-out |

### 5.2 Glass Morphism 标准

```css
/* 玻璃态面板 — 标准配方 */
.glass-panel {
  background: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: var(--radius-lg);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.04);
}

/* 暗色玻璃态 */
[data-theme="dark"] .glass-panel {
  background: rgba(15, 15, 26, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.06);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}
```

### 5.3 页面转场

```css
/* 路由切换动画 */
.page-enter {
  opacity: 0;
  transform: translateY(8px);
}
.page-enter-active {
  opacity: 1;
  transform: translateY(0);
  transition: all 250ms var(--ease-out);
}
.page-exit {
  opacity: 1;
}
.page-exit-active {
  opacity: 0;
  transition: all 150ms var(--ease-in-out);
}
```

---

## 6. 可访问性标准

### 6.1 WCAG AA 色彩对比度

| 元素 | 要求 | 验证 |
|------|------|------|
| 正文（14px） | ≥ 4.5:1 | `#374151` on `#FFF` = 6.5:1 ✅ |
| 大文字（≥18px） | ≥ 3:1 | `#111827` on `#FFF` = 16.9:1 ✅ |
| 主按钮文字 | ≥ 4.5:1 | `#FFF` on `#4F46E5` = 7.1:1 ✅ |
| 暗色正文 | ≥ 4.5:1 | `#F3F4F6` on `#0F0F1A` = 13.2:1 ✅ |

### 6.2 键盘导航

- 所有交互元素可 Tab 聚焦
- Tab 顺序遵循视觉布局
- `focus-visible` 提供 2px + 2px offset 的蓝色轮廓
- Enter/Space 激活按钮，Escape 关闭弹窗
- 箭头键导航菜单和列表

### 6.3 屏幕阅读器

- 语义化 HTML 标签（`<nav>`, `<main>`, `<aside>`）
- 图标提供 `aria-label` 或 `aria-hidden="true"`
- 动态内容使用 `aria-live` 区域
- Modal 打开时 focus trap + `aria-modal="true"`

### 6.4 其他

- 触摸目标最小 44×44px（WCAG 2.5.5）
- 支持 `prefers-reduced-motion` 关闭动画
- 支持浏览器缩放至 200% 不破坏布局
- 表单错误使用颜色 + 图标 + 文字三重提示

---

## 7. 开发者交付规范

### 7.1 CSS 变量命名规则

```
格式: --{category}-{property}-{variant}

示例:
  --color-primary-500      → 颜色 / 主色 / 500 深度
  --text-lg                → 字号 / 大
  --space-4                → 间距 / 16px
  --radius-md              → 圆角 / 中等
  --shadow-glow-sm         → 阴影 / 发光 / 小
  --duration-fast          → 时长 / 快
  --z-modal                → 层级 / 模态
```

### 7.2 组件文件结构

```
components/
├── atoms/
│   ├── Button/
│   │   ├── Button.tsx
│   │   ├── Button.module.css
│   │   ├── Button.test.tsx
│   │   └── index.ts
│   └── Input/...
├── molecules/
│   ├── SearchBar/...
│   ├── FormField/...
│   └── StatCard/...
├── organisms/
│   ├── DataTable/...
│   ├── ChatPanel/...
│   └── TopBar/...
└── templates/
    ├── DashboardLayout/...
    ├── MasterDetail/...
    └── FullCanvas/...
```

### 7.3 设计 QA 检查清单

- [ ] 颜色是否符合 Token 体系（非硬编码 hex）
- [ ] 间距是否使用 `--space-*` 变量
- [ ] 字体/字号是否使用 `--text-*` 变量
- [ ] hover/active/focus 三种状态是否完整
- [ ] 暗色模式是否完全适配
- [ ] 响应式断点是否需要调整
- [ ] 可访问性（对比度、键盘、aria）是否通过
- [ ] 动画是否使用 `--duration-*` 和 `--ease-*` 变量

---

## 附录

### A. 图标系统

使用 `@ant-design/icons`（与 Ant Design 6 兼容），推荐图标集：

- 导航: `AppstoreOutlined`, `ApartmentOutlined`, `RobotOutlined`, `ThunderboltOutlined`
- 操作: `PlusOutlined`, `EditOutlined`, `DeleteOutlined`, `SearchOutlined`
- 状态: `CheckCircleOutlined`, `CloseCircleOutlined`, `ExclamationCircleOutlined`

### B. 实现优先级

```
Phase 1 (核心) ── Design Token · 按钮 · 输入框 · 卡片 · 布局框架
Phase 2 (导航) ── 侧边栏 · 顶栏 · 面包屑 · 标签页
Phase 3 (数据) ── 表格 · 图表 · 筛选器 · 分页
Phase 4 (反馈) ── Modal · Toast · Tooltip · 骨架屏
Phase 5 (动效) ── 页面转场 · 微交互 · 加载动画
```

---

> **设计系统版本**: v2.0  
> **最后更新**: 2026-06-15  
> **下一步**: 基于此规范创建可交互 HTML 原型
