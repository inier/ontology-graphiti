"""本体编辑锁 WebSocket 处理器

客户端连接时传入 ontology_id + user_id，建立 WebSocket 连接后：
- 客户端每 15 秒发送心跳，服务端刷新锁超时
- 服务端 30 秒内未收到心跳，自动释放锁
- 客户端断开连接时自动释放锁
"""

import asyncio
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from odap.biz.core.ontology.design.services.edit_lock_service import get_edit_lock_service

logger = logging.getLogger(__name__)


async def edit_lock_websocket_handler(websocket: WebSocket, ontology_id: str, user_id: str):
    """编辑锁 WebSocket 处理函数

    Args:
        websocket: WebSocket 连接
        ontology_id: 本体 ID
        user_id: 用户 ID
    """
    await websocket.accept()

    lock_service = get_edit_lock_service()
    session_id = id(websocket)  # 用 websocket 对象 id 作为 session_id

    # 尝试获取锁
    result = lock_service.acquire_lock(ontology_id, user_id, str(session_id))
    if result.get("status") == "error":
        await websocket.send_text(json.dumps({
            "type": "lock_denied",
            "data": result,
        }, ensure_ascii=False))
        await websocket.close()
        return

    # 通知客户端锁获取成功
    await websocket.send_text(json.dumps({
        "type": "lock_acquired",
        "data": {
            "ontology_id": ontology_id,
            "user_id": user_id,
            "session_id": str(session_id),
        },
    }, ensure_ascii=False))

    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                msg = json.loads(raw) if raw else {}
                msg_type = msg.get("type", "")

                if msg_type == "heartbeat":
                    # 刷新锁心跳
                    refresh_result = lock_service.refresh_lock(ontology_id, str(session_id))
                    await websocket.send_text(json.dumps({
                        "type": "heartbeat_ack",
                        "data": refresh_result,
                    }, ensure_ascii=False))
                elif msg_type == "release":
                    # 客户端主动释放锁
                    lock_service.release_lock(ontology_id, str(session_id))
                    await websocket.send_text(json.dumps({
                        "type": "lock_released",
                        "data": {"ontology_id": ontology_id},
                    }, ensure_ascii=False))
                    break
            except asyncio.TimeoutError:
                # 30 秒无消息，检查锁是否仍然有效
                lock_status = lock_service.get_lock_status(ontology_id)
                if not lock_status or lock_status.get("session_id") != str(session_id):
                    await websocket.send_text(json.dumps({
                        "type": "lock_expired",
                        "data": {"ontology_id": ontology_id},
                    }, ensure_ascii=False))
                    break
                # 发送心跳探测
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break
    except WebSocketDisconnect:
        logger.info(f"编辑锁 WebSocket 断开: ontology_id={ontology_id}, user_id={user_id}")
    except Exception as e:
        logger.error(f"编辑锁 WebSocket 异常: {e}")
    finally:
        # 断开连接时自动释放锁
        lock_service.release_lock(ontology_id, str(session_id))
        logger.info(f"编辑锁已释放: ontology_id={ontology_id}, session_id={session_id}")
