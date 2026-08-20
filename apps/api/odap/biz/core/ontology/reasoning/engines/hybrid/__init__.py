"""混合推理策略（ADR-075 §4）。

确定性优先：零推导 / 置信度 < 阈值 / 超时才降级 LLM；
引擎抛错拒绝服务（不降级，防止掩盖缺陷）。
"""

from .hybrid_strategy import HybridStrategy, HybridOutcome, REASONING_CONF_THRESHOLD

__all__ = ["HybridStrategy", "HybridOutcome", "REASONING_CONF_THRESHOLD"]
