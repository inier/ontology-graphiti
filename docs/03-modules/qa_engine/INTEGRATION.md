# 问答引擎模块 (QA Engine) - 集成方案

> **文档版本**: 1.0.0 | **日期**: 2026-04-28 | **模块**: M-12

---

## 1. 模块概述

### 1.1 集成目标

本文档描述问答引擎前端模块与 `@openharness/react` 库的集成方案。通过集成 OpenHarness 平台的能力，实现智能问答功能的核心交互界面。

### 1.2 技术栈

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| UI 框架 | React 19 | 前端应用框架 |
| 状态管理 | Zustand 5 | 全局状态管理 |
| UI 组件库 | Ant Design 6 | 企业级 React 组件库 |
| AI SDK | Vercel AI SDK 6 | LLM 对话集成 |
| 外部库 | @openharness/react 1.0.1 | OpenHarness 平台集成 |

---

## 2. @openharness/react 库集成

### 2.1 库简介

`@openharness/react` 是 OpenHarness 平台的 React 组件库，提供与 OpenHarness 运行时环境交互的组件和钩子。

### 2.2 依赖安装

```bash
# 安装依赖
pnpm add @openharness/react

# 检查版本
pnpm list @openharness/react
```

### 2.3 Provider 配置

`@openharness/react` 提供 `OpenHarnessProvider` 组件，用于包裹应用根节点，提供 OpenHarness 运行时上下文。

**QAIProvider.tsx** - 问答模块的 Provider 配置：

```tsx
import { OpenHarnessProvider } from '@openharness/react';

const API_ENDPOINT = 'http://localhost:8000/api/qa';

export interface QAIProviderProps {
  children: React.ReactNode;
}

export function QAIProvider({ children }: QAIProviderProps) {
  return (
    <OpenHarnessProvider>
      {children}
    </OpenHarnessProvider>
  );
}

export { API_ENDPOINT };
```

### 2.4 集成架构

```
┌─────────────────────────────────────────────────────────────┐
│                      React 应用根节点                         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              OpenHarnessProvider                    │    │
│  │  ┌─────────────────────────────────────────────┐   │    │
│  │  │              QAIProvider                    │   │    │
│  │  │  ┌─────────────────────────────────────┐    │   │    │
│  │  │  │         QAChatPage                  │    │   │    │
│  │  │  │  ┌──────────┐ ┌──────────┐        │    │   │    │
│  │  │  │  │ ChatHeader│ │MessageList│       │    │   │    │
│  │  │  │  └──────────┘ └──────────┘        │    │   │    │
│  │  │  │  ┌──────────────────────────┐     │    │   │    │
│  │  │  │  │       ChatInput          │     │    │   │    │
│  │  │  │  └──────────────────────────┘     │    │   │    │
│  │  │  └─────────────────────────────────────┘    │   │    │
│  │  └─────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 前端模块结构

### 3.1 目录结构

```
apps/web/src/modules/qa/
├── providers/
│   └── QAIProvider.tsx       # OpenHarness Provider 集成
├── hooks/
│   ├── useQAI.ts             # 问答交互钩子
│   ├── useSession.ts         # 会话管理钩子
│   └── useChatStorage.ts     # 本地存储钩子
├── components/
│   └── SessionDrawer.tsx     # 历史会话抽屉
├── pages/
│   ├── QAChatPage.tsx        # 问答主页面
│   └── QAChat.tsx            # 问答组件（含统计）
└── index.ts                  # 模块导出
```

### 3.2 核心组件关系

```
QAChatPage (主容器)
├── ChatHeader (顶部导航栏)
├── MessageList (消息列表)
├── ChatInput (输入框)
└── SessionDrawer (历史会话抽屉)
    └── useSession (会话管理)
```

---

## 4. 核心钩子详解

### 4.1 useQAI - 问答交互钩子

**功能**：管理问答消息、发送请求、处理响应状态。

**主要接口**：

```typescript
export interface UseQAIOptions {
  sessionId?: string;           // 初始会话 ID
  onError?: (error: Error) => void;  // 错误回调
}

export interface UseQAIReturn {
  messages: QAMessage[];        // 消息列表
  sendMessage: (content: string) => void;  // 发送消息
  status: 'idle' | 'submitting' | 'streaming' | 'error' | 'waiting_for_input';
  isLoading: boolean;           // 加载状态
  error: Error | null;          // 错误信息
  sessionId: string | null;     // 当前会话 ID
  setSessionId: (id: string | null) => void;  // 设置会话 ID
  clearMessages: () => void;    // 清除消息
  stop: () => void;             // 停止生成
}
```

**消息类型**：

```typescript
export interface QAMessage {
  id: string;                   // 消息 ID
  role: 'user' | 'assistant';   // 角色
  content: string;              // 内容
  timestamp: string;            // 时间戳
  sources?: Array<{            // 参考来源
    source: string;
    excerpt: string;
    confidence: number;
  }>;
  intent?: {                    // 意图信息
    type: string;
    confidence: number;
  };
}
```

### 4.2 useSession - 会话管理钩子

**功能**：管理会话列表、加载会话、删除会话。

**主要接口**：

```typescript
export interface Session {
  session_id: string;           // 会话 ID
  summary: string;              // 会话摘要
  message_count: number;        // 消息数量
  model: string;               // 使用的模型
  created_at: number;           // 创建时间
}

