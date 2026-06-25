# AI 助手独立组件化架构设计

> **文档版本**: v1.0
> **日期**: 2026-06-21
> **状态**: Proposed
> **关联 ADR**: ADR-001(OpenHarness), ADR-002(Graphiti), ADR-003(OPA), ADR-004(Skill), ADR-005(分层Agent), ADR-046(模块化单体)

---

## 1. 背景与问题

### 1.1 当前状态：双轨并行

项目中存在 **两套独立的 AI 助手实现**，互不复用：

| 维度 | ODAP 自建 `assistant/` | OpenHarness AGUI 层 |
|------|----------------------|---------------------|
| **后端** | `odap/biz/core/assistant/` | `odap/infra/openharness/agui/` |
| **工具** | 字典注册表 16 个工具 | OH BaseTool（GraphitiToolAdapter 适配） |
| **协议** | 自定义 SSE（6 类事件） | AG-UI v0.x（17 类事件） |
| **LLM 路径** | ZhipuAI 直接调用 | OpenHarness QueryEngine |
| **HITL** | 无 | Interrupt + asyncio.Future |
| **鉴权** | 无 | OPA 远程 + 本地回退 |
| **OntologyService 耦合** | 直接导入 | 通过 QueryEngine 间接 |
| **是否基于 OpenHarness** | ❌ 否 | ✅ 是 |

**后果**：功能重复、维护成本翻倍、协议不统一、无法接入 IM。

### 1.2 OHMO 的角色缺失

OHMO（`openharness/ohmo/`）是 OpenHarness 的个人 AI Agent 应用，已具备：
- **Gateway 模块**：12 个 IM 渠道适配器（飞书/Slack/Telegram/Discord/钉钉等）
- **Session Runtime Pool**：每会话 RuntimeBundle 管理
- **QueryEngine 集成**：完整的 Agent Loop

但 ODAP 的 AI 助手完全没有利用 OHMO — 无法接入任何 IM。

### 1.3 用户需求

1. 将 AI 助手及相关代码 **独立成单独组件**（前端 + 后端）
2. 规划 **OHMO 和 AI 助手的依赖和相互支撑**
3. 支持 **AGUI 协议** 作为统一通信协议
4. 通过 **OHMO 接入其他 IM**（飞书/Slack/Telegram 等）
5. 全过程 **完全基于 OpenHarness**

---

## 2. 架构设计

### 2.1 核心原则：Host-Plugin 架构

```
┌─────────────────────────────────────────────────────────────┐
│                      用户交互层                               │
│   Web UI (full/compact)  │  IM Channels (12+)               │
└────────────┬─────────────┴──────────────┬───────────────────┘
             │                            │
     ┌───────▼────────┐          ┌───────▼────────┐
     │  Web Channel   │          │  IM Channels   │
     │  Adapter (NEW) │          │  (existing)    │
     └───────┬────────┘          └───────┬────────┘
             │                            │
             └────────────┬───────────────┘
                          │
                  ┌───────▼────────┐
                  │  OHMO Gateway  │  ← 统一入口
                  │  (gateway/)    │    会话路由 + RuntimeBundle 管理
                  └───────┬────────┘
                          │
                  ┌───────▼────────┐
                  │  OpenHarness   │  ← Agent 运行时
                  │  QueryEngine   │    Agent Loop + ToolRegistry
                  │  + AG-UI 协议  │    Hooks + Permission + MCP
                  └───────┬────────┘
                          │
          ┌───────────────▼───────────────┐
          │   ODAP AI Assistant Plugin    │  ← 独立组件
          │   (tools + skills + hooks)    │    领域能力提供者
          └───────────────────────────────┘
```

**四层角色**：

| 层 | 角色 | 职责 |
|----|------|------|
| **OHMO Gateway** | Host（宿主） | 统一入口、会话管理、渠道路由、RuntimeBundle 生命周期 |
| **OpenHarness** | Framework（框架） | Agent Loop、ToolRegistry、HookExecutor、PermissionChecker、MCP |
| **AG-UI** | Protocol（协议） | 17 类事件 wire format、HITL Interrupt、State Snapshot |
| **AI Assistant Plugin** | Plugin（插件） | 领域工具（本体查询/设计/写入）、Skills、Hooks、系统提示词 |

### 2.2 依赖关系：相互支撑

