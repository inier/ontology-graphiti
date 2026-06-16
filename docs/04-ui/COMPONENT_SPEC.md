# 组件规范详细说明

> **版本**: 1.0.0 | **日期**: 2026-04-26
> **状态**: 设计中

---

## 1. 进度展示组件 (ProgressTracker)

### 1.1 组件接口

```typescript
interface ProgressTrackerProps {
  stages: Stage[];
  currentStage: string;
  progress: number;           // 0-100
  estimatedTimeRemaining?: number; // 秒
  onStageClick?: (stage: Stage) => void;
}

interface Stage {
  id: string;
  name: string;
  status: 'pending' | 'in_progress' | 'completed' | 'error' | 'warning';
  startTime?: Date;
  endTime?: Date;
  errorMessage?: string;
}
```

### 1.2 视觉规格

| 元素 | 规格值 |
|------|--------|
| 组件高度 | 120px |
| 阶段标签宽度 | 自适应，最小100px |
| 阶段间间距 | 24px |
| 连接线宽度 | 2px |
| 连接线高度 | 2px |
| 状态图标大小 | 24px |
| 进度条高度 | 8px |
| 圆角 | 8px |

### 1.3 状态颜色映射

```typescript
const STAGE_COLORS = {
  pending: '#d9d9d9',       // 灰色
  in_progress: '#1890ff',   // 蓝色
  completed: '#52c41a',     // 绿色
  error: '#ff4d4f',         // 红色
  warning: '#faad14'        // 黄色
};
```

### 1.4 动画规格

| 动画 | 时长 | 缓动函数 |
|------|------|----------|
| 阶段切换 | 300ms | ease-out |
| 进度条更新 | 200ms | linear |
| 状态图标脉冲 | 1.5s | ease-in-out (循环) |
| 错误提示闪烁 | 0.5s | ease-in-out (循环) |

---

## 2. 原始数据展示组件 (SourceDataPanel)

### 2.1 组件接口

```typescript
interface SourceDataPanelProps {
  question: string;
  documents: Document[];
  searchResults: SearchResult[];
  onDocumentPreview?: (doc: Document) => void;
  onSearchResultClick?: (result: SearchResult) => void;
}

interface Document {
  id: string;
  name: string;
  relevance: number;  // 0-100
  preview?: string;
}

interface SearchResult {
  id: string;
  title: string;
  source: string;
  relevance: number;
  url?: string;
  snippet?: string;
}
```

### 2.2 布局规格

| 区域 | 高度 | 内边距 |
|------|------|--------|
| 问题区域 | auto | 16px |
| 文档列表 | flex: 1 | 16px |
| 搜索结果 | flex: 1 | 16px |

### 2.3 列表项规格

| 元素 | 字号 | 行高 | 间距 |
|------|------|------|------|
| 标题 | 14px | 1.5 | 8px |
| 描述 | 12px | 1.4 | 4px |
| 元信息 | 12px | 1.4 | 8px |

---

## 3. 转化过程展示组件 (TransformPanel)

### 3.1 组件接口

```typescript
interface TransformPanelProps {
  currentStage: Stage;
  stageDetails: StageDetail[];
}

interface StageDetail {
  stageId: string;
  messages: LogMessage[];
  progress: number;
  artifacts?: Artifact[];  // 产出物
}

interface LogMessage {
  id: string;
  timestamp: Date;
  level: 'info' | 'success' | 'warning' | 'error';
  content: string;
}

interface Artifact {
  type: 'text' | 'table' | 'image' | 'json';
  name: string;
  data: any;
}
```

### 3.2 日志显示规格

| 元素 | 规格 |
|------|------|
| 日志容器 | 最大高度400px，overflow-y: auto |
| 日志条目 | 高度动态，字号12px |
| 时间戳 | 字号11px，颜色#8c8c8c |
| 内容 | 字号12px，颜色#262626 |
| 级别图标 | info ℹ️, success ✅, warning ⚠️, error ❌ |

---

## 4. 本体定义展示组件 (OntologyPanel)

### 4.1 组件接口

```typescript
interface OntologyPanelProps {
  ontology: Ontology;
  onNodeClick?: (node: OntologyNode) => void;
  onNodeEdit?: (node: OntologyNode) => void;
  onRelationshipClick?: (rel: Relationship) => void;
}

interface Ontology {
  nodes: OntologyNode[];
  relationships: Relationship[];
}

interface OntologyNode {
  id: string;
  name: string;
  type: 'concept' | 'domain' | 'instance' | 'event';
  properties: Property[];
  propertyCount: number;
  relationshipCount: number;
}

interface Relationship {
  id: string;
  name: string;
  sourceId: string;
  targetId: string;
  type: string;
}
```

