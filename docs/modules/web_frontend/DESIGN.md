# Web 前端模块 (Web Frontend) - 设计文档

> **模块 ID**: M-17 | **优先级**: P0 | **相关 ADR**: ADR-033
> **版本**: 2.0.0 | **日期**: 2026-04-19 | **架构层**: L6 用户交互层

---

## 1. 模块概述

### 1.1 模块定位

Web 前端是 ODAP 平台的**用户交互界面**，提供全流程可视化操作能力：从本体建模、知识图谱浏览、智能问答、模拟推演到审计溯源。它不是简单的数据展示层，而是承载平台核心交互逻辑的富客户端。

### 1.2 核心价值

| 维度 | 价值 | 说明 |
|------|------|------|
| **全流程可视化** | 端到端可见 | 从数据采集 → 知识构建 → 推理分析 → 决策输出全链路可视化 |
| **实时交互** | 即时反馈 | WebSocket 实时推送图谱变化、推演进度、Agent 状态 |
| **操作直观** | 用户体验优先 | 本体管理/角色管理等界面以用户体验为先（NFR-U01） |
| **多场景适配** | 场景无关 | 通过工作空间切换，同一界面适配不同领域 |

### 1.3 现有状态

```
frontend/src/
├── components/          # 7 个组件
│   ├── AppLayout.tsx    # 布局框架（侧边栏+顶栏+内容区）
│   ├── GraphCanvas.tsx  # 知识图谱可视化（D3.js）
│   ├── MapView.tsx      # 态势地图（Leaflet）
│   ├── SimulatorConsole.tsx  # 模拟器控制台
│   ├── StatCard.tsx     # 统计卡片
│   └── TimelineView.tsx # 时间线视图
├── pages/               # 9 个页面
│   ├── Dashboard.tsx    # 总览仪表盘
│   ├── GraphView.tsx    # 图谱浏览
│   ├── IngestPanel.tsx  # 数据接入
│   ├── OntologyGraph.tsx# 本体图谱
│   ├── Simulator.tsx    # 模拟推演
│   ├── SituationMap.tsx # 态势地图
│   ├── Timeline.tsx     # 时间线
│   └── VersionHistory.tsx # 版本历史
├── services/api.ts      # API 服务层
├── types/index.ts       # 类型定义
└── AppRoutes.tsx        # 路由定义
```

**已实现**：7 页面 + 7 组件 + 基础路由
**待建设**：6 占位页面（配置中心、角色管理、OPA 策略、审计日志、Skill 管理）+ 问答面板 + 工作空间切换器

---

## 2. 整体架构

### 2.1 技术栈

| 技术 | 选型 | 理由 |
|------|------|------|
| 框架 | React 18 + TypeScript | 生态成熟，类型安全 |
| 构建 | Vite | HMR 极快，配置简洁 |
| 状态管理 | Zustand | 轻量、简洁、TypeScript 友好 |
| 路由 | React Router v6 | 声明式路由，懒加载 |
| UI 组件库 | Ant Design 5 | 企业级组件齐全，中文友好 |
| 图谱可视化 | D3.js + react-force-graph | 力导向布局，交互丰富 |
| 地图 | Leaflet + react-leaflet | 轻量开源，图层丰富 |
| 图表 | ECharts / Recharts | 可视化能力强 |
| HTTP | Axios | 拦截器、超时控制 |
| WebSocket | 原生 WebSocket + 自封装 | SSE 回退支持 |
| 样式 | CSS Modules + Ant Design Token | 主题定制 + 作用域隔离 |
| 国际化 | react-i18next | i18n 就绪 |

