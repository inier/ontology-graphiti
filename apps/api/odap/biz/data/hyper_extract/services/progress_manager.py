"""ProgressManager — 提取进度跟踪与 SSE 推送管理器。

提供以下能力：
1. 维护任务进度状态（session_id -> ProgressState）
2. 支持进度回调函数注册
3. SSE 订阅者管理
4. 进度事件广播

规则：
- 使用 asyncio.Lock 保证线程安全
- SSE 连接超时后自动清理
- 进度数据只保留最新状态
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime

logger = logging.getLogger("progress_manager")


class ProgressState:
    """提取任务的进度状态"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.status: str = "processing"
        self.stage: str = ""
        self.message: str = ""
        self.progress_percent: float = 0.0
        self.current_step: int = 0
        self.total_steps: int = 0
        self.created_at: float = time.time()
        self.updated_at: float = time.time()
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None

    def update(
        self,
        stage: Optional[str] = None,
        progress_percent: Optional[float] = None,
        message: Optional[str] = None,
        current_step: Optional[int] = None,
        total_steps: Optional[int] = None,
    ) -> None:
        """更新进度状态"""
        if stage is not None:
            self.stage = stage
        if progress_percent is not None:
            self.progress_percent = max(0.0, min(100.0, progress_percent))
        if message is not None:
            self.message = message
        if current_step is not None:
            self.current_step = current_step
        if total_steps is not None:
            self.total_steps = total_steps
        self.updated_at = time.time()

    def complete(self, result: Optional[Dict[str, Any]] = None) -> None:
        """标记完成"""
        self.status = "completed"
        self.progress_percent = 100.0
        self.result = result
        self.updated_at = time.time()

    def fail(self, error: str) -> None:
        """标记失败"""
        self.status = "failed"
        self.error = error
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典用于 SSE 推送"""
        return {
            "session_id": self.session_id,
            "status": self.status,
            "stage": self.stage,
            "message": self.message,
            "progress_percent": round(self.progress_percent, 1),
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "elapsed_seconds": round(time.time() - self.created_at, 1),
            "updated_at": datetime.fromtimestamp(self.updated_at).isoformat(),
        }


class ProgressManager:
    """全局进度管理器单例"""

    _instance: Optional["ProgressManager"] = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self):
        self._states: Dict[str, ProgressState] = {}
        self._subscribers: Dict[str, List["ProgressSubscriber"]] = {}
        self._lock = asyncio.Lock()
        self._cleanup_interval = 300
        asyncio.create_task(self._periodic_cleanup())

    @classmethod
    async def get_instance(cls) -> "ProgressManager":
        """获取单例实例"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = ProgressManager()
        return cls._instance

    async def _periodic_cleanup(self) -> None:
        """定期清理过期的进度状态（超过 1 小时）"""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                async with self._lock:
                    cutoff = time.time() - 3600
                    expired = [sid for sid, state in self._states.items() if state.updated_at < cutoff]
                    for sid in expired:
                        del self._states[sid]
                        if sid in self._subscribers:
                            del self._subscribers[sid]
                    if expired:
                        logger.info(f"清理过期进度状态: {len(expired)} 个")
            except Exception as e:
                logger.error(f"进度清理任务异常: {e}")

    async def create_state(self, session_id: str) -> ProgressState:
        """创建新的进度状态"""
        async with self._lock:
            state = ProgressState(session_id)
            self._states[session_id] = state
            return state

    async def get_state(self, session_id: str) -> Optional[ProgressState]:
        """获取进度状态"""
        async with self._lock:
            return self._states.get(session_id)

    async def update_progress(
        self,
        session_id: str,
        stage: Optional[str] = None,
        progress_percent: Optional[float] = None,
        message: Optional[str] = None,
        current_step: Optional[int] = None,
        total_steps: Optional[int] = None,
    ) -> None:
        """更新进度并广播事件"""
        async with self._lock:
            state = self._states.get(session_id)
            if not state:
                state = ProgressState(session_id)
                self._states[session_id] = state

            state.update(
                stage=stage,
                progress_percent=progress_percent,
                message=message,
                current_step=current_step,
                total_steps=total_steps,
            )

            await self._broadcast(session_id, state)

    async def complete_progress(self, session_id: str, result: Optional[Dict[str, Any]] = None) -> None:
        """标记完成并广播事件"""
        async with self._lock:
            state = self._states.get(session_id)
            if state:
                state.complete(result)
                await self._broadcast(session_id, state)

    async def fail_progress(self, session_id: str, error: str) -> None:
        """标记失败并广播事件"""
        async with self._lock:
            state = self._states.get(session_id)
            if state:
                state.fail(error)
                await self._broadcast(session_id, state)

    async def subscribe(self, session_id: str) -> "ProgressSubscriber":
        """订阅指定任务的进度事件"""
        async with self._lock:
            if session_id not in self._subscribers:
                self._subscribers[session_id] = []

            subscriber = ProgressSubscriber(session_id)
            self._subscribers[session_id].append(subscriber)

            state = self._states.get(session_id)
            if state:
                await subscriber.send(state.to_dict())

            return subscriber

    async def unsubscribe(self, session_id: str, subscriber: "ProgressSubscriber") -> None:
        """取消订阅"""
        async with self._lock:
            subscribers = self._subscribers.get(session_id)
            if subscribers and subscriber in subscribers:
                subscribers.remove(subscriber)
                if not subscribers:
                    del self._subscribers[session_id]

    async def _broadcast(self, session_id: str, state: ProgressState) -> None:
        """广播进度事件给所有订阅者"""
        async with self._lock:
            subscribers = self._subscribers.get(session_id, [])
            data = state.to_dict()
            dead = []

            for sub in subscribers:
                try:
                    await sub.send(data)
                except Exception:
                    dead.append(sub)

            for sub in dead:
                subscribers.remove(sub)


class ProgressSubscriber:
    """进度事件订阅者"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=10)
        self._closed = False

    async def send(self, data: Dict[str, Any]) -> None:
        """发送进度数据"""
        if self._closed:
            return
        try:
            if self._queue.full():
                try:
                    self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            await self._queue.put(data)
        except Exception:
            self._closed = True

    async def receive(self) -> Optional[Dict[str, Any]]:
        """接收进度数据"""
        if self._closed:
            return None
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=60)
        except asyncio.TimeoutError:
            return None

    def close(self) -> None:
        """关闭订阅"""
        self._closed = True


async def get_progress_manager() -> ProgressManager:
    """获取进度管理器实例"""
    return await ProgressManager.get_instance()


class ProgressCallback:
    """进度回调函数包装器"""

    def __init__(self, session_id: str):
        self.session_id = session_id

    async def __call__(
        self,
        stage: str,
        progress: float,
        message: str = "",
        step: int = 0,
        total: int = 0,
    ) -> None:
        """调用进度回调"""
        pm = await get_progress_manager()
        await pm.update_progress(
            session_id=self.session_id,
            stage=stage,
            progress_percent=progress,
            message=message,
            current_step=step,
            total_steps=total,
        )