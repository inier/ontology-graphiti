---
id: odap.l3.qa-engine-integration
status: active
owner: module-owner
version: ''
layer: L3
concern: module-design
lifecycle: living
superseded_by: ''
supersedes: []
last_verified: '2026-10-22'
citations: []
---

# 问答引擎模块 (QA Engine) - 集成方案

> **文档版本**: 2.0.0 | **日期**: 2026-10-22 | **模块**: M-12
>
> **v2.0 变更说明**：依据 [ADR-099](../../07-adr/ADR-099_frontend-agent-protocol-agui.md) 全面重写。v1.0（2026-04-28）以 `@openharness/react` + Vercel AI SDK 5 data stream 为集成主线，该路线**已废弃**，依赖已移除。现行为 **AG-UI** 协议。

---

## 1. 模块概述

### 1.1 集成目标

前端问答与智能助手能力统一由 `ai-assistant` 模块承载，协议层统一为 **AG-UI**。

`qa` 模块在现行架构下承担两件事：

1. **NL 本体查询**：`QueryPage` + `nlQueryStore` + 三检索支柱五阶段管线（见 `API.md`）；
2. **AG-UI 协议底座**：`qa/agui/AGUIProvider.tsx` 作为通用 AG-UI 客户端，同时服务 QA 与本体设计器两个命名空间。

对话入口页面 `pages/QAPage.tsx` 不再自建聊天实现，直接渲染 `AIChatPanel`：

```tsx
// apps/web/src/modules/qa/pages/QAPage.tsx（实况）
import { AIChatPanel } from '@/modules/ai-assistant';

export function QAPage({ agentId }: { agentId?: string }) {
  return (
    <AIChatPanel
      mode="full"
      title="智能问答"
      workspaceId="default"
      context={agentId ? { agent_id: agentId } : undefined}
    />
  );
}
```

### 1.2 技术栈（实况，2026-10-22 核对）

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| UI 框架 | React 19 | 前端应用框架 |
| 状态管理 | Zustand 5 | `nlQueryStore` 等 |
| UI 组件库 | Ant Design 6 | 企业级 React 组件库 |
| **Agent 协议** | **AG-UI** | 自研客户端（`AGUIProvider`），非第三方 SDK |
| 流式传输 | `apiClient.stream()` | `fetch` + `ReadableStream`，自动注入 Bearer、处理 401/403 |

**明确不在技术栈中**：`@openharness/react`、`ai`（Vercel AI SDK）。二者于 2026-10-22 移除，依据见 [ADR-099](../../07-adr/ADR-099_frontend-agent-protocol-agui.md)。

---

## 2. 协议与端点

### 2.1 为什么是 AG-UI

[ADR-070](../../07-adr/ADR-070_基于OpenHarness全能力的AI助手架构.md) 已定调：

> 所有降级路径输出相同的 **AG-UI 事件格式**，前端无需感知降级。
> AG-UI 协议覆盖所有场景 —— 前端只需一套解析器。

后端实现在 `apps/api/odap/infra/openharness/agui/`（`agui_handler.py`、`agui_transport.py`、`agui_models.py`、`agui_extensions.py`、`web_channel.py`），**不实现** AI SDK data stream 协议。

### 2.2 端点清单

| 用途 | 方法 | 路径 | 消费方 |
|------|------|------|--------|
| 对话主链路（AG-UI 事件流） | POST | `/api/assistant/chat` | `useAIChat` |
| 工具直调 | POST | `/api/assistant/tools/execute` | `useAIChat.executeTool` |
| 会话列表 | GET | `/api/qa/sessions?workspace_id=` | `useAIChat.loadSessions` |
| 会话详情 | GET | `/api/qa/sessions/{session_id}` | `useAIChat.selectSession` |
| 删除会话 | DELETE | `/api/qa/sessions/{session_id}` | `useAIChat.deleteSession` |
| AG-UI 通用 run（QA 命名空间） | POST | `/api/ag-ui/run` | `AGUIProvider`（`namespace='ag-ui'`） |
| AG-UI 通用 run（本体设计器命名空间） | POST | `/api/ontology-assistant/run` | `AGUIProvider`（`namespace='ontology-assistant'`） |

> **鉴权**：以上端点后端均挂 `Depends(get_current_user)`。走 `apiClient` 的调用自动注入 `Authorization: Bearer <JWT>`；**裸 `fetch` / `EventSource` 不会**，必须显式传 token（见 §3.2 注意事项）。

### 2.3 事件类型

`AGUIEventType`（`qa/agui/agui_types.ts:10`）共 17 种：

