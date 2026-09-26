"""LLM 降级策略统一模块

当 LLM 服务不可用时，统一返回明确的错误信息，
禁止静默降级或返回 Mock 数据。
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class LLMFallback:
    """LLM 降级策略处理器

    当 LLM 服务不可用时，返回结构化错误信息，
    而非静默降级到规则提取等降级方案。
    """

    @classmethod
    def handle_unavailable(cls, service_name: str, error: Exception) -> Dict[str, Any]:
        """处理 LLM 服务不可用的情况

        Args:
            service_name: 不可用的服务名称
            error: 原始异常对象

        Returns:
            结构化错误字典，包含状态、消息、错误类型和建议重试时间

        Note:
            `detail` 字段保留原始异常的类型与文本，用于问题排查。
            只暴露给系统内部/管理端，面向终端用户的提示仍使用 `message`。
        """
        error_type = type(error).__name__
        detail = str(error).strip() or repr(error)
        logger.error(
            f"{service_name} 服务不可用: [{error_type}] {detail}",
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"{service_name} 服务暂不可用，请稍后重试",
            "detail": f"[{error_type}] {detail}",
            "error_type": "llm_unavailable",
            "retry_after": 30,
        }

    @classmethod
    def describe(cls, service_name: str, error: Exception) -> str:
        """返回带原始原因的可诊断错误文案（用于写入流水线日志/错误字段）"""
        info = cls.handle_unavailable(service_name, error)
        return f"{info['message']}（原因：{info['detail']}）"
