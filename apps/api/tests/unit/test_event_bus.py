"""
Event Bus 单元测试

覆盖:
- DomainEventBus 发布/订阅模式
- subscribe + emit 回调触发
- 事件历史记录
- get_stats() 统计信息
- get_recent_events() 最近事件
- 便捷 emit 方法（emit_entity_changed 等）
- 模块级单例 get_event_bus()
- HookRegistry 注册/注销/查询
- HookContext 数据操作
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event_bus():
    """创建独立的 DomainEventBus 实例"""
    from odap.infra.events.event_bus import DomainEventBus
    return DomainEventBus()


# ---------------------------------------------------------------------------
# TestDomainEventBusSubscribeEmit — 发布/订阅
# ---------------------------------------------------------------------------

class TestDomainEventBusSubscribeEmit:
    @pytest.mark.asyncio
    async def test_subscribe_and_emit(self, event_bus):
        """订阅后 emit 应触发回调"""
        received = []

        def callback(event_type, data, workspace_id):
            received.append({"event_type": event_type, "data": data, "workspace_id": workspace_id})

        event_bus.subscribe("test.event", callback)
        await event_bus.emit("test.event", {"key": "value"}, workspace_id="ws1")

        assert len(received) == 1
        assert received[0]["event_type"] == "test.event"
        assert received[0]["data"]["key"] == "value"
        assert received[0]["workspace_id"] == "ws1"

    @pytest.mark.asyncio
    async def test_async_callback(self, event_bus):
        """异步回调应被正确 await"""
        received = []

        async def async_callback(event_type, data, workspace_id):
            received.append({"event_type": event_type, "data": data})

        event_bus.subscribe("async.event", async_callback)
        await event_bus.emit("async.event", {"async": True})

        assert len(received) == 1
        assert received[0]["data"]["async"] is True

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, event_bus):
        """多个订阅者都应收到事件"""
        count = {"a": 0, "b": 0}

        def cb_a(event_type, data, ws_id):
            count["a"] += 1

        def cb_b(event_type, data, ws_id):
            count["b"] += 1

        event_bus.subscribe("multi.event", cb_a)
        event_bus.subscribe("multi.event", cb_b)
        await event_bus.emit("multi.event", {})

        assert count["a"] == 1
        assert count["b"] == 1

    @pytest.mark.asyncio
    async def test_subscriber_error_does_not_break_others(self, event_bus):
        """一个订阅者异常不应影响其他订阅者"""
        results = []

        def bad_callback(event_type, data, ws_id):
            raise RuntimeError("boom")

        def good_callback(event_type, data, ws_id):
            results.append("good")

        event_bus.subscribe("error.event", bad_callback)
        event_bus.subscribe("error.event", good_callback)
        await event_bus.emit("error.event", {})

        assert len(results) == 1
        assert results[0] == "good"

    @pytest.mark.asyncio
    async def test_no_subscribers_no_error(self, event_bus):
        """无订阅者时 emit 不应报错"""
        await event_bus.emit("unsubscribed.event", {"data": "ok"})


# ---------------------------------------------------------------------------
# TestEventHistory — 事件历史
# ---------------------------------------------------------------------------

class TestEventHistory:
    @pytest.mark.asyncio
    async def test_event_history_recorded(self, event_bus):
        """emit 后应记录到事件历史"""
        await event_bus.emit("history.event", {"key": "val"})
        history = event_bus.get_recent_events()
        assert len(history) >= 1
        assert history[-1]["type"] == "history.event"
        assert history[-1]["data"]["key"] == "val"

    @pytest.mark.asyncio
    async def test_get_recent_events_limit(self, event_bus):
        """get_recent_events 应支持 limit 参数"""
        for i in range(5):
            await event_bus.emit("limit.event", {"i": i})
        recent = event_bus.get_recent_events(limit=3)
        assert len(recent) <= 3

    @pytest.mark.asyncio
    async def test_history_max_size(self, event_bus):
        """事件历史不应超过 _max_history"""
        event_bus._max_history = 5
        for i in range(10):
            await event_bus.emit("overflow.event", {"i": i})
        assert len(event_bus._event_history) <= 5


# ---------------------------------------------------------------------------
# TestGetStats — 统计信息
# ---------------------------------------------------------------------------

class TestGetStats:
    @pytest.mark.asyncio
    async def test_stats_structure(self, event_bus):
        """get_stats 应返回包含预期键的字典"""
        event_bus.subscribe("stats.event", lambda *a: None)
        await event_bus.emit("stats.event", {})

        stats = event_bus.get_stats()
        assert "total_clients" in stats
        assert "workspace_clients" in stats
        assert "event_types" in stats
        assert "history_size" in stats

    @pytest.mark.asyncio
    async def test_stats_event_types(self, event_bus):
        """stats 应列出已订阅的事件类型"""
        event_bus.subscribe("type.a", lambda *a: None)
        event_bus.subscribe("type.b", lambda *a: None)
        stats = event_bus.get_stats()
        assert "type.a" in stats["event_types"]
        assert "type.b" in stats["event_types"]


# ---------------------------------------------------------------------------
# TestConvenienceEmitMethods — 便捷 emit 方法
# ---------------------------------------------------------------------------

class TestConvenienceEmitMethods:
    @pytest.mark.asyncio
    async def test_emit_entity_changed(self, event_bus):
        """emit_entity_changed 应触发 entity:changed 事件"""
        received = []
        event_bus.subscribe("entity:changed", lambda t, d, w: received.append(d))
        await event_bus.emit_entity_changed(
            entity_id="e1",
            entity_type="Agent",
            change_type="update",
            properties={"name": "new"},
            workspace_id="ws1",
        )
        assert len(received) == 1
        assert received[0]["entity_id"] == "e1"
        assert received[0]["change_type"] == "update"

    @pytest.mark.asyncio
    async def test_emit_simulation_progress(self, event_bus):
        """emit_simulation_progress 应触发 simulation:progress 事件"""
        received = []
        event_bus.subscribe("simulation:progress", lambda t, d, w: received.append(d))
        await event_bus.emit_simulation_progress(
            simulation_id="sim1",
            phase="running",
            progress=0.5,
            status="active",
            workspace_id="ws1",
        )
        assert len(received) == 1
        assert received[0]["simulation_id"] == "sim1"
        assert received[0]["progress"] == 0.5

    @pytest.mark.asyncio
    async def test_emit_audit_event(self, event_bus):
        """emit_audit_event 应触发 audit:event 事件"""
        received = []
        event_bus.subscribe("audit:event", lambda t, d, w: received.append(d))
        await event_bus.emit_audit_event(
            event_type="login",
            actor="admin",
            action="LOGIN",
            result="success",
        )
        assert len(received) == 1
        assert received[0]["actor"] == "admin"


# ---------------------------------------------------------------------------
# TestGetEventBus — 模块级单例
# ---------------------------------------------------------------------------

class TestGetEventBus:
    def test_get_event_bus_returns_instance(self):
        """get_event_bus 应返回 DomainEventBus 实例"""
        from odap.infra.events.event_bus import get_event_bus, DomainEventBus
        bus = get_event_bus()
        assert isinstance(bus, DomainEventBus)

    def test_module_level_event_bus(self):
        """模块级 event_bus 变量应为 DomainEventBus 实例"""
        from odap.infra.events.event_bus import event_bus, DomainEventBus
        assert isinstance(event_bus, DomainEventBus)


# ---------------------------------------------------------------------------
# TestHookRegistry — Hook 注册表
# ---------------------------------------------------------------------------

class TestHookRegistry:
    def test_register_and_get_hooks(self):
        """注册 Hook 后应能查询到"""
        from odap.infra.events.hook_system import HookRegistry, HookPhase
        registry = HookRegistry()
        handler = lambda ctx, *a, **kw: None
        registry.register("test.event", "hook1", handler, HookPhase.PRE)
        hooks = registry.get_hooks("test.event", HookPhase.PRE)
        assert len(hooks) == 1
        assert hooks[0].name == "hook1"

    def test_unregister(self):
        """注销 Hook 后应查询不到"""
        from odap.infra.events.hook_system import HookRegistry, HookPhase
        registry = HookRegistry()
        handler = lambda ctx, *a, **kw: None
        registry.register("test.event", "hook1", handler, HookPhase.PRE)
        assert registry.unregister("test.event", "hook1") is True
        assert len(registry.get_hooks("test.event", HookPhase.PRE)) == 0

    def test_unregister_nonexistent(self):
        """注销不存在的 Hook 返回 False"""
        from odap.infra.events.hook_system import HookRegistry
        registry = HookRegistry()
        assert registry.unregister("no.event", "no_hook") is False

    def test_enable_disable(self):
        """启用/禁用 Hook"""
        from odap.infra.events.hook_system import HookRegistry, HookPhase
        registry = HookRegistry()
        handler = lambda ctx, *a, **kw: None
        registry.register("test.event", "hook1", handler, HookPhase.PRE)
        registry.disable("test.event", "hook1")
        hooks = registry.get_hooks("test.event", HookPhase.PRE)
        assert len(hooks) == 0  # disabled hooks filtered out

        registry.enable("test.event", "hook1")
        hooks = registry.get_hooks("test.event", HookPhase.PRE)
        assert len(hooks) == 1

    def test_list_events(self):
        """列出所有已注册事件"""
        from odap.infra.events.hook_system import HookRegistry, HookPhase
        registry = HookRegistry()
        handler = lambda ctx, *a, **kw: None
        registry.register("event.a", "h1", handler, HookPhase.PRE)
        registry.register("event.b", "h2", handler, HookPhase.POST)
        events = registry.list_events()
        assert "event.a" in events
        assert "event.b" in events

    def test_get_hook_summary(self):
        """获取 Hook 注册汇总"""
        from odap.infra.events.hook_system import HookRegistry, HookPhase
        registry = HookRegistry()
        handler = lambda ctx, *a, **kw: None
        registry.register("test.event", "h1", handler, HookPhase.PRE)
        registry.register("test.event", "h2", handler, HookPhase.POST)
        summary = registry.get_hook_summary()
        assert "test.event" in summary
        assert summary["test.event"]["total"] == 2
        assert summary["test.event"]["pre"] == 1
        assert summary["test.event"]["post"] == 1


# ---------------------------------------------------------------------------
# TestHookContext — Hook 上下文
# ---------------------------------------------------------------------------

class TestHookContext:
    def test_set_and_get_data(self):
        """HookContext 数据存取"""
        from odap.infra.events.hook_system import HookContext
        ctx = HookContext(event_name="test")
        ctx.set_data("key1", "value1")
        assert ctx.get_data("key1") == "value1"
        assert ctx.get_data("nonexistent", "default") == "default"

    def test_add_error(self):
        """HookContext 错误记录"""
        from odap.infra.events.hook_system import HookContext
        ctx = HookContext(event_name="test")
        ctx.add_error("error1")
        ctx.add_error("error2")
        assert len(ctx.errors) == 2
        assert "error1" in ctx.errors

    def test_context_attributes(self):
        """HookContext 基本属性"""
        from odap.infra.events.hook_system import HookContext
        ctx = HookContext(event_name="test", agent_id="a1", mission_id="m1")
        assert ctx.event_name == "test"
        assert ctx.agent_id == "a1"
        assert ctx.mission_id == "m1"
