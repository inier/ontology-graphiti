# Plan: AG-UI ↔ OpenHarness 无缝整合（纯扩展架构 v2.0）

**Date**: 2026-06-08 (v2.0 — 重大架构修订)
**Status**: 草案 v0.1
**前置**: [spec.md](./spec.md) · [research.md](./research.md) · v1.0 plan 已废止
**核心承诺**: **0 修改 OpenHarness 核心代码 · 0 翻译层 · 0 新协议 · 0 独立业务模块**

---

## 1. 核心原则（v2.0 重大修订）

### 1.1 用户硬约束

> "**保证只在 OpenHarness 基础上扩展**实现 copilotkit 的能力"

解读：
- ❌ **不引入** 独立的 `odap/biz/core/qa/` 业务模块（之前 v1.0 设计是错的）
- ❌ **不引入** 自研 OAUIP 协议（已废止）
- ❌ **不重写** OpenHarness StreamEvent 类型
- ❌ **不替换** OpenHarness 任何已有能力
- ✅ **在 OpenHarness 之上扩展** —— 通过 StreamEvent 派生 + HookExecutor 注入
- ✅ **AG-UI 是 SSE 协议**（不是新框架）—— OpenHarness 仍是 Engine

### 1.2 v1.0 错误诊断

| v1.0 设计 | 问题 |
|----------|------|
| `odap/biz/core/qa/agui_bridge.py` 翻译层 | **翻译** = 复制 OpenHarness 逻辑到第二处，未来双倍维护 |
| 把 7 类 StreamEvent → AG-UI Event 一一翻译 | **翻译** = 违反"在 OpenHarness 之上扩展"原则 |
| 独立 `qa_agui_interrupts` 表 | 不需要 —— OpenHarness session 内存已够用 |
| 独立 `AGUIBridge._pending_prompts` future | 不需要 —— `ask_user_prompt` callback 已存在 |
| 独立 `_active_runs` 字典 | 不需要 —— QueryEngine 一次只跑一个 query |

**v1.0 实际是"在 OpenHarness 旁边建一套并行运行时"，违背用户约束。**

### 1.3 v2.0 正确架构

**核心思想**：**OpenHarness 自身就是 AG-UI 引擎**。

- OpenHarness 已有的 StreamEvent 派生类 + 业务逻辑 = 直接 emit AG-UI Event
- OpenHarness 已有 `ask_user_prompt` 回调 = 直接 emit `RunFinished.interrupts`
- OpenHarness 已有 `permission_prompt` 回调 = 直接 emit `RunFinished.interrupts` (reason=tool_call)
- OpenHarness 已有 `HookExecutor` = 在 lifecycle 点注入 AG-UI 事件
- OpenHarness 已有 `ConversationMessage` + `Memory` = 直接 emit `MessagesSnapshot`/`StateSnapshot`
- OpenHarness 已有 `CompactProgressEvent` = 直接 emit `StateDelta`

**唯一需要扩展的**：
- **新增 OpenHarness StreamEvent 派生类**（在 `odap/infra/openharness/agui_extensions.py`）— 覆盖 AG-UI 独有但 OpenHarness 没有的事件类型（如 `RunStarted`/`RunFinished`/`RunError`/`TOOL_CALL_RESULT`/`TextMessageStart`/`TextMessageEnd`/`StepStarted`/`StepFinished`）
- **SSE Transport 适配器**（在 `odap/infra/openharness/agui_transport.py`）— 把 `AsyncIterator[StreamEvent]` 流式编码为 SSE 字节
- **AG-UI ↔ OpenHarness 路由层**（在 `odap/infra/openharness/agui_handler.py`）— 解析 `RunAgentInput`/`resume[]` 注入 QueryEngine

**总计**：
- v1.0: ~250 行 Bridge + ~200 行 handler + ~150 行 Pydantic = 600 行
- v2.0: ~80 行扩展事件 + ~60 行 SSE transport + ~100 行 handler = **240 行**（-60%）