```
                    ┌─────────────────────┐
                    │   ODAP AI Assistant │
                    │      Plugin         │
                    │  (tools/skills/     │
                    │   hooks/prompts)    │
                    └─────────┬───────────┘
                              │ 注册工具/技能/钩子
                              ▼
                    ┌─────────────────────┐
                    │     OpenHarness     │
                    │    QueryEngine      │◄──── OHMO 提供 RuntimeBundle
                    │  (Agent Loop)       │      (Engine + Tools + Hooks + Perms)
                    └─────────┬───────────┘
                              │ 流式事件
                              ▼
                    ┌─────────────────────┐
                    │    OHMO Gateway     │
                    │  (Session Pool +    │────► IM Channels (飞书/Slack/...)
                    │   Channel Routing)  │────► Web Channel (SSE)
                    └─────────────────────┘
```

**OHMO 依赖 AI Assistant Plugin**（获取领域能力）：
- OHMO 的 QueryEngine 需要工具才能工作
- AI Assistant Plugin 提供本体工具（查询/设计/写入）、领域 Skills
- 没有 Plugin，OHMO 只是一个通用聊天机器人，无领域知识

**AI Assistant 依赖 OHMO**（获取运行时基础设施）：
- AI Assistant 的工具需要一个运行时来执行
- OHMO 提供 Gateway（会话管理、渠道路由）
- OHMO 提供 RuntimeBundle（QueryEngine + ToolRegistry + HookExecutor）
- 没有 OHMO，AI Assistant 只是一堆工具集合，无运行时

**相互支撑关系**：
- OHMO 提供运行时基础设施 → AI Assistant 提供领域能力
- AG-UI 提供统一通信协议 → 前端和 IM 共享事件格式
- OpenHarness 提供 Agent Loop → 工具自动调度执行

### 2.3 数据流

#### Web UI 路径

```
用户输入
  │
  ▼
WebChannelAdapter (HTTP POST)
  │  构建 InboundMessage(channel="web", chat_id=session_id, sender_id=user_id)
  ▼
OHMO Gateway → MessageBus → OhmoGatewayBridge
  │  session_key = "web:{session_id}:{thread_id}:{user_id}"
  ▼
OhmoSessionRuntimePool.get_bundle(session_key)
  │  创建/复用 RuntimeBundle（QueryEngine + ToolRegistry + Hooks）
  │  ToolRegistry 已注册 AI Assistant Plugin 的工具
  ▼
QueryEngine.submit_message(user_input)
  │  Agent Loop: LLM → Tool Selection → Permission → Execute → Loop
  │  工具执行时调用 OntologyService（通过 ToolExecutionContext 注入）
  ▼
StreamEvents (AssistantTextDelta, ToolExecutionStarted, ...)
  │
  ▼
agui_transport.to_agui_events() → AG-UI Events (17 类)
  │  包括: TEXT_MESSAGE_*, TOOL_CALL_*, CUSTOM(ONTOLOGY_CHANGED), ...
  ▼
WebChannelAdapter → SSE Response → 前端 useAIChat
```

#### IM 路径

```
IM 消息 (飞书/Slack/Telegram/...)
  │
  ▼
ChannelAdapter (FeishuChannel / SlackChannel / ...)
  │  构建 InboundMessage(channel="feishu", chat_id=group_id, sender_id=user_id)
  ▼
MessageBus → OhmoGatewayBridge
  │  session_key = "feishu:{group_id}:{thread_id}:{user_id}"
  ▼
OhmoSessionRuntimePool.get_bundle(session_key)
  │  同上：创建/复用 RuntimeBundle
  ▼
QueryEngine.submit_message(user_input)
  │  同上：Agent Loop
  ▼
GatewayStreamUpdate (kind, text, metadata)
  │  OH StreamEvent → GatewayStreamUpdate 转换
  ▼
OhmoGatewayBridge → OutboundMessage → ChannelAdapter
  │  发送回复到 IM
```

---

## 3. 后端独立组件设计

### 3.1 目录结构