### 4.2 列表规格

| 元素 | 规格 |
|------|------|
| 表格头 | 高度40px，背景#fafafa |
| 表格行 | 高度48px，边框#d9d9d9 |
| 行悬停 | 背景#f5f5f5 |
| 操作按钮 | 字号12px，内边距4px 8px |

---

## 5. 版本管理组件 (VersionManager)

### 5.1 组件接口

```typescript
interface VersionManagerProps {
  versions: Version[];
  currentVersion: Version;
  onVersionSelect?: (version: Version) => void;
  onVersionCompare?: (v1: Version, v2: Version) => void;
  onVersionRollback?: (version: Version) => void;
}

interface Version {
  id: string;
  versionId: string;
  summary: string;
  createdAt: Date;
  status: 'completed' | 'failed' | 'rolling_back';
  duration: number;  // 秒
  entityCount: number;
  relationshipCount: number;
}
```

### 5.2 版本对比视图

| 元素 | 规格 |
|------|------|
| 对比容器 | 两栏布局，每栏50% |
| 版本标题 | 高度48px，背景#fafafa |
| 差异条目 | 高度32px，内边距8px |
| 新增 | 背景#f6ffed，左边框#52c41a 3px |
| 删除 | 背景#fff1f0，左边框#ff4d4f 3px |
| 修改 | 背景#fffbe6，左边框#faad14 3px |

---

## 6. 图谱画布组件 (GraphCanvas)

### 6.1 组件接口

```typescript
interface GraphCanvasProps {
  nodes: GraphNode[];
  relationships: GraphRelationship[];
  selectedNodeId?: string;
  selectedRelId?: string;
  layout?: 'force' | 'circular' | 'grid';
  onNodeClick?: (node: GraphNode, event: MouseEvent) => void;
  onNodeDoubleClick?: (node: GraphNode) => void;
  onNodeDrag?: (node: GraphNode, position: Position) => void;
  onRelClick?: (rel: GraphRelationship) => void;
  onZoom?: (scale: number) => void;
  onPan?: (offset: Position) => void;
}

interface GraphNode {
  id: string;
  name: string;
  type: 'concept' | 'domain' | 'instance' | 'event';
  x?: number;
  y?: number;
  fx?: number;  // 固定x
  fy?: number;  // 固定y
}

interface GraphRelationship {
  id: string;
  source: string;
  target: string;
  name: string;
  type: string;
}
```

### 6.2 力导向图参数

```typescript
const FORCE_CONFIG = {
  forceLink: {
    distance: 120,      // 关系线长度
    strength: 0.5       // 连接强度
  },
  forceManyBody: {
    strength: -300,     // 节点间斥力
    distanceMax: 500    // 最大斥力距离
  },
  forceCenter: {
    strength: 0.1       // 居中力
  },
  forceCollide: {
    radius: 40,          // 碰撞半径
    strength: 0.8       // 碰撞强度
  }
};
```

### 6.3 节点大小计算

```typescript
function calculateNodeRadius(degree: number): number {
  const minRadius = 20;
  const maxRadius = 50;
  const scale = Math.min(degree / 10, 1);
  return minRadius + (maxRadius - minRadius) * scale;
}
```

### 6.4 交互反馈

| 交互 | 反馈 |
|------|------|
| 节点悬停 | scale(1.1)，shadow增强，显示tooltip |
| 节点选中 | stroke-width: 3px，stroke: #1890ff |
| 关系悬停 | stroke-width: 3px，opacity: 1 |
| 关系选中 | stroke-width: 4px，stroke: #1890ff，箭头放大 |
| 拖拽中 | 节点opacity: 0.8，cursor: grabbing |
| 缩放中 | cursor: zoom-in/out |

---

## 7. 节点详情面板 (NodeDetailPanel)

### 7.1 组件接口

```typescript
interface NodeDetailPanelProps {
  node: OntologyNode | null;
  relationships: Relationship[];
  onClose?: () => void;
  onEdit?: (node: OntologyNode) => void;
  onDelete?: (node: OntologyNode) => void;
}
```

### 7.2 面板规格

| 元素 | 规格 |
|------|------|
| 面板宽度 | 320px (固定) |
| 头部 | 高度64px，显示类型图标和名称 |
| 属性区 | 折叠面板，可展开/收起 |
| 关系区 | 折叠面板，显示关系列表 |
| 历史区 | 时间线形式展示节点变更历史 |

---

## 8. 通用组件样式

### 8.1 按钮样式