```
RUN_STARTED / RUN_FINISHED / RUN_ERROR
STEP_STARTED / STEP_FINISHED
TEXT_MESSAGE_START / TEXT_MESSAGE_CONTENT / TEXT_MESSAGE_END
TOOL_CALL_START / TOOL_CALL_ARGS / TOOL_CALL_END / TOOL_CALL_CHUNK / TOOL_CALL_RESULT
STATE_SNAPSHOT / STATE_DELTA
MESSAGES_SNAPSHOT / ACTIVITY_SNAPSHOT
```

运行结果三态：`RunOutcome = 'success' | { type: 'interrupt'; interrupts } | { type: 'error'; error }`。

---

## 3. 两套集成入口

### 3.1 页面级：`AIChatPanel`（推荐）

绝大多数场景直接用组件，不必自己处理事件流。

**Props**（`ai-assistant/components/AIChatPanel.tsx:30`）：

| Prop | 类型 | 说明 |
|------|------|------|
| `mode` | `'full' \| 'compact'` | full=全屏；compact=侧边栏/对话框 |
| `ontologyId` | `string` | 当前本体 ID（本体设计页传入） |
| `workspaceId` | `string` | 工作空间 ID（OPA 鉴权用） |
| `context` | `Record<string, unknown>` | 额外上下文（如 `{ agent_id }`） |
| `title` | `string` | 面板标题 |
| `welcomeMessage` | `string` | 欢迎语 |
| `onOntologyChanged` | `() => void` | 本体被 AI 修改后回调，用于触发设计器刷新 |
| `asDrawer` | `boolean` | compact 模式下是否以 Drawer 呈现（false=内嵌） |
| `open` / `onClose` | `boolean` / `() => void` | Drawer 模式的开关与关闭回调 |

底层 hook 为 `useAIChat(options)`（`ai-assistant/hooks/useAIChat.ts:134`），返回：

```ts
{
  messages, sendMessage, clearMessages, sending,
  executeTool, analysisResults, clearAnalysisResults,
  sessions, currentSessionId, loadSessions, selectSession,
  deleteSession, createNewSession,
  cancel, error, ontologyContext,
}
```

### 3.2 底层：`AGUIProvider` + `useAGUIContext`

适用场景：需要自行消费事件流（如 `StatePanel` 从 `STATE_SNAPSHOT`/`STATE_DELTA` 派生共享状态）、需要 HITL interrupt/resume、或需要独立命名空间。

**Config**（`qa/agui/AGUIProvider.tsx:91`）：

| 字段 | 默认 | 说明 |
|------|------|------|
| `apiBase` | `VITE_API_BASE` | API 基础 URL |
| `token` | — | Bearer JWT |
| `workspaceId` | — | 工作空间 ID |
| `onEvent` | — | 收到任意 AG-UI 事件时的回调 |
| `autoReconnect` | `true` | 断线自动重连 |
| `heartbeatTimeoutMs` | `120000` | SSE 心跳超时（本体设计器操作较慢，故放宽） |
| `namespace` | `'ag-ui'` | `'ag-ui'`（QA）或 `'ontology-assistant'`（本体设计器） |
| `maxRetries` | `2` | 最大重试次数，退避 `1000ms → 3000ms` |

另接受 `children` / `fallback`（ErrorBoundary 降级 UI）/ `onError`。

**Context**（`useAGUIContext()`，`:110`）：

| 字段 | 说明 |
|------|------|
| `status` | `'idle' \| 'streaming' \| 'interrupted' \| 'error' \| 'cancelled'` |
| `events` | 累积事件流（上限 1000 条） |
| `messages` | `messageId → { role, content, toolCalls }` |
| `pendingInterrupts` | 待用户响应的 interrupts |
| `error` | 当前错误 |
| `runAgent(input)` | 发起新 run（可携带 resume） |
| `resume(interruptId, response)` | 响应 interrupt，自动构造下一个携带 resume 的 run |
| `cancel()` / `clear()` | 取消当前 run / 清空状态 |

> **⚠️ 必须显式传 `token`**：`AGUIProvider` 走裸 `fetch` + `EventSource`，绕过 `apiClient` 的鉴权拦截器。不传 token 就是必然 401。`QACopilotDemoPage` 曾因此踩坑，现行写法是 `apiKey={token ?? storeToken}`。

---

## 4. 目录结构（现行）