```
odap/plugins/ai_assistant/              # 独立 OH Plugin 组件
├── plugin.json                          # OH Plugin 清单（声明 tools/skills/hooks）
├── __init__.py                          # 插件入口
├── tools/                               # OH BaseTool 实现
│   ├── __init__.py
│   ├── ontology_query.py                # 查询工具（list_entities, search_entities, query_relations, query_temporal）
│   ├── ontology_design.py               # 设计工具（get_ontology_context, suggest_properties, suggest_relations, check_completeness）
│   ├── ontology_write.py                # 写操作工具（add_property, update_property, create_object_type, add_properties 等）
│   └── graphiti_search.py               # Graphiti 时序知识搜索
├── skills/                              # OH Skill 格式（.md）
│   ├── ontology-overview.md             # 本体概况技能
│   └── completeness-check.md            # 完整性检查技能
├── hooks/                               # OH Hook
│   └── ontology_changed_hook.py         # PostToolUse 钩子：写操作后通知前端刷新
├── prompts/                             # 系统提示词
│   └── system_prompt.py                 # AI 助手系统提示词组装
├── api/                                 # Web API 适配层（薄层）
│   ├── __init__.py
│   ├── routes.py                        # /api/assistant/* → OHMO Gateway 桥接
│   └── web_channel.py                   # WebChannelAdapter 实现
├── context.py                           # ToolExecutionContext 扩展（注入 OntologyService）
├── config.py                            # 组件配置
└── README.md
```

### 3.2 Plugin 清单（plugin.json）

```json
{
  "name": "odap-ai-assistant",
  "version": "1.0.0",
  "description": "ODAP AI Assistant — 本体驱动分析决策平台的 AI 助手插件",
  "type": "plugin",
  "tools": [
    "tools.ontology_query",
    "tools.ontology_design",
    "tools.ontology_write",
    "tools.graphiti_search"
  ],
  "skills": [
    "skills/ontology-overview.md",
    "skills/completeness-check.md"
  ],
  "hooks": [
    {
      "event": "PostToolUse",
      "handler": "hooks.ontology_changed_hook:OntologyChangedHook"
    }
  ],
  "permissions": {
    "tools": {
      "ontology_write.*": "editor",
      "ontology_query.*": "viewer",
      "ontology_design.*": "viewer"
    }
  }
}
```

### 3.3 工具实现模式（BaseTool）

每个工具继承 OpenHarness 的 `BaseTool`，通过 `ToolExecutionContext` 获取 `OntologyService`：

```python
# tools/ontology_query.py
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult
from pydantic import BaseModel, Field

class ListEntitiesInput(BaseModel):
    ontology_id: str = Field(description="本体ID")
    entity_type: str = Field(default="", description="实体类型（可选）")
    limit: int = Field(default=20, description="返回数量上限")

class ListEntitiesTool(BaseTool):
    name = "list_entities"
    description = "列出本体中的实体列表"
    input_model = ListEntitiesInput

    async def execute(self, arguments: ListEntitiesInput, context: ToolExecutionContext) -> ToolResult:
        # 从 context 获取 OntologyService（由 Plugin 注册时注入）
        ontology_service = context.metadata.get("ontology_service")
        if not ontology_service:
            return ToolResult(output="错误：OntologyService 不可用", error=True)

        entities = await ontology_service.list_entities(
            ontology_id=arguments.ontology_id,
            entity_type=arguments.entity_type or None,
            limit=arguments.limit,
        )
        return ToolResult(output=json.dumps(entities, ensure_ascii=False))
```

### 3.4 Web Channel Adapter

Web UI 作为 OHMO 的一个 "web" 渠道，实现 `BaseChannel` 接口：

```python
# api/web_channel.py
from openharness.channels.impl.base import BaseChannel
from openharness.channels.bus.events import InboundMessage, OutboundMessage
from openharness.channels.bus.queue import MessageBus

class WebChannelAdapter(BaseChannel):
    """Web UI 渠道适配器 — 将 HTTP 请求桥接到 OHMO Gateway。

    与飞书/Slack 等 IM 渠道并列，共享同一套：
    - MessageBus 消息总线
    - OhmoSessionRuntimePool 会话池
    - QueryEngine Agent Loop
    """

    name = "web"

    def __init__(self, config: dict, bus: MessageBus):
        super().__init__(config, bus)

    async def start(self) -> None:
        """Web 渠道不需要长连接监听，由 HTTP 路由触发。"""
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        """Web 渠道的回复通过 SSE 流式返回，不需要主动推送。"""
        pass  # SSE 由 API 路由层处理

    async def receive_message(
        self,
        content: str,
        chat_id: str,
        sender_id: str,
        metadata: dict = None,
    ) -> InboundMessage:
        """从 HTTP 请求构建 InboundMessage 并发布到 MessageBus。"""
        msg = InboundMessage(
            channel="web",
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            metadata=metadata or {},
        )
        await self.bus.publish_inbound(msg)
        return msg
```

