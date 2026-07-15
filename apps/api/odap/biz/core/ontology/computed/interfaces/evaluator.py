"""ExpressionEvaluator 抽象接口 (T394-prep)

定义安全沙箱表达式求值器的抽象方法。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List


@dataclass
class EvaluationContext:
    """表达式求值上下文"""
    instance: Dict[str, Any] = field(default_factory=dict)
    properties: Dict[str, Any] = field(default_factory=dict)
    functions: Dict[str, Callable] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """表达式校验结果"""
    valid: bool
    error_message: str = ""
    dependencies: List[str] = field(default_factory=list)


class ExpressionEvaluator(ABC):
    """安全沙箱表达式求值器抽象基类"""

    @abstractmethod
    def evaluate(
        self, expression: str, context: EvaluationContext
    ) -> Any:
        """对单个实例求值"""
        raise NotImplementedError

    @abstractmethod
    def validate(self, expression: str) -> ValidationResult:
        """校验表达式语法 + 提取依赖"""
        raise NotImplementedError

    @abstractmethod
    def extract_dependencies(self, expression: str) -> List[str]:
        """从表达式中提取依赖属性名列表"""
        raise NotImplementedError


__all__ = ["ExpressionEvaluator", "EvaluationContext", "ValidationResult"]