### 2.2 应用架构

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              App Shell                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  AppLayout                                                              │ │
│  │  ┌──────────┬───────────────────────────────────────────────────────┐  │ │
│  │  │ Sidebar  │  Header (WorkspaceSwitcher + UserMenu + Notifications)│  │ │
│  │  │          ├───────────────────────────────────────────────────────┤  │ │
│  │  │ - 总览   │                                                       │  │ │
│  │  │ - 问答   │                   Content Area                        │  │ │
│  │  │ - 图谱   │              (React Router Outlet)                    │  │ │
│  │  │ - 态势   │                                                       │  │ │
│  │  │ - 推演   │                                                       │  │ │
│  │  │ - 时间线 │                                                       │  │ │
│  │  │ - 本体   │                                                       │  │ │
│  │  │ - 工具   │                                                       │  │ │
│  │  │ - 审计   │                                                       │  │ │
│  │  │ - 配置   │                                                       │  │ │
│  │  └──────────┴───────────────────────────────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 页面设计

### 3.1 页面清单与优先级

| 路由 | 页面 | 状态 | 优先级 | 对应模块 |
|------|------|------|--------|---------|
| `/` | Dashboard 总览 | ✅ 已实现 | P0 | - |
| `/qa` | 智能问答 | 🔴 新建 | P0 | M-12 |
| `/graph` | 知识图谱 | ✅ 已实现 | P0 | M-01 |
| `/map` | 态势地图 | ✅ 已实现 | P1 | M-18 |
| `/simulator` | 模拟推演 | ✅ 已实现 | P0 | M-14/M-15 |
| `/timeline` | 时间线 | ✅ 已实现 | P1 | M-01/M-07 |
| `/ontology` | 本体管理 | ✅ 已实现 | P0 | M-03 |
| `/versions` | 版本历史 | ✅ 已实现 | P0 | M-03 |
| `/ingest` | 数据接入 | ✅ 已实现 | P1 | M-06 |
| `/tools` | 工具管理 | 🔴 新建 | P1 | M-11 |
| `/audit` | 审计日志 | 🟡 占位 | P0 | M-07 |
| `/policies` | OPA 策略 | 🟡 占位 | P1 | M-02 |
| `/config` | 配置中心 | 🟡 占位 | P1 | - |
| `/roles` | 角色管理 | 🟡 占位 | P1 | M-02 |

### 3.2 智能问答页面（新建 P0）

```
┌───────────────────────────────────────────────────────────────────┐
│  智能问答                                              [新对话]  │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  👤 东风21D的射程是多少？                                    │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  🤖 东风21D（DF-21D）弹道导弹的射程约为 **1,500公里**。     │ │
│  │                                                             │ │
│  │  该导弹是中国人民解放军装备的反舰弹道导弹，                  │ │
│  │  主要用于对大型水面舰艇实施远程打击。                        │ │
│  │                                                             │ │
│  │  📎 来源:                                                   │ │
│  │  [1] 东风21D实体节点 → 查看图谱                              │ │
│  │  [2] 射程属性边 (valid: 2024-01~) → 查看详情                 │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  👤 它的最新部署位置呢？                                     │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  🤖 根据最新信息，东风21D目前部署在...                      │ │
│  │  ...                                                        │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
├───────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┬──────┐ │
│  │  输入问题...                                         │ 📤  │ │
│  └─────────────────────────────────────────────────────┴──────┘ │
└───────────────────────────────────────────────────────────────────┘
```

**交互特性**：
- SSE 流式输出（逐字显示）
- 来源标注可点击跳转到图谱节点/边
- 支持 Markdown 渲染
- 多轮对话上下文保持
- 会话历史列表（左侧面板）

### 3.3 审计日志页面（升级占位）

```
┌───────────────────────────────────────────────────────────────────┐
│  审计日志                                                         │
├───────────────────────────────────────────────────────────────────┤
│  [时间范围 ▼] [事件类型 ▼] [操作者 ▼] [关键词搜索...       ] [🔍]│
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│  时间线视图                                                       │
│  ─────┼────────┼────────┼────────┼────────┼──────               │
│  09:00    09:15    09:30    09:45    10:00                        │
│    │        │        │        │        │                          │
│    🟢       🔵       🟡       🟢       🔴                       │
│    │        │        │        │        │                          │
│  登录    图谱查询  策略更新  问答     权限拒绝                    │
│                                                                   │
├───────────────────────────────────────────────────────────────────┤
│  事件列表                                                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 🟢 10:00:15  policy.violation  用户 guest 尝试访问...     │  │
│  │ 🔵 09:45:32  qa.ask           用户 admin 提问"东风..."    │  │
│  │ 🟡 09:30:11  policy.update    更新策略 workspace.read     │  │
│  │ 🔵 09:15:05  graph.search     查询目标节点 15 个          │  │
│  │ 🟢 09:00:01  user.login       用户 admin 登录             │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  [上一页]  显示 1-50 / 共 1,234 条  [下一页]                     │
└───────────────────────────────────────────────────────────────────┘
```