### 3.5 API 路由层（薄层）

```python
# api/routes.py
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

@router.post("/chat")
async def chat(request: ChatRequest, user: dict = Depends(get_current_user)):
    """SSE 流式聊天 — 桥接到 OHMO Gateway。

    不再自建 LLM 调用逻辑，完全委托给 OHMO Gateway：
    1. 构建 InboundMessage
    2. 发布到 MessageBus
    3. 消费 OhmoGatewayBridge 的流式输出
    4. 通过 agui_transport 转换为 AG-UI 事件
    5. SSE 返回
    """
    # ...桥接到 OHMO Gateway...
    return StreamingResponse(
        _stream_via_ohmo(request, user),
        media_type="text/event-stream",
    )
```

### 3.6 OntologyChanged Hook

```python
# hooks/ontology_changed_hook.py
from openharness.hooks.events import HookEvent

class OntologyChangedHook:
    """PostToolUse 钩子：写操作工具执行后触发 ONTOLOGY_CHANGED 事件。

    触发条件：工具名匹配 ontology_write.* 模式
    效果：在 AG-UI 事件流中注入 CUSTOM:ONTOLOGY_CHANGED 事件，
          前端收到后刷新本体设计器。
    """

    TOOL_PATTERN = "ontology_write."

    async def execute(self, event: HookEvent, context) -> None:
        if not event.tool_name.startswith(self.TOOL_PATTERN):
            return
        # 通过 context 注入 CUSTOM 事件到流式输出
        await context.emit_custom("ONTOLOGY_CHANGED", {
            "tool": event.tool_name,
            "ontology_id": context.metadata.get("ontology_id"),
        })
```

---

## 4. 前端独立组件设计

### 4.1 目录结构

```
frontend/src/modules/ai-assistant/      # 独立前端模块
├── index.ts                             # 统一导出
├── hooks/
│   ├── useAIChat.ts                     # 统一 Hook（基于 AG-UI 协议）
│   ├── useOHMOGateway.ts                # OHMO Gateway 适配器
│   └── useToolExecution.ts              # 直接工具调用
├── components/
│   ├── AIChatPanel.tsx                  # 统一组件（full/compact 双模式）
│   ├── MessageList.tsx                  # 消息渲染（含 tool_calls + sources + reasoning）
│   ├── ChatInput.tsx                    # 输入框 + 快捷操作
│   ├── SessionSidebar.tsx               # 会话列表（full 模式）
│   └── ToolCallDisplay.tsx              # 工具调用状态展示
├── adapters/
│   └── aguiAdapter.ts                   # AG-UI 协议适配（SSE → React State）
├── types.ts                             # 类型定义
└── styles.ts                            # Emotion CSS 样式
```

### 4.2 useAIChat Hook（AG-UI 协议）

```typescript
// hooks/useAIChat.ts
export function useAIChat(options: UseAIChatOptions): UseAIChatReturn {
  // 基于 AG-UI 协议的统一 Hook
  // 1. 发送消息 → POST /api/assistant/chat
  // 2. 解析 AG-UI SSE 事件流（17 类事件）
  // 3. 管理消息状态、工具调用状态、分析结果
  // 4. 监听 ONTOLOGY_CHANGED → 触发 onOntologyChanged 回调
  // 5. 会话管理（通过 OHMO Gateway 的 session API）
}
```

### 4.3 AIChatPanel 组件（双模式）

```typescript
// components/AIChatPanel.tsx
export function AIChatPanel({ mode, ontologyId, ... }: AIChatPanelProps) {
  // full 模式：SessionSidebar + 全屏聊天区
  // compact 模式：紧凑布局，适合 Drawer/内嵌
  // 两种模式共享 useAIChat hook
}
```

### 4.4 引用方式

```typescript
// 从独立模块导入
import { AIChatPanel } from '@/modules/ai-assistant';
import { useAIChat } from '@/modules/ai-assistant';

// 在 QAPage 中使用
<QAPage>
  <AIChatPanel mode="full" title="智能问答" />
</QAPage>

// 在 OntologyDesignerPage 中使用
<Drawer>
  <AIChatPanel mode="compact" ontologyId={id} onOntologyChanged={refresh} />
</Drawer>

// 在 AdminLayout 中使用
<ExtensionPanel>
  <AIChatPanel mode="compact" />
</ExtensionPanel>
```

