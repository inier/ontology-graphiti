# Contract: HITL 暂停-恢复流程（AG-UI Interrupts 版）

**Date**: 2026-06-08 (FINAL)
**Status**: 草案 v1.0
**依赖**: [ag-ui-bridge.md §3.4](./ag-ui-bridge.md) · [data-model.md §3](../data-model.md) · [AG-UI Interrupts 官方文档](https://docs.ag-ui.com/concepts/interrupts) · [OpenHarness ask_user_question_tool](../../../openharness/src/openharness/tools/ask_user_question_tool.py)
**取代**: 原 [hitl-flow.md v0.1](./hitl-flow.md)（OAUIP 自研版，已废止）

---

## 1. 概述

HITL（Human-in-the-Loop）是 AG-UI 协议的**interrupt-aware run lifecycle** 能力。ODAP 通过 **AG-UI Bridge 适配器** + **OpenHarness `ask_user_question` 工具** 联合实现 — **OpenHarness 是运行时**、**AG-UI 是协议**，两者在不同抽象层无缝协作。

**核心机制**：
- **中断触发**：OpenHarness 工具 `ask_user_question` 阻塞 `QueryEngine` 循环 → Bridge 检测 → 终止 run 并发出 `RunFinished.outcome.interrupts[]`（**AG-UI 标准**）
- **中断恢复**：客户端发**新 run**携带 `RunAgentInput.resume[]` → Bridge 解析 → 唤醒 OpenHarness 阻塞的 future
- **不维护状态机**：完全由 OpenHarness `asyncio.Future` 管理活跃状态，AG-UI 协议只负责"通知 + 响应"

**三种暂停类型**（AG-UI Reason taxonomy）：
- `confirmation` — 二元确认（对应 `ask_user_question` 工具）— `ConfirmCard`
- `input_required` — 等待结构化输入（带 `responseSchema`）— `InputCard`
- `tool_call` — 工具调用审批（OpenHarness `permission_request` 等）— `ActionCard`

---

## 2. 状态机（OpenHarness 内部）

```
                ┌─────────────┐
                │   running   │ (QueryEngine 正常循环)
                └──────┬──────┘
                       │ ask_user_question 工具调用
                       │ ⇩ ToolExecutionStarted
                       ▼
                ┌─────────────┐
                │  pending    │ (ask_user_prompt 阻塞)
                │ (in-memory) │ - _pending_prompts[threadId]
                └──────┬──────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
  ┌──────────┐   ┌──────────┐   ┌──────────┐
  │ resolved │   │cancelled │   │ timeout  │
  └────┬─────┘   └────┬─────┘   └────┬─────┘
       │              │              │
       ▼              ▼              ▼
  ┌──────────┐   ┌──────────┐   ┌──────────┐
  │ resume   │   │  abort   │   │  abort   │
  │ (新 run) │   │ (新 run) │   │ (新 run) │
  │ RUN_INPUT│   │ RUN_INPUT│   │ RUN_INPUT│
  │ .resume[]│   │ .resume[]│   │ .resume[]│
  └────┬─────┘   └────┬─────┘   └────┬─────┘
       │              │              │
       ▼              ▼              ▼
   agent 继续     agent 收到     客户端收到
   执行         "(cancelled)"   RunError
                继续执行       (interrupt_expired)
```

**状态转换规则**：
- `running → pending`：`ask_user_question` 工具被调用，触发 `ask_user_prompt(question)` 阻塞
- `pending → resolved`：客户端发 resume（`status: "resolved"`, `payload: {...}`）→ future.set_result() → 工具返回 payload 转字符串
- `pending → cancelled`：客户端发 resume（`status: "cancelled"`, 无 payload）→ future.set_result("(cancelled)")
- `pending → timeout`：超时扫描器检测 `expires_at < now()`，存储置为 timeout 状态，内存 future 仍阻塞直到客户端响应（此时客户端会收到 `RunError`）

**关键不变量**：
- `_pending_prompts[threadId]` 是**进程内**内存（FastAPI worker）
- 同一 `threadId` 同时最多 1 个 pending interrupt（AG-UI 规定）
- `toolCallId` 跨 run 保持稳定（基于 hash 派生，见 [ag-ui-bridge.md §3.3](./ag-ui-bridge.md)）

---

## 3. AG-UI 协议时序图

### 3.1 confirmation 流程（happy path）

> 对应 OpenHarness `ask_user_question` 工具的**默认** schema（`{approved: bool}`）

```
Client                          AG-UI Bridge                  OpenHarness QueryEngine
  │                                  │                                  │
  │ POST /api/ag-ui/run              │                                  │
  │ {threadId: "sess_abc",           │                                  │
  │  runId: "run_1",                 │                                  │
  │  messages: [{role: "user",       │                                  │
  │             content: "删除 X"}]} │                                  │
  ├─────────────────────────────────►│                                  │
  │                                  │ 1. OPA 鉴权                      │
  │                                  │ 2. AGUIBridge.handle_run()       │
  │                                  │ 3. create QueryEngine            │
  │                                  │ 4. set ask_user_prompt callback  │
  │                                  │    (callback 创建 future)        │
  │                                  │ 5. async run_query(message)      │
  │                                  ├─────────────────────────────────►│
  │                                  │                                  │ 6. LLM 决定
  │                                  │    调用 ask_user_question       │
  │ SSE: RUN_STARTED                 │                                  │
  │ {threadId, runId: "run_1"}       │                                  │
  │ SSE: TEXT_MESSAGE_START          │                                  │
  │ {messageId: "msg_1",             │                                  │
  │  role: "assistant"}              │                                  │
  │ SSE: TEXT_MESSAGE_CONTENT        │                                  │
  │ {messageId: "msg_1",             │                                  │
  │  delta: "正在评估..."}           │                                  │
  │◄─────────────────────────────────┤                                  │
  │                                  │                                  │ 7. Tool start
  │ SSE: TOOL_CALL_START             │ ◄── ToolExecutionStarted ────────┤
  │ {toolCallId: "tc-7a3b9c",        │     (tool_name=                  │
  │  toolCallName:                   │      "ask_user_question",        │
  │   "ask_user_question",           │      tool_input.question)        │
  │  parentMessageId: "msg_1"}       │                                  │
  │ SSE: TOOL_CALL_ARGS              │                                  │
  │ {toolCallId: "tc-7a3b9c",        │                                  │
  │  delta: "{\"question\":          │                                  │
  │          \"要删除 X 节点吗？\"}"}│                                  │
  │ SSE: TOOL_CALL_END               │                                  │
  │ {toolCallId: "tc-7a3b9c"}        │                                  │
  │◄─────────────────────────────────┤                                  │
  │                                  │                                  │ 8. Tool 内部
  │                                  │    ask_user_prompt(question)    │
  │                                  │    ⏸ BLOCKS on future            │
  │                                  │                                  │
  │                                  │ 9. Bridge 检测 tool_name =       │
  │                                  │    "ask_user_question"           │
  │                                  │ 10. emit RunFinished with        │
  │                                  │     outcome.interrupts = [{...}]│
  │                                  │ 11. save_interrupt() 审计持久化   │
  │ SSE: RUN_FINISHED                │                                  │
  │ {threadId, runId: "run_1",       │                                  │
  │  outcome: {                      │                                  │
  │    type: "interrupt",            │                                  │
  │    interrupts: [{                │                                  │
  │      id: "int-001",              │                                  │
  │      reason: "confirmation",     │                                  │
  │      toolCallId: "tc-7a3b9c",    │                                  │
  │      message: "要删除 X 节点吗？",│                                 │
  │      responseSchema: {           │                                  │
  │        type: "object",           │                                  │
  │        properties: {             │                                  │
  │          approved: {type: "bool"}│                                  │
  │        },                        │                                  │
  │        required: ["approved"]    │                                  │
  │      },                          │                                  │
  │      expiresAt: "2026-06-08T     │                                  │
  │                  11:30:00Z",     │                                  │
  │      metadata: {                 │                                  │
  │        card_type: "confirm"      │                                  │
  │      }                           │                                  │
  │    }]                            │                                  │
  │  }}                              │                                  │
  │◄─────────────────────────────────┤                                  │
  │  SSE close                       │                                  │
  │                                  │                                  │
  │ 12. 客户端 CardRegistry 收到    │                                  │
  │     interrupts, 渲染 ConfirmCard │                                  │
  │     "要删除 X 节点吗？[确认][取消]"                                  │
  │                                  │                                  │
  │ 13. 用户点击 "确认"              │                                  │
  │                                  │                                  │
  │ POST /api/ag-ui/run              │                                  │
  │ {threadId: "sess_abc",           │                                  │
  │  runId: "run_2",                 │                                  │
  │  resume: [{                      │                                  │
  │    interruptId: "int-001",       │                                  │
  │    status: "resolved",           │                                  │
  │    payload: {approved: true}     │                                  │
  │  }]}                             │                                  │
  ├─────────────────────────────────►│                                  │
  │                                  │ 14. 查找 _pending_prompts        │
  │                                  │ 15. future.set_result("yes")     │
  │                                  │     (从 {approved: true} 派生)   │
  │                                  │ 16. ask_user_prompt 解除阻塞     │
  │                                  │ 17. ask_user_question 工具完成   │
  │                                  │     output="yes"                 │
  │                                  │ 18. update interrupt status=resolved│
  │                                  │ 19. 创建新 QueryEngine 继续执行 │
  │                                  ├─────────────────────────────────►│
  │ SSE: RUN_STARTED (runId_2)       │                                  │
  │ SSE: TOOL_CALL_RESULT            │                                  │
  │ {messageId: "msg_2",             │ ◄── ToolExecutionCompleted ─────┤
  │  toolCallId: "tc-7a3b9c",        │     (原 toolCallId，不重发 START)│
  │  content: "yes",                 │                                  │
  │  role: "tool"}                   │                                  │
  │  ⓘ 不重发 TOOL_CALL_START       │                                  │
  │◄─────────────────────────────────┤                                  │
  │ SSE: TEXT_MESSAGE_START          │                                  │
  │ SSE: TEXT_MESSAGE_CONTENT        │                                  │
  │  "已删除 X 节点"                │ ◄── AssistantTextDelta ──────────┤
  │ SSE: TEXT_MESSAGE_END            │                                  │
  │  ... (more deltas)               │                                  │
  │ SSE: RUN_FINISHED                │                                  │
  │ {outcome: {type: "success"},     │                                  │
  │  result: {usage: {...}}}         │                                  │
  │◄─────────────────────────────────┤                                  │
```

### 3.2 input_required 流程

> 对应 OpenHarness 工具 `ask_user_question` 携带**额外参数**（如 `input_type=select`），Bridge 自动派生 `responseSchema: {value: string}`

```
Client                          AG-UI Bridge                  OpenHarness QueryEngine
  │                                  │                                  │
  │ POST /api/ag-ui/run              │                                  │
  │ {message: "查询过去几天的销售"}  │                                  │
  │                                  │ ... (steps 1-7 同 3.1)            │
  │                                  │                                  │ 8. ask_user_question
  │                                  │    携带 input_type="select"      │
  │                                  │    ask_user_prompt("请选择时间范围")│
  │                                  │    ⏸ BLOCKS                     │
  │                                  │                                  │
  │ SSE: RUN_FINISHED                │                                  │
  │ {outcome: {                      │                                  │
  │   type: "interrupt",             │                                  │
  │   interrupts: [{                 │                                  │
  │     id: "int-002",               │                                  │
  │     reason: "input_required",    │                                  │
  │     message: "请选择时间范围",   │                                  │
  │     responseSchema: {            │                                  │
  │       type: "object",            │                                  │
  │       properties: {              │                                  │
  │         value: {type: "string"}  │                                  │
  │       },                         │                                  │
  │       required: ["value"]        │                                  │
  │     },                           │                                  │
  │     metadata: {                  │                                  │
  │       card_type: "input",        │                                  │
  │       input_options: [           │                                  │
  │         {value: "1d", label: "过去 1 天"},│                          │
  │         {value: "7d", label: "过去 7 天"},│                          │
  │         {value: "30d", label: "过去 30 天"}│                          │
  │       ]                          │                                  │
  │     }                            │                                  │
  │   }]                             │                                  │
  │ }}                               │                                  │
  │◄─────────────────────────────────┤                                  │
  │                                  │                                  │
  │ 9. 客户端渲染 InputCard          │                                  │
  │    下拉框 + 提交按钮             │                                  │
  │                                  │                                  │
  │ 10. 用户选择 "过去 7 天"         │                                  │
  │                                  │                                  │
  │ POST /api/ag-ui/run              │                                  │
  │ {runId: "run_2",                 │                                  │
  │  resume: [{                      │                                  │
  │    interruptId: "int-002",       │                                  │
  │    status: "resolved",           │                                  │
  │    payload: {value: "7d"}        │                                  │
  │  }]}                             │                                  │
  ├─────────────────────────────────►│                                  │
  │                                  │ 11. future.set_result("7d")      │
  │                                  │ 12. ask_user_question 完成        │
  │                                  │ 13. 继续流式事件                 │
  │ ... (查询过去 7 天销售数据)       │                                  │
```

### 3.3 cancellation 流程

> 用户主动放弃（不提供有效输入）

```
Client                          AG-UI Bridge
  │                                  │
  │ 收到 RUN_FINISHED.interrupts     │
  │ 用户点击 "取消"                  │
  │                                  │
  │ POST /api/ag-ui/run              │
  │ {runId: "run_2",                 │
  │  resume: [{                      │
  │    interruptId: "int-001",       │
  │    status: "cancelled"           │
  │  }]}                             │
  ├─────────────────────────────────►│
  │                                  │ 1. future.set_result("(cancelled)")
  │                                  │ 2. ask_user_question 工具返回
  │                                  │    output="(cancelled)"            │
  │                                  │ 3. LLM 收到 "(cancelled)"        │
  │                                  │ 4. 决定放弃当前操作              │
  │ SSE: RUN_STARTED                 │
  │ SSE: TOOL_CALL_RESULT            │
  │ {toolCallId, content: "(cancelled)"}│
  │ SSE: TEXT_MESSAGE_CONTENT        │
  │  "操作已取消"                    │
  │ SSE: RUN_FINISHED                │
  │ {outcome: {type: "success"}}     │
  │◄─────────────────────────────────┤
```

### 3.4 timeout 流程（客户端 30 分钟内未响应）

```
Client                          AG-UI Bridge                  Background Scanner
  │                                  │                                  │
  │ 收到 RUN_FINISHED.interrupts     │                                  │
  │ 客户端倒计时显示                 │                                  │
  │                                  │                                  │
  │                                  │ 1. Scanner 每 60s 扫描          │
  │                                  │    get_pending_interrupts_      │
  │                                  │    with_timeout_lt(now)         │
  │                                  │ 2. 找到 int-001                 │
  │                                  │    (expires_at < now)           │
  │                                  │ 3. update_status(              │
  │                                  │     id=int-001,                 │
  │                                  │     status=TIMEOUT)             │
  │                                  │                                  │
  │ 4. (30 分钟后) 客户端仍在等待     │                                  │
  │                                  │                                  │
  │ 5. 客户端因其他操作触发新请求     │                                  │
  │    或主动取消                    │                                  │
  │                                  │                                  │
  │                                  │ ⓘ 重要：客户端的 future 仍      │
  │                                  │   阻塞中。客户端可：            │
  │                                  │                                  │
  │                                  │ 方案 A：继续等待 5 分钟         │
  │                                  │   → future 自然超时            │
  │                                  │   → tool 输出 "(timeout)"       │
  │                                  │   → LLM 继续                    │
  │                                  │                                  │
  │                                  │ 方案 B：发新 run 强制取消       │
  │                                  │   → future.set_result("(cancelled)")│
  │                                  │                                  │
  │                                  │ 方案 C：什么都不做              │
  │                                  │   → 5 分钟后 future 自然超时   │
  │                                  │   → 客户端 SSE 仍在 stream     │
  │                                  │   → 客户端可关闭连接            │
```

**超时关键不变量**（AG-UI 规定）：
- 客户端不应在 `expiresAt` 之后**主动**发 resume → 会被 Bridge 拒绝并返回 `RunError(code="interrupt_expired")`
- 服务端扫描器**仅**修改存储状态（审计），**不**主动 resolve future（避免与服务端判定竞态）
- 客户端可**查询** `GET /api/ag-ui/interrupts/{id}` 获取最终状态

### 3.5 并发冲突（同 threadId 第二 run）

```
Client A                        Client B                       AG-UI Bridge
  │                                  │                              │
  │ SSE: RUN_FINISHED.interrupts     │                              │
  │  int-001 (id)                    │                              │
  │◄─────────────────────────────────┤                              │
  │                                  │                              │
  │ POST /api/ag-ui/run {runId:"r2", resume:[{id: int-001, ...}]}  │
  ├──────────────────────────────────┼─────────────────────────────►│
  │                                  │                              │ 1. 查 _active_runs
  │                                  │    {sess_abc: None}          │   (int-001 已中断)
  │                                  │ 2. resolve future            │
  │                                  │ 3. 启动新 run_2              │
  │                                  │ 4. _active_runs[sess_abc]    │
  │                                  │    = task_run_2              │
  │ SSE: RUN_STARTED (run_2)         │                              │
  │  ... (继续流式)                  │                              │
  │                                  │                              │
  │                                  │ POST /api/ag-ui/run {runId:"r3"}  │
  │                                  ├─────────────────────────────►│
  │                                  │                              │ 5. 查 _active_runs
  │                                  │    {sess_abc: task_run_2}    │   仍活跃！
  │                                  │ 409 Conflict                 │ 6. return 409
  │                                  │◄─────────────────────────────┤
  │                                  │ 7. Client B 等待 run_2 完成  │
```

**冲突处理**：
- AG-UI 规定：同一 `threadId` 同时最多 1 个 active run
- Bridge 在收到新 run 时检查 `_active_runs[threadId]`，若存在则返回 `409 Conflict`
- 客户端应等待前一个 run 完成（含 RUN_FINISHED）后再发起新 run

---

## 4. 幂等性保证

**场景**：网络不稳定时，客户端重发同一 resume 请求。

**AG-UI 规定**：相同 `(threadId, interruptId, status, payload)` 可安全重放（[Interrupts §Contract rules](https://docs.ag-ui.com/concepts/interrupts#contract-rules) rule 5）。

**Bridge 实现**：
- `future.set_result()` 只能调用一次（`asyncio.Future` 保证）
- 重放 resume → Bridge 检测 `interruptId` 在 `_pending_prompts` 中已不存在 → 返回 `RunError(code="unknown_interrupt")`（**已 resolve 视为 no-op**）

**存储层幂等**（`SQLiteAGUIInterruptStorage`）：
- `save_interrupt` 使用 `INSERT OR REPLACE` 幂等
- `update_status` 对已 resolved/timeout 的记录是 no-op

---

## 5. 工具 schema → responseSchema 派生

| OpenHarness 工具 | reason | responseSchema | 客户端卡片 |
|-----------------|--------|---------------|-----------|
| `ask_user_question`（默认） | `confirmation` | `{type: "object", properties: {approved: {type: "boolean"}}, required: ["approved"]}` | `ConfirmCard` |
| `ask_user_question`（含 `input_type=select`） | `input_required` | `{type: "object", properties: {value: {type: "string"}}, required: ["value"]}` | `InputCard` |
| `ask_user_question`（含 `input_type=multiselect`） | `input_required` | `{type: "object", properties: {value: {type: "array", items: {type: "string"}}}, required: ["value"]}` | `InputCard` (multi) |
| `ask_user_question`（含 `input_type=text`） | `input_required` | `{type: "object", properties: {value: {type: "string"}}, required: ["value"]}` | `InputCard` (text) |
| `permission_request` | `tool_call` | `{type: "object", properties: {approved: {type: "boolean"}, editedArgs: {type: "object"}}, required: ["approved"]}` | `ActionCard` |
| 任何 `tool_name` 匹配 `*_approval` | `tool_call` | 同上 | `ActionCard` |
| 其他 | `"odap:" + tool_name` | `{type: "object", properties: {value: {type: "string"}}}` | 通用 `ActionCard` |

**完整派生规则**：[ag-ui-bridge.md §3.4.1](./ag-ui-bridge.md#34-hitl-中断事件最复杂单独成节)

---

## 6. 客户端 resume 解析

`RunAgentInput.resume[]` 解析为 OpenHarness `ask_user_prompt` 返回值（字符串）：

| reason | payload | 转换结果（ask_user_prompt 返回值） |
|--------|---------|----------------------------------|
| `confirmation` | `{approved: true}` | `"yes"` |
| `confirmation` | `{approved: false}` | `"no"` |
| `input_required` (select) | `{value: "7d"}` | `"7d"` |
| `input_required` (multiselect) | `{value: ["A", "B"]}` | `"A, B"` |
| `input_required` (text) | `{value: "any text"}` | `"any text"` |
| `tool_call` | `{approved: true, editedArgs: {...}}` | JSON 字符串（让 LLM 解析） |
| `cancelled` | `null` | `"(cancelled)"` |

**为什么简化 approved → yes/no？** OpenHarness `ask_user_question` 工具返回**字符串**给 LLM，自然语言 yes/no 比 `{approved: true}` 更易理解。

---

## 7. 单元测试

按 AGENTS.md 规则 9，新增 `tests/unit/test_hitl_flow.py`：

```python
# tests/unit/test_hitl_flow.py

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from odap.biz.core.qa.agui_bridge import AGUIBridge
from odap.biz.core.qa.agui_models import (
    Interrupt, InterruptReason, InterruptStatus, ResumeEntry, ResumeStatus, RunAgentInput
)
from odap.biz.core.qa.storage.sqlite_agui_interrupt_storage import SQLiteAGUIInterruptStorage


# === 中断触发 ===

@pytest.mark.asyncio
async def test_ask_user_question_triggers_interrupt():
    """验证 ask_user_question 工具触发 RunFinished.interrupts。"""
    bridge = AGUIBridge()

    # Mock QueryEngine 流式发出 ToolExecutionStarted
    async def mock_stream():
        yield ToolExecutionStarted(
            tool_name="ask_user_question",
            tool_input={"question": "要删除 X 吗？"},
        )
        # 模拟工具阻塞... future 永远不 resolve
        await asyncio.sleep(60)
        yield ToolExecutionCompleted(
            tool_name="ask_user_question",
            output="yes",
            is_error=False,
        )

    with patch.object(bridge, "_create_query_engine", return_value=mock_stream()):
        events = []
        async for event in bridge.handle_run(
            thread_id="sess_1",
            run_id="run_1",
            message="删除 X",
        ):
            events.append(event)
            if event.type == "RUN_FINISHED":
                break

    # 验证最后一个事件是 RUN_FINISHED 携带 interrupt
    assert events[-1].type == "RUN_FINISHED"
    assert events[-1].outcome.type == "interrupt"
    assert len(events[-1].outcome.interrupts) == 1
    interrupt = events[-1].outcome.interrupts[0]
    assert interrupt.reason == "confirmation"
    assert interrupt.message == "要删除 X 吗？"
    assert "approved" in interrupt.responseSchema["properties"]


# === 中断恢复 ===

@pytest.mark.asyncio
async def test_resume_resolves_ask_user_prompt():
    """验证客户端 resume 触发 future.set_result 并启动新 run。"""
    bridge = AGUIBridge()

    # 1. 模拟活跃 pending interrupt
    future = asyncio.Future()
    bridge._pending_prompts["sess_1"] = {
        "interruptId": "int-001",
        "future": future,
        "tool_call_id": "tc-abc",
        "created_at": datetime.now(),
        "timeout_at": datetime.now() + timedelta(minutes=30),
    }

    # 2. 客户端发 resume
    resume_input = RunAgentInput(
        threadId="sess_1",
        runId="run_2",
        resume=[
            ResumeEntry(
                interruptId="int-001",
                status=ResumeStatus.RESOLVED,
                payload={"approved": True},
            )
        ],
    )

    # 3. 调用 handle_resume（不真正流式）
    with patch.object(bridge, "_run_query_resume") as mock_resume:
        mock_resume.return_value = async_iter([])  # 空流
        async for _ in bridge.handle_resume(resume_input):
            pass

    # 4. 验证 future 被设置为 "yes"
    assert future.done()
    assert future.result() == "yes"

    # 5. 验证 _pending_prompts 已清理
    assert "sess_1" not in bridge._pending_prompts


# === toolCallId 稳定 ===

def test_tool_call_id_stable_across_runs():
    """验证同一工具调用在 run_1 和 run_2 中 toolCallId 一致。"""
    from odap.biz.core.qa.agui_bridge import make_tool_call_id

    tool_input = {"question": "要删除 X 吗？"}

    id_run1 = make_tool_call_id("sess_1", "ask_user_question", tool_input)
    id_run2 = make_tool_call_id("sess_1", "ask_user_question", tool_input)

    assert id_run1 == id_run2  # 稳定 hash

    # 不同 input → 不同 ID
    id_other = make_tool_call_id("sess_1", "ask_user_question", {"question": "其他"})
    assert id_other != id_run1


# === 错误处理 ===

@pytest.mark.asyncio
async def test_resume_with_unknown_interrupt_id_returns_error():
    """验证 resume 中 interruptId 找不到 → RunError。"""
    bridge = AGUIBridge()
    resume_input = RunAgentInput(
        threadId="sess_1",
        runId="run_2",
        resume=[
            ResumeEntry(
                interruptId="int-nonexistent",
                status=ResumeStatus.RESOLVED,
                payload={"approved": True},
            )
        ],
    )

    events = []
    async for event in bridge.handle_resume(resume_input):
        events.append(event)

    assert any(e.type == "RUN_ERROR" for e in events)
    error = next(e for e in events if e.type == "RUN_ERROR")
    assert error.code == "unknown_interrupt"


@pytest.mark.asyncio
async def test_resume_after_expiry_returns_error():
    """验证 resume 超过 expiresAt → RunError。"""
    bridge = AGUIBridge()

    # 创建已过期的 pending
    future = asyncio.Future()
    bridge._pending_prompts["sess_1"] = {
        "interruptId": "int-001",
        "future": future,
        "tool_call_id": "tc-abc",
        "created_at": datetime.now() - timedelta(hours=1),
        "timeout_at": datetime.now() - timedelta(minutes=30),  # 已过期
    }

    resume_input = RunAgentInput(
        threadId="sess_1",
        runId="run_2",
        resume=[ResumeEntry(interruptId="int-001", status=ResumeStatus.RESOLVED, payload={})],
    )

    events = []
    async for event in bridge.handle_resume(resume_input):
        events.append(event)

    assert any(e.code == "interrupt_expired" for e in events if e.type == "RUN_ERROR")


# === responseSchema 派生 ===

def test_response_schema_for_confirmation():
    """验证 ask_user_question → confirmation responseSchema。"""
    from odap.biz.core.qa.agui_bridge import derive_response_schema

    schema = derive_response_schema("ask_user_question", {"question": "test"})
    assert schema["type"] == "object"
    assert "approved" in schema["properties"]
    assert schema["properties"]["approved"]["type"] == "boolean"
    assert "approved" in schema["required"]


def test_response_schema_for_input_required():
    """验证 ask_user_question with input_type=select → input_required schema。"""
    from odap.biz.core.qa.agui_bridge import derive_response_schema

    schema = derive_response_schema(
        "ask_user_question",
        {"question": "test", "input_type": "select", "options": ["A", "B"]},
    )
    assert "value" in schema["properties"]
    assert schema["properties"]["value"]["type"] == "string"
    assert "value" in schema["required"]


def test_response_schema_for_tool_call():
    """验证 permission_request → tool_call schema with editedArgs。"""
    from odap.biz.core.qa.agui_bridge import derive_response_schema

    schema = derive_response_schema("permission_request", {"action": "delete", "node_id": "X"})
    assert "approved" in schema["properties"]
    assert "editedArgs" in schema["properties"]
    assert "approved" in schema["required"]


# === 超时扫描器 ===

@pytest.mark.asyncio
async def test_timeout_scanner_marks_expired(tmp_path):
    """验证超时扫描器将 pending 标记为 timeout。"""
    db = tmp_path / "qa_agui.db"
    storage = SQLiteAGUIInterruptStorage(db_path=str(db))

    # 创建已过期的 pending
    record = AGUIInterruptRecord(
        id="int-001",
        session_id="sess_1",
        run_id="run_1",
        tool_call_id="tc-1",
        tool_name="ask_user_question",
        reason=InterruptReason.CONFIRMATION.value,
        message="过期",
        response_schema={},
        expires_at=datetime.now() - timedelta(seconds=1),
    )
    storage.save_interrupt(record)

    from odap.biz.core.qa.agui_timeout_scanner import AGUIInterruptTimeoutScanner
    scanner = AGUIInterruptTimeoutScanner(storage)
    count = await scanner.scan_and_timeout()

    assert count == 1
    updated = storage.list_by_session("sess_1")[0]
    assert updated.status == InterruptStatus.TIMEOUT
```

---

## 8. 端到端测试

```python
# tests/e2e/test_hitl_flow.py

import json
from fastapi.testclient import TestClient
from odap.web.app import app


def test_full_hitl_confirm_flow():
    """端到端：ask → interrupt → confirm → resume → done。"""
    client = TestClient(app)

    # 1. 启动 run（agent 会触发 ask_user_question）
    with client.stream(
        "POST",
        "/api/ag-ui/run",
        json={
            "threadId": "sess_e2e",
            "runId": "run_1",
            "messages": [{"role": "user", "content": "删除 X 节点"}],
        },
        headers={"Authorization": "Bearer <test_token>"},
    ) as response:
        interrupt_id = None
        tool_call_id = None
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            if event["type"] == "RUN_FINISHED":
                outcome = event.get("outcome", {})
                if outcome.get("type") == "interrupt":
                    interrupt = outcome["interrupts"][0]
                    interrupt_id = interrupt["id"]
                    tool_call_id = interrupt["toolCallId"]
                    break

    assert interrupt_id is not None, "Agent should have triggered HITL"
    assert tool_call_id is not None

    # 2. 客户端发 resume
    with client.stream(
        "POST",
        "/api/ag-ui/run",
        json={
            "threadId": "sess_e2e",
            "runId": "run_2",
            "resume": [
                {
                    "interruptId": interrupt_id,
                    "status": "resolved",
                    "payload": {"approved": True},
                }
            ],
        },
        headers={"Authorization": "Bearer <test_token>"},
    ) as response:
        events = []
        for line in response.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

    # 3. 验证收到 TOOL_CALL_RESULT（带原 toolCallId）+ RUN_FINISHED success
    result_event = next(
        (e for e in events if e["type"] == "TOOL_CALL_RESULT" and e["toolCallId"] == tool_call_id),
        None,
    )
    assert result_event is not None, f"Should receive TOOL_CALL_RESULT for {tool_call_id}"
    assert result_event["content"] == "yes"

    final = events[-1]
    assert final["type"] == "RUN_FINISHED"
    assert final["outcome"]["type"] == "success"
```

---

## 9. 关联文档

- [ag-ui-bridge.md §3.4](./ag-ui-bridge.md) — Interrupt 事件翻译（含字段映射、reason 路由表、responseSchema 派生）
- [data-model.md §3](../data-model.md) — 审计表 `qa_agui_interrupts` schema
- [generative-ui-card.md](./generative-ui-card.md) — ConfirmCard / InputCard / ActionCard 卡片契约
- [AG-UI Interrupts 官方文档](https://docs.ag-ui.com/concepts/interrupts) — interrupt-aware lifecycle 权威定义
- [OpenHarness ask_user_question_tool](../../../openharness/src/openharness/tools/ask_user_question_tool.py) — HITL 触发器
- [OpenHarness QueryEngine](../../../openharness/src/openharness/engine/query_engine.py) — 内存状态机 + `ask_user_prompt` 回调
- [plan.md §AG-UI Bridge 事件映射](../plan.md#ag-ui-bridge-事件映射核心设计) — 事件映射

---

**Version**: 1.0 (FINAL) | **Date**: 2026-06-08
