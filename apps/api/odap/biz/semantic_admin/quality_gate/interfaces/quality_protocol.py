"""Quality Gate 接口定义模块（对齐 specs/007 §4 三关质量闸）。

包含：
- QualityEvaluatorProtocol：evaluate_candidate / evaluate_batch 的 Protocol 抽象
- SubMetricDict：子指标详情 TypedDict（score/reason/rule_name/threshold）
- QualityReportDict：16 子指标完整报告结构
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Protocol, Tuple, TypedDict, runtime_checkable


# ======================================================================
# TypedDict 定义
# ======================================================================

class SubMetric(TypedDict, total=False):
    """单条子指标（G1/G2/G3 任一子项详情）。"""
    submetric: str       # 如 g1_name_valid / g2_usl_disjointness / g3_property_density
    score: float         # 0~1 连续分；布尔判定用 1.0 / 0.0
    reason: str          # 人类可读理由
    rule_name: str       # 规则名：如 semadm_g1_1_name_regex / semadm_g3_2_doc_hits
    threshold: Optional[float]  # 阈值（None=无具体阈值）
    extras: Optional[Dict[str, Any]]  # G3.5 可放 risk_tags/suggestions/checker


class QualityReport(TypedDict, total=False):
    """16 子指标完整质量报告（= usl_quality_reports 表可直接 save 的 dict）。"""
    id: Optional[str]
    candidate_id: str
    gate1_score: float          # 0~1
    gate1_details: List[SubMetric]   # 必含 7 子项
    gate2_score: float          # 0~1
    gate2_details: List[SubMetric]   # 必含 4 子项
    gate3_score: float          # 0~1
    gate3_details: List[SubMetric]   # 必含 5 子项
    total_score: float          # 0.35*g1 + 0.40*g2 + 0.25*g3
    tier: str                   # HIGH/MEDIUM/LOW/VERY_LOW
    created_at: Optional[str]


# ======================================================================
# 权重常量
# ======================================================================

# 三关外权重（§4.1）
GATE_WEIGHTS = (0.35, 0.40, 0.25)

# G3 内部 5 子项权重（§4.5）
GATE3_INNER_WEIGHTS = (0.30, 0.20, 0.15, 0.15, 0.20)

# 合法 SemanticType（与 storage 模块保持一致，§1.2 G1.3）
VALID_SEMANTIC_TYPES = {
    "对象类型", "关系类型", "属性", "动作类型", "过程类型", "规则类型",
}

# G1 子项权重（FAIL 类权重×5，WARN 类×1）—— §4.3 扣分项推导
G1_SUB_WEIGHTS = (5, 1, 5, 1, 1, 1, 1)

# §4.2 分层阈值 tier
TIER_HIGH     = "HIGH"        # >= 0.85
TIER_MEDIUM   = "MEDIUM"      # [0.70, 0.85)
TIER_LOW      = "LOW"         # [0.50, 0.70)
TIER_VERY_LOW = "VERY_LOW"    # < 0.50

# Candidate origin（spec §2.2 origin 枚举）
ORIGIN_USL    = "usl"
ORIGIN_LLM    = "llm"
ORIGIN_HYBRID = "hybrid"
ORIGIN_HUMAN  = "human"

# QualityReport dict 的必需/可选字段（运行时校验用）
QUALITY_REPORT_REQUIRED_KEYS: Tuple[str, ...] = (
    "candidate_id", "gate1_score", "gate1_details", "gate2_score", "gate2_details",
    "gate3_score", "gate3_details", "total_score", "tier",
)
QUALITY_REPORT_OPTIONAL_KEYS: Tuple[str, ...] = ("id", "created_at")


@runtime_checkable
class QualityEvaluatorProtocol(Protocol):
    """Quality Evaluator 的 Protocol 抽象（便于 Mock / 替换）。"""

    def evaluate_candidate(
        self,
        candidate: Dict[str, Any],
        *,
        usl_storage: Optional[Any] = None,
        domain_terms_hint: Optional[Iterable[str]] = None,
        disjoint_pairs_hint: Optional[Iterable[Tuple[str, str]]] = None,
    ) -> QualityReport:
        """对单条 candidate 评估，返回可直接 save 的 QualityReport（含 16 子指标）。
        :param candidate: 与 usl_schema_candidates 行字段对齐的 dict
        :param usl_storage: 若传入，G1.7 去重、G2.1 disjoint 查询可走真实 USL DB
        :param domain_terms_hint: 已知 domain 规范术语集合（用于跳过 DB 查询快速比对）
        :param disjoint_pairs_hint: 已知 (term_a,term_b) 不相交对集合
        """
        ...

    def evaluate_batch(
        self,
        candidates: Iterable[Dict[str, Any]],
        *,
        usl_storage: Optional[Any] = None,
        domain_terms_hint: Optional[Iterable[str]] = None,
        disjoint_pairs_hint: Optional[Iterable[Tuple[str, str]]] = None,
    ) -> List[QualityReport]:
        """批量评估；默认逐次调用 evaluate_candidate，可子类优化并发。"""
        ...


__all__ = [
    "SubMetric", "QualityReport",
    "GATE_WEIGHTS", "GATE3_INNER_WEIGHTS", "G1_SUB_WEIGHTS", "VALID_SEMANTIC_TYPES",
    "QualityEvaluatorProtocol",
]