### 3.4 工具管理页面（新建 P1）

```
┌───────────────────────────────────────────────────────────────────┐
│  工具管理                                            [注册工具]  │
├───────────────────────────────────────────────────────────────────┤
│  [全部 ▼] [情报 ▼] [作战 ▼] [分析 ▼] [可视化 ▼] [搜索...    ]  │
├───────────────────────────────────────────────────────────────────┤
│  ┌─────────────┬──────────┬────────┬────────┬────────┬───────┐  │
│  │ 工具名称     │ 类别     │ 来源   │ 健康度  │ 调用/24h│ 操作 │  │
│  ├─────────────┼──────────┼────────┼────────┼────────┼───────┤  │
│  │ radar_scan  │ 情报采集 │ Skill  │ 🟢 健康 │ 1,234  │ 详情 │  │
│  │ threat_assess│ 分析计算 │ Skill  │ 🟢 健康 │  856   │ 详情 │  │
│  │ mcp_weather │ 环境数据 │ MCP    │ 🟡 退化 │  432   │ 详情 │  │
│  │ gen_plan    │ 决策推荐 │ Skill  │ 🔴 异常 │   12   │ 详情 │  │
│  └─────────────┴──────────┴────────┴────────┴────────┴───────┘  │
└───────────────────────────────────────────────────────────────────┘
```

---

## 4. 核心组件设计

### 4.1 WorkspaceSwitcher（工作空间切换器）

```tsx
interface WorkspaceSwitcherProps {
  currentWorkspace: Workspace;
  workspaces: Workspace[];
  onSwitch: (workspaceId: string) => Promise<void>;
}

/**
 * 顶部栏组件，显示当前工作空间名称和切换下拉
 * 
 * 交互：
 * - 点击展开工作空间列表
 * - 搜索过滤
 * - 切换时显示加载状态
 * - 显示每个空间的领域标签和状态
 */
```

### 4.2 QAPanel（问答面板）

```tsx
interface QAPanelProps {
  workspaceId: string;
}

/**
 * 智能问答面板
 * 
 * 子组件：
 * - QAHeader: 会话管理（新建/切换/历史）
 * - QAMessageList: 消息列表（用户问题+系统回答）
 * - QAMessage: 单条消息（支持 Markdown 渲染 + 来源标注）
 * - SourceAnnotation: 来源标注（可点击跳转图谱）
 * - QAInput: 输入框（支持 Enter 发送、Shift+Enter 换行）
 * 
 * 特性：
 * - SSE 流式输出（逐字显示）
 * - 来源标注可点击跳转到图谱节点/边
 * - 自动滚动到底部
 * - 消息搜索
 */
```

### 4.3 AuditTimeline（审计时间线）

```tsx
interface AuditTimelineProps {
  workspaceId: string;
  filters?: AuditFilter;
}

/**
 * 审计时间线组件
 * 
 * 子组件：
 * - TimelineAxis: 时间轴线（缩放/拖拽）
 * - TimelineEvent: 事件标记（颜色/图标按严重级别）
 * - EventDetail: 事件详情弹窗
 * - AuditTable: 事件列表表格（排序/过滤/分页）
 */
```

### 4.4 ToolHealthIndicator（工具健康指示器）

```tsx
interface ToolHealthIndicatorProps {
  health: ToolHealth;
}

/**
 * 工具健康指示器
 * 
 * 显示：
 * - 健康状态（🟢/🟡/🔴）
 * - 成功率
 * - 平均耗时
 * - 最近错误
 */
```