```css
.btn {
  height: 32px;
  padding: 0 16px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-primary {
  background: #1890ff;
  color: #fff;
  border: none;
}

.btn-primary:hover {
  background: #40a9ff;
}

.btn-default {
  background: #fff;
  color: #262626;
  border: 1px solid #d9d9d9;
}

.btn-default:hover {
  color: #1890ff;
  border-color: #1890ff;
}
```

### 8.2 卡片样式

```css
.card {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  padding: 16px;
}

.card-header {
  font-size: 16px;
  font-weight: 500;
  color: #262626;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #d9d9d9;
}
```

### 8.3 折叠面板

```css
.collapse-item {
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  margin-bottom: 8px;
  overflow: hidden;
}

.collapse-header {
  height: 40px;
  padding: 0 12px;
  background: #fafafa;
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
}

.collapse-content {
  padding: 12px;
  background: #fff;
}
```

---

## 9. 状态指示器

### 9.1 加载状态

#### 9.1.1 全局 Loading（GlobalLoading）

全局 Loading 必须在 Layout 层级复用，浮于页面内容之上，不占用文档流空间。

**规则：**
- 全局 Loading 必须使用 `GlobalLoading` 组件（`shared/components/GlobalLoading.tsx`），由 `useGlobalLoading` store 控制
- 禁止在页面/组件中自行创建 `position: fixed` 的全屏 loading 遮罩
- `GlobalLoading` 挂载在 `AppLayout` 的 Content 区域内，通过 `position: absolute` + `inset: 0` 覆盖内容
- 任何需要页面级 loading 的场景，统一调用 `useGlobalLoading().show(tip, delay)` / `hide()`

**适用场景：**
- 页面首次加载（如工作空间初始化、本体列表加载）
- 全局性操作（如工作空间切换后的数据刷新）

**不适用场景（使用局部 Spin）：**
- 组件内局部操作（搜索、查询、表单提交）→ 用 `<Spin spinning={...}>`
- Table 翻页 → 用 Table `loading` prop
- Drawer/Modal 内操作 → 用局部 `<OverlaySpin>`

**组件接口：**

```typescript
// Store: useGlobalLoading
interface GlobalLoadingState {
  visible: boolean;       // 是否显示
  tip: string;            // 提示文字，默认 "加载中..."
  delay: number;          // 延迟显示(ms)，避免闪烁，默认 200ms
  show: (tip?: string, delay?: number) => void;
  hide: () => void;
}

// 使用示例
const { show, hide } = useGlobalLoading();
show('正在加载数据...', 0);  // delay=0 立即显示
// ...异步操作
hide();
```

**视觉规格：**

| 属性 | 值 |
|------|-----|
| 定位 | `position: absolute; inset: 0`（相对于 Layout Content） |
| 层级 | `z-index: 1000` |
| 遮罩 | `background: rgba(255, 255, 255, 0.6)` |
| 模糊 | `backdrop-filter: blur(2px)` |
| 交互 | `pointer-events: auto`（阻止底层操作） |
| 旋转器 | Ant Design `<Spin size="large" tip={tip} delay={delay}>` |

#### 9.1.2 局部 OverlaySpin

组件内浮层 loading，不占布局空间：

```typescript
interface OverlaySpinProps {
  spinning: boolean;
  tip?: string;
  children?: React.ReactNode;
  minHeight?: number;  // 无 children 时容器最小高度，默认 120px
}
```

#### 9.1.3 骨架屏

```css
.skeleton {
  background: linear-gradient(90deg, #f0f0f0 25%, #e8e8e8 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
}

@keyframes skeleton-loading {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
```

### 9.2 空状态

```typescript
const EMPTY_STATE = {
  image: '/images/empty-state.svg',
  title: '暂无数据',
  description: '请先提交问题以开始本体构建'
};
```

### 9.3 错误状态

```typescript
const ERROR_STATE = {
  icon: '❌',
  title: '处理失败',
  description: '请稍后重试或联系管理员',
  actionText: '重试'
};
```

---

## 10. 响应式断点

```css
/* 桌面大屏 */
@media (min-width: 1440px) {
  .main-layout { max-width: 1600px; }
  .three-column { grid-template-columns: 280px 1fr 320px; }
}

/* 桌面 */
@media (max-width: 1439px) {
  .three-column { grid-template-columns: 240px 1fr 280px; }
}

/* 平板横屏 */
@media (max-width: 1199px) {
  .three-column { grid-template-columns: 1fr 1fr; }
  .left-panel { display: none; }  /* 折叠为抽屉 */
}

/* 平板竖屏 */
@media (max-width: 991px) {
  .three-column { grid-template-columns: 1fr; }
  .layout-container { flex-direction: column; }
}

/* 移动端 */
@media (max-width: 767px) {
  .header { height: 48px; }
  .bottom-tab { display: flex; }
}
```
