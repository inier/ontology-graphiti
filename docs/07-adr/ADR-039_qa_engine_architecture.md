# ADR-039: 问答引擎架构

## 状态
已接受

## 上下文

ODAP 平台需要一个问答引擎（M-12），作为用户与知识图谱的主要交互界面。核心需求：

1. **自然语言提问**：用户无需学习查询语言，直接用自然语言提问
2. **RAG 增强**：从 Graphiti 双时态知识图谱检索事实，结合 LLM 生成答案
3. **双时态推理**：支持"当时发生了什么"类时间感知问题
4. **溯源追踪**：每个答案附带来源节点/边，支持跳转验证
5. **多轮对话**：维护会话上下文，支持追问和澄清
6. **复杂问题升级**：超出 QA 能力时，升级到 Intelligence Agent 处理

### 架构选择

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A. 单体 QA Pipeline** | 查询理解→检索→生成→溯源 线性流水线 | 简单、易调试 | 不支持工具调用、无法升级到 Agent |
| **B. QA + Agent 双层** | 简单问题走 QA Pipeline，复杂问题升级到 Agent | 分层处理、资源效率高 | 需要准确的路由判断 |
| **C. 纯 Agent 驱动** | 所有问题都通过 Agent ReAct 循环处理 | 统一架构、工具灵活 | 延迟高、成本高、简单问题浪费 |

## 决策

**采用方案 B：QA + Agent 双层架构**。

### 架构设计

```
用户提问
    │
    ▼
QueryUnderstanding（查询理解）
    ├── 意图分类（简单查询 / 复杂分析 / 工具调用）
    ├── 时间表达式解析
    └── 实体识别
    │
    ├── 简单查询 ──▶ RetrievalOrchestrator ──▶ AnswerGenerator ──▶ SourceTracker
    │                   │                         │                   │
    │                   ▼                         ▼                   ▼
    │               Graphiti.search()         LLM.generate()     溯源链路
    │               三层降级检索
    │
    └── 复杂分析 ──▶ Intelligence Agent（ReAct 循环 + 工具调用）
                         │
                         ▼
                     Agent Response → SourceTracker
```

### 核心组件

| 组件 | 职责 |
|------|------|
| QAEngine | 入口协调器，管理会话和路由 |
| QueryUnderstanding | 意图分类 + 时间解析 + 实体识别 |
| RetrievalOrchestrator | 三层降级检索（向量→关键词→内存） |
| AnswerGenerator | LLM 生成 + Prompt 工程 |
| SourceTracker | 答案→源 Episode/Entity 溯源 |
| DialogManager | 多轮上下文管理（窗口 + 摘要） |
| TemporalQueryParser | "上周"/"事件发生时"→双时态查询参数 |

### 路由策略

| 意图 | 路由目标 | 判断依据 |
|------|---------|---------|
| 简单事实查询 | QA Pipeline | 单实体、无推理链 |
| 关系查询 | QA Pipeline | 实体间关系、路径 |
| 时间查询 | QA Pipeline + TemporalQueryParser | 含时间表达式 |
| 复杂分析 | Intelligence Agent | 需多步推理/工具调用 |
| 需决策 | Commander Agent | 涉及行动方案 |

## 后果

### 变得更容易

- **简单问题快速响应**：QA Pipeline 不经过 Agent 循环，延迟低
- **成本可控**：简单查询仅需 1 次 LLM 调用（生成），复杂查询才走 ReAct
- **可扩展**：新增意图类型只需扩展 QueryUnderstanding

### 变得更难

- **路由准确性**：意图分类错误会导致简单问题走 Agent（浪费）或复杂问题走 QA（质量差）
- **双路径维护**：QA Pipeline 和 Agent 路径需分别维护和测试
- **溯源统一**：QA 溯源（Graphiti 检索结果）和 Agent 溯源（ReAct 步骤）格式不同，需统一展示

### 风险与缓解

| 风险 | 缓解 |
|------|------|
| 意图分类准确率不足 | 置信度阈值 + 人工确认 + 自动学习 |
| Agent 升级延迟过高 | 流式输出 + 超时降级到 QA |
| 溯源格式不统一 | SourceTracker 统一输出 SourceTrace 结构 |

## 可逆性

**中**。QA Pipeline 和 Agent 是两个独立路径，可以分别演进。如果 QA Pipeline 能力增强（如支持工具调用），可以逐步收敛到单路径。但双层架构的接口（QueryUnderstanding 路由、DialogManager 共享）修改成本中等。