---

## 5. 状态管理

### 5.1 Store 设计（Zustand）

```typescript
// 全局状态
interface AppStore {
  // 认证
  user: UserInfo | null;
  token: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;

  // 工作空间
  currentWorkspace: Workspace | null;
  workspaces: Workspace[];
  switchWorkspace: (id: string) => Promise<void>;
  loadWorkspaces: () => Promise<void>;

  // 通知
  notifications: Notification[];
  addNotification: (n: Notification) => void;
  removeNotification: (id: string) => void;
}

// 问答状态
interface QAStore {
  sessions: QASession[];
  currentSessionId: string | null;
  messages: Record<string, QAMessage[]>;  // sessionId → messages
  isStreaming: boolean;
  
  createSession: () => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  loadHistory: (sessionId: string) => Promise<void>;
}

// 审计状态
interface AuditStore {
  events: AuditEvent[];
  total: number;
  filters: AuditFilter;
  loading: boolean;
  
  loadEvents: (filters: AuditFilter) => Promise<void>;
  setFilter: (key: string, value: unknown) => void;
}
```

### 5.2 WebSocket 管理

```typescript
class WebSocketManager {
  private connections: Map<string, WebSocket>;
  private listeners: Map<string, Set<(data: unknown) => void>>;
  private reconnectTimers: Map<string, number>;

  /**
   * 连接管理
   * - 自动重连（指数退避）
   * - 心跳保活
   * - 认证 Token 注入
   * - 按工作空间隔离
   */

  connect(channel: string, workspaceId: string): void;
  disconnect(channel: string): void;
  subscribe(channel: string, listener: (data: unknown) => void): () => void;
  send(channel: string, data: unknown): void;
}

// 通道定义
const WS_CHANNELS = {
  SIMULATION_EVENTS: '/ws/simulation/{id}',   // 推演事件流
  GRAPH_UPDATES: '/ws/graph/updates',          // 图谱变更通知
  AGENT_STATUS: '/ws/agent/status',            // Agent 状态变更
  NOTIFICATIONS: '/ws/notifications',          // 系统通知
};
```

---

## 6. API 服务层

### 6.1 服务架构

```typescript
// services/api.ts - 基础 HTTP 客户端
class ApiClient {
  private axios: AxiosInstance;

  constructor() {
    this.axios = axios.create({
      baseURL: '/api',
      timeout: 30000,
    });

    // 请求拦截器：注入 Token
    this.axios.interceptors.request.use((config) => {
      const token = useAppStore.getState().token;
      if (token) config.headers.Authorization = `Bearer ${token}`;
      return config;
    });

    // 响应拦截器：处理 401/403
    this.axios.interceptors.response.use(
      (res) => res,
      (err) => {
        if (err.response?.status === 401) {
          useAppStore.getState().logout();
        }
        return Promise.reject(err);
      }
    );
  }
}

// 按模块拆分的服务
// services/qa.ts         → QAEngine API
// services/workspace.ts  → WorkspaceManager API
// services/audit.ts      → AuditLogger API
// services/tools.ts      → ToolRegistry API
// services/simulation.ts → SimulationService API
// services/ontology.ts   → OntologyManager API
// services/graphiti.ts   → GraphitiClient API
```

### 6.2 类型定义扩展

```typescript
// types/index.ts - 新增类型

// 工作空间
export interface Workspace {
  id: string;
  name: string;
  description: string;
  domain: string;
  status: 'active' | 'archived' | 'deleted';
  created_at: string;
  updated_at: string;
}

// 审计事件
export interface AuditEvent {
  id: string;
  timestamp: string;
  event_type: string;
  severity: 'debug' | 'info' | 'warn' | 'error' | 'critical';
  actor_type: string;
  actor_id: string;
  actor_name: string;
  action: string;
  resource_type: string;
  resource_id: string;
  result_status: 'success' | 'failure' | 'denied';
  result_message: string;
  workspace_id: string;
  trace_id: string;
  duration_ms?: number;
}

// 问答消息
export interface QAMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  timestamp: string;
  metadata?: {
    source_nodes?: string[];
    source_edges?: string[];
    confidence?: number;
    latency_ms?: number;
  };
}

// 工具描述
export interface ToolDescriptor {
  id: string;
  name: string;
  description: string;
  category: string;
  source: string;
  health?: {
    status: 'healthy' | 'degraded' | 'unhealthy';
    success_rate: number;
    avg_duration_ms: number;
  };
}
```

