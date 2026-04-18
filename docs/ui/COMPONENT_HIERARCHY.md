# ODAP 前端组件分级管理规范

> **版本**: 1.0.0 | **日期**: 2026-04-17

---

## 1. 组件分级体系

### 1.1 组件分级定义

| 级别 | 定义 | 原则 |
|------|------|------|
| **L1 原子组件** | 最基本的 UI 元素 | 不可再分，可复用性最高 |
| **L2 分子组件** | 原子组件的组合 | 独立功能，可复用 |
| **L3 组织组件** | 业务组件的组合 | 特定业务场景 |
| **L4 模板组件** | 页面级布局组件 | 页面结构，可配置 |
| **L5 页面组件** | 完整页面 | 路由级组件 |

---

## 2. 组件目录结构

```
frontend/src/
├── components/                    # L1-L3 组件
│   ├── atoms/                    # L1 原子组件
│   │   ├── Button/
│   │   │   ├── index.ts
│   │   │   ├── Button.tsx
│   │   │   └── Button.module.css
│   │   ├── Input/
│   │   ├── Select/
│   │   ├── Badge/
│   │   └── Icon/
│   │
│   ├── molecules/               # L2 分子组件
│   │   ├── SearchBar/
│   │   ├── DataTable/
│   │   ├── StatCard/
│   │   └── FilterPanel/
│   │
│   ├── organisms/               # L3 组织组件
│   │   ├── GraphCanvas/
│   │   ├── MapView/
│   │   ├── TimelineView/
│   │   ├── EntityPanel/
│   │   └── SimulatorConsole/
│   │
│   └── templates/              # L4 模板组件
│       ├── PageHeader/
│       ├── DataGrid/
│       └── DetailLayout/
│
├── pages/                       # L5 页面组件
│   ├── Dashboard/
│   ├── OntologyGraph/
│   ├── Timeline/
│   ├── SituationMap/
│   ├── Simulator/
│   ├── IngestPanel/
│   └── VersionHistory/
│
├── layouts/                     # L4 布局组件
│   ├── AppLayout/
│   ├── MobileLayout/
│   └── BlankLayout/
│
├── hooks/                       # 自定义 Hooks
│   ├── useBreakpoint.ts
│   ├── useScenario.ts
│   └── useGraph.ts
│
├── utils/                       # 工具函数
│   ├── responsive.ts
│   ├── i18n.ts
│   └── formatters.ts
│
├── locales/                    # 国际化资源
│   ├── zh-CN/
│   │   └── messages.json
│   └── en-US/
│       └── messages.json
│
└── styles/                     # 全局样式
    ├── variables.css
    ├── global.css
    └── theme.ts
```

---

## 3. 组件分级规范

### 3.1 L1 原子组件（Atoms）

**原则**：
- 单一职责，只做一件事
- 无业务逻辑，只有展示逻辑
- 接收 props 控制外观和行为
- 可在任意场景复用

**示例**：
```tsx
// atoms/Button/Button.tsx
interface ButtonProps {
  variant: 'primary' | 'secondary' | 'ghost';
  size: 'small' | 'medium' | 'large';
  children: React.ReactNode;
  onClick?: () => void;
}
```

### 3.2 L2 分子组件（Molecules）

**原则**：
- 由 L1 组件组合
- 有独立的业务功能
- 可配置，行为相对固定
- 可在多个页面复用

**示例**：
```tsx
// molecules/SearchBar/SearchBar.tsx
interface SearchBarProps {
  placeholder?: string;
  onSearch: (value: string) => void;
  filters?: FilterConfig[];
}
```

### 3.3 L3 组织组件（Organisms）

**原则**：
- 由 L1/L2 组件组合
- 完整的业务功能模块
- 有较强的业务关联性
- 通常是页面的核心功能区

**示例**：
```tsx
// organisms/GraphCanvas/GraphCanvas.tsx
interface GraphCanvasProps {
  scenarioId: string;
  onNodeClick?: (node: GraphNode) => void;
  onRefresh?: () => void;
}
```

### 3.4 L4 模板组件（Templates）

**原则**：
- 页面级布局组件
- 定义页面结构，不关心业务
- 可配置 sections/regions
- 跨业务复用

**示例**：
```tsx
// templates/PageLayout/PageLayout.tsx
interface PageLayoutProps {
  header?: React.ReactNode;
  sidebar?: React.ReactNode;
  content: React.ReactNode;
  footer?: React.ReactNode;
}
```

### 3.5 L5 页面组件（Pages）

**原则**：
- 路由级组件
- 组装 L1-L4 组件
- 包含页面业务逻辑
- 连接 Redux/Context

**示例**：
```tsx
// pages/Dashboard/Dashboard.tsx
// 使用 useScenario 获取全局状态
// 调用 API 获取数据
// 组装各种组件
```

---

## 4. 组件命名规范

| 类型 | 命名方式 | 示例 |
|------|----------|------|
| 目录 | PascalCase | `GraphCanvas/` |
| 组件文件 | PascalCase | `GraphCanvas.tsx` |
| 样式文件 | PascalCase.module.css | `GraphCanvas.module.css` |
| 测试文件 | PascalCase.test.tsx | `GraphCanvas.test.tsx` |
| Props 类型 | {ComponentName}Props | `GraphCanvasProps` |
| 样式类 | BEM 风格 | `graph-canvas__header--active` |

---

## 5. 组件开发规范

### 5.1 Props 定义

```tsx
interface ComponentNameProps {
  // 必选属性
  requiredProp: string;

  // 可选属性
  optionalProp?: number;

  // 回调函数
  onAction?: () => void;

  // 样式覆盖
  className?: string;
  style?: React.CSSProperties;
}
```

### 5.2 默认值处理

```tsx
const Component = ({ variant = 'primary', size = 'medium' }: ComponentProps) => {
  // ...
};
```

### 5.3 样式隔离

```tsx
import styles from './ComponentName.module.css';

export function Component({ className }: ComponentProps) {
  return (
    <div className={`${styles.container} ${className || ''}`}>
      {/* ... */}
    </div>
  );
}
```

---

## 6. 相关文档

- [移动优先设计规范](../ui/MOBILE_FIRST_DESIGN.md)
- [响应式与国际化 ADR](../adr/ADR-037_frontend_mobile_first_i18n.md)