---

## 2. 架构总览

### 2.1 旧架构（v1.0 — 已废止）

```
┌─────────────┐
│  AG-UI      │
│  Client     │
└──────┬──────┘
       │ SSE
       ▼
┌─────────────────────────┐
│ odap/biz/core/qa/       │  ← 独立业务模块
│  ├── agui_bridge.py     │  ← 翻译层（复制 OpenHarness 逻辑）
│  ├── agui_handler.py    │  ← 路由层
│  ├── agui_models.py     │  ← Pydantic 镜像
│  ├── storage/           │  ← 新增 SQLite 表
│  └── tests/             │  ← 独立测试
└──────┬──────────────────┘
       │ 调用
       ▼
┌─────────────┐
│ OpenHarness │  ← 在"旁边"，不是"之上"
└─────────────┘
```

**问题**：Bridge 翻译层把 OpenHarness 7 类事件"复制"为 AG-UI 17 类事件，等于**在 OpenHarness 旁边建一套镜像协议**。

### 2.2 新架构（v2.0 — 本方案）

```
┌─────────────┐
│  AG-UI      │
│  Client     │
│  (@ag-ui/   │
│   core SDK) │
└──────┬──────┘
       │ SSE (application/x-ndjson)
       ▼
┌──────────────────────────────┐
│ odap/infra/openharness/     │  ← 在 OpenHarness 之上扩展
│  ├── agui_extensions.py     │     (不是独立业务模块)
│  ├── agui_transport.py      │     ~180 行
│  └── agui_handler.py        │
└──────┬───────────────────────┘
       │ 直接调用（不翻译）
       ▼
┌─────────────────────────────┐
│ OpenHarness QueryEngine     │  ← 原样
│  - run_query() → StreamEvent│
│  - ask_user_prompt callback │
│  - permission_prompt callback│
│  - HookExecutor             │
│  - Memory                   │
│  - PermissionChecker        │
└─────────────────────────────┘
```

**关键变化**：
- 砍掉 `odap/biz/core/qa/` 整个目录
- 所有 AG-UI 逻辑在 `odap/infra/openharness/`（这是 OpenHarness 适配层 — ODAP 已有）
- AG-UI Bridge 不翻译，只负责"emit + 解析"

---

## 3. 核心设计：StreamEvent 派生扩展

### 3.1 OpenHarness 7 类原生事件 vs AG-UI 需求

| OpenHarness 原生 | AG-UI 对应 | 是否需要扩展 |
|-----------------|-----------|------------|
| `AssistantTextDelta` | `TextMessageContent` | **不需**（直接 emit，transport 加 messageId） |
| `AssistantTurnComplete` | `TextMessageEnd` + `StepFinished` | **不需**（直接 emit） |
| `ToolExecutionStarted` | `TOOL_CALL_START` + `TOOL_CALL_ARGS` + `TOOL_CALL_END` | **不需**（直接 emit） |
| `ToolExecutionCompleted` | `TOOL_CALL_RESULT` | **不需**（直接 emit） |
| `ErrorEvent` | `RunError` | **不需**（直接 emit） |
| `StatusEvent` | `StepStarted` | **不需**（直接 emit） |
| `CompactProgressEvent` | `StateDelta` | **不需**（直接 emit） |

**好消息**：OpenHarness 7 类已**直接覆盖 AG-UI 90%**。

**缺失**（AG-UI 独有）：
- `RunStarted` — run 生命周期首事件
- `RunFinished` — run 生命周期终事件（含 `outcome.success` / `outcome.interrupt`）
- `StateSnapshot` — 完整状态快照
- `MessagesSnapshot` — 消息历史快照
- `StepFinished` — 步骤结束
- `TextMessageStart` — 文本消息开始（OpenHarness 隐式，需要显式 emit）