export interface UseSessionReturn {
  sessions: Session[];         // 会话列表
  loading: boolean;             // 加载状态
  error: Error | null;         // 错误信息
  fetchSessions: () => Promise<void>;     // 获取会话列表
  loadSession: (sessionId: string) => Promise<Session | null>;  // 加载会话
  deleteSession: (sessionId: string) => Promise<boolean>;       // 删除会话
}
```

### 4.3 useChatStorage - 本地存储钩子

**功能**：将聊天记录持久化到 localStorage，支持会话恢复。

**存储键策略**：

```typescript
// 根据 sessionId 动态生成存储键
function getStorageKey(sessionId: string | null): string {
  if (sessionId) {
    return `qa_chat_state_${sessionId}`;
  }
  return `qa_chat_state_default`;
}
```

**防抖策略**：500ms 防抖，避免频繁写入。

---

## 5. API 配置

### 5.1 后端接口地址

```typescript
const API_ENDPOINT = 'http://localhost:8000/api/qa';
const SESSIONS_ENDPOINT = 'http://localhost:8000/api/qa/sessions';
```

### 5.2 环境配置建议

在 `.env` 文件中配置：

```env
# 开发环境
VITE_QA_API_BASE=http://localhost:8000/api/qa

# 生产环境
VITE_QA_API_BASE=https://your-domain.com/api/qa
```

### 5.3 请求超时配置

```typescript
const REQUEST_TIMEOUT = 30000;  // 30 秒超时
```

---

## 6. 组件集成示例

### 6.1 基础使用

```tsx
import { QAIProvider } from './modules/qa/providers/QAIProvider';
import { QAChatPage } from './modules/qa/pages/QAChatPage';

function App() {
  return (
    <QAIProvider>
      <QAChatPage />
    </QAIProvider>
  );
}
```

### 6.2 带自定义配置的集成

```tsx
import { QAIProvider } from './modules/qa/providers/QAIProvider';
import { QAChatPage } from './modules/qa/pages/QAChatPage';
import { ConfigProvider, App as AntdApp } from 'antd';

function App() {
  return (
    <ConfigProvider theme={{ token: { colorPrimary: '#1890ff' } }}>
      <AntdApp>
        <QAIProvider>
          <QAChatPage
            style={{ height: '600px' }}
            className="custom-qa-chat"
          />
        </QAIProvider>
      </AntdApp>
    </ConfigProvider>
  );
}
```

### 6.3 自定义错误处理

```tsx
import { message } from 'antd';
import { useQAI } from './hooks/useQAI';

function CustomQAComponent() {
  const handleError = (error: Error) => {
    message.error(`问答出错: ${error.message}`);
    // 上报到监控系统
    console.error('QA Error:', error);
  };

  const { sendMessage, messages } = useQAI({
    onError: handleError
  });

  return (
    <div>
      {/* 自定义 UI */}
    </div>
  );
}
```

---

## 7. 配置说明

### 7.1 Ant Design 主题配置

```typescript
const themeConfig = {
  token: {
    colorPrimary: '#1890ff',
    borderRadius: 8,
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial',
  },
  components: {
    Card: {
      borderRadiusLG: 12,
    },
    Button: {
      borderRadius: 8,
    },
  },
};
```

### 7.2 消息列表样式配置

```typescript
const messageListConfig = {
  maxWidth: '70%',           // 消息气泡最大宽度
  animationDuration: 300,    // 动画时长（毫秒）
  maxSourcesDisplay: 3,      // 最大显示来源数
  bubbleBorderRadius: 12,    // 气泡圆角
};
```

### 7.3 会话抽屉配置

```typescript
const drawerConfig = {
  width: 400,                // 抽屉宽度
  placement: 'right',        // 抽屉位置
  maxSessionsDisplay: 50,    // 最大显示会话数
};
```

---

## 8. 状态管理

### 8.1 本地状态 (useState)

- `input`: 输入框内容
- `sessionDrawerOpen`: 会话抽屉开关状态

### 8.2 派生状态 (useMemo/useCallback)

- `isLoading`: 根据 `status` 推导
- `filteredSessions`: 根据搜索条件过滤的会话列表

### 8.3 持久化状态 (localStorage)

- 聊天记录
- 当前会话 ID
- 最后更新时间

---

## 9. 错误处理

### 9.1 网络错误

```typescript
if (!response.ok) {
  throw new Error(`请求失败: ${response.status}`);
}
```

### 9.2 AbortError 处理

```typescript
if (err instanceof Error && err.name === 'AbortError') {
  setStatus('idle');
  return;
}
```

### 9.3 全局错误回调

```typescript
onError?.(error);
message.error(error.message || '发生错误，请重试');
```

---

## 10. 性能优化

### 10.1 消息列表虚拟化

当消息数量超过 100 条时，考虑使用虚拟列表：

```typescript
import { FixedSizeList } from 'react-window';

<FixedSizeList
  height={400}
  itemCount={messages.length}
  itemSize={80}
>
  {MessageItem}
</FixedSizeList>
```

### 10.2 防抖存储

```typescript
const DEBOUNCE_MS = 500;  // 500ms 防抖写入
```

### 10.3 依赖优化

```typescript
useEffect(() => {
  // 依赖于特定变量，避免不必要的重渲染
}, [messages, sessionId]);
```

---

## 11. 相关文档

- [API 使用文档](./API.md)
- [架构设计文档](./DESIGN.md)
- [ADR-039 问答引擎架构决策](../../07-adr/ADR-039_qa_engine_architecture.md)
