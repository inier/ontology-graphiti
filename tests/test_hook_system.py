"""
Hook System 测试用例
"""

import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.hook_system import (
    HookRegistry,
    HookExecutor,
    HookContext,
    HookPhase,
    HookPriority,
    HookRegistration,
    HookDecorator,
    BuiltinHooks,
    register_builtin_hooks,
)


def test_hook_phase_enum():
    """测试 HookPhase 枚举"""
    print("=== 测试 HookPhase 枚举 ===")
    assert HookPhase.PRE.value == "pre"
    assert HookPhase.POST.value == "post"
    assert HookPhase.ON_ERROR.value == "on_error"
    print("HookPhase 枚举测试通过")
    return True


def test_hook_priority_enum():
    """测试 HookPriority 枚举"""
    print("\n=== 测试 HookPriority 枚举 ===")
    assert HookPriority.CRITICAL.value == 1
    assert HookPriority.HIGH.value == 25
    assert HookPriority.MEDIUM.value == 50
    assert HookPriority.LOW.value == 75
    assert HookPriority.DEFAULT.value == 100
    print("HookPriority 枚举测试通过")
    return True


def test_hook_context():
    """测试 HookContext"""
    print("\n=== 测试 HookContext ===")
    context = HookContext(event_name="test.event", agent_id="agent1", mission_id="mission1")

    context.set_data("key1", "value1")
    assert context.get_data("key1") == "value1"
    assert context.get_data("nonexistent", "default") == "default"

    context.add_error("error1")
    assert len(context.errors) == 1
    assert context.errors[0] == "error1"

    print("HookContext 测试通过")
    return True


def test_hook_registry_singleton():
    """测试 HookRegistry 单例"""
    print("\n=== 测试 HookRegistry 单例 ===")
    registry1 = HookRegistry.get_instance()
    registry2 = HookRegistry.get_instance()
    assert registry1 is registry2
    print("HookRegistry 单例测试通过")
    return True


def test_hook_registration():
    """测试 Hook 注册"""
    print("\n=== 测试 Hook 注册 ===")
    registry = HookRegistry()
    hook_called = {"count": 0}

    async def test_handler(ctx, *args, **kwargs):
        hook_called["count"] += 1
        return True

    result = registry.register(
        event="test.event",
        name="test_hook",
        handler=test_handler,
        phase=HookPhase.POST,
        priority=HookPriority.HIGH.value,
        description="测试 Hook",
    )
    assert result == True

    hooks = registry.get_hooks("test.event")
    assert len(hooks) == 1
    assert hooks[0].name == "test_hook"
    assert hooks[0].priority == HookPriority.HIGH.value

    print("Hook 注册测试通过")
    return True


def test_hook_unregister():
    """测试 Hook 注销"""
    print("\n=== 测试 Hook 注销 ===")
    registry = HookRegistry()

    async def handler1(ctx):
        return True

    async def handler2(ctx):
        return True

    registry.register("test.event", "hook1", handler1, HookPhase.POST)
    registry.register("test.event", "hook2", handler2, HookPhase.POST)

    assert len(registry.get_hooks("test.event")) == 2

    result = registry.unregister("test.event", "hook1")
    assert result == True
    assert len(registry.get_hooks("test.event")) == 1

    result = registry.unregister("test.event", "nonexistent")
    assert result == False

    print("Hook 注销测试通过")
    return True


def test_hook_enable_disable():
    """测试 Hook 启用/禁用"""
    print("\n=== 测试 Hook 启用/禁用 ===")
    registry = HookRegistry()

    async def handler(ctx):
        return True

    registry.register("test.event", "test_hook", handler, HookPhase.POST)
    assert len(registry.get_hooks("test.event")) == 1
    assert registry.get_hooks("test.event")[0].enabled == True

    registry.disable("test.event", "test_hook")
    assert len(registry.get_hooks("test.event")) == 0

    registry.enable("test.event", "test_hook")
    assert len(registry.get_hooks("test.event")) == 1
    assert registry.get_hooks("test.event")[0].enabled == True

    print("Hook 启用/禁用测试通过")
    return True


def test_hook_executor_pre_hooks():
    """测试 Pre Hooks 执行"""
    print("\n=== 测试 Pre Hooks 执行 ===")

    async def run():
        registry = HookRegistry()
        executor = HookExecutor(registry)
        context = HookContext(event_name="test.event")

        pre_called = {"count": 0}

        async def pre_hook1(ctx, *args, **kwargs):
            pre_called["count"] += 1
            return True

        async def pre_hook2(ctx, *args, **kwargs):
            return False

        registry.register("test.event", "pre1", pre_hook1, HookPhase.PRE, HookPriority.HIGH.value)
        registry.register("test.event", "pre2", pre_hook2, HookPhase.PRE, HookPriority.MEDIUM.value)

        result = await executor.execute_pre_hooks("test.event", context, (), {})
        assert result == False
        assert pre_called["count"] == 1

        return True

    result = asyncio.run(run())
    assert result == True
    print("Pre Hooks 执行测试通过")
    return True