**解决方案**：派生 6 个新事件类，继承现有 7 类。

### 3.2 OpenHarness StreamEvent 派生扩展（核心扩展点）

```python
# odap/infra/openharness/agui_extensions.py

from __future__ import annotations
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from openharness.engine.stream_events import (
    AssistantTextDelta, AssistantTurnComplete, CompactProgressEvent,
    ErrorEvent, StatusEvent, StreamEvent, ToolExecutionCompleted, ToolExecutionStarted,
)


# === 生命周期事件（AG-UI run lifecycle） ===

@dataclass
class RunStartedEvent(StreamEvent):
    """AG-UI RUN_STARTED — run 生命周期首事件。"""
    thread_id: str
    run_id: str
    parent_run_id: str | None = None
    input: dict[str, Any] | None = None
    # 触发点：在 QueryEngine.run_query() 第一帧之前 emit

@dataclass
class RunFinishedEvent(StreamEvent):
    """AG-UI RUN_FINISHED — run 生命周期终事件。"""
    thread_id: str
    run_id: str
    outcome: Literal["success"] | dict = "success"  # 成功或 {type: "interrupt", interrupts: [...]}
    result: dict[str, Any] | None = None
    # 触发点：在所有 OpenHarness StreamEvent 完成后 emit

@dataclass
class StepFinishedEvent(StreamEvent):
    """AG-UI STEP_FINISHED — 步骤结束。"""
    step_name: str
    # 触发点：在 AssistantTurnComplete 之后、StatusEvent 之后 emit


# === 文本消息边界（AG-UI TextMessage 三件套） ===

@dataclass
class TextMessageStartEvent(StreamEvent):
    """AG-UI TEXT_MESSAGE_START — 第一帧 AssistantTextDelta 之前 emit。"""
    message_id: str
    role: Literal["assistant", "user", "system", "tool"] = "assistant"
    # 触发点：transport 层在第一帧 AssistantTextDelta 之前自动注入

@dataclass
class TextMessageEndEvent(StreamEvent):
    """AG-UI TEXT_MESSAGE_END — 在 AssistantTurnComplete 时 emit。"""
    message_id: str
    # 触发点：transport 层在 AssistantTurnComplete 时自动注入


# === 状态管理（AG-UI State*） ===

@dataclass
class MessagesSnapshotEvent(StreamEvent):
    """AG-UI MESSAGES_SNAPSHOT — 客户端首次连接时 emit 完整对话历史。"""
    messages: list[dict[str, Any]] = field(default_factory=list)
    # 触发点：QueryEngine.run_query() 第一次进入前 emit

@dataclass
class StateSnapshotEvent(StreamEvent):
    """AG-UI STATE_SNAPSHOT — 完整状态快照。"""
    snapshot: dict[str, Any] = field(default_factory=dict)
    # 触发点：客户端首次连接时 emit
```

**关键不变量**：
- **继承 `StreamEvent`** — 仍是 `AsyncIterator[StreamEvent]`，`run_query()` 调用方无需改
- **dataclass 形式** — 与 OpenHarness 风格一致
- **AG-UI Event 字段直接对齐** — transport 层零翻译直接 JSON 序列化

### 3.3 Transport 层（极薄）