---

## 前端集成方案

### 技术选型

| 类别 | 选型 | 版本 | 说明 |
|------|------|------|------|
| UI 框架 | React | 19.x | 主流前端框架 |
| 状态管理 | Zustand | 5.x | 轻量级状态管理 |
| 组件库 | Ant Design | 6.x | 企业级 UI 组件 |
| AI 集成 | Vercel AI SDK | 6.x | LLM 对话支持 |
| OpenHarness | @openharness/react | 1.0.1 | OpenHarness 平台集成 |

### 前端模块结构

```
frontend/src/modules/qa/
├── providers/
│   └── QAIProvider.tsx       # OpenHarness Provider 集成
├── hooks/
│   ├── useQAI.ts             # 问答交互状态管理
│   ├── useSession.ts          # 会话管理（列表/CRUD）
│   └── useChatStorage.ts      # localStorage 持久化
├── components/
│   └── SessionDrawer.tsx      # 历史会话抽屉组件
├── pages/
│   ├── QAChatPage.tsx         # 问答应容器页面
│   └── QAChat.tsx            # 问答组件（含统计 Tab）
└── index.ts                  # 模块导出
```

### 核心组件关系

```
QAChatPage (主容器)
├── ChatHeader        # 头部导航栏
├── MessageList       # 消息列表渲染
├── ChatInput        # 文本输入 + 发送按钮
└── SessionDrawer    # 历史会话抽屉
    └── useSession   # 会话管理钩子
```

### 状态管理架构

```typescript
// useQAI - 问答状态
interface UseQAIOptions {
  sessionId?: string;
  onError?: (error: Error) => void;
}

interface UseQAIReturn {
  messages: QAMessage[];           // 消息列表
  sendMessage: (content: string) => void;
  status: 'idle' | 'submitting' | 'streaming' | 'error' | 'waiting_for_input';
  sessionId: string | null;
  clearMessages: () => void;
  stop: () => void;                // 中止生成
}

// useSession - 会话管理
interface UseSessionReturn {
  sessions: Session[];
  loading: boolean;
  error: Error | null;
  fetchSessions: () => Promise<void>;
  loadSession: (sessionId: string) => Promise<Session | null>;
  deleteSession: (sessionId: string) => Promise<boolean>;
}
```

### API 集成

**后端接口**：

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 问答 | POST | `/api/qa/ask` | 发送问题，获取回答 |
| 会话列表 | GET | `/api/qa/sessions` | 获取会话列表 |
| 会话详情 | GET | `/api/qa/sessions/{id}` | 获取指定会话 |
| 删除会话 | DELETE | `/api/qa/sessions/{id}` | 删除指定会话 |
| 会话历史 | GET | `/api/qa/sessions/{id}/history` | 获取消息历史 |
| 提交反馈 | POST | `/api/qa/sessions/{id}/feedback` | 提交问答反馈 |

### 会话持久化策略

```typescript
// localStorage 存储键策略
function getStorageKey(sessionId: string | null): string {
  return sessionId
    ? `qa_chat_state_${sessionId}`
    : 'qa_chat_state_default';
}

// 防抖写入：500ms
const DEBOUNCE_MS = 500;
```

### OpenHarness Provider 集成

```tsx
import { OpenHarnessProvider } from '@openharness/react';

function QAIProvider({ children }: QAIProviderProps) {
  return (
    <OpenHarnessProvider>
      {children}
    </OpenHarnessProvider>
  );
}
```

### 错误处理机制

| 错误类型 | 处理策略 | 用户体验 |
|---------|---------|---------|
| 网络错误 | 重试 3 次，指数退避 | 显示"网络异常" |
| 超时错误 | AbortController 取消 | 显示"请求超时" |
| 服务端错误 | 降级到 Mock 数据 | 显示友好错误提示 |
| 认证错误 | 跳转登录页 | 提示重新登录 |

## 关联

- 关联 ADR-002（Graphiti 知识图谱）
- 关联 ADR-005（分层 Agent 架构）
- 关联 M-12 DESIGN.md（详细架构设计）
- 影响 WR-13（问答引擎）
- 关联 @openharness/react 集成方案（[INTEGRATION.md](../03-modules/qa_engine/INTEGRATION.md)）
- 关联 API 使用文档（[API.md](../03-modules/qa_engine/API.md)）
