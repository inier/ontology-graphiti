"""test_ooda_lifecycle.py - OODA 生命周期钩子单元测试

测试 OODAExecutor 执行器、OODALifecycleHook 回调、
钩子异常不中断 OODA 循环、OODAExecutor 完整流程。

适配统一接口：OODALifecycleHook 来自 interfaces/ooda_interface.py，
签名 on_phase_start(phase, context) / on_phase_end(phase, result, context)。
"""

import pytest
import asyncio
from typing import Any, Dict


# ---------------------------------------------------------------------------
# 延迟导入 fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def ooda_lifecycle_module():
    """导入 ooda_lifecycle 模块"""
    try:
        import odap.biz.core.agent.impl.ooda_lifecycle as mod
    except ImportError:
        pytest.skip("ooda_lifecycle not importable")
    return mod


@pytest.fixture
def ooda_interface_module():
    """导入 ooda_interface 模块（统一接口定义）"""
    try:
        import odap.biz.core.agent.interfaces.ooda_interface as mod
    except ImportError:
        pytest.skip("ooda_interface not importable")
    return mod


@pytest.fixture
def mock_ooda():
    """创建 mock OODA 实现（5 阶段：observe/orient/decide/act/evaluate）"""

    class MockOODA:
        def __init__(self):
            self.observe_called = False
            self.orient_called = False
            self.decide_called = False
            self.act_called = False
            self.evaluate_called = False

        async def observe(self, context):
            self.observe_called = True
            return {"observations": [{"content": "test"}], "observation_count": 1}

        async def orient(self, observe_result):
            self.orient_called = True
            return {"analysis": {"urgency": "normal"}, "key_entities": []}

        async def decide(self, orient_result):
            self.decide_called = True
            return {"decision": "proceed", "confidence": 0.8}

        async def act(self, decide_result):
            self.act_called = True
            return {"action": "execute", "result": "success"}

        async def evaluate(self, act_result, decide_result):
            self.evaluate_called = True
            return {"deviation": 0.0, "requires_monitoring": False}

    return MockOODA()


@pytest.fixture
def executor(ooda_lifecycle_module, mock_ooda):
    """创建 OODAExecutor"""
    OODAExecutor = ooda_lifecycle_module.OODAExecutor
    return OODAExecutor(mock_ooda)


# ---------------------------------------------------------------------------
# TestLifecycleHooks
# ---------------------------------------------------------------------------

class TestLifecycleHooks:
    @pytest.mark.asyncio
    async def test_on_phase_start_called(self, ooda_lifecycle_module, ooda_interface_module, mock_ooda):
        """on_phase_start 在每个阶段开始前被调用"""
        OODAExecutor = ooda_lifecycle_module.OODAExecutor
        OODALifecycleHook = ooda_interface_module.OODALifecycleHook

        start_calls = []

        class TrackingHook(OODALifecycleHook):
            async def on_phase_start(self, phase, context):
                start_calls.append(phase)

        executor = OODAExecutor(mock_ooda, hooks=[TrackingHook()])
        await executor.run({"query": "test"})

        assert "observe" in start_calls
        assert "orient" in start_calls
        assert "decide" in start_calls
        assert "act" in start_calls
        # evaluate 阶段也应该被调用（因为 mock_ooda 有 evaluate 方法）
        assert "evaluate" in start_calls

    @pytest.mark.asyncio
    async def test_on_phase_end_called_with_3_params(self, ooda_lifecycle_module, ooda_interface_module, mock_ooda):
        """on_phase_end(phase, result, context) 3 参数签名被正确调用"""
        OODAExecutor = ooda_lifecycle_module.OODAExecutor
        OODALifecycleHook = ooda_interface_module.OODALifecycleHook

        end_calls = []

        class TrackingHook(OODALifecycleHook):
            async def on_phase_end(self, phase, result, context):
                end_calls.append((phase, result is not None, context is not None))

        executor = OODAExecutor(mock_ooda, hooks=[TrackingHook()])
        await executor.run({"query": "test"})

        # 每个阶段的 result 和 context 都不为 None
        for phase, has_result, has_context in end_calls:
            assert has_result, f"phase {phase} should have result"
            assert has_context, f"phase {phase} should have context"

        phases = [call[0] for call in end_calls]
        assert "observe" in phases
        assert "act" in phases

    @pytest.mark.asyncio
    async def test_hook_exception_does_not_break_cycle(self, ooda_lifecycle_module, ooda_interface_module, mock_ooda):
        """钩子抛出异常不中断 OODA 循环"""
        OODAExecutor = ooda_lifecycle_module.OODAExecutor
        OODALifecycleHook = ooda_interface_module.OODALifecycleHook

        class BrokenHook(OODALifecycleHook):
            async def on_phase_start(self, phase, context):
                raise RuntimeError("hook crashed!")
            async def on_phase_end(self, phase, result, context):
                raise RuntimeError("hook crashed again!")

        executor = OODAExecutor(mock_ooda, hooks=[BrokenHook()])
        # 不应抛出异常
        result = await executor.run({"query": "test"})

        # OODA 循环应正常完成
        assert "observe" in result
        assert "act" in result
        assert mock_ooda.observe_called
        assert mock_ooda.act_called

    @pytest.mark.asyncio
    async def test_multiple_hooks_all_called(self, ooda_lifecycle_module, ooda_interface_module, mock_ooda):
        """多个钩子都被调用"""
        OODAExecutor = ooda_lifecycle_module.OODAExecutor
        OODALifecycleHook = ooda_interface_module.OODALifecycleHook

        calls_a = []
        calls_b = []

        class HookA(OODALifecycleHook):
            async def on_phase_start(self, phase, context):
                calls_a.append(phase)

        class HookB(OODALifecycleHook):
            async def on_phase_start(self, phase, context):
                calls_b.append(phase)

        executor = OODAExecutor(mock_ooda, hooks=[HookA(), HookB()])
        await executor.run({"query": "test"})

        # 5 阶段（含 evaluate）
        assert len(calls_a) >= 4
        assert len(calls_b) >= 4