```python
# odap/infra/openharness/agui_transport.py

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from openharness.engine.stream_events import (
    AssistantTextDelta, AssistantTurnComplete, CompactProgressEvent,
    ErrorEvent, StatusEvent, StreamEvent, ToolExecutionCompleted, ToolExecutionStarted,
)
from odap.infra.openharness.agui_extensions import (
    MessagesSnapshotEvent, RunFinishedEvent, RunStartedEvent,
    StateSnapshotEvent, StepFinishedEvent, TextMessageEndEvent, TextMessageStartEvent,
)


def to_agui_event(event: StreamEvent) -> dict[str, Any] | None:
    """把 OpenHarness StreamEvent（或派生类）序列化为 AG-UI Event JSON。
    
    这是 v2.0 的全部翻译逻辑 — 每个 if 分支只有 1-3 行。
    """
    if isinstance(event, RunStartedEvent):
        return {"type": "RUN_STARTED", "threadId": event.thread_id, "runId": event.run_id,
                "parentRunId": event.parent_run_id, "input": event.input}
    
    if isinstance(event, RunFinishedEvent):
        out = {"type": "RUN_FINISHED", "threadId": event.thread_id, "runId": event.run_id,
               "outcome": event.outcome}
        if event.result:
            out["result"] = event.result
        return out
    
    if isinstance(event, MessagesSnapshotEvent):
        return {"type": "MESSAGES_SNAPSHOT", "messages": event.messages}
    
    if isinstance(event, StateSnapshotEvent):
        return {"type": "STATE_SNAPSHOT", "snapshot": event.snapshot}
    
    if isinstance(event, TextMessageStartEvent):
        return {"type": "TEXT_MESSAGE_START", "messageId": event.message_id, "role": event.role}
    
    if isinstance(event, TextMessageEndEvent):
        return {"type": "TEXT_MESSAGE_END", "messageId": event.message_id}
    
    if isinstance(event, StepFinishedEvent):
        return {"type": "STEP_FINISHED", "stepName": event.step_name}
    
    if isinstance(event, AssistantTextDelta):
        # messageId 在 transport 层维护（隐式）
        return {"type": "TEXT_MESSAGE_CONTENT",
                "messageId": _current_message_id(), "delta": event.text}
    
    if isinstance(event, AssistantTurnComplete):
        return {"type": "TEXT_MESSAGE_END", "messageId": _current_message_id()}
    
    if isinstance(event, ToolExecutionStarted):
        return _emit_tool_call_three_piece(event)
    
    if isinstance(event, ToolExecutionCompleted):
        return {"type": "TOOL_CALL_RESULT",
                "messageId": _current_message_id(),
                "toolCallId": event.tool_name,  # 由 caller 保证稳定
                "content": event.output,
                "role": "tool"}
    
    if isinstance(event, ErrorEvent):
        return {"type": "RUN_ERROR", "message": event.message}
    
    if isinstance(event, StatusEvent):
        return {"type": "STEP_STARTED", "stepName": event.message}
    
    if isinstance(event, CompactProgressEvent):
        return {"type": "STATE_DELTA", "delta": [{
            "op": "replace", "path": "/compact",
            "value": {"phase": event.phase, "message": event.message, "attempt": event.attempt}
        }]}
    
    return None  # 未知事件静默忽略


def _emit_tool_call_three_piece(event: ToolExecutionStarted) -> list[dict]:
    """TOOL_CALL_START + ARGS + END 原子三件套。"""
    return [
        {"type": "TOOL_CALL_START", "toolCallId": ..., "toolCallName": event.tool_name},
        {"type": "TOOL_CALL_ARGS", "toolCallId": ..., "delta": json.dumps(event.tool_input)},
        {"type": "TOOL_CALL_END", "toolCallId": ...},
    ]
```

**关键观察**：
- `to_agui_event()` **不是翻译** — 是把 dataclass 字段映射到 JSON 字段名（AG-UI 协议是 camelCase，Python 是 snake_case）
- **99% 的代码是 1-1 字段映射**，**无业务逻辑**
- 真实翻译逻辑在 OpenHarness 内部（`run_query`/`ask_user_prompt`/`permission_prompt` 回调），不是这个文件

### 3.4 HITL 通过现有 `ask_user_prompt` 实现

