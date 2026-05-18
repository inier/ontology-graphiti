# ODAP 前端组件设计文档

> **版本**: 1.0.0 | **日期**: 2026-05-18
> **状态**: 已发布 | **优先级**: P0

---

## 1. 概述

### 1.1 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 19.2.4 | UI 框架 |
| TypeScript | 5.x | 类型安全 |
| Ant Design | 6.3.5 | 组件库 |
| Zustand | 5.0.12 | 状态管理 |
| React Router | 7.14.1 | 路由 |
| AntV G6 | 5.1.0 | 图谱可视化 |
| ECharts | 6.0.0 | 图表 |
| Leaflet | 1.9.4 | 地图 |
| @emotion/css | 11.13.5 | CSS-in-JS |
| Vite | 8.x | 构建工具 |
| Vitest | - | 测试框架 |

### 1.2 目录结构

```
frontend/src/
├── App.tsx                    # 应用根组件
├── AppRoutes.tsx              # 路由配置
├── App.css                    # 全局样式
├── main.tsx                   # 入口文件
├── config.ts                  # 配置（API_BASE）
├── index.css                  # 基础样式
├── modules/
│   ├── agent/                 # 智能体模块
│   ├── audit/                 # 审计模块
│   ├── business/              # 业务规则模块
│   ├── config/                # 配置/策略模块
│   ├── ingest/                # 数据摄入模块
│   ├── knowledge/             # 知识库模块
│   ├── ontology/              # 本体模块
│   ├── qa/                    # 智能问答模块
│   ├── roles/                 # 角色管理模块
│   ├── shared/                # 共享模块
│   ├── system/                # 系统管理模块
│   ├── version/               # 版本管理模块
│   └── workspace/             # 工作空间模块
└── test/
    ├── setup.ts               # 测试配置
    └── api_integration.test.ts # API 集成测试
```

---

## 2. 路由配置

**来源文件**: `frontend/src/AppRoutes.tsx`

| 路径 | 组件 | 模块 | 说明 |
|------|------|------|------|
| `/` | MyAgents | agent | 默认页 - 我的智能体 |
| `/my-agents` | MyAgents | agent | 我的智能体 |
| `/agent-chat/:agentId` | AgentChat | agent | 智能体对话 |
| `/admin` | OntologySemanticNetwork | ontology | 本体语义网络 |
| `/admin/agents` | AgentManagement | agent | 智能体管理 |
| `/admin/ontology` | OntologySemanticNetwork | ontology | 本体管理 |
| `/admin/ingest` | IngestPanel | ingest | 数据摄入 |
| `/admin/simulator` | Simulator | ingest | 模拟推演 |
| `/admin/roles` | RoleManager | roles | 角色管理 |
| `/admin/policies` | PolicyManagement | config | 策略管理 |
| `/admin/skills` | SkillManagement | system | 技能管理 |
| `/admin/audit` | AuditLog | audit | 审计日志 |
| `/admin/workspace` | WorkspaceManager | workspace | 工作空间 |
| `/admin/knowledge` | KnowledgeBase | knowledge | 知识库 |
| `/admin/business-logic` | Logic | business | 业务逻辑 |
| `/admin/business-rules` | Rules | business | 业务规则 |
| `/qa` | QAChatPage | qa | 智能问答 |

---

## 3. 模块组件详细设计

### 3.1 agent 模块 — 智能体

**目录**: `frontend/src/modules/agent/`

#### 3.1.1 MyAgents

**文件**: `pages/MyAgents.tsx`
**路由**: `/my-agents`, `/`
**功能**: 智能体列表页面，按角色过滤展示可用智能体

**Props**: 无（路由页面组件）

**状态管理**: 本地 useState
- `agents`: Agent[] - 智能体列表
- `loading`: boolean - 加载状态
- `searchText`: string - 搜索关键词
- `currentRoleId`: string - 当前角色 ID

**API 调用**:
- `agentApi.listAgentsByRole(roleId)` - 按角色列出智能体
- `agentApi.listAgents()` - 列出所有智能体（降级）

**子组件**: AgentCard, Tag, Card, Input, Row, Col

#### 3.1.2 AgentChat

**文件**: `pages/AgentChat.tsx`
**路由**: `/agent-chat/:agentId`
**功能**: 智能体对话页面

