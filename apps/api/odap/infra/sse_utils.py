"""SSE 公共工具 — 心跳保活 + 统一 StreamingResponse 构造。

P3-M7 整改：原先 hyper_extract 和 ontology extraction 两个进度流端点各自
复制了一份 event_generator，且都没有心跳。当 nginx/反向代理 idle timeout
小于 60s 时连接会被静默切断。本模块提供：

1. progress_event_generator(pm, session_id) — 带心跳的公共生成器
2. sse_response(generator) — 统一 SSE 响应头构造
"""

import asyncio
import json
from typing import AsyncGenerator, Optional

from fastapi.responses import StreamingResponse

# 心跳间隔（秒）。SSE comment line ": heartbeat\n\n" 会被 EventSource 忽略，
# 但能保持 TCP 连接活跃，防止 nginx/代理 idle 超时切断。
# 15s 是安全值 — 大多数反向代理 idle timeout ≥ 60s。
SSE_HEARTBEAT_INTERVAL = 15.0

# 标准 SSE 响应头
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲，确保实时推送
}


async def progress_event_generator(
    pm,
    session_id: str,
    *,
    heartbeat_interval: float = SSE_HEARTBEAT_INTERVAL,
) -> AsyncGenerator[str, None]:
    """带心跳保活的进度事件生成器。

    订阅 ProgressManager 的指定 session，每次收到事件 yield 一条 SSE data 行；
    若 heartbeat_interval 内无事件，yield 一条 SSE comment（: heartbeat）保活。
    当订阅被关闭或客户端断开时退出。

    Args:
        pm: ProgressManager 实例
        session_id: 进度会话 ID
        heartbeat_interval: 心跳间隔秒数
    """
    queue = await pm.subscribe(session_id)

    try:
        while True:
            # 检查订阅是否已被关闭（如 state 过期被清理）
            if queue.is_closed:
                break

            event = await queue.receive(timeout=heartbeat_interval)
            if event is None:
                # 超时无事件 — 发送心跳保活，而非关闭流
                if queue.is_closed:
                    break
                yield ": heartbeat\n\n"
                continue

            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"

            # 事件标记完成/失败时，发完最后一条就退出
            if isinstance(event, dict) and event.get("status") in ("completed", "failed"):
                break
    finally:
        await pm.unsubscribe(session_id, queue)


def sse_response(generator: AsyncGenerator[str, None]) -> StreamingResponse:
    """构造标准 SSE StreamingResponse。"""
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