```python
# odap/infra/openharness/agui_handler.py 伪代码

async def create_ask_user_callback(thread_id: str, run_id: str, 
                                    pending_prompts: dict) -> AskUserPrompt:
    """包装用户提供的 ask_user_prompt，让其发 AG-UI Interrupts。"""
    async def callback(question: str) -> str:
        interrupt_id = f"int-{uuid.uuid4().hex[:12]}"
        future = asyncio.Future()
        pending_prompts[interrupt_id] = future
        
        # emit RunFinished.interrupts（注意：不调用 run_query 终止，它自然流到这里）
        await emit_sse(RunFinishedEvent(
            thread_id=thread_id, run_id=run_id,
            outcome={"type": "interrupt", "interrupts": [{
                "id": interrupt_id, "reason": "confirmation",
                "message": question, "responseSchema": CONFIRM_SCHEMA,
                "metadata": {"card_type": "confirm"},
            }]},
        ))
        # run 自然结束（无更多事件），客户端发新 run resume
        
        # 等待客户端响应
        answer = await future  # 30 分钟超时
        return answer
    return callback
```

**关键观察**：
- **复用** OpenHarness `ask_user_prompt` 回调
- **新增** RunFinishedEvent（已在 agui_extensions.py 派生）
- **不修改** `ask_user_question_tool.py` 一行

### 3.5 permissions 通过现有 `permission_prompt` 实现

```python
# OpenHarness 已有 permission_prompt 参数
engine = QueryEngine(
    ...,
    permission_prompt=my_callback,  # ← 我们注入
)
```

```python
# agui_handler.py 中的 callback
async def permission_callback(tool_name: str, tool_input: dict) -> bool:
    """危险工具拦截 — 翻译为 AG-UI Interrupt (reason=tool_call)。"""
    interrupt_id = f"int-{uuid.uuid4().hex[:12]}"
    future = asyncio.Future()
    pending_prompts[interrupt_id] = future
    
    await emit_sse(RunFinishedEvent(
        thread_id=..., run_id=...,
        outcome={"type": "interrupt", "interrupts": [{
            "id": interrupt_id, "reason": "tool_call",
            "toolCallId": tool_name,
            "message": f"agent 想要执行 {tool_name}，是否允许？",
            "responseSchema": TOOL_CALL_SCHEMA,  # {approved, editedArgs}
        }]},
    ))
    
    response = await future
    return response.get("approved", False)
```

**关键观察**：
- **复用** OpenHarness `permission_prompt` 回调（已有 — 见 query_engine.py:35）
- **不修改** `permissions/checker.py` 一行
- 客户端得到 HITL 卡片（同 ask_user_question 路径）

### 3.6 memory/skills/tasks 通过 HookExecutor 扩展

```python
# OpenHarness HookExecutor（已有）— 在 lifecycle 点执行用户 hook
# AG-UI 客户端需要在以下 lifecycle 点收到事件：
#   - SESSION_START    → MESSAGES_SNAPSHOT + STATE_SNAPSHOT
#   - SESSION_END      → RUN_FINISHED (success)
#   - PRE_TOOL_USE     → TOOL_CALL_START
#   - POST_TOOL_USE    → TOOL_CALL_RESULT
#   - PRE_COMPACT      → STATE_DELTA (compact starting)
#   - POST_COMPACT     → STATE_DELTA (compact done)
#   - STOP             → RUN_FINISHED (cancelled)

# 在 agui_handler.py 中注册这些 hook：
async def setup_agui_hooks(engine: QueryEngine, session: dict) -> None:
    """为 QueryEngine 注册 AG-UI 事件 hook。"""
    
    # 1. SESSION_START → emit RunStarted + MessagesSnapshot + StateSnapshot
    await engine.hook_executor.execute(HookEvent.SESSION_START, {
        "thread_id": session["id"],
        "run_id": session["run_id"],
        "messages": engine.messages,
        "memory": engine.memory.snapshot(),  # OpenHarness Memory 模块
        "active_skills": engine.skills.active,  # OpenHarness skills 模块
    })
    
    # 2. SESSION_END → emit RunFinished (success)
    @on_event(HookEvent.SESSION_END)
    async def on_end(payload):
        await emit_sse(RunFinishedEvent(
            thread_id=session["id"], run_id=session["run_id"],
            outcome="success", result={"usage": engine.cost_tracker.snapshot()}
        ))
    
    # 3. PRE_TOOL_USE / POST_TOOL_USE → tool_call 三件套 + result
    # （OpenHarness 内部已经处理，我们通过 StreamEvent 直接 emit）
    
    # 4. PRE_COMPACT / POST_COMPACT → StateDelta
    # （OpenHarness CompactProgressEvent 已经覆盖，transport 翻译）
```