**Props**: 无（通过 useParams 获取 agentId）

**状态管理**: 本地 useState
- `agent`: Agent | null - 智能体信息
- `messages`: ChatMessage[] - 对话消息列表
- `inputText`: string - 输入文本
- `loading`: boolean - 加载状态

**API 调用**:
- `agentApi.getAgent(agentId)` - 获取智能体信息

**已知问题**: handleSend 使用 setTimeout 模拟回复，未调用真实 API

#### 3.1.3 AgentManagement

**文件**: `pages/AgentManagement.tsx`
**路由**: `/admin/agents`
**功能**: 智能体管理页面（CRUD）

**类型定义** (`types.ts`):
```typescript
interface Agent {
  id: string;
  name: string;
  role: string;
  description: string;
  model: string;
  status: 'active' | 'inactive';
  capabilities: string[];
}
```

---

### 3.2 audit 模块 — 审计

**目录**: `frontend/src/modules/audit/`

#### 3.2.1 AuditLog

**文件**: `pages/AuditLog.tsx`
**路由**: `/admin/audit`
**功能**: 审计日志页面，支持事件类型/严重程度/时间范围筛选

**状态管理**: 本地 useState
- `events`: AuditEvent[] - 审计事件列表
- `stats`: AuditStats | null - 统计信息
- `loading`: boolean - 加载状态
- `filters`: AuditFilters - 筛选条件
- `pagination`: { page, pageSize, total } - 分页

**API 调用**:
- `api.getAuditStats()` - 获取审计统计
- `api.listAuditEvents(params)` - 列出审计事件

**子组件**: Table, Select, DatePicker, Statistic, Card, Tag

#### 3.2.2 AuditTimeline（未使用）

**文件**: 导出自 `index.ts`
**路由**: 未在路由中使用
**状态**: **废弃代码** - 导出但未使用

---

### 3.3 business 模块 — 业务规则

**目录**: `frontend/src/modules/business/`

#### 3.3.1 Logic

**文件**: `pages/Logic.tsx`
**路由**: `/admin/business-logic`
**功能**: 业务逻辑管理页面

**API 调用**: 通过 `logicApi` 注入 BusinessEntityManager

#### 3.3.2 Rules

**文件**: `pages/Rules.tsx`
**路由**: `/admin/business-rules`
**功能**: 业务规则管理页面

**API 调用**: 通过 `ruleApi` 注入 BusinessEntityManager

#### 3.3.3 BusinessEntityManager（通用组件）

**功能**: 通用业务实体管理组件，通过 props 区分实体类型

**Props**:
```typescript
interface BusinessEntityManagerProps {
  entityType: 'process' | 'rule' | 'logic' | 'indicator';
  api: BusinessApi;
  columns: ColumnDef[];
}
```

**类型定义** (`types.ts`):
```typescript
interface BusinessEntity {
  id: string;
  name: string;
  display_name?: string;
  description?: string;
  status: 'draft' | 'active' | 'archived';
  created_at: string;
  updated_at: string;
}
```

---

### 3.4 config 模块 — 策略管理

**目录**: `frontend/src/modules/config/`

#### 3.4.1 PolicyManagement

**文件**: `index.ts` (default export)
**路由**: `/admin/policies`
**功能**: OPA 策略管理页面

**API 调用**:
- `api.listPolicies()` - 列出策略
- `api.createPolicy(data)` - 创建策略
- `api.updatePolicy(id, data)` - 更新策略
- `api.deletePolicy(id)` - 删除策略

---

### 3.5 ingest 模块 — 数据摄入

**目录**: `frontend/src/modules/ingest/`

#### 3.5.1 IngestPanel

**文件**: `index.ts` 导出
**路由**: `/admin/ingest`
**功能**: 数据摄入面板，支持多种摄入方式

**API 调用**:
- `api.ingestText(text, scenarioId)` - 文本摄入
- `api.ingestNews(url, scenarioId)` - 新闻摄入
- `api.ingestRandom(parties, scenarioId)` - 随机生成

#### 3.5.2 Simulator

**文件**: `index.ts` 导出
**路由**: `/admin/simulator`
**功能**: 模拟推演控制台

#### 3.5.3 SimulatorConsole（未使用）

