"""LLM Rationale Generator (T423)

为 Goal 生成业务合理性说明 (rationale)。采用多轮追问逻辑：
1. 第一次生成初始 rationale
2. 检查质量（是否包含关键要素、长度是否合理）
3. 如不满足则发起追问，最多 MAX_ROUNDS 轮

依赖注入 LLMClientProtocol 接口（mock 实现保证测试可重现）。
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from ..models import Goal

logger = logging.getLogger(__name__)


# 视为"足够好"的最小长度
MIN_RATIONALE_LEN = 60
MAX_ROUNDS = 3

# 关键要素关键词（rationale 中应至少包含一个）
KEY_ELEMENT_KEYWORDS = [
    "objective", "goal", "value", "impact", "metric", "success",
    "user", "stakeholder", "benefit", "risk", "objective", "objective",
]


@runtime_checkable
class LLMClientProtocol(Protocol):
    """LLM 客户端协议（最小接口）"""

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """对话式调用 LLM；messages 是 OpenAI 风格的 [{role, content}, ...]"""
        ...


class MockLLMClient:
    """用于测试的 Mock LLM 客户端

    行为：
    - 第一次返回初始 rationale（基于 goal 标题拼接）
    - 追问时返回增强版（含更多关键要素）
    - 可注入 raise_on_call 异常模拟 LLM 错误
    """

    def __init__(self, raise_on_call: Optional[Exception] = None):
        self.raise_on_call = raise_on_call
        self.call_count = 0
        self.last_messages: List[Dict[str, str]] = []

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """Mock LLM 响应"""
        if self.raise_on_call is not None:
            self.call_count += 1
            raise self.raise_on_call
        self.call_count += 1
        self.last_messages = list(messages)
        # 从 messages 中抽取 user 内容用于响应生成
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content", "")
                break
        if "follow-up" in last_user.lower() or "?" in last_user[-20:]:
            # 追问响应：返回更长 + 包含关键词
            return (
                "The rationale is reinforced: this work targets business "
                "value by aligning stakeholders around a measurable "
                "metric. The success metric is the achievement of the "
                "stated business objective, which benefits users through "
                "improved outcomes. Risks are mitigated by staged rollout."
            )
        # 初始响应：长度在 default min_length (60) 之上、含关键词，
        # 以保证 service 路径单次调用即可满足；但长度 < 80 字符，
        # 多轮测试用 min_length=80 时仍会触发追问。
        return "This addresses value, metric, objective, stakeholder and risk."


class RationaleGenerator:
    """LLM 驱动的 Rationale 生成器（多轮追问）"""

    def __init__(
        self,
        llm_client: LLMClientProtocol = None,
        max_rounds: int = MAX_ROUNDS,
        min_length: int = MIN_RATIONALE_LEN,
    ):
        self.llm_client = llm_client or MockLLMClient()
        self.max_rounds = max(1, int(max_rounds))
        self.min_length = max(20, int(min_length))

    async def generate(self, goal: Goal) -> str:
        """为给定 Goal 生成 business rationale（多轮追问）

        Args:
            goal: 目标领域对象

        Returns:
            生成的 rationale 文本
        """
        try:
            messages = self._build_initial_messages(goal)
            current = await self._safe_chat(messages)
            if current is None:
                return self._fallback(goal)

            rounds = 0
            while (
                rounds < self.max_rounds - 1
                and not self._is_satisfactory(current)
            ):
                follow_up = self._build_follow_up_question(goal, current)
                messages = messages + [
                    {"role": "assistant", "content": current},
                    {"role": "user", "content": follow_up},
                ]
                next_text = await self._safe_chat(messages)
                if next_text is None:
                    break
                current = next_text
                rounds += 1
            return current
        except Exception as exc:  # 降级：返回结构化 fallback
            logger.warning("RationaleGenerator.generate degraded: %s", exc)
            return self._fallback(goal)

    async def _safe_chat(
        self, messages: List[Dict[str, str]]
    ) -> Optional[str]:
        """调用 LLM；异常时返回 None（不抛给上层）"""
        try:
            return await self.llm_client.chat(messages)
        except Exception as exc:
            logger.warning("LLM call failed: %s", exc)
            return None

    def _build_initial_messages(self, goal: Goal) -> List[Dict[str, str]]:
        """构造初始 prompt"""
        prompt = (
            "Generate a concise business rationale for the following goal. "
            "Explain the business value, the key stakeholders, the success "
            "metric, and the main risk.\n\n"
            f"Title: {goal.title}\n"
            f"Description: {goal.description or '(none)'}\n"
            f"Business Objective: {goal.business_objective}\n"
        )
        return [
            {
                "role": "system",
                "content": (
                    "You are an OntoFlow business analyst. Produce a "
                    "rationale in 2-3 short paragraphs."
                ),
            },
            {"role": "user", "content": prompt},
        ]

    def _build_follow_up_question(
        self, goal: Goal, current: str
    ) -> str:
        """构造追问问题：要求补齐缺失要素"""
        missing = self._missing_elements(current)
        if not missing:
            return (
                "The previous answer is too short. Please expand with "
                "more concrete details (follow-up question)."
            )
        return (
            "Please follow-up and address these missing elements: "
            + ", ".join(missing)
            + "."
        )

    def _is_satisfactory(self, text: str) -> bool:
        """检查文本是否满足：长度 + 至少包含一个关键词"""
        if not text:
            return False
        if len(text.strip()) < self.min_length:
            return False
        lower = text.lower()
        return any(kw in lower for kw in KEY_ELEMENT_KEYWORDS)

    def _missing_elements(self, text: str) -> List[str]:
        """识别文本中缺失的关键要素（最多 3 个）"""
        if not text:
            return ["objective", "metric", "risk"]
        lower = text.lower()
        missing: List[str] = []
        if "metric" not in lower and "success" not in lower:
            missing.append("metric")
        if "stakeholder" not in lower and "user" not in lower:
            missing.append("stakeholder")
        if "risk" not in lower:
            missing.append("risk")
        if "benefit" not in lower and "value" not in lower:
            missing.append("benefit")
        return missing[:3]

    def _fallback(self, goal: Goal) -> str:
        """LLM 不可用时的降级输出"""
        return (
            f"Rationale (fallback) for goal '{goal.title}': "
            f"{goal.business_objective}. "
            f"Success metric: achievement of stated business objective. "
            f"Stakeholders: workspace '{goal.workspace_id}' owners. "
            f"Main risk: scope creep; mitigation by staged proposals."
        )


# 同步便捷方法（用于在同步代码中调用）
def generate_rationale_sync(
    goal: Goal, llm_client: LLMClientProtocol = None
) -> str:
    """同步包装：内部跑 asyncio.run"""
    gen = RationaleGenerator(llm_client=llm_client)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 在已有 event loop 中则退化为 fallback
            return gen._fallback(goal)
        return loop.run_until_complete(gen.generate(goal))
    except RuntimeError:
        return asyncio.run(gen.generate(goal))


__all__ = [
    "RationaleGenerator",
    "LLMClientProtocol",
    "MockLLMClient",
    "generate_rationale_sync",
]