**关键观察**：
- **复用** OpenHarness 已有 10 个 HookEvent（见 hooks/events.py）
- **不修改** `hooks/executor.py` 一行
- AG-UI 事件通过 hook 注入

### 3.7 swarm 多 agent 扩展

```python
# OpenHarness swarm 已有 team_create / send_message / mailbox
# AG-UI 客户端需要看到：
#   - SUB_AGENT_START (新事件类型)
#   - SUB_AGENT_PROGRESS (新事件类型)
#   - SUB_AGENT_RESULT (新事件类型)

# 在 odap/infra/openharness/agui_extensions.py 中新增：

@dataclass
class SubAgentStartEvent(StreamEvent):
    """子 agent 启动（覆盖 OpenHarness swarm 协同）。"""
    parent_thread_id: str
    sub_agent_id: str
    sub_agent_role: str
    initial_message: str

@dataclass
class SubAgentResultEvent(StreamEvent):
    """子 agent 完成。"""
    parent_thread_id: str
    sub_agent_id: str
    output: str
    is_error: bool = False
```

**触发点**：在 OpenHarness `swarm/team_create` 工具发出时，`send_message` 工具分发时，通过 hook 注入（**不修改** swarm/ 任何文件）。

### 3.8 tasks 长任务扩展

```python
# OpenHarness 已有 6 个 task 工具（task_create / task_list / task_output / task_stop / task_update / task_get）
# AG-UI 通过现有 TOOL_CALL_RESULT 机制（card_type=task_progress）暴露

# 客户端看到 TOOL_CALL_RESULT content:
# {"card_type": "task_progress", "card_props": {
#   "task_id": "t-001", "status": "running", "progress": 0.5,
#   "output_preview": "..."
# }}
```

**关键观察**：
- **不新增** StreamEvent 类型
- 复用现有 `TOOL_CALL_RESULT` + card_type 扩展
- 长任务卡片前端实现（前端 card 增量）

---

## 4. ODAP 集成层（现有 v2_adapter 复用）

ODAP 已有 `odap/infra/openharness/v2_adapter.py`，封装 OpenHarness 集成。**新增 AG-UI 适配到此层**：

```python
# odap/infra/openharness/v2_adapter.py (新增方法)

class OpenHarnessV2Adapter:
    """ODAP ↔ OpenHarness 适配（AG-UI 入口追加）。"""
    
    def create_agui_session(self, user_id: str, ws_id: str, model: str) -> QueryEngine:
        """创建带 AG-UI 回调的 QueryEngine。"""
        engine = QueryEngine(
            api_client=self._get_api_client(model),
            tool_registry=self._get_tool_registry(),
            permission_checker=self._get_permission_checker(),
            cwd=self._workspace_cwd(ws_id),
            model=model,
            system_prompt=self._build_system_prompt(ws_id),
            ask_user_prompt=self._create_agui_ask_user_callback(...),  # ← 新增
            permission_prompt=self._create_agui_permission_callback(...),  # ← 新增
            hook_executor=self._get_hook_executor(...),  # ← 复用
        )
        return engine
```

**关键观察**：
- 适配器类**已有**（ODAP 现行）
- 只需**追加** `create_agui_session()` 方法
- 不修改适配器**现有方法** — O 向后兼容

