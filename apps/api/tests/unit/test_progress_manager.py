"""ProgressManager 回归测试

覆盖 P0-M1（owner_id IDOR 校验）、P0-M6（cleanup task 强引用 + 锁改名）、
P3-M7（receive timeout 参数化 + is_closed 属性）。

测试项：
1. ProgressState.is_owned_by — owner/admin/non-owner/None-owner 四种场景
2. ProgressSubscriber.receive — 自定义 timeout + is_closed 属性
3. ProgressManager.get_instance — 并发调用不死锁（回归 P0-M6）
4. ProgressManager.create_state — owner_id 正确记录
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

import pytest

from odap.biz.data.hyper_extract.services.progress_manager import (
    ProgressManager,
    ProgressState,
    ProgressSubscriber,
)


# ============================================================
# ProgressState.is_owned_by (P0-M1)
# ============================================================


class TestProgressStateOwnership:
    """P0-M1: ProgressState IDOR 校验。"""

    def test_owner_can_access(self):
        """创建者本人可以访问。"""
        state = ProgressState("sess-1", owner_id="user-A")
        user = {"sub": "user-A", "role": "member"}
        assert state.is_owned_by(user) is True

    def test_non_owner_blocked(self):
        """非创建者非 admin 被拒绝。"""
        state = ProgressState("sess-1", owner_id="user-A")
        user = {"sub": "user-B", "role": "member"}
        assert state.is_owned_by(user) is False

    def test_admin_can_access_any(self):
        """admin 可以访问任意 session。"""
        state = ProgressState("sess-1", owner_id="user-A")
        user = {"sub": "admin-1", "role": "admin"}
        assert state.is_owned_by(user) is True

    def test_none_owner_allows_all(self):
        """owner_id 为 None（旧数据兼容）时跳过校验，允许所有访问。"""
        state = ProgressState("sess-1", owner_id=None)
        user = {"sub": "user-B", "role": "member"}
        assert state.is_owned_by(user) is True

    def test_non_dict_user_blocked(self):
        """user 参数不是 dict 时拒绝（防御性）。"""
        state = ProgressState("sess-1", owner_id="user-A")
        assert state.is_owned_by(None) is False  # type: ignore[arg-type]
        assert state.is_owned_by("not-a-dict") is False  # type: ignore[arg-type]

    def test_user_without_sub_blocked(self):
        """user dict 缺少 sub 字段时拒绝。"""
        state = ProgressState("sess-1", owner_id="user-A")
        user: Dict[str, Any] = {"role": "member"}  # 无 sub
        assert state.is_owned_by(user) is False


# ============================================================
# ProgressSubscriber (P3-M7)
# ============================================================


class TestProgressSubscriber:
    """P3-M7: receive timeout 参数化 + is_closed 属性。"""

    def test_is_closed_initially_false(self):
        sub = ProgressSubscriber("sess-1")
        assert sub.is_closed is False

    def test_is_closed_after_close(self):
        sub = ProgressSubscriber("sess-1")
        sub.close()
        assert sub.is_closed is True

    @pytest.mark.asyncio
    async def test_receive_returns_none_on_timeout(self):
        """超时返回 None，但不关闭 subscriber。"""
        sub = ProgressSubscriber("sess-1")
        result = await sub.receive(timeout=0.05)
        assert result is None
        assert sub.is_closed is False  # 超时 ≠ 关闭

    @pytest.mark.asyncio
    async def test_receive_returns_data(self):
        """收到数据时返回 dict。"""
        sub = ProgressSubscriber("sess-1")
        await sub.send({"status": "processing", "progress_percent": 50.0})
        result = await sub.receive(timeout=1.0)
        assert result is not None
        assert result["status"] == "processing"

    @pytest.mark.asyncio
    async def test_receive_returns_none_when_closed(self):
        """关闭后 receive 立即返回 None。"""
        sub = ProgressSubscriber("sess-1")
        sub.close()
        result = await sub.receive(timeout=1.0)
        assert result is None


# ============================================================
# ProgressManager.get_instance 并发安全 (P0-M6 回归)
# ============================================================


class TestProgressManagerSingleton:
    """P0-M6: _instance_lock 改名后并发 get_instance 不死锁。"""

    @pytest.mark.asyncio
    async def test_get_instance_returns_singleton(self):
        """多次调用返回同一实例。"""
        # 重置单例以隔离测试
        ProgressManager._instance = None
        pm1 = await ProgressManager.get_instance()
        pm2 = await ProgressManager.get_instance()
        assert pm1 is pm2

    @pytest.mark.asyncio
    async def test_concurrent_get_instance_no_deadlock(self):
        """并发调用 get_instance 不死锁（P0-M6 回归核心）。"""
        ProgressManager._instance = None
        # 10 个并发任务同时初始化
        managers = await asyncio.gather(
            *[ProgressManager.get_instance() for _ in range(10)]
        )
        # 全部应返回同一实例
        assert all(m is managers[0] for m in managers)

    @pytest.mark.asyncio
    async def test_cleanup_task_holds_strong_reference(self):
        """cleanup task 持有强引用，不被 GC 回收（P0-M6）。"""
        ProgressManager._instance = None
        pm = await ProgressManager.get_instance()
        # _cleanup_task 应为 asyncio.Task 且未完成
        assert hasattr(pm, "_cleanup_task")
        assert pm._cleanup_task is not None
        assert not pm._cleanup_task.done()


# ============================================================
# ProgressManager.create_state + owner_id (P0-M1)
# ============================================================


class TestProgressManagerOwnerID:
    """P0-M1: create_state 正确记录 owner_id。"""

    @pytest.mark.asyncio
    async def test_create_state_with_owner(self):
        ProgressManager._instance = None
        pm = await ProgressManager.get_instance()
        state = await pm.create_state("sess-owner-test", owner_id="user-X")
        assert state.owner_id == "user-X"

    @pytest.mark.asyncio
    async def test_create_state_without_owner_compat(self):
        """不传 owner_id 时默认 None（向后兼容）。"""
        ProgressManager._instance = None
        pm = await ProgressManager.get_instance()
        state = await pm.create_state("sess-compat-test")
        assert state.owner_id is None

    @pytest.mark.asyncio
    async def test_get_state_returns_correct_owner(self):
        ProgressManager._instance = None
        pm = await ProgressManager.get_instance()
        await pm.create_state("sess-get-test", owner_id="user-Y")
        state = await pm.get_state("sess-get-test")
        assert state is not None
        assert state.owner_id == "user-Y"