def test_hook_executor_post_hooks():
    """测试 Post Hooks 执行"""
    print("\n=== 测试 Post Hooks 执行 ===")

    async def run():
        registry = HookRegistry()
        executor = HookExecutor(registry)
        context = HookContext(event_name="test.event")

        post_called = {"count": 0}

        async def post_hook(ctx, result=None):
            post_called["count"] += 1

        registry.register("test.event", "post1", post_hook, HookPhase.POST)

        await executor.execute_post_hooks("test.event", context, {"result": "success"})
        assert post_called["count"] == 1

        return True

    result = asyncio.run(run())
    assert result == True
    print("Post Hooks 执行测试通过")
    return True


def test_hook_executor_error_hooks():
    """测试 Error Hooks 执行"""
    print("\n=== 测试 Error Hooks 执行 ===")

    async def run():
        registry = HookRegistry()
        executor = HookExecutor(registry)
        context = HookContext(event_name="test.event")

        error_called = {"count": 0}

        async def error_hook(ctx, error):
            error_called["count"] += 1

        registry.register("test.event", "error1", error_hook, HookPhase.ON_ERROR)

        error = ValueError("test error")
        await executor.execute_error_hooks("test.event", context, error)
        assert error_called["count"] == 1

        return True

    result = asyncio.run(run())
    assert result == True
    print("Error Hooks 执行测试通过")
    return True


def test_hook_priority_order():
    """测试 Hook 优先级顺序"""
    print("\n=== 测试 Hook 优先级顺序 ===")
    registry = HookRegistry()
    execution_order = {"order": []}

    async def handler1(ctx):
        execution_order["order"].append("low")
        return True

    async def handler2(ctx):
        execution_order["order"].append("high")
        return True

    async def handler3(ctx):
        execution_order["order"].append("critical")
        return True

    registry.register("test.event", "low", handler1, HookPhase.POST, HookPriority.LOW.value)
    registry.register("test.event", "high", handler2, HookPhase.POST, HookPriority.HIGH.value)
    registry.register("test.event", "critical", handler3, HookPhase.POST, HookPriority.CRITICAL.value)

    hooks = registry.get_hooks("test.event", HookPhase.POST)
    assert hooks[0].name == "critical"
    assert hooks[1].name == "high"
    assert hooks[2].name == "low"

    print("Hook 优先级顺序测试通过")
    return True


def test_hook_summary():
    """测试 Hook 汇总"""
    print("\n=== 测试 Hook 汇总 ===")
    registry = HookRegistry()

    async def handler(ctx):
        return True

    registry.register("event1", "hook1", handler, HookPhase.PRE)
    registry.register("event1", "hook2", handler, HookPhase.POST)
    registry.register("event2", "hook3", handler, HookPhase.ON_ERROR)

    summary = registry.get_hook_summary()
    assert "event1" in summary
    assert summary["event1"]["total"] == 2
    assert summary["event1"]["pre"] == 1
    assert summary["event1"]["post"] == 1
    assert "event2" in summary

    print("Hook 汇总测试通过")
    return True


def test_builtin_hooks():
    """测试内置 Hooks"""
    print("\n=== 测试内置 Hooks ===")

    async def run():
        register_builtin_hooks()
        registry = HookRegistry.get_instance()

        summary = registry.get_hook_summary()
        assert "mission.start" in summary
        assert "mission.complete" in summary

        print("内置 Hooks 注册成功")
        return True

    result = asyncio.run(run())
    assert result == True
    print("内置 Hooks 测试通过")
    return True


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始运行 Hook System 测试...")
    print("=" * 60)

    tests = [
        test_hook_phase_enum,
        test_hook_priority_enum,
        test_hook_context,
        test_hook_registry_singleton,
        test_hook_registration,
        test_hook_unregister,
        test_hook_enable_disable,
        test_hook_executor_pre_hooks,
        test_hook_executor_post_hooks,
        test_hook_executor_error_hooks,
        test_hook_priority_order,
        test_hook_summary,
        test_builtin_hooks,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"  ❌ {test.__name__} 返回 False")
        except Exception as e:
            failed += 1
            print(f"  ❌ {test.__name__}: {e}")

    print("\n" + "=" * 60)
    print(f"测试结果: 成功 {passed}, 失败 {failed}")
    print("=" * 60)

    if failed == 0:
        print("🎉 所有测试通过！")
    else:
        print("❌ 有测试失败，请检查代码")

    return failed == 0


if __name__ == "__main__":
    run_all_tests()