---

## 5. 路由层

```python
# odap/infra/openharness/agui_handler.py

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

router = APIRouter(prefix="/api/ag-ui", tags=["ag-ui"])

@router.post("/run")
async def run_agent(
    request: RunAgentInput,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """AG-UI 协议入口：客户端发 RunAgentInput，服务端流式返回 AG-UI Event。"""
    
    # 1. OPA 鉴权
    await opa_check(user, "ag_ui:run", ws_id=request.threadId)
    
    # 2. 解析 resume[]（如果有）
    if request.resume:
        return await _handle_resume(request, user)
    
    # 3. 创建带 AG-UI 回调的 QueryEngine（v2_adapter）
    engine = odap_openharness_v2_adapter.create_agui_session(
        user_id=user.id, ws_id=user.ws_id, model=resolve_model(request),
    )
    
    # 4. 流式返回（transport 直接 emit）
    return EventSourceResponse(_stream_agui_events(engine, request))


async def _stream_agui_events(engine: QueryEngine, request: RunAgentInput) -> AsyncIterator[dict]:
    """把 QueryEngine 流式输出编码为 AG-UI Event。
    
    关键：此函数是 emit 层，不是翻译层。
    """
    # 首事件：RunStarted
    yield to_agui_event(RunStartedEvent(
        thread_id=request.threadId, run_id=request.runId, input={"messages": request.messages},
    ))
    
    # 真实流：QueryEngine.run_query() → StreamEvent → AG-UI Event
    async for event in engine.run_query(user_message=request.messages[-1]["content"]):
        agui_event = to_agui_event(event)
        if agui_event:
            yield agui_event
        # 注意：HITL 中断由 ask_user_prompt callback 内部 emit RunFinished.interrupts
        # 注意：run 自然结束后 QueryEngine 不再发事件，需要我们 emit RunFinished (success)
    
    # 终事件：RunFinished (success)
    yield to_agui_event(RunFinishedEvent(
        thread_id=request.threadId, run_id=request.runId, outcome="success",
        result={"usage": engine.cost_tracker.snapshot()},
    ))
```

**关键观察**：
- `_stream_agui_events` 90% 是 `to_agui_event()` 调用
- 真实业务逻辑在 `engine.run_query()`（OpenHarness）和 `ask_user_prompt` 回调（我们注入的）
- 不重新实现 OpenHarness 任何循环逻辑

---

## 6. v2.0 vs v1.0 完整对比

| 维度 | v1.0 (废止) | v2.0 (本方案) | 改进 |
|------|------------|-------------|------|
| 独立业务模块 | `odap/biz/core/qa/` | 0 | -100% |
| 翻译层行数 | ~250 | ~80 (to_agui_event 字段映射) | -68% |
| OpenHarness 核心修改 | 0 | **0** | 持平 |
| OpenHarness 派生类新增 | 0 | 6 个 | 净增 |
| HookExecutor 修改 | 0 | **0** | 持平 |
| 持久化表新增 | 1 (`qa_agui_interrupts`) | **0** | -100% |
| 内存状态新增 | 1 dict (`_pending_prompts`) | 0 (复用 `ask_user_prompt` future) | -100% |
| 客户端依赖 | 需自实现 | `@ag-ui/core` SDK | 工业标准 |
| 协议兼容性 | OAUIP 自研 | AG-UI v0.x | 通用 |
| 单元测试目标 | 20 个 | 8 个 | -60% |
| 实现周期 | 5.2 周 | **3.5 周** | -33% |

---

## 7. Phase 任务重排（v2.0 简化版）

### Phase 0: 协议对齐（0.5 天）
- R-01: 输出 [contracts/ag-ui-bridge.md](./contracts/ag-ui-bridge.md) 字段映射表（已在 v1.0 完成，v2.0 直接复用）
- R-02: 列出 6 个新派生类（见 §3.2）
- R-03: 删除 `odap/biz/core/qa/` 整个目录（如果存在）