---

## 5. OHMO ↔ AI Assistant 依赖矩阵

### 5.1 OHMO 对 AI Assistant 的依赖

| OHMO 组件 | 依赖的 AI Assistant 能力 | 依赖方式 |
|-----------|------------------------|----------|
| QueryEngine | 本体查询工具（list_entities 等） | ToolRegistry 自动注册 |
| QueryEngine | 本体设计工具（suggest_properties 等） | ToolRegistry 自动注册 |
| QueryEngine | 本体写入工具（create_object_type 等） | ToolRegistry 自动注册 |
| System Prompt | 领域系统提示词 | Plugin prompts/ 注入 |
| Skills | 领域技能（ontology-overview 等） | Plugin skills/ 加载 |
| Hooks | 写操作后刷新钩子 | Plugin hooks/ 注册 |

### 5.2 AI Assistant 对 OHMO 的依赖

| AI Assistant 组件 | 依赖的 OHMO 能力 | 依赖方式 |
|-------------------|-----------------|----------|
| 工具执行 | QueryEngine Agent Loop | OHMO RuntimeBundle |
| 工具执行 | ToolRegistry 工具调度 | OHMO RuntimeBundle |
| 权限检查 | PermissionChecker + OPA | OHMO RuntimeBundle |
| 生命周期钩子 | HookExecutor | OHMO RuntimeBundle |
| 会话管理 | OhmoSessionRuntimePool | OHMO Gateway |
| Web 接入 | WebChannelAdapter | OHMO Gateway |
| IM 接入 | IM Channel Adapters | OHMO Gateway |
| 记忆 | GraphitiMemoryAdapter | OHMO Memory |
| AG-UI 协议 | StreamEvent → AG-UI 映射 | agui_transport |

### 5.3 依赖方向不变量

```
AI Assistant Plugin  ──注册──►  OpenHarness ToolRegistry
                                 (单向依赖，Plugin 不反向调用 OHMO)

OHMO Gateway  ──创建──►  RuntimeBundle (含 ToolRegistry)
                          (OHMO 持有 RuntimeBundle，Plugin 的工具在其中执行)

Web/IM Channel  ──发布──►  MessageBus  ──消费──►  OhmoGatewayBridge
                                                ──调用──►  RuntimeBundle
```

**关键不变量**：AI Assistant Plugin **不直接依赖** OHMO Gateway。Plugin 只负责声明工具/技能/钩子，由 OHMO 在创建 RuntimeBundle 时加载和注册。

---

## 6. AGUI 协议统一

### 6.1 协议层架构

```
┌────────────────────────────────────────────┐
│           前端 / IM 客户端                   │
│  useAIChat (AG-UI SSE)  │  IM (OHMO Gateway)│
└──────────┬──────────────┴────────┬─────────┘
           │                       │
           │    AG-UI Events       │  GatewayStreamUpdate
           │    (17 类 wire format)│  (OH 内部格式)
           │                       │
    ┌──────▼──────┐        ┌──────▼──────┐
    │  Web API    │        │  OHMO       │
    │  /api/      │        │  Gateway    │
    │  assistant  │        │  bridge     │
    └──────┬──────┘        └──────┬──────┘
           │                       │
           └──────────┬────────────┘
                      │
              ┌───────▼────────┐
              │  agui_transport │  ← 统一转换层
              │  to_agui_events │
              └───────┬────────┘
                      │
              ┌───────▼────────┐
              │  OpenHarness   │
              │  StreamEvents  │
              └────────────────┘
```

### 6.2 事件映射

| OpenHarness StreamEvent | AG-UI Event | 用途 |
|------------------------|-------------|------|
| (run 开始) | RUN_STARTED | 标记 Agent Loop 开始 |
| AssistantTextDelta (首帧) | TEXT_MESSAGE_START | 文本消息开始 |
| AssistantTextDelta (增量) | TEXT_MESSAGE_CONTENT | 文本增量 |
| AssistantTurnComplete | TEXT_MESSAGE_END | 文本消息结束 |
| ToolExecutionStarted | TOOL_CALL_START + TOOL_CALL_ARGS + TOOL_CALL_END | 工具调用三件套 |
| ToolExecutionCompleted | TOOL_CALL_RESULT | 工具执行结果 |
| (HITL ask_user) | RUN_FINISHED (interrupts) | 等待用户确认 |
| (HITL permission) | RUN_FINISHED (interrupts) | 等待工具授权 |
| (自定义 ONTOLOGY_CHANGED) | CUSTOM | 本体变更通知 |
| (自定义 ANALYSIS_RESULT) | CUSTOM | 分析结果 |
| (run 结束) | RUN_FINISHED | 标记 Agent Loop 结束 |
| (错误) | RUN_ERROR | 错误事件 |

