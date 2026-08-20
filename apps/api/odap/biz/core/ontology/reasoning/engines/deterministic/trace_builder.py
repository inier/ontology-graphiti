"""TraceBuilder — 推导过程 → rule_trace 结构化输出 (ADR-075 §2)。

将 DatalogEngine 查询结果与规则执行统计包装为
结构化推理轨迹（rule_trace），供前端推理路径解释面板消费。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .datalog_engine import ReasoningResult


@dataclass
class RuleTrace:
    """单次推理的轨迹记录"""
    goal: str
    rule_id: str
    rule_text: str
    matched_rows: int
    elapsed_ms: float
    truncated: bool
    fired_at: str = ""
    bindings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "rule_id": self.rule_id,
            "rule_text": self.rule_text,
            "matched_rows": self.matched_rows,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "truncated": self.truncated,
            "fired_at": self.fired_at,
            "bindings": self.bindings,
        }


class TraceBuilder:
    """构建推理轨迹（可挂接指标/审计）"""

    def __init__(self):
        self._traces: List[RuleTrace] = []

    def build(
        self,
        result: ReasoningResult,
        rule_id: str = "",
        rule_text: str = "",
        bindings: Optional[Dict[str, Any]] = None,
    ) -> RuleTrace:
        """由 ReasoningResult 构建单条轨迹"""
        trace = RuleTrace(
            goal=result.goal,
            rule_id=rule_id,
            rule_text=rule_text,
            matched_rows=len(result.rows),
            elapsed_ms=result.elapsed_ms,
            truncated=result.truncated,
            fired_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            bindings=bindings or {},
        )
        self._traces.append(trace)
        return trace

    def build_from_rows(
        self,
        goal: str,
        rows: List[tuple],
        rule_id: str = "",
        rule_text: str = "",
        elapsed_ms: float = 0.0,
        truncated: bool = False,
        bindings: Optional[Dict[str, Any]] = None,
    ) -> RuleTrace:
        """由查询结果直接构建轨迹（无需 ReasoningResult）"""
        result = ReasoningResult(
            goal=goal,
            rows=rows,
            truncated=truncated,
            elapsed_ms=elapsed_ms,
        )
        return self.build(result, rule_id, rule_text, bindings)

    def clear(self) -> None:
        self._traces.clear()

    def all_traces(self) -> List[Dict[str, Any]]:
        """返回全部轨迹（dict 列表）"""
        return [t.to_dict() for t in self._traces]


__all__ = ["RuleTrace", "TraceBuilder"]