**状态**: **废弃代码** - 导出但未在路由中使用

---

### 3.6 ontology 模块 — 本体

**目录**: `frontend/src/modules/ontology/`

#### 3.6.1 OntologySemanticNetwork

**文件**: `index.ts` 导出
**路由**: `/admin`, `/admin/ontology`
**功能**: 本体语义网络可视化（AntV G6）

**API 调用**:
- `api.getOntologySchema()` - 获取本体 Schema
- `api.queryGraph(params)` - 查询图谱

#### 3.6.2 未使用组件

| 组件 | 状态 |
|------|------|
| GraphView | 导出但未在路由中使用 |
| OntologyBuilder | 导出但未在路由中使用 |
| GraphCanvas | 导出但未在路由中使用 |
| OntologyIngestPipeline | 导出但未在路由中使用 |

---

### 3.7 qa 模块 — 智能问答

**目录**: `frontend/src/modules/qa/`

#### 3.7.1 QAChatPage（新版）

**文件**: `pages/QAChatPage.tsx`
**路由**: `/qa`
**代码量**: ~1365 行
**功能**: 智能问答聊天页面，包含会话管理、消息交互、建议面板

**内部组件**:
- Sidebar - 会话列表
- ChatHeader - 聊天头部
- MessageList - 消息列表
- ChatInput - 输入框
- SuggestionPanel - 建议面板

**Hooks**:
- `useQAI` - QA 交互 Hook
- `useSession` - 会话管理 Hook
- `useInputHistory` - 输入历史 Hook

**API 调用**: 通过 `useQAI` 和 `useSession` hooks 间接调用

**已知问题**:
- 组件过大（1365 行），应拆分为独立文件
- handleDeleteSession 中 `sessionId === sessionId` 永远为 true
- setSuggestions 状态被设置但从未读取

#### 3.7.2 QAChat（旧版）

**文件**: `pages/QAChat.tsx`
**代码量**: ~870 行
**状态**: **废弃代码** - 未在路由中使用，被 QAChatPage 替代

**已知问题**:
- simulatePipeline 使用 setTimeout 模拟
- 统计数据加载失败时使用硬编码 mock 数据

---

### 3.8 roles 模块 — 角色管理

**目录**: `frontend/src/modules/roles/`

#### 3.8.1 RoleManager

**文件**: `index.ts` 导出
**路由**: `/admin/roles`
**功能**: 角色管理页面（CRUD）

**API 调用**:
- `api.listRoles()` - 列出角色
- `api.createRole(data)` - 创建角色
- `api.updateRole(id, data)` - 更新角色
- `api.deleteRole(id)` - 删除角色

---

### 3.9 shared 模块 — 共享

**目录**: `frontend/src/modules/shared/`

#### 3.9.1 api.ts — 统一 API 服务

**代码量**: ~1600 行
**功能**: 核心统一 API 服务层

**API 分组**:

| 分组 | 方法数 | 端点前缀 |
|------|--------|---------|
| 场景管理（旧版） | 6 | `/api/scenarios` |
| 本体摄入 | 12 | `/api/ontology/ingest` |
| 本体构建 | 3 | `/api/ontology/ingest/builds` |
| 处理日志 | 3 | `/api/ontology/ingest/{id}/logs` |
| 本体版本 | 2 | `/api/ontology/ingest/versions` |
| 本体文档 | 3 | `/api/ontology/schema`, `/api/ontology/ingest/documents` |
| 旧版摄入 | 5 | `/api/ingest` |
| 版本管理 | 4 | `/api/versions` |
| 工作空间 | 6 | `/api/workspaces` |
| 审计日志 | 4 | `/api/audit` |
| 图谱查询 | 5 | `/api/query` |
| 图谱生成 | 5 | `/api/graph` |
| 场景管理（新版） | 7 | `/api/workspaces/{ws}/scenarios` |
| 智能问答 | 8 | `/api/qa` |
| 用户认知引擎 | 4 | `/api/cognition` |
| 闭环反馈 | 2 | `/api/feedback` |
| Skill 管理 | 9 | `/api/skill` |
| 事件模拟器 | 7 | `/api/event-simulator` |
| OPA 策略 | 5 | `/api/policies` |
| 系统监控 | 2 | `/api/v1/monitoring`, `/health` |
| 角色管理 | 4 | `/api/roles` |
| Agent | 4 | `/api/agent` |
| Agent 对话 | 1 | `/api/agent/chat` |