### Phase 1: StreamEvent 派生扩展（1 天）
- B-01: `odap/infra/openharness/agui_extensions.py` — 6 个派生类（RunStarted / RunFinished / StepFinished / TextMessageStart / TextMessageEnd / MessagesSnapshot / StateSnapshot）
- B-02: `odap/infra/openharness/agui_transport.py` — `to_agui_event()` 函数 + 状态跟踪
- B-03: 单元测试 `test_agui_transport.py`（8 个 case）

### Phase 2: 回调注入（1.5 天）
- B-04: `odap/infra/openharness/agui_handler.py` — `create_agui_session()` + `_stream_agui_events()` + resume 处理
- B-05: 在 `v2_adapter.py` 中追加 `create_agui_session()` 方法（不修改现有）
- B-06: 单元测试 `test_agui_handler.py`（HITL 场景）

### Phase 3: 路由注册（0.5 天）
- B-07: 在 `odap/web/app.py` 中 `include_router(agui_router)` —— 路由实际定义在 `agui_handler.py` 内部
- B-08: OPA 策略 `ag_ui:run` 注册
- B-09: 端到端测试（用 TestClient）

### Phase 4: 前端集成（1 天）
- F-01: 引入 `@ag-ui/core` npm 包（不引入 `@copilotkit/*`）
- F-02: `frontend/src/modules/qa/providers/AGUIProvider.tsx` — SSE 客户端（~80 行）
- F-03: `frontend/src/modules/qa/hooks/useAGUI.ts` — Hook 封装（~60 行）
- F-04: 复用已有 7 类卡片注册表（`frontend/src/modules/qa/cards/registry.ts`）
- F-05: 单元测试（8 个 case）

### Phase 5: 集成验证（0.5 天）
- T-01: 端到端测试：query → tool_call → AG-UI 流式事件
- T-02: 端到端测试：HITL 确认（ask_user_question 触发）
- T-03: 端到端测试：危险工具拦截（permission_prompt 触发）
- T-04: 性能：SSE TTFB < 200ms

**总计**：5 天（vs v1.0 的 5.2 周 — **-90%**）

---

## 8. 关键不变量（v2.0 必须满足）

1. **0 修改** `openharness/src/openharness/**` 任何文件
2. **0 新增** `odap/biz/core/qa/**` 独立业务模块
3. **0 新增** SQLite 表
4. **0 新增** OpenHarness StreamEvent **修改**（仅派生）
5. **复用** `ask_user_prompt` + `permission_prompt` + `HookExecutor` + `Memory` + `ConversationMessage` 全部现有能力
6. **AG-UI Bridge 是 emit 层**（to_agui_event 是字段名映射，非业务翻译）

---

## 9. 关联文档

- [spec.md](./spec.md) — 评估 spec
- [research.md](./research.md) — 决策依据
- [contracts/ag-ui-bridge.md](./contracts/ag-ui-bridge.md) — 字段映射表（v1.0 输出，v2.0 复用）
- [ODAP v2 Adapter](../odap/infra/openharness/v2_adapter.py) — OpenHarness 集成层（追加 AG-UI 入口）
- [OpenHarness stream_events.py](../openharness/src/openharness/engine/stream_events.py) — 7 类原生事件
- [OpenHarness query_engine.py](../openharness/src/openharness/engine/query_engine.py) — `ask_user_prompt` + `permission_prompt` 回调
- [OpenHarness hooks/events.py](../openharness/src/openharness/hooks/events.py) — 10 类 lifecycle hook
- [OpenHarness permissions/checker.py](../openharness/src/openharness/permissions/checker.py) — 危险工具拦截

---

**Version**: 2.0 (FINAL) | **Date**: 2026-06-08 | **架构修订**：从"翻译层并行运行时"→"派生扩展 + emit 层"
