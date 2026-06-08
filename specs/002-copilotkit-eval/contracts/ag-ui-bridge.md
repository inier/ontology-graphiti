# Contract: AG-UI ↔ OpenHarness Bridge 事件映射契约

**Date**: 2026-06-08 (FINAL)
**Status**: 草案 v0.1
**依赖**: [plan.md §AG-UI Bridge 事件映射](../plan.md#ag-ui-bridge-事件映射核心设计) · [AG-UI 官方协议](https://docs.ag-ui.com/concepts/events) · [OpenHarness stream_events.py](../../../openharness/src/openharness/engine/stream_events.py)
**被依赖**: [hitl-flow.md](./hitl-flow.md) · [generative-ui-card.md](./generative-ui-card.md) · [data-model.md](../data-model.md)

---

## 1. 概述

本文档定义 **AG-UI 工业标准协议**（wire protocol）与 **OpenHarness agent runtime**（内部事件流）之间的**事件翻译契约**。该契约由 `odap/biz/core/qa/agui_bridge.py`（`AGUIBridge` 类）实现，是两个系统之间的**唯一接缝**。

**设计原则**：
- **AG-UI 是协议（contract）**，OpenHarness 是运行时（runtime）— 两者在不同抽象层
- **翻译是 1:1 映射**：每个 OpenHarness 事件都有明确的 AG-UI 对应事件，反之亦然
- **不破坏 OpenHarness 核心**：通过 `QueryEngine` 公开 API + `ask_user_prompt` 回调对接，零修改
- **不引入持久层**：HITL 暂停复用 OpenHarness session 内存，零新表

**核心洞察**：
- OpenHarness 的 `ask_user_question` 工具是**天然 HITL 触发器** — 不需要新状态机
- AG-UI 的 `RunFinished.outcome.interrupts` 是**工业标准中断信号** — 不需要自研协议
- 两者结合：**OpenHarness 触发中断 → AG-UI 携带 Interrupt[] 终止 run → 客户端 UI 渲染 → 客户端发新 run 带 resume → OpenHarness 续跑**

---

## 2. 事件源定义

### 2.1 OpenHarness StreamEvent（7 类，[源码](../../../openharness/src/openharness/engine/stream_events.py#L1-L89)）

| 事件类 | 字段 | 含义 |
|--------|------|------|
| `AssistantTextDelta` | `text: str` | 增量 assistant 文本（流式） |
| `AssistantTurnComplete` | `message: ConversationMessage`, `usage: UsageSnapshot` | assistant 轮次结束 |
| `ToolExecutionStarted` | `tool_name: str`, `tool_input: dict` | 工具开始执行 |
| `ToolExecutionCompleted` | `tool_name: str`, `output: str`, `is_error: bool` | 工具执行完成（`output` 必为 JSON 字符串） |
| `ErrorEvent` | `message: str`, `recoverable: bool` | 错误事件 |
| `StatusEvent` | `message: str` | 状态消息 |
| `CompactProgressEvent` | `phase: Literal[...]`, `trigger`, `message`, `attempt`, `checkpoint`, `metadata` | 上下文压缩进度 |

### 2.2 AG-UI 事件（按官方 [events 文档](https://docs.ag-ui.com/concepts/events) 分类）

| 类别 | 事件 | 关键字段 |
|------|------|----------|
| **Lifecycle** | `RunStarted` | `threadId`, `runId`, `parentRunId?`, `input?` |
| | `RunFinished` | `threadId`, `runId`, `result?`, `outcome?: { type: "success" \| "interrupt", interrupts?: Interrupt[] }` |
| | `RunError` | `message`, `code?` |
| | `StepStarted` | `stepName` |
| | `StepFinished` | `stepName` |
| **Text Message** | `TextMessageStart` | `messageId`, `role` |
| | `TextMessageContent` | `messageId`, `delta` |
| | `TextMessageEnd` | `messageId` |
| | `TextMessageChunk` | `messageId?`, `role?`, `delta?`（自动展开三件套） |
| **Tool Call** | `ToolCallStart` | `toolCallId`, `toolCallName`, `parentMessageId?` |
| | `ToolCallArgs` | `toolCallId`, `delta` |
| | `ToolCallEnd` | `toolCallId` |
| | `ToolCallResult` | `messageId`, `toolCallId`, `content`, `role?: "tool"` |
| | `ToolCallChunk` | 自动展开三件套 |
| **State Management** | `StateSnapshot` | `state` |
| | `StateDelta` | `delta`（JSON Patch） |
| | `MessagesSnapshot` | `messages` |
| **Interrupt 字段**（嵌于 `RunFinished.outcome`）| `Interrupt` | `id`, `reason`, `message?`, `toolCallId?`, `responseSchema?`, `expiresAt?`, `metadata?` |

---

## 3. 完整事件翻译表

> **翻译方向 1：OpenHarness → AG-UI**（Bridge 推送 SSE 事件给客户端）
> **翻译方向 2：AG-UI → OpenHarness**（客户端 `RunAgentInput` → 触发 OpenHarness `ask_user_prompt` resolve）

### 3.1 主表（方向 1：OpenHarness StreamEvent → AG-UI Event）

| # | OpenHarness StreamEvent | AG-UI Event(s) 翻译结果 | 翻译逻辑 | 备注 |
|---|------------------------|----------------------|---------|------|
| 1 | `AssistantTextDelta(text)` | `TextMessageContent(messageId, delta=text)` | 直接转发 | **第一行 delta 前**会自动派发 `TextMessageStart`（保留 messageId） |
| 2 | `AssistantTurnComplete(message, usage)` | `TextMessageEnd(messageId)` + `StepFinished(stepName="assistant_turn")` | 触发 turn 边界 | `usage` 写入 `RunFinished.result.usage`（不直接发） |
| 3 | `ToolExecutionStarted(tool_name, tool_input)` | `ToolCallStart(toolCallId, toolCallName)` + `ToolCallArgs(toolCallId, delta=json.dumps(tool_input))` + `ToolCallEnd(toolCallId)` | 生成稳定 `toolCallId`（见 §3.3） | 三个事件**原子发送** |
| 4 | `ToolExecutionCompleted(tool_name, output, is_error=False)` | `ToolCallResult(messageId, toolCallId, content=output, role="tool")` | `output` 必须是 JSON 字符串 | **Generative UI 关键点**：`output` 格式为 `{"card_type": "...", "card_props": {...}}` |
| 4.1 | `ToolExecutionCompleted(tool_name, output, is_error=True)` | `ToolCallResult(...)` + `StepFinished(stepName="tool_error")` | 标记工具失败 | 客户端可降级渲染错误卡 |
| 5 | `ErrorEvent(message, recoverable=True)` | `RunError(message, code="agent_error")` | 终止当前 run | `recoverable=False` 时 Bridge 主动 `RunFinished` 不发 `interrupts` |
| 6 | `StatusEvent(message)` | `StepStarted(stepName=message)` | 包装为步骤 | 客户端可显示"正在 XXX" |
| 7 | `CompactProgressEvent(phase, ...)` | `StateDelta(delta=[{op: "add", path: "/compact", value: {...}}])` | 状态变化 | 客户端可更新压缩进度条 |
| 8 | **`ask_user_question` tool start**（事件 3 的特化） | `ToolCallStart` + `ToolCallArgs` + **`RunFinished(outcome: { type: "interrupt", interrupts: [...] })`** | **HITL 触发**：终止 run 并携带 Interrupt[] | **关键**：不发 `ToolCallResult`；中断信息见 §3.4 |
| 9 | **客户端 `RunAgentInput.resume` 到达** | **（方向 2）** 解析 `resume[]` → resolve 对应 `ask_user_prompt` future | **HITL 恢复** | 见 §3.5 |
| 10 | **`ask_user_question` tool complete (after user input)** | `ToolCallResult(toolCallId, content=user_answer, role="tool")` | 继续 run | 在 resume 触发的**新 run**（`runId_2`）中发出，对应**原** `toolCallId` |

### 3.2 run 生命周期事件（Bridge 内部生成）

| # | 触发时机 | AG-UI Event | 翻译逻辑 | 备注 |
|---|---------|------------|---------|------|
| L1 | 收到 `POST /api/ag-ui/run` 第一帧 | `RunStarted(threadId, runId, input=...)` | 启动新 run | `threadId` 来自 `session_id`；`runId` 用 `uuid4()` |
| L2 | 收到 `AssistantTextDelta` 第一帧 | `TextMessageStart(messageId, role="assistant")` | 隐式生成 | `messageId` 稳定到 `TextMessageEnd` |
| L3 | 收到 `StatusEvent` | `StepStarted(stepName=message)` | 直接转发 | |
| L4 | OpenHarness `AssistantTurnComplete` 之后 | `StepFinished(stepName="assistant_turn")` | 隐式 | |
| L5 | **所有事件流完成且无中断** | `RunFinished(threadId, runId, result={usage}, outcome: { type: "success" })` | 终止 run | 成功路径 |
| L6 | **OpenHarness 触发 `ask_user_question`** | `RunFinished(threadId, runId, outcome: { type: "interrupt", interrupts: [Interrupt] })` | 终止 run | **HITL 路径**（见 §3.4） |

### 3.3 `toolCallId` 生成规则

**必须稳定** — 同一工具调用在 run 内和 resume run 内共享同一 `toolCallId`，否则 AG-UI 客户端无法关联中断和结果。

```python
# odap/biz/core/qa/agui_bridge.py

import hashlib
from typing import Any

def make_tool_call_id(thread_id: str, tool_name: str, tool_input: Any) -> str:
    """基于 thread_id + tool_name + tool_input 计算稳定 ID。"""
    payload = f"{thread_id}|{tool_name}|{json.dumps(tool_input, sort_keys=True)}"
    return "tc-" + hashlib.sha256(payload.encode()).hexdigest()[:16]
```

**为什么是稳定 ID？** AG-UI 规定：tool-bound interrupt 在 resume run 中**不重新发出** `ToolCallStart`，直接发 `ToolCallResult(messageId, toolCallId, content)` 关联原 `toolCallId`（[Interrupts 文档](https://docs.ag-ui.com/concepts/interrupts#tool-bound-interrupts)）。

### 3.4 HITL 中断事件（最复杂，单独成节）

当 OpenHarness 检测到 `ask_user_question` 工具被调用，Bridge 翻译为 AG-UI **interrupt 终止事件**：

```json
{
  "type": "RUN_FINISHED",
  "threadId": "sess_abc123",
  "runId": "run_xyz789",
  "outcome": {
    "type": "interrupt",
    "interrupts": [
      {
        "id": "int-001",
        "reason": "tool_call",
        "message": "要删除 X 节点吗？",
        "toolCallId": "tc-7a3b9c2d4e5f",
        "responseSchema": {
          "type": "object",
          "properties": {
            "approved": { "type": "boolean" }
          },
          "required": ["approved"]
        },
        "metadata": {
          "odap": {
            "tool_name": "ask_user_question",
            "original_question": "要删除 X 节点吗？",
            "card_type": "confirm"
          }
        }
      }
    ]
  }
}
```

**字段映射表**：

| AG-UI Interrupt 字段 | OpenHarness 来源 | 翻译规则 |
|---------------------|------------------|---------|
| `id` | Bridge 自动生成 `int-{uuid4().hex[:12]}` | 全局唯一 |
| `reason` | 工具名 → 类别映射 | `ask_user_question` → `"confirmation"`；其他工具触发 → `"tool_call"` |
| `message` | `AskUserQuestionToolInput.question` | 直接转发 |
| `toolCallId` | §3.3 生成的稳定 ID | 必填（`reason="tool_call"` 时） |
| `responseSchema` | 基于工具 schema 自动生成 | 见 §3.4.1 |
| `expiresAt` | Bridge 配置默认 30 分钟 | ISO-8601 字符串 |
| `metadata.card_type` | 工具名 → 卡片类型映射 | `ask_user_question` → `"confirm"`；其他 → `"action"` |

**Reason 路由表**（基于 [AG-UI Reason taxonomy](https://docs.ag-ui.com/concepts/interrupts#reason-taxonomy)）：

| OpenHarness 工具 | AG-UI `reason` | 客户端渲染 |
|------------------|---------------|----------|
| `ask_user_question` | `confirmation` | `ConfirmCard`（默认 yes/no） |
| `ask_user_question`（含 `input_type=select` 参数） | `input_required` | `InputCard` |
| `permission_request`（OpenHarness 权限） | `tool_call` | `ActionCard` + 权限说明 |
| 任何 `tool_name` 匹配 `*_approval` 通配 | `tool_call` | `ActionCard` + 审批流 |
| 其他 | `"odap:" + tool_name`（自定义 namespace） | 通用 `ActionCard` + `metadata` |

**3.4.1 `responseSchema` 自动生成**

```python
# 简化版（实际在 Bridge 中实现）

def derive_response_schema(tool_name: str, tool_input: dict) -> dict:
    """从 OpenHarness 工具 input 推断 AG-UI Interrupt responseSchema。"""
    if tool_name == "ask_user_question":
        # 默认 confirmation
        return {
            "type": "object",
            "properties": {"approved": {"type": "boolean"}},
            "required": ["approved"]
        }
    elif tool_name == "ask_user_question_input":
        # input_required
        return {
            "type": "object",
            "properties": {
                "value": {"type": "string"},
            },
            "required": ["value"]
        }
    else:
        # tool_call (通用审批)
        return {
            "type": "object",
            "properties": {
                "approved": {"type": "boolean"},
                "editedArgs": {"type": "object"}
            },
            "required": ["approved"]
        }
```

### 3.5 resume 事件（方向 2：AG-UI → OpenHarness）

客户端收到 `RUN_FINISHED` 携带 `interrupts` 后，渲染 UI 并通过 `POST /api/ag-ui/run` 提交**新 run**：

```json
{
  "threadId": "sess_abc123",
  "runId": "run_resume_001",  // 新 runId
  "resume": [
    {
      "interruptId": "int-001",
      "status": "resolved",  // or "cancelled"
      "payload": { "approved": true }  // 符合 responseSchema
    }
  ]
}
```

**Bridge 翻译逻辑**：

```python
# odap/biz/core/qa/agui_bridge.py 伪代码

async def handle_resume(thread_id: str, resume: list[dict]) -> AsyncIterator[AGUIEvent]:
    """处理客户端 resume 请求，恢复 OpenHarness ask_user_prompt 阻塞。"""
    # 1. 查找该 thread 的 pending ask_user_prompt future
    pending = self._pending_prompts.get(thread_id)
    if not pending:
        raise RunError("No pending interrupt for this thread")

    # 2. 逐个解析 resume 数组
    responses = {}
    for entry in resume:
        interrupt_id = entry["interruptId"]
        status = entry["status"]  # "resolved" | "cancelled"
        payload = entry.get("payload", {})

        if interrupt_id not in pending:
            raise RunError(f"Unknown interruptId: {interrupt_id}")

        # 3. 转换为 OpenHarness 工具返回值
        if status == "cancelled":
            responses[interrupt_id] = "(cancelled)"
        else:
            # 按 responseSchema 转换为用户答案字符串
            responses[interrupt_id] = self._format_answer(payload)

    # 4. resolve future，恢复 OpenHarness 工具执行
    pending["future"].set_result(responses[pending["interrupt_id"]])

    # 5. 启动新 run，继续流式事件
    async for event in self._run_query_resume(thread_id):
        yield event
```

---

## 4. 完整调用时序图

### 4.1 纯对话流（无工具）

```
Client                         AG-UI Bridge                  OpenHarness QueryEngine
  │                                  │                                  │
  │ POST /api/ag-ui/run              │                                  │
  │ {threadId, messages: [...]}      │                                  │
  ├─────────────────────────────────►│                                  │
  │                                  │ 1. create QueryEngine           │
  │                                  │ 2. set ask_user_prompt callback │
  │                                  │ 3. async run_query(message)     │
  │                                  ├─────────────────────────────────►│
  │                                  │                                  │ 4. LLM streams
  │ SSE: RUN_STARTED                 │ ◄────────────────────────────────┤
  │ {threadId, runId}                │                                  │
  │◄─────────────────────────────────┤                                  │
  │                                  │                                  │ 5. First delta
  │ SSE: TEXT_MESSAGE_START          │ ◄── AssistantTextDelta("Hi") ───┤
  │ {messageId, role: "assistant"}   │                                  │
  │◄─────────────────────────────────┤                                  │
  │                                  │                                  │ 6. Continue
  │ SSE: TEXT_MESSAGE_CONTENT        │ ◄── AssistantTextDelta(" 你好") ┤
  │ {messageId, delta: " 你好"}      │                                  │
  │◄─────────────────────────────────┤                                  │
  │  ... (more deltas)               │                                  │
  │                                  │                                  │ 7. Turn complete
  │ SSE: TEXT_MESSAGE_END            │ ◄── AssistantTurnComplete ──────┤
  │ SSE: STEP_FINISHED               │                                  │
  │ SSE: RUN_FINISHED                │                                  │
  │ {outcome: {type: "success"},     │                                  │
  │  result: {usage: {...}}}         │                                  │
  │◄─────────────────────────────────┤                                  │
  │                                  │ 8. SSE close                    │
```

### 4.2 工具调用流（Generative UI，无 HITL）

```
Client                         AG-UI Bridge                  OpenHarness QueryEngine
  │                                  │                                  │
  │ POST /api/ag-ui/run              │                                  │
  │ {message: "查询 X 节点关联"}     │                                  │
  ├─────────────────────────────────►│                                  │
  │                                  │ (steps 1-3 同 4.1)               │
  │                                  ├─────────────────────────────────►│
  │                                  │                                  │ 4. LLM decides
  │                                  │    to call graph_query tool      │
  │                                  │                                  │ 5. Tool start
  │ SSE: TOOL_CALL_START             │ ◄── ToolExecutionStarted ────────┤
  │ {toolCallId, toolCallName}       │                                  │
  │ SSE: TOOL_CALL_ARGS              │ ◄── ToolExecutionStarted ────────┤
  │ {toolCallId, delta: "{...}"}     │                                  │
  │ SSE: TOOL_CALL_END               │ ◄── ToolExecutionStarted ────────┤
  │ {toolCallId}                     │                                  │
  │◄─────────────────────────────────┤                                  │
  │                                  │                                  │ 6. Tool executes
  │                                  │    in OpenHarness                │
  │                                  │                                  │ 7. Tool complete
  │ SSE: TOOL_CALL_RESULT            │ ◄── ToolExecutionCompleted ─────┤
  │ {toolCallId,                     │     output: '{"card_type":       │
  │  content: '{"card_type":         │     "graph", "card_props":       │
  │   "graph", "card_props":         │     {nodes: [...], edges: [...]}}'
  │   {nodes: [...],                  │                                  │
  │    edges: [...]}}',              │                                  │
  │  role: "tool"}                   │                                  │
  │◄─────────────────────────────────┤                                  │
  │  → 客户端 CardRegistry 查找      │                                  │
  │    "graph" → GraphCard           │                                  │
  │  → React 渲染 G6 图谱           │                                  │
  │                                  │                                  │ 8. LLM continues
  │ SSE: TEXT_MESSAGE_CONTENT        │ ◄── AssistantTextDelta ──────────┤
  │  "查询到 5 个关联节点"          │                                  │
  │◄─────────────────────────────────┤                                  │
  │  ... (more deltas + RUN_FINISHED)                                │
```

### 4.3 HITL 中断-恢复流（核心复杂场景）

```
Client                         AG-UI Bridge                  OpenHarness QueryEngine
  │                                  │                                  │
  │ POST /api/ag-ui/run              │                                  │
  │ {message: "删除 X 节点"}         │                                  │
  ├─────────────────────────────────►│                                  │
  │                                  │ 1. create QueryEngine           │
  │                                  │ 2. set ask_user_prompt callback │
  │                                  │    (callback creates Future)     │
  │                                  │ 3. async run_query              │
  │                                  ├─────────────────────────────────►│
  │                                  │                                  │ 4. LLM streams
  │ SSE: RUN_STARTED                 │ ◄────────────────────────────────┤
  │◄─────────────────────────────────┤                                  │
  │ SSE: TEXT_MESSAGE_CONTENT        │ ◄── AssistantTextDelta ──────────┤
  │  "正在评估..."                   │                                  │
  │◄─────────────────────────────────┤                                  │
  │                                  │                                  │ 5. LLM decides
  │                                  │    to call ask_user_question    │
  │                                  │                                  │ 6. Tool start
  │ SSE: TOOL_CALL_START             │ ◄── ToolExecutionStarted ────────┤
  │ {toolCallId,                     │     (tool_name=                  │
  │  toolCallName:                   │      "ask_user_question")        │
  │   "ask_user_question"}           │                                  │
  │ SSE: TOOL_CALL_ARGS              │ ◄── (same event) ────────────────┤
  │ {toolCallId, delta:              │                                  │
  │  '{"question":                   │                                  │
  │   "要删除 X 节点吗？"}'}         │                                  │
  │ SSE: TOOL_CALL_END               │                                  │
  │ {toolCallId}                     │                                  │
  │◄─────────────────────────────────┤                                  │
  │                                  │                                  │ 7. ask_user_question
  │                                  │    calls ask_user_prompt(...)   │
  │                                  │    ⏸ BLOCKS on Future           │
  │                                  │                                  │
  │                                  │ 8. Bridge 检测 tool_name =      │
  │                                  │    "ask_user_question"          │
  │                                  │ 9. emit RunFinished with        │
  │                                  │    outcome.interrupts[]         │
  │ SSE: RUN_FINISHED                │                                  │
  │ {outcome: {                      │                                  │
  │   type: "interrupt",             │                                  │
  │   interrupts: [{                 │                                  │
  │     id: "int-001",               │                                  │
  │     reason: "confirmation",      │                                  │
  │     toolCallId: "tc-xxx",        │                                  │
  │     message: "要删除 X 节点吗？" │
  │   }]                             │                                  │
  │ }}                               │                                  │
  │◄─────────────────────────────────┤                                  │
  │  → 客户端看到 interrupts，渲染   │                                  │
  │    ConfirmCard "删除 X 节点？"   │                                  │
  │                                  │                                  │
  │ 10. 用户点击 "确认"              │                                  │
  │                                  │                                  │
  │ POST /api/ag-ui/run              │                                  │
  │ {threadId, runId: "run_2",       │                                  │
  │  resume: [{                      │                                  │
  │    interruptId: "int-001",       │                                  │
  │    status: "resolved",           │                                  │
  │    payload: {approved: true}     │                                  │
  │  }]}                             │                                  │
  ├─────────────────────────────────►│                                  │
  │                                  │ 11. 查找 pending future         │
  │                                  │ 12. set_result("yes")            │
  │                                  │ 13. ask_user_prompt 解除阻塞   │
  │                                  │ 14. ask_user_question 工具完成 │
  │                                  │     output="yes"                 │
  │                                  │ 15. 触发 ToolExecutionCompleted│
  │                                  ├─────────────────────────────────►│
  │                                  │                                  │ 16. LLM continues
  │                                  │                                  │     (基于 user answer)
  │                                  │                                  │ 17. New run starts
  │ SSE: RUN_STARTED (runId_2)       │                                  │
  │ SSE: TOOL_CALL_RESULT            │ ◄── ToolExecutionCompleted ─────┤
  │ {toolCallId: "tc-xxx",           │     (原 toolCallId, content="yes")
  │  content: "yes",                 │                                  │
  │  role: "tool"}                   │                                  │
  │  ⓘ 不重新发 TOOL_CALL_START      │                                  │
  │◄─────────────────────────────────┤                                  │
  │ SSE: TEXT_MESSAGE_CONTENT        │ ◄── AssistantTextDelta ──────────┤
  │  "已删除 X 节点"                 │                                  │
  │◄─────────────────────────────────┤                                  │
  │  ...                             │                                  │
  │ SSE: RUN_FINISHED                │                                  │
  │ {outcome: {type: "success"}}     │                                  │
  │◄─────────────────────────────────┤                                  │
```

**关键不变量**：
1. **同一 `toolCallId`**：`tc-xxx` 在 run_1 和 run_2 中保持一致
2. **不重发 ToolCallStart**：run_2 中 OpenHarness 完成 ask_user_question 时**不**再触发 `ToolExecutionStarted`
3. **tool_bound interrupt**：resume 路径直接发 `ToolCallResult` 关联原 `toolCallId`

---

## 5. Shared State 翻译

OpenHarness 已有 `QueryEngine.messages`（对话历史）和 `Memory` 模块。AG-UI 的 `StateSnapshot` / `StateDelta` 翻译规则：

| OpenHarness 来源 | AG-UI 事件 | 触发时机 | payload |
|------------------|-----------|---------|---------|
| `QueryEngine.messages` | `MessagesSnapshot(messages)` | 每次 `RUN_STARTED` 前 | OpenHarness ConversationMessage 列表（已扁平化） |
| `QueryEngine.messages` 增量 | `StateDelta(delta=JSON_PATCH)` | 每个 `TextMessageContent` 后 | `{op: "add", path: "/messages/-", value: new_msg}` |
| `Memory` 跨 session 数据 | `StateSnapshot({memory: [...], facts: [...]})` | 客户端首次连接时 | 完整快照 |
| `CompactProgressEvent` | `StateDelta(delta=...)` | 上下文压缩时 | `{op: "replace", path: "/compact_progress", value: {...}}` |

**为什么需要 snapshot + delta？** AG-UI 客户端需要完整 state 用于渲染（snapshot），但持续发送全量浪费带宽（delta）。

---

## 6. 错误处理翻译

| OpenHarness 事件 | AG-UI 事件 | 客户端降级渲染 |
|-----------------|-----------|--------------|
| `ErrorEvent(recoverable=True)` | `StepStarted(stepName="error_recovery")` + `RunFinished` (无 outcome) | 客户端可选择 retry |
| `ErrorEvent(recoverable=False)` | `RunError(message, code="fatal")` | 客户端显示错误页 |
| OPA 鉴权失败（Bridge 层） | `RunError(message, code="403_forbidden")` | 客户端显示权限错误 |
| LLM API 超时 | `RunError(message, code="llm_timeout")` | 客户端可 retry |
| 客户端 resume 但 `interruptId` 找不到 | `RunError(message, code="unknown_interrupt")` | 客户端显示"会话已过期" |
| 客户端 resume 超过 `expiresAt` | `RunError(message, code="interrupt_expired")` | 客户端显示"已超时" |

---

## 7. 并发与状态管理

### 7.1 单 thread 多 run 顺序

AG-UI 规定：**同一 thread 同一时刻只能有一个 active run**。Bridge 通过以下机制保证：

```python
class AGUIBridge:
    def __init__(self):
        self._active_runs: dict[str, asyncio.Task] = {}  # threadId -> task
        self._pending_prompts: dict[str, dict] = {}      # threadId -> {interruptId, future, ...}
```

- 收到新 run 请求时，若 `threadId` 已有 active task，**拒绝并返回 409 Conflict**
- run 完成（含 interrupt）后，从 `_active_runs` 移除
- resume run 启动时，校验 `threadId` 有 pending interrupt，否则返回 409

### 7.2 ask_user_prompt Future 管理

```python
# odap/biz/core/qa/agui_bridge.py 伪代码

class AGUIBridge:
    async def _create_ask_user_callback(self, thread_id: str) -> AskUserPrompt:
        """为该 thread 创建 ask_user_prompt 回调，返回 future。"""
        future: asyncio.Future[str] = asyncio.Future()
        interrupt_id = f"int-{uuid4().hex[:12]}"
        self._pending_prompts[thread_id] = {
            "interruptId": interrupt_id,
            "future": future,
            "created_at": datetime.now(),
            "timeout_at": datetime.now() + timedelta(minutes=30),
        }

        async def callback(question: str) -> str:
            # 此回调由 OpenHarness ask_user_question 工具调用
            # 1. emit ToolCallStart + RunFinished.interrupts
            await self._emit_interrupt(
                thread_id=thread_id,
                interrupt_id=interrupt_id,
                question=question,
            )
            # 2. 阻塞等待客户端 resume
            try:
                answer = await asyncio.wait_for(future, timeout=1800)
                return answer
            except asyncio.TimeoutError:
                return "(timeout)"

        return callback
```

**并发安全保证**：
- `future` 是 `thread_id` scope 的，多客户端竞争由 `_active_runs` 字典保证互斥
- `future.set_result()` 只能调用一次（asyncio Future 保证）
- 超时由 `wait_for` 保证 30 分钟兜底

### 7.3 多 HITL 并行（罕见但需支持）

**场景**：agent 一次性触发多个 `ask_user_question`（如"批准 A 和 B？"）。

AG-UI 支持 `interrupts: Interrupt[]` 数组。Bridge 翻译：

```python
# OpenHarness 当前不支持单 turn 多 ask_user_question（顺序执行）
# 若未来支持，Bridge 聚合到单个 interrupts[] 数组
# 当前：第二个 ask_user_question 会等到第一个的 future resolve 后才触发
```

**结论**：MVP 只支持单 HITL，AG-UI interrupts 数组长度为 1。Phase 2 之后若 OpenHarness 支持多 tool 并行，再扩展。

---

## 8. 端到端示例

### 8.1 完整 HITL 流程（curl 模拟）

```bash
# 步骤 1: 启动 run，agent 评估后会中断
curl -N -X POST http://localhost:8000/api/ag-ui/run \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "threadId": "sess_demo_1",
    "runId": "run_1",
    "messages": [{"role": "user", "content": "删除 X 节点"}]
  }'

# 接收 SSE 事件流（截取关键）
# data: {"type":"RUN_STARTED","threadId":"sess_demo_1","runId":"run_1"}
# data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"msg_1","delta":"正在评估..."}
# data: {"type":"TOOL_CALL_START","toolCallId":"tc-7a3b9c2d4e5f","toolCallName":"ask_user_question"}
# data: {"type":"TOOL_CALL_ARGS","toolCallId":"tc-7a3b9c2d4e5f","delta":"{\"question\":\"要删除 X 节点吗？\"}"}
# data: {"type":"TOOL_CALL_END","toolCallId":"tc-7a3b9c2d4e5f"}
# data: {"type":"RUN_FINISHED","threadId":"sess_demo_1","runId":"run_1","outcome":{"type":"interrupt","interrupts":[{"id":"int-001","reason":"confirmation","toolCallId":"tc-7a3b9c2d4e5f","message":"要删除 X 节点吗？","responseSchema":{...}}]}}

# 步骤 2: 用户点击"确认"后，发送 resume
curl -N -X POST http://localhost:8000/api/ag-ui/run \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "threadId": "sess_demo_1",
    "runId": "run_2",
    "resume": [{
      "interruptId": "int-001",
      "status": "resolved",
      "payload": {"approved": true}
    }]
  }'

# 接收 SSE 事件流（截取关键）
# data: {"type":"RUN_STARTED","threadId":"sess_demo_1","runId":"run_2"}
# data: {"type":"TOOL_CALL_RESULT","messageId":"msg_1","toolCallId":"tc-7a3b9c2d4e5f","content":"yes","role":"tool"}
# data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"msg_2","delta":"已删除 X 节点"}
# data: {"type":"RUN_FINISHED","threadId":"sess_demo_1","runId":"run_2","outcome":{"type":"success"},"result":{"usage":{...}}}
```

### 8.2 工具调用流（Generative UI，curl 模拟）

```bash
# 步骤 1: 查询图谱
curl -N -X POST http://localhost:8000/api/ag-ui/run \
  -H "Authorization: Bearer <token>" \
  -d '{
    "threadId": "sess_demo_2",
    "runId": "run_1",
    "messages": [{"role": "user", "content": "查询 X 节点的关联实体"}]
  }'

# 接收事件
# data: {"type":"RUN_STARTED",...}
# data: {"type":"TOOL_CALL_START","toolCallId":"tc-abc","toolCallName":"graph_query"}
# data: {"type":"TOOL_CALL_ARGS","toolCallId":"tc-abc","delta":"{\"node_id\":\"X\"}"}
# data: {"type":"TOOL_CALL_END","toolCallId":"tc-abc"}
# data: {"type":"TOOL_CALL_RESULT","messageId":"msg_1","toolCallId":"tc-abc","content":"{\"card_type\":\"graph\",\"card_props\":{\"nodes\":[...],\"edges\":[...]}}","role":"tool"}
# data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"msg_2","delta":"查询到 5 个关联节点"}
# data: {"type":"RUN_FINISHED",...}
```

---

## 9. 协议版本协商

**AG-UI spec 版本**：v0.x（截至 2026-06，仍在演进）

**Bridge 实现策略**：
- **server 端**：实现 spec v0.x 的所有 mandatory 事件（`RunStarted` / `RunFinished` / `RunError` / `TextMessage*` / `ToolCall*`）
- **client 端**：使用 `@ag-ui/core` SDK（spec 兼容）
- **未知事件**：`AGUIEvent` 的 Pydantic 模型用 `extra="allow"` 接收，前端忽略未知事件（降级渲染）
- **新事件类型**：spec 升级时 Bridge 仅需新增翻译函数，无需破坏现有协议

**版本字段**：AG-UI 暂未在事件中携带 `version` 字段（设计中）。Bridge 通过 `Content-Type: application/x-ndjson` + 自定义 header `X-AG-UI-Version: 0.1` 协商（Phase 2 决定是否启用）。

---

## 10. 与 OpenHarness 现有能力的复用清单

| 能力 | OpenHarness 模块 | AG-UI 翻译 | 新增代码 |
|------|-----------------|-----------|---------|
| 流式 LLM 输出 | `AssistantTextDelta` | `TextMessage*` | 0 行 |
| 工具调用追踪 | `ToolExecutionStarted/Completed` | `ToolCallStart/Result` | 0 行 |
| HITL 中断 | `ask_user_question` + `ask_user_prompt` callback | `RunFinished.interrupts` + resume | ~50 行（future 管理） |
| 对话历史 | `QueryEngine.messages` | `MessagesSnapshot` | ~10 行 |
| 跨 session 记忆 | `Memory` 模块 | `StateSnapshot` | ~10 行 |
| 错误处理 | `ErrorEvent` | `RunError` | 0 行 |
| 状态消息 | `StatusEvent` | `StepStarted/Finished` | 0 行 |
| 上下文压缩 | `CompactProgressEvent` | `StateDelta` | ~5 行 |
| 权限检查 | OpenHarness `permission_prompt` | 暂不暴露给 AG-UI（内部使用） | 0 行 |
| Hook 系统 | `HookExecutor` | 暂不暴露给 AG-UI | 0 行 |

**总计新增代码**：`AGUIBridge` 类 ~200 行 + `ask_user_prompt` future 管理 ~50 行 = **~250 行 Python**。

---

## 11. 单元测试要求

按 AGENTS.md 规则 3 与 9，新增 `tests/unit/test_agui_bridge.py` 覆盖：

| 测试 ID | 测试名 | 覆盖点 |
|---------|-------|-------|
| T-01 | `test_translate_assistant_text_delta` | `AssistantTextDelta` → `TextMessageContent` |
| T-02 | `test_translate_assistant_turn_complete` | `AssistantTurnComplete` → `TextMessageEnd` + `StepFinished` |
| T-03 | `test_translate_tool_execution_started` | `ToolExecutionStarted` → `ToolCallStart/Args/End` 三件套 |
| T-04 | `test_translate_tool_execution_completed` | `ToolExecutionCompleted` → `ToolCallResult`（含 JSON 解析） |
| T-05 | `test_translate_error_event_recoverable` | `ErrorEvent(recoverable=True)` → `StepStarted` + `RunFinished` |
| T-06 | `test_translate_error_event_fatal` | `ErrorEvent(recoverable=False)` → `RunError` |
| T-07 | `test_translate_status_event` | `StatusEvent` → `StepStarted` |
| T-08 | `test_translate_compact_progress` | `CompactProgressEvent` → `StateDelta` |
| T-09 | `test_ask_user_question_triggers_interrupt` | `ask_user_question` 工具 → `RunFinished.interrupts` |
| T-10 | `test_tool_call_id_stable_across_runs` | 同一工具调用在 run_1 和 run_2 中 toolCallId 一致 |
| T-11 | `test_resume_resolves_ask_user_prompt` | 客户端 resume → `ask_user_prompt` future resolve |
| T-12 | `test_response_schema_for_confirmation` | `ask_user_question` → `responseSchema` 含 `approved` |
| T-13 | `test_response_schema_for_input_required` | 带 `input_type=select` → `responseSchema` 含 `value` |
| T-14 | `test_run_lifecycle_events_emitted` | 验证 RUN_STARTED 在第一帧前，RUN_FINISHED 在最后 |
| T-15 | `test_concurrent_runs_rejected` | 同一 threadId 第二 run 返回 409 |
| T-16 | `test_unknown_interrupt_id_returns_error` | resume 中 interruptId 找不到 → `RunError` |
| T-17 | `test_expired_interrupt_rejected` | resume 超过 expiresAt → `RunError` |
| T-18 | `test_messages_snapshot_emitted_on_run_start` | 验证 `MessagesSnapshot` 在 `RUN_STARTED` 前发出 |
| T-19 | `test_state_delta_for_compact_progress` | 验证 `StateDelta` JSON Patch 格式 |
| T-20 | `test_opa_auth_required` | 缺少 token → 401 / OPA 拒绝 → 403 |

---

## 12. 性能指标

| 指标 | 目标 | 测量方法 |
|------|------|---------|
| Bridge 翻译开销 | < 5ms / event | `time.perf_counter()` 包裹翻译函数 |
| SSE TTFB | < 200ms (P95) | 服务端从收到请求到发出第一个 SSE 事件 |
| run_2 (resume) 启动延迟 | < 100ms (P95) | 从 `POST /run` 收到 resume 到发出 `RUN_STARTED` |
| ask_user_prompt future 阻塞内存 | < 1KB / pending | `sys.getsizeof(future)` |
| 并发 run 支持 | ≥ 100 / instance | `asyncio.gather` 压测 |

---

## 13. 安全考虑

| 风险 | 缓解措施 |
|------|---------|
| **toolCallId 冲突** | §3.3 稳定 hash 算法 + uuid fallback |
| **resume 重放攻击** | AG-UI 规定 idempotency（相同 `(threadId, interruptId, status, payload)` 可重放），Bridge 用 LRU cache 去重 |
| **过期 resume** | 校验 `expiresAt`（AG-UI 协议规定），过期返回 `RunError` |
| **跨租户 threadId 复用** | OPA 鉴权校验 `ws_id`（AGENTS.md 硬约束） |
| **tool_input 注入** | OpenHarness 工具 input 由 Pydantic 模型校验（已有） |
| **SSE 慢客户端** | Heartbeat 30s + 反向压力断开（FastAPI StreamingResponse 默认行为） |

---

## 14. 关联文档

- [plan.md](../plan.md) — 主实施计划（AG-UI Bridge 章节）
- [spec.md](../spec.md) — 评估 spec（AG-UI 决策）
- [research.md](../research.md) — Phase 0 决策依据（v2.0）
- [data-model.md](../data-model.md) — 数据模型（AG-UI 事件镜像）
- [hitl-flow.md](./hitl-flow.md) — HITL 流程契约（基于本文档 §3.4）
- [generative-ui-card.md](./generative-ui-card.md) — 卡片注册契约（基于本文档 §3.1 第 4 项）
- [AG-UI Events 官方文档](https://docs.ag-ui.com/concepts/events) — 事件类型权威定义
- [AG-UI Interrupts 官方文档](https://docs.ag-ui.com/concepts/interrupts) — HITL 机制
- [AG-UI Serialization 官方文档](https://docs.ag-ui.com/concepts/serialization) — JSON 编码格式
- [OpenHarness stream_events.py](../../../openharness/src/openharness/engine/stream_events.py) — 事件源
- [OpenHarness ask_user_question_tool.py](../../../openharness/src/openharness/tools/ask_user_question_tool.py) — HITL 触发器
- [ODAP v2 Adapter](../../../odap/infra/openharness/v2_adapter.py) — OpenHarness 集成层

---

**Version**: 1.0 (FINAL) | **Date**: 2026-06-08
