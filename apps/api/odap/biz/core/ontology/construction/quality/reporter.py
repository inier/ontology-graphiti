"""QualityReporter — 质量报告生成器。

将 GateResult 转换为人类可读的质量报告。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .gate import GateResult, GateAction


@dataclass
class QualityReport:
    """构建质量报告"""
    pipeline_run_id: str = ""
    timestamp: str = ""
    overall_score: float = 0.0
    overall_grade: str = "F"
    total_checks: int = 0
    passed_checks: int = 0
    blocked: bool = False
    pre_result: Optional[Dict[str, Any]] = None
    inline_results: List[Dict[str, Any]] = field(default_factory=list)
    post_result: Optional[Dict[str, Any]] = None
    recommendations: List[str] = field(default_factory=list)

    @classmethod
    def from_gate_results(
        cls,
        pipeline_run_id: str,
        pre: Optional[GateResult],
        inline_results: List[GateResult],
        post: Optional[GateResult],
    ) -> "QualityReport":
        all_results = []
        if pre:
            all_results.append(pre)
        all_results.extend(inline_results)
        if post:
            all_results.append(post)

        total = sum(len(r.checks) for r in all_results)
        passed = sum(sum(1 for c in r.checks if c.passed) for r in all_results)
        scores = [c.score for r in all_results for c in r.checks]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        grade = "A" if avg_score >= 0.9 else "B" if avg_score >= 0.7 else "C" if avg_score >= 0.5 else "D" if avg_score >= 0.3 else "F"

        blocked = any(r.blocked for r in all_results)

        # Generate recommendations
        recs = []
        for r in all_results:
            for c in r.checks:
                if c.action == GateAction.BLOCK and not c.passed:
                    recs.append(f"[阻断] {c.rule_name}: {c.message}")
                elif c.action == GateAction.WARN and not c.passed:
                    recs.append(f"[告警] {c.rule_name}: {c.message}")

        return cls(
            pipeline_run_id=pipeline_run_id,
            timestamp="",
            overall_score=avg_score,
            overall_grade=grade,
            total_checks=total,
            passed_checks=passed,
            blocked=blocked,
            pre_result=pre.__dict__ if pre else None,
            inline_results=[r.__dict__ for r in inline_results],
            post_result=post.__dict__ if post else None,
            recommendations=recs,
        )

    def to_dict(self) -> dict:
        return {
            "pipeline_run_id": self.pipeline_run_id,
            "timestamp": self.timestamp,
            "overall_score": round(self.overall_score, 2),
            "overall_grade": self.overall_grade,
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "blocked": self.blocked,
            "pre_result": self.pre_result,
            "inline_results": self.inline_results,
            "post_result": self.post_result,
            "recommendations": self.recommendations,
        }


__all__ = ["QualityReport"]
