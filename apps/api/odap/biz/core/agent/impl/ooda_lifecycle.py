"""OODA 生命周期钩子执行器

提供 OODAExecutor，在 OODA 循环的各阶段前后调用 OODALifecycleHook。
统一使用 interfaces/ooda_interface.py 中的 OODALifecycleHook 定义（3 参数签名）。
"""

import logging
from typing import Any, Dict, List, Optional

from odap.biz.core.agent.interfaces.ooda_interface import OODALifecycleHook

logger = logging.getLogger(__name__)


class OODAExecutor:
    """带生命周期钩子的 OODA 执行器

    在每个阶段前后调用已注册的 OODALifecycleHook。
    钩子异常被捕获并记录，不会中断 OODA 循环。

    注意：OODALifecycleHook 统一定义在 interfaces/ooda_interface.py 中，
    签名为 on_phase_start(phase, context) / on_phase_end(phase, result, context)。
    """

    def __init__(self, ooda: Any, hooks: Optional[List[OODALifecycleHook]] = None):
        self._ooda = ooda
        self._hooks: List[OODALifecycleHook] = hooks or []

    def add_hook(self, hook: OODALifecycleHook) -> None:
        """添加生命周期钩子"""
        self._hooks.append(hook)

    async def _fire_on_phase_start(self, phase: str, context: Dict[str, Any]) -> None:
        """触发所有钩子的 on_phase_start，异常不中断"""
        for hook in self._hooks:
            try:
                await hook.on_phase_start(phase, context)
            except Exception as e:
                logger.warning("OODALifecycleHook on_phase_start error (phase=%s): %s", phase, e)

    async def _fire_on_phase_end(self, phase: str, result: Any, context: Dict[str, Any]) -> None:
        """触发所有钩子的 on_phase_end，异常不中断"""
        for hook in self._hooks:
            try:
                await hook.on_phase_end(phase, result, context)
            except Exception as e:
                logger.warning("OODALifecycleHook on_phase_end error (phase=%s): %s", phase, e)

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行完整的 OODA 循环（5 阶段：O-O-D-A-E），带生命周期钩子"""
        # Observe
        await self._fire_on_phase_start("observe", context)
        observe_result = await self._ooda.observe(context)
        await self._fire_on_phase_end("observe", observe_result, context)

        # Orient
        await self._fire_on_phase_start("orient", context)
        orient_result = await self._ooda.orient(observe_result)
        await self._fire_on_phase_end("orient", orient_result, context)

        # Decide
        await self._fire_on_phase_start("decide", context)
        decide_result = await self._ooda.decide(orient_result)
        await self._fire_on_phase_end("decide", decide_result, context)

        # Act
        await self._fire_on_phase_start("act", context)
        act_result = await self._ooda.act(decide_result)
        await self._fire_on_phase_end("act", act_result, context)

        # Evaluate
        if hasattr(self._ooda, 'evaluate'):
            await self._fire_on_phase_start("evaluate", context)
            evaluate_result = await self._ooda.evaluate(act_result, decide_result)
            await self._fire_on_phase_end("evaluate", evaluate_result, context)
        else:
            evaluate_result = None

        result = {
            "observe": observe_result,
            "orient": orient_result,
            "decide": decide_result,
            "act": act_result,
        }
        if evaluate_result is not None:
            result["evaluate"] = evaluate_result
        return result