**关键类型**:
```typescript
interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties: Record<string, any>;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  type: string;
  properties: Record<string, any>;
}
```

#### 3.9.2 stores/index.ts — Zustand Store

**useAppStore**:
```typescript
interface AppState {
  user: UserInfo | null;
  token: string | null;
  currentWorkspace: Workspace | null;
  workspaces: Workspace[];
  notifications: Notification[];
  loading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  loadWorkspaces: () => Promise<void>;
  switchWorkspace: (id: string) => void;
  addNotification: (n: Notification) => void;
  removeNotification: (id: string) => void;
  clearError: () => void;
}
```

**useAuditStore**:
```typescript
interface AuditState {
  events: AuditEvent[];
  total: number;
  loading: boolean;
  filters: AuditFilters;
  loadEvents: (params?) => Promise<void>;
  setFilter: (key: string, value: any) => void;
  clearFilters: () => void;
}
```

#### 3.9.3 types/index.ts — 共享类型

```typescript
interface Scenario {
  scenario_id: string;
  name: string;
  description: string;
  workspace_id: string;
  ontology_id?: string;
  doc_count: number;
  event_count: number;
  entity_count: number;
  created_at: string;
  updated_at: string;
}

interface Entity {
  entity_id: string;
  entity_type: string;
  name: string;
  properties: Record<string, any>;
}

interface Relation {
  relation_id: string;
  relation_type: string;
  source_entity: string;
  target_entity: string;
  properties: Record<string, any>;
}
```

---

### 3.10 system 模块 — 系统管理

**目录**: `frontend/src/modules/system/`

#### 3.10.1 SkillManagement

**文件**: `index.ts` 导出
**路由**: `/admin/skills`
**功能**: 技能管理页面

**API 调用**:
- `api.listSkills()` - 列出技能
- `api.registerSkill(data)` - 注册技能
- `api.activateSkill(id)` - 激活技能
- `api.deactivateSkill(id)` - 停用技能

---

### 3.11 version 模块 — 版本管理

**目录**: `frontend/src/modules/version/`

#### 3.11.1 VersionHistory

**文件**: `index.ts` 导出
**功能**: 版本历史页面

**API 调用**:
- `api.listVersions(scenarioId)` - 列出版本
- `api.rollbackVersion(versionId, scenarioId)` - 回滚版本
- `api.diffVersions(v1, v2)` - 版本对比

---

### 3.12 workspace 模块 — 工作空间

**目录**: `frontend/src/modules/workspace/`

#### 3.12.1 WorkspaceManager

**文件**: `index.ts` 导出
**路由**: `/admin/workspace`
**功能**: 工作空间管理页面

**API 调用**:
- `api.listWorkspaces()` - 列出工作空间
- `api.createWorkspace(data)` - 创建工作空间
- `api.updateWorkspace(id, data)` - 更新工作空间
- `api.deleteWorkspace(id)` - 删除工作空间

#### 3.12.2 WorkspaceSwitcher（未使用）

**状态**: **废弃代码** - 导出但未在路由中使用

---

### 3.13 knowledge 模块 — 知识库

**目录**: `frontend/src/modules/knowledge/`

#### 3.13.1 KnowledgeBase

**文件**: `index.ts` 导出
**路由**: `/admin/knowledge`
**功能**: 知识库管理页面

---

## 4. 组件层级关系