---

## 7. 主题与样式

### 7.1 主题配置

```typescript
// 采用 Ant Design 5 的 Token 系统
const themeConfig = {
  token: {
    colorPrimary: '#1677ff',       // 主色
    borderRadius: 6,               // 圆角
    colorBgContainer: '#ffffff',   // 背景色
  },
  components: {
    Layout: {
      siderBg: '#001529',          // 侧边栏深色
      headerBg: '#ffffff',         // 顶栏白色
    },
    Menu: {
      darkItemBg: '#001529',       // 深色菜单
    },
  },
};

// 暗色主题
const darkThemeConfig = {
  token: {
    colorPrimary: '#1677ff',
    colorBgContainer: '#141414',
    colorBgElevated: '#1f1f1f',
    colorText: 'rgba(255,255,255,0.85)',
  },
};
```

### 7.2 响应式设计

| 断点 | 宽度 | 布局 |
|------|------|------|
| xs | < 576px | 侧边栏折叠，内容全宽 |
| sm | 576-768px | 侧边栏图标模式 |
| md | 768-992px | 侧边栏展开，内容区自适应 |
| lg | 992-1200px | 完整布局 |
| xl | > 1200px | 宽屏优化，图谱/地图更大画布 |

---

## 8. 性能优化策略

| 策略 | 说明 |
|------|------|
| **路由懒加载** | React.lazy + Suspense，按页面拆分 bundle |
| **组件 memo** | 纯展示组件 React.memo，避免不必要重渲染 |
| **虚拟列表** | 审计日志/消息列表使用虚拟滚动 |
| **图谱 LOD** | 大规模图谱分级渲染（远距聚合、近距细节） |
| **WebSocket 增量更新** | 图谱/地图只更新变化部分，不全量刷新 |
| **请求去重** | 相同参数的并发请求自动去重 |
| **缓存策略** | 工作空间/本体等低频变更数据前端缓存 |

---

## 9. 构建与部署

### 9.1 开发环境

```bash
# 启动开发服务器
cd frontend && npm run dev
# → http://localhost:5173

# API 代理到后端
# vite.config.ts → proxy: { '/api': 'http://localhost:8000' }
```

### 9.2 生产构建

```bash
# 构建
npm run build
# → dist/

# 集成到 FastAPI 静态文件
# main.py → mount_static("frontend/dist")
```

---

## 10. 实现路径

### Phase 0 (当前)

- [x] 基础框架搭建（React + Vite + Ant Design）
- [x] 7 页面 + 7 组件实现
- [x] 基础路由 + API 服务层
- [x] 图谱可视化（D3.js）
- [x] 地图可视化（Leaflet）
- [x] 时间线组件

### Phase 1

- [ ] 智能问答页面（QAPanel + SSE 流式）
- [ ] 工作空间切换器（WorkspaceSwitcher）
- [ ] 审计日志页面（AuditTimeline + AuditTable）
- [ ] Zustand 状态管理重构
- [ ] WebSocket 管理器

### Phase 2

- [ ] 工具管理页面
- [ ] OPA 策略管理页面
- [ ] 角色管理页面
- [ ] 配置中心页面
- [ ] 暗色主题
- [ ] 国际化（i18n）

### Phase 3

- [ ] 图谱高级交互（路径查询、子图提取）
- [ ] 推演对比视图
- [ ] Agent 状态监控面板
- [ ] 移动端适配
- [ ] 离线模式（PWA）