### 6.3 前端 AG-UI 解析

```typescript
// useAIChat 中的 SSE 解析（伪代码）
function parseAGUIEvent(rawData: string): AGUIEvent | null {
  const data = JSON.parse(rawData);
  switch (data.type) {
    case 'RUN_STARTED':
      setSending(true);
      break;
    case 'TEXT_MESSAGE_CONTENT':
      appendMessageDelta(data.delta);
      break;
    case 'TOOL_CALL_START':
      addToolCall(data.toolCallId, data.toolName);
      break;
    case 'TOOL_CALL_END':
      updateToolCallStatus(data.toolCallId, 'completed');
      break;
    case 'CUSTOM':
      if (data.name === 'ONTOLOGY_CHANGED') {
        onOntologyChanged?.();
      } else if (data.name === 'ANALYSIS_RESULT') {
        addAnalysisResult(data.data);
      }
      break;
    case 'RUN_FINISHED':
      if (data.outcome?.type === 'interrupt') {
        // HITL：显示确认对话框
        showInterruptDialog(data.outcome.interrupts);
      } else {
        setSending(false);
      }
      break;
  }
}
```

---

## 7. IM 接入方案

### 7.1 OHMO Gateway 架构

```
┌─────────────────────────────────────────────────────────┐
│                    IM 平台                               │
│  飞书 │ Slack │ Telegram │ Discord │ 钉钉 │ Email │ ... │
└────────┬──────┬──────────┬──────────┬──────┬──────┬────┘
         │      │          │          │      │      │
    ┌────▼──────▼──────────▼──────────▼──────▼──────▼────┐
    │              Channel Adapters                       │
    │  (FeishuChannel, SlackChannel, TelegramChannel,    │
    │   DiscordChannel, DingTalkChannel, EmailChannel)   │
    └────────────────────┬───────────────────────────────┘
                         │ InboundMessage / OutboundMessage
                         │
                    ┌────▼────┐
                    │  Message │  ← 统一消息总线
                    │   Bus    │
                    └────┬────┘
                         │
                    ┌────▼────┐
                    │ Gateway  │  ← 会话桥接
                    │ Bridge   │
                    └────┬────┘
                         │
                    ┌────▼────┐
                    │ Session  │  ← 每会话 RuntimeBundle
                    │ Runtime  │    (QueryEngine + Tools + Hooks)
                    │   Pool   │
                    └─────────┘
```

### 7.2 渠道接入流程

**接入新 IM 渠道的步骤**：

1. **实现 ChannelAdapter**：继承 `BaseChannel`，实现 `start()` / `stop()` / `send()`
2. **配置渠道参数**：在 OHMO 配置中添加渠道配置（API Token、Webhook URL 等）
3. **注册到 ChannelManager**：在 `openharness/src/openharness/channels/impl/manager.py` 注册
4. **启动 OHMO Gateway**：`ohmo gateway start --channels feishu,slack`

**会话路由**：
```
session_key = f"{channel}:{chat_id}:{thread_id}:{sender_id}"

示例：
  web:user123:session-abc:user123
  feishu:group_456:thread_789:user_001
  slack:C123456:none:U789012
```

### 7.3 Web 渠道（新增）

Web UI 作为 OHMO 的一个 "web" 渠道：

```python
# 注册 Web Channel
channel_manager.register("web", WebChannelAdapter)

# Web 渠道的会话路由
session_key = f"web:{session_id}:{thread_id}:{user_id}"

# Web 渠道的消息流
HTTP POST /api/assistant/chat
  → WebChannelAdapter.receive_message()
  → MessageBus.publish_inbound()
  → OhmoGatewayBridge 消费
  → OhmoSessionRuntimePool.get_bundle()
  → QueryEngine.submit_message()
  → StreamEvents → agui_transport → AG-UI SSE → 前端
```

---

## 8. 迁移路线

### Phase 1: 后端插件化（2-3 周）

