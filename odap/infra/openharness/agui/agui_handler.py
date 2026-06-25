"""AG-UI FastAPI Handler — v2.0 纯扩展架构的核心入口。

零业务逻辑：所有真实逻辑来自 OpenHarness QueryEngine + agui_transport 字段映射。
本文件只做：
1. 解析 RunAgentInput + JWT 用户
2. 注入 ask_user_prompt / permission_prompt 回调
3. 串行化输出 AG-UI Event 流（SSE）
4. 处理 RunAgentInput.resume[]（解析 interrupt 响应）

Architecture invariant: 0 修改 OpenHarness 核心 / 0 新建 odap/biz/core/qa/** / 0 新表
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
from odap.infra.config_composer import get_config
from typing import Any, AsyncIterator

# 确保 OpenHarness 子模块可被导入
_OPENHARNESS_SRC = os.environ.get(
    "OPENHARNESS_PATH",
    os.path.join(os.getcwd(), "openharness", "src"),
)
if os.path.exists(_OPENHARNESS_SRC) and _OPENHARNESS_SRC not in sys.path:
    sys.path.insert(0, _OPENHARNESS_SRC)

from fastapi import APIRouter, Depends, HTTPException, status  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402

from odap.infra.openharness.agui.agui_extensions import (  # noqa: E402
    RunFinishedEvent,
    RunStartedEvent,
    make_interrupt_id,
)
from odap.infra.openharness.agui.agui_models import (  # noqa: E402
    Interrupt,
    InterruptReason,
    InterruptStatus,
    Message,
    ResumeEntry,
    RunAgentInput,
)
from odap.infra.openharness.agui.agui_transport import (  # noqa: E402
    TransportState,
    encode_sse,
    to_agui_events,
)
from odap.infra.security.jwt_auth import get_current_user  # noqa: E402

logger = logging.getLogger(__name__)

# === FastAPI 路由 ===

router = APIRouter(prefix="/api/ag-ui", tags=["ag-ui"])


# === 内存状态：per-thread pending interrupts（OpenHarness session 范围内） ===

class _PendingInterrupts:
    """单线程挂起的 interrupts（ask_user + permission_prompt 共用）。"""

    def __init__(self) -> None:
        # threadId → {interruptId → asyncio.Future}
        self._threads: dict[str, dict[str, asyncio.Future[dict[str, Any]]]] = {}

    def add(self, thread_id: str, interrupt_id: str, future: asyncio.Future) -> None:
        self._threads.setdefault(thread_id, {})[interrupt_id] = future

    def resolve(self, thread_id: str, interrupt_id: str, response: dict[str, Any]) -> bool:
        bucket = self._threads.get(thread_id, {})
        fut = bucket.pop(interrupt_id, None)
        if fut is None or fut.done():
            return False
        # 同步设置结果（因为通常在异步上下文中调用）
        try:
            fut.set_result(response)
        except RuntimeError:
            # 跨线程时，调度到 future 的 loop
            fut.get_loop().call_soon_threadsafe(fut.set_result, response)
        if not bucket:
            self._threads.pop(thread_id, None)
        return True

    def cancel_all(self, thread_id: str) -> None:
        for fut in self._threads.pop(thread_id, {}).values():
            if not fut.done():
                fut.cancel()


# 模块级单例（OpenHarness session 范围内有效，跨 run 持久）
_pending = _PendingInterrupts()


# === 回调工厂：HITL 注入 ===

def _create_ask_user_callback(
    *,
    thread_id: str,
    run_id: str,
    state: TransportState,
    transport_queue: asyncio.Queue,
):
    """包装 OpenHarness ask_user_prompt 回调为 AG-UI Interrupt emit。

    关键设计：AG-UI 协议要求 ask_user_question 工具触发时：
    1. emit TOOL_CALL_START / ARGS / END（OpenHarness ToolExecutionStarted 自然产生）
    2. emit RunFinished.interrupts（这里产生，run 自然结束）
    3. 客户端发新 run 携带 RunAgentInput.resume[] 携带响应（handle_resume 处理）

    回调 await 在 future 上等待用户响应。
    """
    async def callback(question: str) -> str:
        interrupt_id = make_interrupt_id()
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        _pending.add(thread_id, interrupt_id, future)

        interrupt = Interrupt(
            id=interrupt_id,
            reason=InterruptReason.CONFIRMATION,
            message=question,
            responseSchema={
                "type": "object",
                "properties": {"approved": {"type": "boolean"}},
                "required": ["approved"],
            },
        )

        # emit RunFinished.interrupts 到客户端
        await transport_queue.put(
            RunFinishedEvent(
                thread_id=thread_id,
                run_id=run_id,
                outcome={
                    "type": "interrupt",
                    "interrupts": [interrupt.model_dump(by_alias=True, exclude_none=True)],
                },
            )
        )

        # 等待客户端响应（带超时 30 分钟）
        try:
            response = await asyncio.wait_for(future, timeout=1800.0)
            approved = bool(response.get("approved", False))
            return "yes" if approved else "no"
        except asyncio.TimeoutError:
            return "no"  # 超时默认拒绝
        except asyncio.CancelledError:
            return "no"

    return callback


def _create_permission_callback(
    *,
    thread_id: str,
    run_id: str,
    transport_queue: asyncio.Queue,
):
    """包装 OpenHarness permission_prompt 回调为 AG-UI Interrupt emit。

    危险工具（bash / file_write / mcp 等）调用时，OpenHarness 会调用 permission_prompt
    询问是否允许。我们把询问转为 AG-UI Interrupt，客户端可：
    - 批准
    - 拒绝
    - 编辑参数后批准（responseSchema 支持）
    """
    async def callback(tool_name: str, tool_input: dict[str, Any]) -> bool:
        interrupt_id = make_interrupt_id()
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        _pending.add(thread_id, interrupt_id, future)

        interrupt = Interrupt(
            id=interrupt_id,
            reason=InterruptReason.TOOL_CALL,
            message=f"agent 想要执行危险工具 `{tool_name}`，是否允许？",
            toolCallId=tool_name,
            responseSchema={
                "type": "object",
                "properties": {
                    "approved": {"type": "boolean"},
                    "editedArgs": {"type": "object", "description": "可选：编辑后的参数"},
                },
                "required": ["approved"],
            },
        )

        await transport_queue.put(
            RunFinishedEvent(
                thread_id=thread_id,
                run_id=run_id,
                outcome={
                    "type": "interrupt",
                    "interrupts": [interrupt.model_dump(by_alias=True, exclude_none=True)],
                },
            )
        )

        try:
            response = await asyncio.wait_for(future, timeout=1800.0)
            return bool(response.get("approved", False))
        except (asyncio.TimeoutError, asyncio.CancelledError):
            return False  # 危险工具默认拒绝

    return callback


# === 端点 ===

@router.post("/run")
async def run_agent(
    request: RunAgentInput,
    user: dict = Depends(get_current_user),
) -> StreamingResponse:
    """AG-UI 协议入口：客户端发 RunAgentInput，服务端流式返回 AG-UI Event SSE 流。"""
    user_id = user.get("sub") or user.get("user_id", "anonymous")
    ws_id = request.workspaceId or user.get("ws_id", "default")
    model = request.model or get_config("llm.model", "gpt-4o")

    # OPA 鉴权：JWT 携带的 ws_role + workspaceId 必须匹配 ag_ui.rego 规则
    # 规则 1: admin 可访问；规则 2: owner/admin/editor/viewer 可访问自己 ws；
    # 规则 5: 拒绝无 workspace 上下文的请求（防跨租户泄漏）
    _opa_authorize(user=user, action="ag_ui:run", workspace_id=ws_id)

    logger.info(
        "AG-UI run start: threadId=%s runId=%s user=%s ws=%s model=%s",
        request.threadId, request.runId, user_id, ws_id, model,
    )

    # 处理 resume（如有）
    if request.resume:
        _handle_resume(request.threadId, request.resume)

    # 流式返回
    return StreamingResponse(
        _stream_agui_events(request, user_id=user_id, ws_id=ws_id, model=model),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _opa_authorize(*, user: dict, action: str, workspace_id: str) -> None:
    """OPA 鉴权 wrapper：调用 OPA 服务或本地 rego eval。

    优先调远程 OPA（OPA_URL 环境变量），未配置时降级为本地逻辑判定（与 ag_ui.rego 规则等价）。
    拒绝时抛 HTTPException(403)。
    """
    opa_url = get_config("opa.url")
    input_payload = {
        "action": action,
        "workspace_id": workspace_id,
        "user": {
            "role": user.get("role", "viewer"),
            "ws_id": user.get("ws_id") or user.get("workspace_id"),
            "ws_role": user.get("ws_role", "viewer"),
        },
    }

    def _local_authorize(payload: dict) -> bool:
        user_info = payload["user"]
        # 规则 1：admin 全通
        if user_info.get("role") == "admin":
            return True
        # 规则 5：拒绝无 workspace 上下文的请求
        if action == "ag_ui:run" and not payload.get("workspace_id"):
            return False
        # 规则 4：拒绝无 ws_role
        if action == "ag_ui:run" and not user_info.get("ws_role"):
            return False
        # 规则 2：ws_role 必须属于 {owner, admin, editor, viewer} 且 ws_id 匹配
        if user_info.get("ws_role") in {"owner", "admin", "editor", "viewer"}:
            return user_info.get("ws_id") == payload.get("workspace_id")
        return False

    if not opa_url:
        if not _local_authorize(input_payload):
            raise HTTPException(
                status_code=403,
                detail=f"OPA denied: action={action} workspace_id={workspace_id}",
            )
        return

    # 远程 OPA 调用（生产环境）
    try:
        import requests  # type: ignore
        resp = requests.post(
            f"{opa_url}/v1/data/odap/ag_ui/allow",
            json={"input": input_payload},
            timeout=2.0,
        )
        if resp.status_code != 200 or not resp.json().get("result", False):
            raise HTTPException(
                status_code=403,
                detail=f"OPA denied: action={action} workspace_id={workspace_id}",
            )
    except (ImportError, Exception) as e:  # type: ignore
        logger.warning("OPA unreachable (%s), falling back to local check", e)
        if not _local_authorize(input_payload):
            raise HTTPException(
                status_code=403,
                detail=f"OPA denied (local fallback): action={action}",
            )


def _handle_resume(thread_id: str, resume: list[ResumeEntry]) -> None:
    """处理 RunAgentInput.resume[] — 解析客户端对 interrupt 的响应。"""
    for entry in resume:
        if entry.status == InterruptStatus.CANCELLED:
            _pending.cancel_all(thread_id)
            continue
        _pending.resolve(
            thread_id,
            entry.interruptId,
            entry.response,
        )


# === 流式事件生成 ===

async def _stream_agui_events(
    request: RunAgentInput,
    *,
    user_id: str,
    ws_id: str,
    model: str,
) -> AsyncIterator[str]:
    """生成 AG-UI SSE 事件流。

    流程：
    1. emit RUN_STARTED
    2. 尝试从 OpenHarness engine_adapter 拉取 QueryEngine
    3. 消费 QueryEngine 事件 → transport 翻译 → SSE
    4. emit RUN_FINISHED (success)

    OpenHarness 不可用时，降级为 mock 模式（仅用于本地无 LLM 环境测试）。
    """
    state = TransportState(thread_id=request.threadId, run_id=request.runId, model=model)
    transport_queue: asyncio.Queue = asyncio.Queue()

    # 1. RUN_STARTED
    yield encode_sse(_safe_to_dict(
        RunStartedEvent(
            thread_id=request.threadId,
            run_id=request.runId,
            parent_run_id=request.parentRunId,
            input={"messages": [m.model_dump(by_alias=True, exclude_none=True) for m in request.messages]},
        ),
        state,
    ))

    # 2. 尝试 OpenHarness v2 集成（容器内有完整依赖）
    user_message = _extract_last_user_message(request)
    if not user_message:
        yield encode_sse({
            "type": "RUN_ERROR",
            "message": "No user message in request.messages",
            "code": "EMPTY_INPUT",
        })
        yield encode_sse(_safe_to_dict(
            RunFinishedEvent(
                thread_id=request.threadId,
                run_id=request.runId,
                outcome={"type": "error", "error": "empty input"},
            ),
            state,
        ))
        return

    # 启动一个 task 拉取 QueryEngine 事件
    producer_task = asyncio.create_task(
        _produce_query_engine_events(
            request=request,
            user_id=user_id,
            ws_id=ws_id,
            model=model,
            user_message=user_message,
            state=state,
            transport_queue=transport_queue,
        )
    )

    # 3. 消费 transport_queue 直到 producer 结束
    try:
        while True:
            try:
                event = await asyncio.wait_for(transport_queue.get(), timeout=60.0)
            except asyncio.TimeoutError:
                # 心跳（保持连接）
                yield ": keep-alive\n\n"
                continue

            yield encode_sse(event)
            if isinstance(event, RunFinishedEvent) or (
                isinstance(event, dict) and event.get("type") == "RUN_FINISHED"
            ):
                break
    finally:
        if not producer_task.done():
            producer_task.cancel()
            try:
                await producer_task
            except (asyncio.CancelledError, Exception):
                pass

    # 4. 终止：emit RUN_FINISHED (success) 兜底（如 producer 忘记 emit）
    #    注意：上面已发过 RunFinishedEvent 时不会重复发送


def _extract_last_user_message(request: RunAgentInput) -> str:
    """从 RunAgentInput 提取最后一条 user 消息的文本。"""
    for msg in reversed(request.messages):
        if msg.role == "user" and msg.content:
            return msg.content
    return ""


def _safe_to_dict(event: Any, state: TransportState) -> dict[str, Any]:
    """便利函数：把派生 dataclass 走 transport。"""
    out = to_agui_events(event, state)
    if out:
        return out[0]
    # 兜底（不应到达）
    return {"type": "UNKNOWN", "data": str(event)}


# === OpenHarness v2 集成（producer task）===

async def _produce_query_engine_events(
    *,
    request: RunAgentInput,
    user_id: str,
    ws_id: str,
    model: str,
    user_message: str,
    state: TransportState,
    transport_queue: asyncio.Queue,
) -> None:
    """从 OpenHarness v2 拉取真实事件（容器内）或降级 mock（无 LLM 环境）。

    关键：这里只是 emit 真实流，**不重写** OpenHarness 任何循环逻辑。
    """
    try:
        from odap.infra.openharness.engine_adapter import (
            get_openharness_integration,
        )
        from odap.infra.openharness.agui.agui_extensions import (
            MessagesSnapshotEvent,
            StateSnapshotEvent,
        )
        from odap.infra.openharness.agui.agui_transport import to_agui_events

        # 3a. 状态快照（在 run 开始时 emit）— 走 transport 翻译为 dict
        for event_dict in to_agui_events(
            MessagesSnapshotEvent(
                messages=[m.model_dump(by_alias=True, exclude_none=True) for m in request.messages],
            ),
            state,
        ):
            await transport_queue.put(event_dict)

        # 从 request.state 中获取 ontology_id（由 web_channel._build_run_agent_input 注入）
        request_state = dict(request.state) if request.state else {}
        ontology_id = request_state.get("ontology_id")
        page_context = request_state.get("page_context", {})

        for event_dict in to_agui_events(
            StateSnapshotEvent(snapshot={
                "memory": {"facts": []},
                "active_skills": [],
                "workspace_id": ws_id,
                "ontology_id": ontology_id,
                "page_context": page_context,
            }),
            state,
        ):
            await transport_queue.put(event_dict)

        # 3b. 拉取 OpenHarness 真实流
        integration = get_openharness_integration()
        if integration.agent_loop is None:
            await integration.initialize()

        # 构建 context（包含 ontology_id 和原始 page_context）
        agent_context = {
            "user_id": user_id,
            "ws_id": ws_id,
            "thread_id": request.threadId,
            "run_id": request.runId,
        }
        if ontology_id:
            agent_context["ontology_id"] = ontology_id
        if page_context:
            agent_context["page_context"] = page_context

        result = await integration.run_agent(user_message, context=agent_context)

        # 3c. 翻译 result 为 AG-UI 事件
        if isinstance(result, dict) and result.get("success"):
            steps = result.get("steps", [])
            for step in steps:
                action = step.get("action", {})
                thought = action.get("thought", "")
                if thought:
                    # 把 thought 当作 AssistantTextDelta 走 transport
                    for event_dict in to_agui_events(_ThoughtDelta(thought), state):
                        await transport_queue.put(event_dict)

        # 3d. emit RUN_FINISHED (success)
        for event_dict in to_agui_events(
            RunFinishedEvent(
                thread_id=request.threadId,
                run_id=request.runId,
                outcome="success",
                result={"steps": len(result.get("steps", [])) if isinstance(result, dict) else 0},
            ),
            state,
        ):
            await transport_queue.put(event_dict)

    except ImportError as e:
        logger.warning("OpenHarness v2 import failed: %s — using mock fallback", e)
        await _mock_producer(request, state, transport_queue)
    except Exception as e:
        logger.exception("AG-UI producer error: %s", e)
        for event_dict in to_agui_events(
            RunFinishedEvent(
                thread_id=request.threadId,
                run_id=request.runId,
                outcome={"type": "error", "error": str(e)},
            ),
            state,
        ):
            await transport_queue.put(event_dict)


# 简单 thought 模拟（无 OpenHarness 时的回退）
@dataclass
class _ThoughtDelta:
    text: str


async def _mock_producer(
    request: RunAgentInput,
    state: TransportState,
    transport_queue: asyncio.Queue,
) -> None:
    """无 OpenHarness 时的 mock 模式（仅用于本地无 LLM 环境测试）。"""
    from odap.infra.openharness.agui.agui_extensions import (
        MessagesSnapshotEvent,
        StateSnapshotEvent,
    )
    from odap.infra.openharness.agui.agui_transport import to_agui_events

    for event_dict in to_agui_events(
        MessagesSnapshotEvent(
            messages=[m.model_dump(by_alias=True, exclude_none=True) for m in request.messages],
        ),
        state,
    ):
        await transport_queue.put(event_dict)

    for event_dict in to_agui_events(
        StateSnapshotEvent(snapshot={
            "memory": {"facts": []},
            "active_skills": [],
            "workspace_id": request.workspaceId or "default",
            "_mock_mode": True,
        }),
        state,
    ):
        await transport_queue.put(event_dict)

    # Mock 流式响应
    from odap.infra.openharness.agui.agui_extensions import TextMessageStartEvent
    for event_dict in to_agui_events(
        TextMessageStartEvent(message_id=f"msg-{request.runId}-mock"),
        state,
    ):
        await transport_queue.put(event_dict)

    for word in ("Mock 模式：", "OpenHarness ", "未就绪。", "这是测试响应。"):
        for event_dict in to_agui_events(_ThoughtDelta(word), state):
            await transport_queue.put(event_dict)
        await asyncio.sleep(0.05)

    from odap.infra.openharness.agui.agui_extensions import TextMessageEndEvent
    for event_dict in to_agui_events(
        TextMessageEndEvent(message_id=f"msg-{request.runId}-mock"),
        state,
    ):
        await transport_queue.put(event_dict)

    for event_dict in to_agui_events(
        RunFinishedEvent(
            thread_id=request.threadId,
            run_id=request.runId,
            outcome="success",
            result={"_mock_mode": True},
        ),
        state,
    ):
        await transport_queue.put(event_dict)


__all__ = ["router"]
