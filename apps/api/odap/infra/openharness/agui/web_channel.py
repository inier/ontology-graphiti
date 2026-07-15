"""Web Channel Adapter + API Bridge — Phase 2 核心组件。

将 Web UI 的 AI 助手请求桥接到 OpenHarness QueryEngine + AG-UI 协议，
同时提供 OHMO Gateway 集成接口（为 IM 渠道接入做准备）。

双路径设计：
1. 主路径（直接 AGUI）：/api/assistant/chat → chat_via_agui() → QueryEngine → AG-UI SSE
2. OHMO 路径（可选）：WebChannelAdapter → MessageBus → GatewayBridge → RuntimeBundle

Architecture invariant: 0 修改 OpenHarness 核心 / 复用现有 AGUI transport
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, AsyncIterator, Dict, Optional

logger = logging.getLogger(__name__)

# 确保 OpenHarness 可导入
_OPENHARNESS_SRC = os.environ.get(
    "OPENHARNESS_PATH",
    os.path.join(os.getcwd(), "openharness", "src"),
)
if os.path.exists(_OPENHARNESS_SRC) and _OPENHARNESS_SRC not in sys.path:
    sys.path.insert(0, _OPENHARNESS_SRC)


# ---------------------------------------------------------------------------
# WebChannelAdapter — OHMO Gateway 渠道适配器
# ---------------------------------------------------------------------------

try:
    from openharness.channels.impl.base import BaseChannel
    from openharness.channels.bus.events import InboundMessage, OutboundMessage
    from openharness.channels.bus.queue import MessageBus

    _OH_CHANNELS_AVAILABLE = True
except ImportError:
    _OH_CHANNELS_AVAILABLE = False
    logger.debug("OpenHarness channels not available, WebChannelAdapter disabled")


@dataclass
class _WebSessionQueue:
    """Per-session 出站消息队列。"""

    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    created_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())


class WebChannelAdapter(BaseChannel if _OH_CHANNELS_AVAILABLE else object):
    """Web 渠道适配器 — 将 Web UI 消息路由到 OHMO Gateway。

    与 IM 渠道（飞书/Slack/Telegram）并列，作为 OHMO 的 "web" 渠道。
    Web 请求通过 HTTP POST 发送，响应通过 SSE 流式返回。

    消息流：
        Web POST → submit_and_stream() → InboundMessage → bus → GatewayBridge
        → RuntimeBundle → GatewayStreamUpdate → bus → send() → SSE queue

    使用方式：
        adapter = WebChannelAdapter(config, bus)
        await adapter.start()
        # SSE 端点
        async for sse_chunk in adapter.submit_and_stream(user_msg, session_key):
            yield sse_chunk
    """

    name = "web"

    def __init__(self, config: Any, bus: "MessageBus"):
        if _OH_CHANNELS_AVAILABLE:
            super().__init__(config, bus)
        self._session_queues: Dict[str, _WebSessionQueue] = {}

    async def start(self) -> None:
        """启动 Web 渠道。Web 不需要长连接监听，只需标记为运行状态。"""
        self._running = True
        logger.info("WebChannelAdapter started")

    async def stop(self) -> None:
        """停止 Web 渠道，清理所有会话队列。"""
        self._running = False
        for sq in self._session_queues.values():
            await sq.queue.put(None)  # 发送终止信号
        self._session_queues.clear()
        logger.info("WebChannelAdapter stopped")

    async def send(self, msg: "OutboundMessage") -> None:
        """接收来自 OHMO Gateway 的出站消息，推送到对应会话的 SSE 队列。

        OHMO Gateway 处理完消息后，通过 bus.publish_outbound() 发布回复，
        最终调用此方法将回复推送到等待中的 SSE 响应。
        """
        session_key = msg.metadata.get("session_key", msg.chat_id)
        sq = self._session_queues.get(session_key)
        if sq is None:
            logger.warning("WebChannelAdapter: no SSE listener for session %s", session_key)
            return

        payload = {
            "type": "GATEWAY_UPDATE",
            "kind": msg.metadata.get("kind", "progress"),
            "content": msg.content,
            "metadata": msg.metadata,
        }
        await sq.queue.put(payload)

        # 如果是最终消息，发送终止信号
        if msg.metadata.get("kind") == "final":
            await sq.queue.put(None)

    def _get_or_create_queue(self, session_key: str) -> _WebSessionQueue:
        """获取或创建会话队列。"""
        if session_key not in self._session_queues:
            self._session_queues[session_key] = _WebSessionQueue()
        return self._session_queues[session_key]

    async def submit_and_stream(
        self,
        message: str,
        *,
        sender_id: str,
        chat_id: str,
        session_key: str | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """提交消息到 OHMO Gateway 并流式返回回复。

        这是 Web API 调用的入口点：
        1. 注册 SSE 监听队列
        2. 发布 InboundMessage 到 MessageBus
        3. 流式返回队列中的消息

        Args:
            message: 用户消息文本
            sender_id: 发送者 ID（来自 JWT）
            chat_id: 聊天 ID（通常是 session_id 或 thread_id）
            session_key: 会话 key（可选，默认从 chat_id 推导）
            metadata: 额外元数据（ontology_id, workspace_id 等）
        """
        if not self._running:
            raise RuntimeError("WebChannelAdapter is not running")

        sk = session_key or f"web:{chat_id}:{sender_id}"
        sq = self._get_or_create_queue(sk)

        # 构造 InboundMessage
        inbound = InboundMessage(
            channel=self.name,
            sender_id=sender_id,
            chat_id=chat_id,
            content=message,
            metadata={**(metadata or {}), "session_key": sk},
            session_key_override=sk,
        )

        # 发布到 MessageBus（GatewayBridge 会消费）
        await self.bus.publish_inbound(inbound)

        # 流式返回队列中的消息
        try:
            while True:
                item = await asyncio.wait_for(sq.queue.get(), timeout=120.0)
                if item is None:
                    break  # 终止信号
                yield item
        except asyncio.TimeoutError:
            yield {"type": "GATEWAY_TIMEOUT", "message": "Gateway response timeout"}
        finally:
            # 清理会话队列
            self._session_queues.pop(sk, None)


# ---------------------------------------------------------------------------
# API Bridge — /api/assistant/chat → QueryEngine + AG-UI SSE
# ---------------------------------------------------------------------------

def _build_run_agent_input(
    message: str,
    *,
    ontology_id: str | None = None,
    workspace_id: str = "default",
    session_id: str | None = None,
    context: Dict[str, Any] | None = None,
    user_id: str = "anonymous",
) -> "RunAgentInput":
    """从 ChatRequest 参数构造 AG-UI RunAgentInput。

    将 ODAP 的 ChatRequest 格式转换为 AG-UI 协议的 RunAgentInput，
    保留 ontology_id 和 context 作为 ODAP 扩展字段。
    """
    from odap.infra.openharness.agui.agui_models import Message, RunAgentInput

    thread_id = session_id or f"web-{uuid.uuid4().hex[:12]}"
    run_id = f"run-{uuid.uuid4().hex[:12]}"

    msg = Message(
        id=f"msg-{uuid.uuid4().hex[:12]}",
        role="user",
        content=message,
    )

    # 将 ODAP context 注入 state（AG-UI 协议的 state 字段）
    state: Dict[str, Any] = {}
    if ontology_id:
        state["ontology_id"] = ontology_id
    if context:
        state["page_context"] = context

    return RunAgentInput(
        threadId=thread_id,
        runId=run_id,
        messages=[msg],
        state=state,
        workspaceId=workspace_id,
        userId=user_id,
    )


async def chat_via_agui(
    message: str,
    *,
    ontology_id: str | None = None,
    workspace_id: str = "default",
    session_id: str | None = None,
    context: Dict[str, Any] | None = None,
    user_id: str = "anonymous",
) -> AsyncGenerator[str, None]:
    """通过 AG-UI 协议运行 AI 助手对话。

    这是 /api/assistant/chat 的新路径：
    1. 构造 RunAgentInput
    2. 注入本体上下文到 system prompt
    3. 调用 AGUI handler 的 _stream_agui_events() 生成 SSE 流
    4. 流式返回 AG-UI 事件（含字段兼容映射）

    与旧的 ChatService.chat() 相比：
    - 使用 OpenHarness QueryEngine 而非直接调用 ZhipuAI
    - 使用 AG-UI 17 类事件而非自定义 6 类事件
    - 工具通过 ToolRegistry 调用（包含 AI Assistant Plugin 的 16 个工具）

    字段兼容映射（AG-UI → 前端期望格式）：
    - TOOL_CALL_START: toolCallName → tool_name
    - RUN_STARTED: 添加 session_id
    """
    from odap.infra.openharness.agui.agui_handler import _stream_agui_events
    from odap.infra.openharness.agui.agui_models import RunAgentInput

    # 1. 构造 RunAgentInput
    request = _build_run_agent_input(
        message,
        ontology_id=ontology_id,
        workspace_id=workspace_id,
        session_id=session_id,
        context=context,
        user_id=user_id,
    )

    # 2. 获取模型配置
    from odap.infra.config_composer import get_config
    model = get_config("llm.model", "gpt-4o")

    # 3. 流式返回 AG-UI SSE 事件（含字段兼容映射）
    async for sse_chunk in _stream_agui_events(
        request,
        user_id=user_id,
        ws_id=workspace_id,
        model=model,
    ):
        # sse_chunk 格式: "data: {json}\n\n"
        # 解析并做字段兼容映射
        if sse_chunk.startswith("data: "):
            data_str = sse_chunk[6:].strip()
            if data_str and data_str != "[DONE]":
                try:
                    event = json.loads(data_str)
                    # 字段兼容映射
                    _map_agui_event_for_frontend(event, request.threadId)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    continue
                except (json.JSONDecodeError, Exception):
                    pass
        yield sse_chunk

    # 发送终止信号
    yield "data: [DONE]\n\n"


def _map_agui_event_for_frontend(event: Dict[str, Any], thread_id: str) -> None:
    """将 AG-UI 事件字段映射为前端期望的格式（原地修改）。

    前端 useAIChat.ts 期望的字段名与 AG-UI 协议有细微差异：
    - TOOL_CALL_START: 前端用 tool_name，AG-UI 用 toolCallName
    - RUN_STARTED: 前端用 session_id，AG-UI 用 threadId
    - TOOL_CALL_END: 前端不需要额外字段

    此函数原地修改 event dict，添加前端期望的字段。
    """
    event_type = event.get("type", "")

    if event_type == "TOOL_CALL_START":
        # AG-UI: toolCallName → 前端: tool_name
        if "toolCallName" in event and "tool_name" not in event:
            event["tool_name"] = event["toolCallName"]

    elif event_type == "RUN_STARTED":
        # 前端通过 session_id 跟踪会话
        if "session_id" not in event:
            event["session_id"] = thread_id

    elif event_type == "TOOL_CALL_END":
        # AG-UI 的 toolCallId 映射到前端期望的格式
        if "toolCallId" in event and "tool_call_id" not in event:
            event["tool_call_id"] = event["toolCallId"]


async def chat_via_agui_response(
    message: str,
    *,
    ontology_id: str | None = None,
    workspace_id: str = "default",
    session_id: str | None = None,
    context: Dict[str, Any] | None = None,
    user_id: str = "anonymous",
):
    """创建 StreamingResponse，通过 AG-UI 协议返回 SSE 流。

    供 FastAPI 路由直接使用：
        return await chat_via_agui_response(message, ontology_id=..., ...)
    """
    from fastapi.responses import StreamingResponse

    return StreamingResponse(
        chat_via_agui(
            message,
            ontology_id=ontology_id,
            workspace_id=workspace_id,
            session_id=session_id,
            context=context,
            user_id=user_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Gateway Bootstrap — OHMO Gateway 启动时加载 AI Assistant Plugin
# ---------------------------------------------------------------------------

_web_adapter: Optional[WebChannelAdapter] = None


def get_web_channel_adapter() -> Optional[WebChannelAdapter]:
    """获取全局 WebChannelAdapter 实例。

    用于 OHMO Gateway 启动时注册 Web 渠道。
    """
    return _web_adapter


async def init_web_channel(bus: "MessageBus", config: Any = None) -> WebChannelAdapter:
    """初始化 WebChannelAdapter 并注册到 MessageBus。

    在应用启动时调用：
        adapter = await init_web_channel(bus)
        await adapter.start()
    """
    global _web_adapter

    if not _OH_CHANNELS_AVAILABLE:
        raise RuntimeError("OpenHarness channels not available")

    # 默认配置：允许所有用户
    if config is None:
        @dataclass
        class _DefaultConfig:
            allow_from: list = field(default_factory=lambda: ["*"])

        config = _DefaultConfig()

    _web_adapter = WebChannelAdapter(config, bus)
    await _web_adapter.start()
    logger.info("WebChannelAdapter initialized and started")
    return _web_adapter
