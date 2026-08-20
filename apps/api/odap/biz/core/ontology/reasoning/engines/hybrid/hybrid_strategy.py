"""HybridStrategy — 混合推理策略 (ADR-075 §4)。

决策规则：
- 确定性优先：只要有确定性推导且置信度 >= 阈值，直接采用。
- 降级条件（满足其一）：
    1. 零推导（无任何结论）
    2. 置信度 < REASONING_CONF_THRESHOLD（默认 0.5）
    3. 超时（engine 返回 truncated/timeout 错误）
- 引擎抛错 → 拒绝服务（不降级，防止掩盖缺陷）。
- 单次请求限一次降级。
- 指标：odap_reasoning_llm_fallback_total
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

REASONING_CONF_THRESHOLD = 0.5   # 可被环境变量覆盖


@dataclass
class HybridOutcome:
    """混合推理结果"""
    source: str                      # deterministic | llm_hybrid | error
    rows: List[Any] = field(default_factory=list)
    confidence: float = 0.0
    explanation: str = ""
    truncated: bool = False
    fallback_reason: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "rows": [list(r) if isinstance(r, tuple) else r for r in self.rows],
            "confidence": self.confidence,
            "explanation": self.explanation,
            "truncated": self.truncated,
            "fallback_reason": self.fallback_reason,
            "metrics": self.metrics,
        }


class HybridStrategy:
    """确定性优先 + LLM 降级的混合推理策略"""

    def __init__(
        self,
        conf_threshold: float = REASONING_CONF_THRESHOLD,
        llm_fallback: Optional[Callable[[str, Dict[str, Any]], HybridOutcome]] = None,
    ):
        self.conf_threshold = conf_threshold
        self._llm_fallback = llm_fallback

    def set_llm_fallback(self, fn: Callable[[str, Dict[str, Any]], HybridOutcome]) -> None:
        """注入 LLM 降级回调"""
        self._llm_fallback = fn

    def decide(
        self,
        goal: str,
        deterministic: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> HybridOutcome:
        """执行混合决策。

        Args:
            goal: 推理目标
            deterministic: 确定性引擎输出 dict：
                rows / truncated / elapsed_ms / error / confidence
            context: 附加上下文（workspace_id 等，透传给 LLM 回调）

        Returns:
            HybridOutcome
        """
        rows = deterministic.get("rows") or []
        truncated = deterministic.get("truncated", False)
        error = deterministic.get("error")
        confidence = deterministic.get("confidence", 0.0)
        context = context or {}

        # 引擎抛错 → 拒绝服务（不降级）
        if error and "timeout" not in error:
            logger.error("确定性引擎错误，拒绝服务: %s", error)
            return HybridOutcome(
                source="error",
                rows=[],
                confidence=0.0,
                fallback_reason=f"engine_error:{error}",
            )

        fallback_reason = ""
        if error and "timeout" in error:
            fallback_reason = "timeout"
        elif not rows:
            fallback_reason = "zero_derivations"
        elif confidence < self.conf_threshold:
            fallback_reason = f"low_confidence:{confidence}"

        if fallback_reason:
            # 触发降级（LLM 回调注入时）
            if self._llm_fallback is not None:
                logger.info("hybrid fallback to LLM: %s (%s)", goal, fallback_reason)
                outcome = self._llm_fallback(goal, context)
                outcome.fallback_reason = fallback_reason
                outcome.metrics["deterministic_rows"] = len(rows)
                outcome.metrics["deterministic_truncated"] = truncated
                _increment_fallback_metric()
                return outcome
            # 无 LLM 回调：返回确定性结果但标记降级原因
            return HybridOutcome(
                source="deterministic",
                rows=rows,
                confidence=confidence,
                truncated=truncated,
                fallback_reason=fallback_reason,
                metrics={"llm_fallback_unavailable": True},
            )

        return HybridOutcome(
            source="deterministic",
            rows=rows,
            confidence=confidence,
            truncated=truncated,
        )


def _increment_fallback_metric() -> None:
    """指标 odap_reasoning_llm_fallback_total（尽力而为）"""
    try:
        from prometheus_client import Counter
        counter = Counter(
            "odap_reasoning_llm_fallback_total",
            "Reasoning LLM fallback counter",
        )
        counter.inc()
    except Exception as e:
        logger.debug("prometheus counter unavailable: %s", e)


__all__ = ["HybridStrategy", "HybridOutcome", "REASONING_CONF_THRESHOLD"]