**目标**：将 `assistant/` 模块迁移为 OH Plugin 结构

| 步骤 | 内容 | 产出 |
|------|------|------|
| 1.1 | 创建 `odap/plugins/ai_assistant/` 目录结构 | 目录 + plugin.json |
| 1.2 | 将 tools.py 的 16 个工具迁移为 BaseTool 子类 | tools/*.py |
| 1.3 | 通过 ToolExecutionContext 注入 OntologyService（消除直接导入） | context.py |
| 1.4 | 创建 OntologyChangedHook（PostToolUse 钩子） | hooks/ |
| 1.5 | 编写 OH Skill 格式的领域技能 | skills/*.md |
| 1.6 | 编写系统提示词组装 | prompts/ |

**验收**：Plugin 可被 OpenHarness PluginLoader 加载，工具注册到 ToolRegistry。

### Phase 2: Web Channel + OHMO 集成（2-3 周）

**目标**：Web UI 通过 OHMO Gateway 路由

| 步骤 | 内容 | 产出 |
|------|------|------|
| 2.1 | 实现 WebChannelAdapter | api/web_channel.py |
| 2.2 | 实现 API 路由桥接层（/api/assistant/chat → OHMO Gateway） | api/routes.py |
| 2.3 | 集成 agui_transport 统一事件转换 | 复用现有 agui/ |
| 2.4 | OHMO Gateway 启动时加载 AI Assistant Plugin | 启动配置 |
| 2.5 | 会话管理 API 对接 OHMO SessionBackend | session API |

**验收**：Web UI 消息通过 OHMO Gateway → QueryEngine → AG-UI SSE 完整链路。

### Phase 3: 前端 AG-UI 统一（1-2 周）

**目标**：前端完全使用 AG-UI 协议

| 步骤 | 内容 | 产出 |
|------|------|------|
| 3.1 | 创建 `frontend/src/modules/ai-assistant/` 独立模块 | 目录结构 |
| 3.2 | useAIChat 重构为 AG-UI 协议解析 | hooks/useAIChat.ts |
| 3.3 | AIChatPanel 迁移到独立模块 | components/ |
| 3.4 | 更新所有引用点（QAPage, OntologyDesignerPage, AdminLayout, ProLayout） | 导入路径更新 |

**验收**：前端统一使用 AG-UI 17 类事件，无自定义 SSE 格式。

### Phase 4: 死代码清理 + IM 接入验证（1 周）

**目标**：移除旧实现，验证 IM 接入

| 步骤 | 内容 | 产出 |
|------|------|------|
| 4.1 | 删除 `odap/biz/core/assistant/` 旧模块 | 清理 |
| 4.2 | 删除旧的前端 useAIChat/AIChatPanel（已迁移到独立模块） | 清理 |
| 4.3 | 配置飞书/Slack 渠道适配器 | IM 配置 |
| 4.4 | 端到端测试：Web + IM 双渠道验证 | 测试报告 |

**验收**：旧代码完全移除，IM 渠道可收发消息。

---

## 9. 关键设计决策（ADR 级别）

### ADR-048: AI 助手独立组件化

**Status**: Proposed

**Context**: 项目存在两套并行 AI 助手实现（自建 assistant/ + OH AGUI），功能重复、协议不统一、无法接入 IM。用户要求将 AI 助手独立成组件，通过 OHMO 接入 IM，完全基于 OpenHarness。

**Decision**: 采用 Host-Plugin 架构：
1. OHMO Gateway 作为统一入口（Host），管理会话、渠道路由、RuntimeBundle
2. AI Assistant 作为独立 OH Plugin，提供领域工具/技能/钩子
3. AG-UI v0.x 作为统一通信协议（17 类事件）
4. Web UI 作为 OHMO 的 "web" 渠道，与 IM 渠道并列
5. 工具通过 ToolExecutionContext 获取 OntologyService（消除直接导入耦合）

**Consequences**:
- ✅ 统一协议：Web 和 IM 共享 AG-UI 事件格式
- ✅ IM 接入：通过 OHMO Gateway 即可接入 12+ IM 渠道
- ✅ 解耦：AI Assistant Plugin 不直接依赖 OHMO Gateway
- ✅ 可迁移：Plugin 结构可独立迁移到其他 OH 项目
- ⚠️ 迁移成本：需要重构 assistant/ 模块为 Plugin 结构
- ⚠️ 复杂度增加：引入 OHMO Gateway 作为中间层

### ADR-049: Web Channel 作为 OHMO 渠道

**Status**: Proposed

**Context**: Web UI 当前直接调用后端 API，与 IM 渠道完全隔离。需要统一入口。

**Decision**: Web UI 作为 OHMO 的 "web" 渠道，实现 WebChannelAdapter，与飞书/Slack 等 IM 渠道并列。

**Consequences**:
- ✅ 统一会话管理：Web 和 IM 共享 OhmoSessionRuntimePool
- ✅ 统一工具调度：所有渠道共享 ToolRegistry
- ⚠️ Web 渠道需要适配 SSE 流式响应（IM 渠道是消息推送模式）

---

## 10. 与现有架构的关系

### 10.1 复用的现有组件

| 现有组件 | 角色 | 复用方式 |
|---------|------|---------|
| `odap/infra/openharness/agui/` | AG-UI 协议层 | 直接复用，作为统一事件转换层 |
| `odap/infra/openharness/engine_adapter.py` | OH 引擎适配 | 复用 GraphitiToolAdapter、OHQueryEngineFactory |
| `odap/infra/openharness/permission_backend.py` | OPA 权限后端 | 复用，注入 PermissionChecker |
| `odap/infra/openharness/memory_adapter.py` | Graphiti 记忆适配 | 复用，注入 Memory |
| `openharness/ohmo/gateway/` | OHMO 网关 | 直接复用，新增 WebChannelAdapter |
| `openharness/src/openharness/channels/` | 渠道适配器框架 | 直接复用 BaseChannel |

### 10.2 替换的组件

| 旧组件 | 新组件 | 原因 |
|--------|--------|------|
| `odap/biz/core/assistant/tools.py` | `odap/plugins/ai_assistant/tools/*.py` | 迁移为 BaseTool |
| `odap/biz/core/assistant/services/chat_service.py` | OHMO Gateway + QueryEngine | 不再自建 LLM 调用 |
| `odap/biz/core/assistant/api/routes.py` | `odap/plugins/ai_assistant/api/routes.py` | 桥接到 OHMO Gateway |
| 自定义 SSE（6 类事件） | AG-UI v0.x（17 类事件） | 统一协议 |

### 10.3 新增的组件

| 新组件 | 职责 |
|--------|------|
| `odap/plugins/ai_assistant/plugin.json` | OH Plugin 清单 |
| `odap/plugins/ai_assistant/context.py` | ToolExecutionContext 扩展 |
| `odap/plugins/ai_assistant/api/web_channel.py` | Web 渠道适配器 |
| `odap/plugins/ai_assistant/hooks/ontology_changed_hook.py` | 写操作后刷新钩子 |
| `frontend/src/modules/ai-assistant/` | 独立前端模块 |

---

## 11. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| OHMO Gateway 引入增加延迟 | Web UI 响应变慢 | WebChannelAdapter 直接调用 RuntimePool，跳过 MessageBus |
| 迁移期间功能中断 | 旧 assistant/ 被删除前无法使用 | Phase 1-2 保持旧接口可用，Phase 4 才删除 |
| OntologyService 注入复杂 | ToolExecutionContext 需要扩展 | 在 Plugin 加载时注入到 ToolRegistry 元数据 |
| IM 渠道配置复杂 | 每个渠道有不同的认证方式 | 复用 OHMO 现有配置体系，通过 `ohmo config` 管理 |
| AG-UI 协议学习成本 | 前端需要理解 17 类事件 | 封装在 useAIChat hook 中，组件层无感知 |

---

## 12. 总结

本架构设计的核心是 **Host-Plugin 分层**：

1. **OHMO = Host**：统一入口、会话管理、渠道路由、RuntimeBundle 生命周期
2. **OpenHarness = Framework**：Agent Loop、ToolRegistry、HookExecutor、Permission
3. **AG-UI = Protocol**：17 类事件 wire format，Web 和 IM 共享
4. **AI Assistant = Plugin**：独立组件，提供领域工具/技能/钩子

**关键收益**：
- 一份代码，双渠道（Web + IM）复用
- 完全基于 OpenHarness，无自建 Agent Loop
- 独立组件，可独立迁移和维护
- AG-UI 统一协议，支持 HITL 和 State Snapshot
- OHMO Gateway 即时获得 12+ IM 渠道接入能力