```
App
├── AppLayout (Header + Sidebar + Content)
│   ├── Header
│   │   ├── Logo
│   │   ├── WorkspaceSwitcher
│   │   ├── SearchInput
│   │   ├── NotificationBell
│   │   └── UserAvatar
│   └── Sidebar
│       └── Menu (17 items)
└── AppRoutes
    ├── MyAgents (/)
    │   └── AgentCard[]
    ├── AgentChat (/agent-chat/:id)
    │   ├── ChatHeader
    │   ├── MessageList
    │   │   └── MessageBubble[]
    │   └── ChatInput
    ├── OntologySemanticNetwork (/admin)
    │   ├── GraphCanvas (AntV G6)
    │   └── NodeDetailPanel
    ├── IngestPanel (/admin/ingest)
    │   ├── Tabs (文本/新闻/随机/导入)
    │   └── IngestHistory
    ├── QAChatPage (/qa)
    │   ├── Sidebar (会话列表)
    │   ├── ChatHeader
    │   ├── MessageList
    │   ├── ChatInput
    │   └── SuggestionPanel
    ├── AuditLog (/admin/audit)
    │   ├── FilterBar
    │   ├── StatsCards
    │   └── EventTable
    ├── BusinessEntityManager (/admin/business-*)
    │   ├── EntityTable
    │   └── EntityForm (Modal)
    ├── RoleManager (/admin/roles)
    ├── PolicyManagement (/admin/policies)
    ├── SkillManagement (/admin/skills)
    ├── WorkspaceManager (/admin/workspace)
    └── KnowledgeBase (/admin/knowledge)
```

---

## 5. API 服务层架构

### 5.1 服务层结构

```
api.ts (主服务, ~1600行)
├── fetchJson<T>() - 通用请求封装
├── 场景管理 API (旧版 + 新版)
├── 本体摄入 API
├── 构建状态 API
├── 版本管理 API
├── 工作空间 API
├── 审计日志 API
├── 图谱查询/生成 API
├── 智能问答 API
├── 用户认知引擎 API
├── 闭环反馈 API
├── Skill 管理 API
├── 事件模拟器 API
├── OPA 策略 API
├── 系统监控 API
├── 角色管理 API
└── Agent API

agentApi.ts (Agent 专用服务)
└── listAgents, getAgent, listAgentsByRole

businessApi.ts (业务专用服务)
├── logicApi (逻辑 CRUD)
└── ruleApi (规则 CRUD)
```

### 5.2 环境变量

| 变量名 | 默认值 | 使用位置 |
|--------|--------|---------|
| VITE_API_BASE | `http://localhost:8000` | config.ts → api.ts |
| VITE_API_BASE_URL | - | agentApi.ts, businessApi.ts |

**已知问题**: 两套环境变量名不一致

---

## 6. 状态管理架构

### 6.1 全局 Store (Zustand)

| Store | 状态 | 使用情况 |
|-------|------|---------|
| useAppStore | user, token, workspaces, notifications | App.tsx 未使用（自行管理 workspace） |
| useAuditStore | events, total, filters | AuditLog.tsx 未使用（自行管理状态） |

### 6.2 本地状态 (useState)

大多数页面组件使用本地 useState 管理状态，未使用全局 Store。

---

## 7. 已知问题与改进建议

| 编号 | 问题 | 影响 | 建议 |
|------|------|------|------|
| FE-001 | api.ts 1600 行，应按领域拆分 | 难以维护 | 拆分为 api/ontology.ts, api/workspace.ts 等 |
| FE-002 | QAChatPage 1365 行，包含 5 个内部组件 | 难以维护 | 拆分为独立文件 |
| FE-003 | QAChat（旧版）与 QAChatPage（新版）并存 | 代码冗余 | 删除 QAChat |
| FE-004 | Workspace 类型在 api.ts 和 stores 中重复定义 | 类型冲突 | 统一到 shared/types |
| FE-005 | AuditEvent 类型在 api.ts 和 stores 中重复定义 | 类型冲突 | 统一到 shared/types |
| FE-006 | AgentChat 使用 setTimeout 模拟回复 | 功能缺失 | 调用真实 API |
| FE-007 | useAppStore.login 是 mock 实现 | 功能缺失 | 对接真实认证 API |
| FE-008 | VITE_API_BASE 与 VITE_API_BASE_URL 不一致 | 配置混乱 | 统一环境变量名 |
| FE-009 | 多个导出组件未在路由中使用 | 死代码 | 清理或标记为内部使用 |
| FE-010 | Store 定义了但页面组件未使用 | 状态管理混乱 | 统一状态管理策略 |
| FE-011 | 现有测试文件与实际 API 签名严重脱节 | 测试无法运行 | 重写测试文件 |
| FE-012 | 同时引入 @ant-design/charts, @ant-design/plots, echarts | 包体积大 | 统一图表库 |

---

**文档版本历史**:

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0.0 | 2026-05-18 | 初始版本，基于代码分析梳理 |