# ---------------------------------------------------------------------------
# TestOODAExecutor
# ---------------------------------------------------------------------------

class TestOODAExecutor:
    @pytest.mark.asyncio
    async def test_full_cycle(self, executor, mock_ooda):
        """完整 OODA 循环执行"""
        result = await executor.run({"query": "test"})
        assert mock_ooda.observe_called
        assert mock_ooda.orient_called
        assert mock_ooda.decide_called
        assert mock_ooda.act_called
        assert result["observe"]["observation_count"] == 1
        assert result["act"]["result"] == "success"

    @pytest.mark.asyncio
    async def test_evaluate_phase_included(self, ooda_lifecycle_module, mock_ooda):
        """evaluate 阶段被包含在结果中（当 OODA 实现有 evaluate 方法时）"""
        OODAExecutor = ooda_lifecycle_module.OODAExecutor
        executor = OODAExecutor(mock_ooda)
        result = await executor.run({"query": "test"})

        assert mock_ooda.evaluate_called
        assert "evaluate" in result
        assert result["evaluate"]["deviation"] == 0.0

    @pytest.mark.asyncio
    async def test_no_evaluate_when_not_available(self, ooda_lifecycle_module):
        """当 OODA 实现没有 evaluate 方法时，不包含 evaluate 阶段"""

        class SimpleOODA:
            async def observe(self, context):
                return {"observed": True}
            async def orient(self, observe_result):
                return {"oriented": True}
            async def decide(self, orient_result):
                return {"decided": True}
            async def act(self, decide_result):
                return {"acted": True}

        OODAExecutor = ooda_lifecycle_module.OODAExecutor
        executor = OODAExecutor(SimpleOODA())
        result = await executor.run({"query": "test"})

        assert "evaluate" not in result
        assert "observe" in result

    @pytest.mark.asyncio
    async def test_add_hook(self, ooda_lifecycle_module, ooda_interface_module, mock_ooda):
        """动态添加钩子"""
        OODAExecutor = ooda_lifecycle_module.OODAExecutor
        OODALifecycleHook = ooda_interface_module.OODALifecycleHook

        calls = []

        class LateHook(OODALifecycleHook):
            async def on_phase_start(self, phase, context):
                calls.append(phase)

        executor = OODAExecutor(mock_ooda)
        executor.add_hook(LateHook())
        await executor.run({"query": "test"})

        assert len(calls) >= 4

    @pytest.mark.asyncio
    async def test_no_hooks_still_works(self, ooda_lifecycle_module, mock_ooda):
        """没有钩子时 OODA 循环正常执行"""
        OODAExecutor = ooda_lifecycle_module.OODAExecutor
        executor = OODAExecutor(mock_ooda, hooks=[])
        result = await executor.run({"query": "test"})
        assert result is not None
        assert "observe" in result
