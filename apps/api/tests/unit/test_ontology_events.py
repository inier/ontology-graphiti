"""
测试本体事件相关模块
覆盖: DomainEventBus (事件总线), HookSystem (Hook 注册/执行/装饰器)

由于 odap/biz/core/ontology/events.py 不存在，测试 odap/infra/events/ 下的
event_bus.py 和 hook_system.py 中的事件基础设施。
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


# ─────────────────────────────────────────────────
# DomainEventBus 测试
# ─────────────────────────────────────────────────

class TestDomainEventBus:
    """测试 DomainEventBus 事件总线核心功能"""

    @pytest.fixture
    def bus(self):
        from odap.infra.events.event_bus import DomainEventBus
        return DomainEventBus()

    def test_bus_init(self, bus):
        """事件总线初始化状态正确"""
        assert len(bus._ws_clients) == 0
        assert len(bus._subscribers) == 0
        assert len(bus._event_history) == 0
        assert bus._max_history == 1000

    @pytest.mark.asyncio
    async def test_emit_records_history(self, bus):
        """emit 记录事件到历史"""
        await bus.emit("test:event", {"key": "value"})
        assert len(bus._event_history) == 1
        assert bus._event_history[0]["type"] == "test:event"
        assert bus._event_history[0]["data"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_emit_with_workspace(self, bus):
        """emit 带 workspace_id 记录历史"""
        await bus.emit("test:event", {"key": "value"}, workspace_id="ws-1")
        assert len(bus._event_history) == 1

    @pytest.mark.asyncio
    async def test_emit_history_max_limit(self, bus):
        """事件历史不超过最大限制"""
        bus._max_history = 5
        for i in range(10):
            await bus.emit("test:event", {"index": i})
        assert len(bus._event_history) == 5
        # 保留最后5条
        assert bus._event_history[0]["data"]["index"] == 5

    @pytest.mark.asyncio
    async def test_subscribe_and_callback(self, bus):
        """subscribe 注册回调后 emit 触发回调"""
        received = []

        def sync_callback(event_type, data, workspace_id):
            received.append({"type": event_type, "data": data, "ws": workspace_id})

        bus.subscribe("test:callback", sync_callback)
        await bus.emit("test:callback", {"msg": "hello"}, workspace_id="ws-1")

        assert len(received) == 1
        assert received[0]["type"] == "test:callback"
        assert received[0]["data"] == {"msg": "hello"}
        assert received[0]["ws"] == "ws-1"

    @pytest.mark.asyncio
    async def test_subscribe_async_callback(self, bus):
        """subscribe 注册异步回调后 emit 触发"""
        received = []

        async def async_callback(event_type, data, workspace_id):
            received.append({"type": event_type, "data": data})

        bus.subscribe("test:async", async_callback)
        await bus.emit("test:async", {"msg": "async_hello"})

        assert len(received) == 1
        assert received[0]["data"] == {"msg": "async_hello"}

    @pytest.mark.asyncio
    async def test_subscribe_callback_error_does_not_crash(self, bus):
        """回调抛异常不影响 emit 执行"""
        def bad_callback(event_type, data, workspace_id):
            raise RuntimeError("callback error")

        bus.subscribe("test:error", bad_callback)
        # 不应抛出异常
        await bus.emit("test:error", {"msg": "should not crash"})
        assert len(bus._event_history) == 1

    @pytest.mark.asyncio
    async def test_emit_entity_changed(self, bus):
        """emit_entity_changed 发出正确事件"""
        received = []
        bus.subscribe("entity:changed", lambda t, d, w: received.append(d))
        await bus.emit_entity_changed(
            entity_id="e-1",
            entity_type="Person",
            change_type="created",
            properties={"name": "张三"},
            workspace_id="ws-1",
        )
        assert len(received) == 1
        assert received[0]["entity_id"] == "e-1"
        assert received[0]["entity_type"] == "Person"
        assert received[0]["change_type"] == "created"

    @pytest.mark.asyncio
    async def test_emit_intel_updated(self, bus):
        """emit_intel_updated 发出正确事件"""
        received = []
        bus.subscribe("intel:updated", lambda t, d, w: received.append(d))
        await bus.emit_intel_updated(
            report_id="r-1",
            source="web",
            confidence=0.85,
            summary="情报摘要",
        )
        assert len(received) == 1
        assert received[0]["report_id"] == "r-1"
        assert received[0]["confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_emit_action_result(self, bus):
        """emit_action_result 发出正确事件"""
        received = []
        bus.subscribe("action:result", lambda t, d, w: received.append(d))
        await bus.emit_action_result(
            action_id="a-1",
            action_type="attack",
            target_id="t-1",
            status="completed",
            result={"damage": 50},
        )
        assert received[0]["action_id"] == "a-1"
        assert received[0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_emit_simulation_progress(self, bus):
        """emit_simulation_progress 发出正确事件"""
        received = []
        bus.subscribe("simulation:progress", lambda t, d, w: received.append(d))
        await bus.emit_simulation_progress(
            simulation_id="sim-1",
            phase="running",
            progress=0.5,
            status="active",
            data={"step": 10},
        )
        assert received[0]["simulation_id"] == "sim-1"
        assert received[0]["progress"] == 0.5

    @pytest.mark.asyncio
    async def test_emit_simulation_completed(self, bus):
        """emit_simulation_completed 发出正确事件"""
        received = []
        bus.subscribe("simulation:completed", lambda t, d, w: received.append(d))
        await bus.emit_simulation_completed(
            simulation_id="sim-1",
            results={"winner": "red"},
        )
        assert received[0]["results"]["winner"] == "red"

    @pytest.mark.asyncio
    async def test_emit_simulation_failed(self, bus):
        """emit_simulation_failed 发出正确事件"""
        received = []
        bus.subscribe("simulation:failed", lambda t, d, w: received.append(d))
        await bus.emit_simulation_failed(
            simulation_id="sim-1",
            error="timeout",
        )
        assert received[0]["error"] == "timeout"

    def test_get_stats(self, bus):
        """get_stats 返回正确统计"""
        stats = bus.get_stats()
        assert "total_clients" in stats
        assert "workspace_clients" in stats
        assert "event_types" in stats
        assert "history_size" in stats
        assert stats["total_clients"] == 0
        assert stats["history_size"] == 0

    def test_get_recent_events(self, bus):
        """get_recent_events 返回最近事件"""
        bus._event_history = [
            {"type": f"event-{i}", "data": {}, "timestamp": "2026-01-01"}
            for i in range(10)
        ]
        recent = bus.get_recent_events(limit=3)
        assert len(recent) == 3
        assert recent[-1]["type"] == "event-9"

    def test_get_event_bus_singleton(self):
        """get_event_bus 返回全局单例"""
        from odap.infra.events.event_bus import get_event_bus, DomainEventBus
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert isinstance(bus1, DomainEventBus)
        assert bus1 is bus2


# ─────────────────────────────────────────────────
# HookPhase / HookPriority 测试
# ─────────────────────────────────────────────────

class TestHookEnums:
    """测试 Hook 枚举类型"""

    def test_hook_phase_values(self):
        from odap.infra.events.hook_system import HookPhase
        assert HookPhase.PRE.value == "pre"
        assert HookPhase.POST.value == "post"
        assert HookPhase.ON_ERROR.value == "on_error"

    def test_hook_priority_values(self):
        from odap.infra.events.hook_system import HookPriority
        assert HookPriority.CRITICAL.value < HookPriority.HIGH.value
        assert HookPriority.HIGH.value < HookPriority.MEDIUM.value
        assert HookPriority.MEDIUM.value < HookPriority.LOW.value
        assert HookPriority.LOW.value < HookPriority.DEFAULT.value

    def test_hook_phase_is_str_enum(self):
        """HookPhase 是 (str, Enum) 双继承"""
        from odap.infra.events.hook_system import HookPhase
        assert isinstance(HookPhase.PRE, str)


# ─────────────────────────────────────────────────
# HookContext 测试
# ─────────────────────────────────────────────────

class TestHookContext:
    """测试 HookContext 上下文对象"""

    def test_context_init(self):
        from odap.infra.events.hook_system import HookContext
        ctx = HookContext(event_name="test:event", agent_id="agent-1", mission_id="mission-1")
        assert ctx.event_name == "test:event"
        assert ctx.agent_id == "agent-1"
        assert ctx.mission_id == "mission-1"
        assert ctx.data == {}
        assert ctx.errors == []

    def test_context_set_get_data(self):
        from odap.infra.events.hook_system import HookContext
        ctx = HookContext(event_name="test")
        ctx.set_data("key1", "value1")
        assert ctx.get_data("key1") == "value1"
        assert ctx.get_data("nonexistent") is None
        assert ctx.get_data("nonexistent", "default") == "default"

    def test_context_add_error(self):
        from odap.infra.events.hook_system import HookContext
        ctx = HookContext(event_name="test")
        ctx.add_error("error1")
        ctx.add_error("error2")
        assert len(ctx.errors) == 2
        assert "error1" in ctx.errors


# ─────────────────────────────────────────────────
# HookRegistry 测试
# ─────────────────────────────────────────────────

class TestHookRegistry:
    """测试 HookRegistry 注册/注销/查询"""

    @pytest.fixture
    def registry(self):
        from odap.infra.events.hook_system import HookRegistry
        # 每次创建新实例，避免单例干扰
        reg = HookRegistry()
        return reg

    def test_register_hook(self, registry):
        """注册 Hook"""
        def dummy_handler(ctx, *args, **kwargs):
            pass

        result = registry.register(
            event="test:event",
            name="dummy_hook",
            handler=dummy_handler,
            phase=HookPhase.PRE,
            priority=HookPriority.HIGH.value,
        )
        assert result is True
        hooks = registry.get_hooks("test:event", HookPhase.PRE)
        assert len(hooks) == 1
        assert hooks[0].name == "dummy_hook"

    def test_register_multiple_hooks_sorted_by_priority(self, registry):
        """多个 Hook 按优先级排序"""
        from odap.infra.events.hook_system import HookPhase, HookPriority

        registry.register("test:event", "low_hook", lambda ctx: None, HookPhase.PRE, HookPriority.LOW.value)
        registry.register("test:event", "critical_hook", lambda ctx: None, HookPhase.PRE, HookPriority.CRITICAL.value)
        registry.register("test:event", "medium_hook", lambda ctx: None, HookPhase.PRE, HookPriority.MEDIUM.value)

        hooks = registry.get_hooks("test:event", HookPhase.PRE)
        assert len(hooks) == 3
        assert hooks[0].name == "critical_hook"
        assert hooks[1].name == "medium_hook"
        assert hooks[2].name == "low_hook"

    def test_unregister_hook(self, registry):
        """注销 Hook"""
        from odap.infra.events.hook_system import HookPhase
        registry.register("test:event", "to_remove", lambda ctx: None, HookPhase.PRE)
        result = registry.unregister("test:event", "to_remove")
        assert result is True
        hooks = registry.get_hooks("test:event", HookPhase.PRE)
        assert len(hooks) == 0

    def test_unregister_nonexistent_hook(self, registry):
        """注销不存在的 Hook 返回 False"""
        result = registry.unregister("nonexistent:event", "no_hook")
        assert result is False

    def test_enable_disable_hook(self, registry):
        """启用/禁用 Hook"""
        from odap.infra.events.hook_system import HookPhase
        registry.register("test:event", "toggle_hook", lambda ctx: None, HookPhase.PRE)

        # 禁用
        result = registry.disable("test:event", "toggle_hook")
        assert result is True
        hooks = registry.get_hooks("test:event", HookPhase.PRE)
        assert len(hooks) == 0  # 禁用后不返回

        # 启用
        result = registry.enable("test:event", "toggle_hook")
        assert result is True
        hooks = registry.get_hooks("test:event", HookPhase.PRE)
        assert len(hooks) == 1

    def test_list_events(self, registry):
        """列出所有已注册事件"""
        from odap.infra.events.hook_system import HookPhase
        registry.register("event:a", "hook1", lambda ctx: None, HookPhase.PRE)
        registry.register("event:b", "hook2", lambda ctx: None, HookPhase.POST)
        events = registry.list_events()
        assert "event:a" in events
        assert "event:b" in events

    def test_get_hook_summary(self, registry):
        """获取 Hook 注册汇总"""
        from odap.infra.events.hook_system import HookPhase
        registry.register("test:event", "hook1", lambda ctx: None, HookPhase.PRE)
        registry.register("test:event", "hook2", lambda ctx: None, HookPhase.POST)
        summary = registry.get_hook_summary()
        assert "test:event" in summary
        assert summary["test:event"]["total"] == 2
        assert summary["test:event"]["pre"] == 1
        assert summary["test:event"]["post"] == 1


# ─────────────────────────────────────────────────
# HookExecutor 测试
# ─────────────────────────────────────────────────

class TestHookExecutor:
    """测试 HookExecutor 执行逻辑"""

    @pytest.fixture
    def executor_and_registry(self):
        from odap.infra.events.hook_system import HookRegistry, HookExecutor, HookPhase, HookPriority
        registry = HookRegistry()
        executor = HookExecutor(registry=registry)
        return executor, registry

    @pytest.mark.asyncio
    async def test_execute_pre_hooks_pass(self, executor_and_registry):
        """Pre Hook 返回 None 时继续执行"""
        executor, registry = executor_and_registry
        registry.register("test:event", "pass_hook", lambda ctx: None, HookPhase.PRE)
        ctx = HookContext(event_name="test:event")
        result = await executor.execute_pre_hooks("test:event", ctx)
        assert result is True

    @pytest.mark.asyncio
    async def test_execute_pre_hooks_abort(self, executor_and_registry):
        """Pre Hook 返回 False 时中断执行"""
        executor, registry = executor_and_registry
        registry.register("test:event", "abort_hook", lambda ctx: False, HookPhase.PRE)
        ctx = HookContext(event_name="test:event")
        result = await executor.execute_pre_hooks("test:event", ctx)
        assert result is False

    @pytest.mark.asyncio
    async def test_execute_pre_hooks_error_aborts(self, executor_and_registry):
        """Pre Hook 抛异常时中断执行"""
        executor, registry = executor_and_registry
        def bad_hook(ctx):
            raise RuntimeError("hook error")
        registry.register("test:event", "bad_hook", bad_hook, HookPhase.PRE)
        ctx = HookContext(event_name="test:event")
        result = await executor.execute_pre_hooks("test:event", ctx)
        assert result is False
        assert len(ctx.errors) > 0

    @pytest.mark.asyncio
    async def test_execute_post_hooks(self, executor_and_registry):
        """Post Hook 正常执行"""
        executor, registry = executor_and_registry
        called = []
        registry.register("test:event", "post_hook", lambda ctx, result: called.append(result), HookPhase.POST)
        ctx = HookContext(event_name="test:event")
        await executor.execute_post_hooks("test:event", ctx, result="test_result")
        assert called == ["test_result"]

    @pytest.mark.asyncio
    async def test_execute_error_hooks(self, executor_and_registry):
        """Error Hook 正常执行"""
        executor, registry = executor_and_registry
        errors_caught = []
        registry.register("test:event", "error_hook", lambda ctx, err: errors_caught.append(str(err)), HookPhase.ON_ERROR)
        ctx = HookContext(event_name="test:event")
        await executor.execute_error_hooks("test:event", ctx, RuntimeError("test error"))
        assert len(errors_caught) == 1
        assert "test error" in errors_caught[0]

    def test_record_execution_history(self, executor_and_registry):
        """记录执行历史"""
        executor, _ = executor_and_registry
        from odap.infra.events.hook_system import HookPhase
        executor.record_execution("test:event", "hook1", HookPhase.PRE, True)
        history = executor.get_execution_history()
        assert len(history) == 1
        assert history[0]["event"] == "test:event"
        assert history[0]["success"] is True

    def test_execution_history_limit(self, executor_and_registry):
        """执行历史内部列表不超过 1000 条"""
        executor, _ = executor_and_registry
        from odap.infra.events.hook_system import HookPhase
        for i in range(1100):
            executor.record_execution("test:event", f"hook-{i}", HookPhase.PRE, True)
        # 内部列表被截断到 1000
        assert len(executor._execution_history) == 1000
        # get_execution_history 默认 limit=100
        history = executor.get_execution_history()
        assert len(history) == 100
        # 传入更大的 limit 可以获取更多
        history_all = executor.get_execution_history(limit=2000)
        assert len(history_all) == 1000


# ─────────────────────────────────────────────────
# HookRegistration 测试
# ─────────────────────────────────────────────────

class TestHookRegistration:
    """测试 HookRegistration 数据类"""

    def test_registration_defaults(self):
        from odap.infra.events.hook_system import HookRegistration, HookPhase
        reg = HookRegistration(
            name="test_hook",
            handler=lambda: None,
            phase=HookPhase.PRE,
        )
        assert reg.name == "test_hook"
        assert reg.enabled is True
        assert reg.description == ""
        assert reg.tags == []

    def test_registration_with_all_fields(self):
        from odap.infra.events.hook_system import HookRegistration, HookPhase
        reg = HookRegistration(
            name="full_hook",
            handler=lambda: None,
            phase=HookPhase.POST,
            priority=10,
            enabled=False,
            description="A test hook",
            tags=["test", "hook"],
        )
        assert reg.priority == 10
        assert reg.enabled is False
        assert reg.description == "A test hook"
        assert "test" in reg.tags


# ─────────────────────────────────────────────────
# 内置 Hook 工厂函数测试
# ─────────────────────────────────────────────────

class TestBuiltinHookFactories:
    """测试 create_logging_hook / create_timing_hook 工厂函数"""

    @pytest.mark.asyncio
    async def test_create_logging_hook(self):
        """create_logging_hook 返回可调用异步函数"""
        from odap.infra.events.hook_system import create_logging_hook, HookPhase, HookContext
        hook = create_logging_hook(HookPhase.PRE, "test:event")
        ctx = HookContext(event_name="test:event")
        # 不应抛出异常
        await hook(ctx)

    @pytest.mark.asyncio
    async def test_create_timing_hook_pre(self):
        """create_timing_hook PRE 阶段记录开始时间"""
        from odap.infra.events.hook_system import create_timing_hook, HookPhase, HookContext
        hook = create_timing_hook(HookPhase.PRE, "test:event")
        ctx = HookContext(event_name="test:event")
        await hook(ctx)
        # PRE 阶段不报错即可

    @pytest.mark.asyncio
    async def test_create_timing_hook_post(self):
        """create_timing_hook POST 阶段计算耗时"""
        from odap.infra.events.hook_system import create_timing_hook, HookPhase, HookContext
        hook = create_timing_hook(HookPhase.POST, "test:event")
        ctx = HookContext(event_name="test:event")
        # 没有 PRE 记录的 start_time，不应报错
        await hook(ctx)


# ─────────────────────────────────────────────────
# 事件总线与 Hook 集成测试
# ─────────────────────────────────────────────────

class TestEventBusHookIntegration:
    """测试事件总线与 Hook 系统的集成"""

    @pytest.mark.asyncio
    async def test_event_bus_subscriber_receives_hook_events(self):
        """事件总线订阅者能收到 Hook 相关事件"""
        from odap.infra.events.event_bus import DomainEventBus
        bus = DomainEventBus()

        received = []
        bus.subscribe("entity:changed", lambda t, d, w: received.append(d))

        await bus.emit_entity_changed(
            entity_id="e-1",
            entity_type="Unit",
            change_type="updated",
            properties={"status": "active"},
            workspace_id="ws-1",
        )

        assert len(received) == 1
        assert received[0]["entity_id"] == "e-1"
        assert received[0]["change_type"] == "updated"

    @pytest.mark.asyncio
    async def test_event_bus_multiple_subscribers(self):
        """多个订阅者都能收到事件"""
        from odap.infra.events.event_bus import DomainEventBus
        bus = DomainEventBus()

        received_a = []
        received_b = []
        bus.subscribe("test:multi", lambda t, d, w: received_a.append(d))
        bus.subscribe("test:multi", lambda t, d, w: received_b.append(d))

        await bus.emit("test:multi", {"msg": "broadcast"})

        assert len(received_a) == 1
        assert len(received_b) == 1
        assert received_a[0]["msg"] == "broadcast"
        assert received_b[0]["msg"] == "broadcast"

    @pytest.mark.asyncio
    async def test_event_bus_emit_serialization(self):
        """emit 生成可序列化的 JSON 消息"""
        from odap.infra.events.event_bus import DomainEventBus
        bus = DomainEventBus()

        captured_messages = []

        # Mock _broadcast 捕获消息
        original_broadcast = bus._broadcast
        async def mock_broadcast(message, workspace_id=None):
            captured_messages.append(message)

        bus._broadcast = mock_broadcast
        await bus.emit("test:serialize", {"key": "value"}, workspace_id="ws-1")

        assert len(captured_messages) == 1
        parsed = json.loads(captured_messages[0])
        assert parsed["type"] == "test:serialize"
        assert parsed["data"] == {"key": "value"}
        assert parsed["workspace_id"] == "ws-1"
        assert "timestamp" in parsed


# 需要在模块顶部导入 HookPhase / HookPriority / HookContext 以供测试使用
from odap.infra.events.hook_system import HookPhase, HookPriority, HookContext