```
apps/web/src/modules/
├── qa/
│   ├── agui/                      # AG-UI 协议底座
│   │   ├── AGUIProvider.tsx       # Provider + useAGUIContext（heartbeat/重连/命名空间/ErrorBoundary）
│   │   ├── agui_types.ts          # 事件与卡片类型（镜像后端 agui_models.py）
│   │   ├── CardRegistry.tsx       # <CardRenderer>
│   │   ├── cardRegistryTable.tsx  # card_type → 组件注册表
│   │   ├── cardComponents.tsx     # action / confirm / input / unknown
│   │   ├── HITLPanel.tsx          # interrupt 人机协同面板
│   │   ├── StatePanel.tsx         # 共享状态展示（STATE_SNAPSHOT/DELTA）
│   │   └── QACopilotDemoPage.tsx  # 演示页
│   ├── components/                # NL 查询与卡片渲染组件
│   │   ├── InlineChart.tsx        # 图表卡片渲染（6 类）
│   │   ├── TemporalCardView.tsx   # 时序卡片
│   │   └── ReportLinkView.tsx     # 报告链接卡片
│   ├── pages/                     # QAPage / QueryPage / EvaluationPage
│   ├── services/nlQueryApi.ts     # NL 查询 API
│   ├── stores/nlQueryStore.ts     # NL 查询状态
│   └── types.ts                   # 卡片数据类型（ChartSpec / TemporalCard / ReportLink）
└── ai-assistant/
    ├── components/AIChatPanel.tsx # 对话面板（唯一聊天 UI 实现）
    └── hooks/useAIChat.ts         # 对话 hook（AG-UI 事件解析 + 会话管理 + 工具调用）
```

---

## 5. 状态与持久化

| 状态 | 载体 | 说明 |
|------|------|------|
| 对话消息 | `useAIChat.messages`（组件内 state） | 随会话切换 |
| 会话列表/详情 | 后端 `/api/qa/sessions` | 由 `useAIChat` 拉取，非 localStorage |
| NL 查询流程 | `nlQueryStore`（Zustand） | 意图→计划→检索→生成五阶段 |
| AG-UI 事件流 | `AGUIProvider` context | 上限 1000 条，`clear()` 清空 |

> 旧 `useChatStorage`（localStorage 会话持久化）已于 2026-10-21 随 QA v1 栈删除，会话持久化改由后端承担。

---

## 6. 已知能力边界（对接前必读）

| 能力 | 状态 | 说明 |
|------|:----:|------|
| 文本流式回答 | ✅ | `TEXT_MESSAGE_CONTENT` |
| 工具调用 | ✅ | `TOOL_CALL_START/ARGS/END/RESULT`，`useAIChat.executeTool` 可直调 |
| HITL interrupt / resume | ✅ | 仅 `AGUIProvider` 路径 |
| 共享状态（memory/skills/sessions） | ✅ | 仅 `AGUIProvider` 路径（`StatePanel`） |
| 图表卡片 | ⚠️ 部分 | `InlineChart` 支持 line / bar / pie / scatter / radar / heatmap；`map` / `network` **显式报不支持**（不静默降级成折线图） |
| `qa_engine` 的 `{type:"chart"}` / `{type:"temporal"}` 自定义事件 | ❌ 未消费 | `useAIChat` 类型里保留了 `charts?` / `temporal?` 字段，但**无渲染逻辑**。需要图表时走 AG-UI `CardType='chart'` 卡片 |

---

## 7. 历史方案（已废弃）

v1.0 的集成主线是 `@openharness/react`（provider + AI SDK 5 transport）+ 自研 `useQAI`：

- `useQAI` / `useChatStorage` / `qaStore` / `qaApi` / `QAIProvider` / `ChartRenderer` 共 **6 个文件 / 782 行**，已于 2026-10-21 整批删除（归档：`.workbuddy/archive/zero-ref-2026-10-20/modules/qa/`，逐文件 sha256 校验）。
- `@openharness/react` 与 `ai` 两个依赖已于 2026-10-22 移除。

**为什么不复活**：SDK 的 `createOHTransport` 只解析 AI SDK 5 data stream 协议，而后端实现的是 AG-UI —— 协议层不匹配，装上也用不了。复活它等于在 AG-UI 之外再造第二套对话引擎。

**复引入条件**（唯一合法路径，见 ADR-099 第 4 条）：①后端新增 AI SDK 5 data stream 端点；②ADR-070「前端只需一套解析器」被显式修订为允许双协议。

---

## 8. 相关文档

- [ADR-099 前端 Agent 集成协议收敛为 AG-UI](../../07-adr/ADR-099_frontend-agent-protocol-agui.md)
- [ADR-070 基于 OpenHarness 全能力的 AI 助手架构](../../07-adr/ADR-070_基于OpenHarness全能力的AI助手架构.md)
- [ADR-039 问答引擎架构](../../07-adr/ADR-039_qa_engine_architecture.md)（其 Provider 集成片段已被 ADR-099 取代）
- [API.md](./API.md) — 端点契约与错误码
- [DESIGN.md](./DESIGN.md) — 架构设计
- [OPEN-DECISIONS.md](../../decisions/OPEN-DECISIONS.md) — QA 旧栈删除台账（RESOLVED 条目）
