"""QualityCalculator — 22 子指标质量闸计算器（版块清理 2026-08-07）。

在原有 16 子指标（QualityEvaluator 实现）基础上，新增 6 项从 006 ValidationEngine
移交的子指标，扩展为完整的 22 子指标质量闸：

  G1 × 10（句法/结构 + 完整性）：
    G1.1-G1.7 原有 7 项（委托 QualityEvaluator）
    G1.8 fill_rate        [006 移交] 属性字段填充率 ≥ 0.5（WARN -0.10）
    G1.9 empty_rate       [006 移交] 必填字段空值率 ≤ 0.3（WARN -0.08）
    G1.10 orphan_ratio    [006 移交] 孤儿实体占比 ≤ 0.3（WARN -0.05）

  G2 × 7（语义一致性 + 引用一致性）：
    G2.1-G2.4 原有 4 项（委托 QualityEvaluator）
    G2.5 dangling_relations       [006 移交] 悬空关系检查（布尔，WARN -0.15）
    G2.6 invalid_action_targets   [006 移交] 动作目标指向无效 ObjectType（布尔，WARN -0.10）
    G2.7 invalid_rule_references  [006 移交] 规则引用实体不存在（布尔，WARN -0.10）

  G3 × 5（领域质量，不变）：委托 QualityEvaluator

权重公式（data-model.md §4.1 权威定义）：
  total_score = 0.35 × gate1_score + 0.40 × gate2_score + 0.25 × gate3_score

权威来源：
  - specs/007-semantic-admin-suite/data-model.md §4
  - specs/007-semantic-admin-suite/contracts/quality-gate-approval.md
  - specs/REFACTORING-NOTES.md
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .quality_evaluator import (
    QualityEvaluator,
    _mk,
    _safe_float,
    score_to_tier,
)

logger = logging.getLogger(__name__)


# ======================================================================
# 22 子指标权重常量（版块清理新增）
# ======================================================================

# G1 × 10 子项权重（FAIL 类×5，WARN 类×1）
# G1.1/G1.3 为 FAIL 类（×5），G1.2/G1.4-G1.10 为 WARN/INFO 类（×1）
# 权威来源：data-model.md §4.3 扣分项推导
G1_SUB_WEIGHTS_22: Tuple[float, ...] = (
    5.0,  # G1.1 name_valid (FAIL -0.35)
    1.0,  # G1.2 en_mapping_valid (WARN -0.08)
    5.0,  # G1.3 semantic_type_valid (FAIL -0.15)
    1.0,  # G1.4 synonyms_size_valid (WARN)
    1.0,  # G1.5 synonyms_dedup_ratio (WARN)
    1.0,  # G1.6 circular_inclusion_free (WARN)
    1.0,  # G1.7 usl_duplicate_check (INFO)
    1.0,  # G1.8 fill_rate [006 移交] (WARN -0.10)
    1.0,  # G1.9 empty_rate [006 移交] (WARN -0.08)
    1.0,  # G1.10 orphan_ratio [006 移交] (WARN -0.05)
)

# 6 项新子指标的阈值（与 contracts/quality-gate-approval.md SubmetricThreshold 对齐）
G1_8_FILL_RATE_THRESHOLD = 0.50     # ≥ 0.5
G1_9_EMPTY_RATE_THRESHOLD = 0.30    # ≤ 0.3
G1_10_ORPHAN_RATIO_THRESHOLD = 0.30  # ≤ 0.3

# G2.8 SHACL 合规率阈值（ADR-077 §5，实例数据 SHACL 校验通过率）
G2_8_SHACL_COMPLIANCE_THRESHOLD = 0.85  # ≥ 0.85（与质量闸 HIGH 档对齐）

# 规则名前缀（与现有 quality_evaluator.py 保持一致）
_RULE_PREFIX = "semadm"


# ======================================================================
# 6 项新子指标计算函数（从 006 ValidationEngine 移交）
# ======================================================================

def _eval_g1_fill_rate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """G1.8 [006 移交]: 属性字段填充率 fill_rate ≥ 0.5。

    输入：candidate.fill_rate（float 0-1，由调用方预计算）
    评分：score = fill_rate（直接使用预计算值）
    失败动作：fill_rate < 0.5 → WARN，标记 needs_review（-0.10）

    若 candidate 无 fill_rate 字段（非 006 移交场景），默认 1.0 + INFO reason。
    """
    fill_rate = _safe_float(
        candidate.get("fill_rate"),
        default=1.0,
        clamp_01=True,
    )
    has_field = "fill_rate" in candidate
    if not has_field:
        return _mk(
            submetric="g1_fill_rate",
            score=1.0,
            reason="无 fill_rate 数据（非 006 移交场景），默认通过",
            rule_name=f"{_RULE_PREFIX}_g1_8_fill_rate",
            threshold=G1_8_FILL_RATE_THRESHOLD,
        )
    ok = fill_rate >= G1_8_FILL_RATE_THRESHOLD
    return _mk(
        submetric="g1_fill_rate",
        score=fill_rate,
        reason=(
            f"fill_rate={fill_rate:.3f} ≥ {G1_8_FILL_RATE_THRESHOLD} ✓"
            if ok
            else f"fill_rate={fill_rate:.3f} < {G1_8_FILL_RATE_THRESHOLD}，标记 needs_review（-0.10）"
        ),
        rule_name=f"{_RULE_PREFIX}_g1_8_fill_rate",
        threshold=G1_8_FILL_RATE_THRESHOLD,
    )


def _eval_g1_empty_rate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """G1.9 [006 移交]: 必填字段空值率 empty_rate ≤ 0.3。

    输入：candidate.empty_rate（float 0-1，由调用方预计算）
    评分：score = 1.0 - empty_rate（反转：空值率越低分数越高）
    失败动作：empty_rate > 0.3 → WARN，标记 needs_review（-0.08）

    若 candidate 无 empty_rate 字段，默认 0.0 + INFO reason（视为无空值）。
    """
    empty_rate = _safe_float(
        candidate.get("empty_rate"),
        default=0.0,
        clamp_01=True,
    )
    has_field = "empty_rate" in candidate
    if not has_field:
        return _mk(
            submetric="g1_empty_rate",
            score=1.0,
            reason="无 empty_rate 数据（非 006 移交场景），默认通过",
            rule_name=f"{_RULE_PREFIX}_g1_9_empty_rate",
            threshold=G1_9_EMPTY_RATE_THRESHOLD,
        )
    score = max(0.0, 1.0 - empty_rate)
    ok = empty_rate <= G1_9_EMPTY_RATE_THRESHOLD
    return _mk(
        submetric="g1_empty_rate",
        score=score,
        reason=(
            f"empty_rate={empty_rate:.3f} ≤ {G1_9_EMPTY_RATE_THRESHOLD} ✓"
            if ok
            else f"empty_rate={empty_rate:.3f} > {G1_9_EMPTY_RATE_THRESHOLD}，标记 needs_review（-0.08）"
        ),
        rule_name=f"{_RULE_PREFIX}_g1_9_empty_rate",
        threshold=G1_9_EMPTY_RATE_THRESHOLD,
    )


def _eval_g1_orphan_ratio(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """G1.10 [006 移交]: 孤儿实体占比 orphan_ratio ≤ 0.3。

    输入：candidate.orphan_ratio（float 0-1，由调用方预计算）
    评分：score = 1.0 - orphan_ratio（反转：孤儿率越低分数越高）
    失败动作：orphan_ratio > 0.3 → WARN，标记 needs_review（-0.05）

    若 candidate 无 orphan_ratio 字段，默认 0.0 + INFO reason（视为无孤儿）。
    """
    orphan_ratio = _safe_float(
        candidate.get("orphan_ratio"),
        default=0.0,
        clamp_01=True,
    )
    has_field = "orphan_ratio" in candidate
    if not has_field:
        return _mk(
            submetric="g1_orphan_ratio",
            score=1.0,
            reason="无 orphan_ratio 数据（非 006 移交场景），默认通过",
            rule_name=f"{_RULE_PREFIX}_g1_10_orphan_ratio",
            threshold=G1_10_ORPHAN_RATIO_THRESHOLD,
        )
    score = max(0.0, 1.0 - orphan_ratio)
    ok = orphan_ratio <= G1_10_ORPHAN_RATIO_THRESHOLD
    return _mk(
        submetric="g1_orphan_ratio",
        score=score,
        reason=(
            f"orphan_ratio={orphan_ratio:.3f} ≤ {G1_10_ORPHAN_RATIO_THRESHOLD} ✓"
            if ok
            else f"orphan_ratio={orphan_ratio:.3f} > {G1_10_ORPHAN_RATIO_THRESHOLD}，标记 needs_review（-0.05）"
        ),
        rule_name=f"{_RULE_PREFIX}_g1_10_orphan_ratio",
        threshold=G1_10_ORPHAN_RATIO_THRESHOLD,
    )


def _eval_g2_dangling_relations(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """G2.5 [006 移交]: 悬空关系检查 dangling_relations（布尔，WARN -0.15）。

    输入：candidate.dangling_relations（List[Dict]，由调用方预计算）
      每项形如 {"subject": str, "relation": str, "object": str}
    评分：无悬空 → 1.0；存在悬空 → 0.0
    失败动作：存在悬空边 → WARN，列出悬空边（-0.15）

    若 candidate 无 dangling_relations 字段，默认空列表 + INFO reason。
    """
    raw = candidate.get("dangling_relations")
    if raw is None:
        return _mk(
            submetric="g2_dangling_relations",
            score=1.0,
            reason="无 dangling_relations 数据（非 006 移交场景），默认通过",
            rule_name=f"{_RULE_PREFIX}_g2_5_dangling_relations",
            threshold=None,
        )
    if isinstance(raw, str):
        # JSON 字符串容错
        import json as _json
        try:
            raw = _json.loads(raw)
        except Exception:
            raw = []
    if not isinstance(raw, (list, tuple)):
        raw = []
    dangling_count = len(raw)
    ok = dangling_count == 0
    return _mk(
        submetric="g2_dangling_relations",
        score=1.0 if ok else 0.0,
        reason=(
            "无悬空关系 ✓"
            if ok
            else f"检测到 {dangling_count} 条悬空关系，列出前 3 条：{list(raw[:3])}（-0.15）"
        ),
        rule_name=f"{_RULE_PREFIX}_g2_5_dangling_relations",
        threshold=None,
    )


def _eval_g2_invalid_action_targets(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """G2.6 [006 移交]: 动作目标指向无效 ObjectType（布尔，WARN -0.10）。

    输入：candidate.invalid_action_targets（List[str]，由调用方预计算）
      每项为无效目标 ObjectType 名称
    评分：无无效目标 → 1.0；存在无效目标 → 0.0
    失败动作：存在无效目标 → WARN，列出无效目标（-0.10）

    若 candidate 无 invalid_action_targets 字段，默认空列表 + INFO reason。
    """
    raw = candidate.get("invalid_action_targets")
    if raw is None:
        return _mk(
            submetric="g2_invalid_action_targets",
            score=1.0,
            reason="无 invalid_action_targets 数据（非 006 移交场景），默认通过",
            rule_name=f"{_RULE_PREFIX}_g2_6_invalid_action_targets",
            threshold=None,
        )
    if isinstance(raw, str):
        import json as _json
        try:
            raw = _json.loads(raw)
        except Exception:
            raw = []
    if not isinstance(raw, (list, tuple)):
        raw = []
    invalid_count = len(raw)
    ok = invalid_count == 0
    return _mk(
        submetric="g2_invalid_action_targets",
        score=1.0 if ok else 0.0,
        reason=(
            "所有动作目标指向有效 ObjectType ✓"
            if ok
            else f"检测到 {invalid_count} 个无效动作目标：{list(raw[:3])}（-0.10）"
        ),
        rule_name=f"{_RULE_PREFIX}_g2_6_invalid_action_targets",
        threshold=None,
    )


def _eval_g2_invalid_rule_references(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """G2.7 [006 移交]: 规则引用实体不存在（布尔，WARN -0.10）。

    输入：candidate.invalid_rule_references（List[str]，由调用方预计算）
      每项为无效引用的实体名称
    评分：无无效引用 → 1.0；存在无效引用 → 0.0
    失败动作：存在无效引用 → WARN，列出无效引用（-0.10）

    若 candidate 无 invalid_rule_references 字段，默认空列表 + INFO reason。
    """
    raw = candidate.get("invalid_rule_references")
    if raw is None:
        return _mk(
            submetric="g2_invalid_rule_references",
            score=1.0,
            reason="无 invalid_rule_references 数据（非 006 移交场景），默认通过",
            rule_name=f"{_RULE_PREFIX}_g2_7_invalid_rule_references",
            threshold=None,
        )
    if isinstance(raw, str):
        import json as _json
        try:
            raw = _json.loads(raw)
        except Exception:
            raw = []
    if not isinstance(raw, (list, tuple)):
        raw = []
    invalid_count = len(raw)
    ok = invalid_count == 0
    return _mk(
        submetric="g2_invalid_rule_references",
        score=1.0 if ok else 0.0,
        reason=(
            "所有规则引用指向有效实体 ✓"
            if ok
            else f"检测到 {invalid_count} 个无效规则引用：{list(raw[:3])}（-0.10）"
        ),
        rule_name=f"{_RULE_PREFIX}_g2_7_invalid_rule_references",
        threshold=None,
    )


def _eval_g2_shacl_compliance(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """G2.8 [ADR-077 §5]: SHACL 合规率 shacl_compliance ≥ 0.85。

    输入：candidate.shacl_compliance（float 0-1，由 SHACL 校验器计算通过率）
    评分：score = shacl_compliance（直接使用预计算值）
    失败动作：shacl_compliance < 0.85 → WARN，标记 needs_review（-0.10）

    若 candidate 无 shacl_compliance 字段（未接入 SHACL 校验），默认 1.0 + INFO reason。
    """
    shacl_compliance = _safe_float(
        candidate.get("shacl_compliance"),
        default=1.0,
        clamp_01=True,
    )
    has_field = "shacl_compliance" in candidate
    if not has_field:
        return _mk(
            submetric="g2_shacl_compliance",
            score=1.0,
            reason="无 shacl_compliance 数据（未接入 SHACL 校验），默认通过",
            rule_name=f"{_RULE_PREFIX}_g2_8_shacl_compliance",
            threshold=G2_8_SHACL_COMPLIANCE_THRESHOLD,
        )
    ok = shacl_compliance >= G2_8_SHACL_COMPLIANCE_THRESHOLD
    return _mk(
        submetric="g2_shacl_compliance",
        score=shacl_compliance,
        reason=(
            f"shacl_compliance={shacl_compliance:.3f} ≥ {G2_8_SHACL_COMPLIANCE_THRESHOLD} ✓"
            if ok
            else f"shacl_compliance={shacl_compliance:.3f} < {G2_8_SHACL_COMPLIANCE_THRESHOLD}，标记 needs_review（-0.10）"
        ),
        rule_name=f"{_RULE_PREFIX}_g2_8_shacl_compliance",
        threshold=G2_8_SHACL_COMPLIANCE_THRESHOLD,
    )


# ======================================================================
# QualityCalculator 主类
# ======================================================================

class QualityCalculator:
    """22 子指标质量闸计算器（版块清理 2026-08-07）。

    在原有 16 子指标（QualityEvaluator）基础上，新增 6 项从 006 ValidationEngine
    移交的子指标（G1.8-G1.10 完整性 + G2.5-G2.7 引用一致性），合计 22 子指标。

    设计模式：组合优于继承。QualityCalculator 持有 QualityEvaluator 实例，
    委托其计算 16 原有子指标，再追加 6 项新子指标，最后重新聚合 gate 分数。

    权重公式（data-model.md §4.1）：
        total_score = 0.35 × gate1_score + 0.40 × gate2_score + 0.25 × gate3_score

    G1 × 10 加权（FAIL 类×5，WARN 类×1）：
        G1.1/G1.3 FAIL（×5），G1.2/G1.4-G1.10 WARN/INFO（×1）

    G2 × 7 简单平均：
        G2.1-G2.7 各 1.0 权重（硬门槛 G2.1/G2.3 命中即 0.0）

    G3 × 5 加权（不变）：
        0.30/0.20/0.15/0.15/0.20（委托 QualityEvaluator）
    """

    # 22 子指标权重（暴露便于调参覆盖，默认值来自 data-model.md）
    gate_weights: Tuple[float, float, float] = (0.35, 0.40, 0.25)
    g1_sub_weights_22: Tuple[float, ...] = G1_SUB_WEIGHTS_22

    def __init__(
        self,
        base_evaluator: Optional[QualityEvaluator] = None,
    ) -> None:
        """初始化 QualityCalculator。

        Args:
            base_evaluator: 可选的 QualityEvaluator 实例（用于计算 16 原有子指标）。
                若为 None，自动创建默认 QualityEvaluator。
        """
        self.base = base_evaluator or QualityEvaluator()

    # ------------------------------------------------------------------
    def evaluate_candidate(
        self,
        candidate: Dict[str, Any],
        *,
        usl_storage: Optional[Any] = None,
        domain_terms_hint: Optional[Iterable[str]] = None,
        disjoint_pairs_hint: Optional[Iterable[Tuple[str, str]]] = None,
    ) -> Dict[str, Any]:
        """评估单条 candidate，返回 22 子指标完整 QualityReport。

        流程：
          1. 调用 base_evaluator 获得 16 原有子指标（G1×7 + G2×4 + G3×5）
          2. 计算 6 项新子指标（G1.8-G1.10 + G2.5-G2.7）
          3. 合并 gate1_details（7→10）/ gate2_details（4→7）
          4. 重新计算 gate1_score（10 子项加权）/ gate2_score（7 子项平均）
          5. 重新计算 total_score（0.35*g1 + 0.40*g2 + 0.25*g3）+ tier

        Args:
            candidate: 与 usl_schema_candidates 行字段对齐的 dict。
                版块清理新增字段（由 006 ExtractService 预计算填入）：
                - fill_rate (float): 属性字段填充率
                - empty_rate (float): 必填字段空值率
                - orphan_ratio (float): 孤儿实体占比
                - dangling_relations (List[Dict]): 悬空关系列表
                - invalid_action_targets (List[str]): 无效动作目标列表
                - invalid_rule_references (List[str]): 无效规则引用列表
            usl_storage: 透传给 base_evaluator
            domain_terms_hint: 透传给 base_evaluator（G1.7 USL 同名检查）
            disjoint_pairs_hint: 透传给 base_evaluator（G2.1 不相交检查）

        Returns:
            QualityReport dict（含 22 子指标 + 3 关总分 + tier），可直接 save 到
            usl_quality_reports 表。
        """
        # Step 1: 委托 base_evaluator 计算 16 原有子指标
        base_report = self.base.evaluate_candidate(
            candidate,
            usl_storage=usl_storage,
            domain_terms_hint=domain_terms_hint,
            disjoint_pairs_hint=disjoint_pairs_hint,
        )

        # Step 2: 计算 6 项新子指标
        g1_8 = _eval_g1_fill_rate(candidate)
        g1_9 = _eval_g1_empty_rate(candidate)
        g1_10 = _eval_g1_orphan_ratio(candidate)
        g2_5 = _eval_g2_dangling_relations(candidate)
        g2_6 = _eval_g2_invalid_action_targets(candidate)
        g2_7 = _eval_g2_invalid_rule_references(candidate)
        g2_8 = _eval_g2_shacl_compliance(candidate)

        # Step 3: 合并 gate1_details (7→10) / gate2_details (4→8)
        gate1_details: List[Dict[str, Any]] = list(
            base_report.get("gate1_details") or []
        ) + [g1_8, g1_9, g1_10]
        gate2_details: List[Dict[str, Any]] = list(
            base_report.get("gate2_details") or []
        ) + [g2_5, g2_6, g2_7, g2_8]
        gate3_details: List[Dict[str, Any]] = list(
            base_report.get("gate3_details") or []
        )

        # Step 4: 重新计算 gate1_score（10 子项加权）/ gate2_score（7 子项平均）
        gate1_score = self._compute_gate1_score_22(gate1_details)
        gate2_score = self._compute_gate2_score_22(gate2_details)
        gate3_score = float(base_report.get("gate3_score") or 0.0)

        # Step 5: 重新计算 total_score + tier
        total_score = round(
            self.gate_weights[0] * gate1_score
            + self.gate_weights[1] * gate2_score
            + self.gate_weights[2] * gate3_score,
            6,
        )
        tier = score_to_tier(total_score)

        return {
            "candidate_id": base_report.get("candidate_id"),
            "gate1_score": round(gate1_score, 6),
            "gate1_details": gate1_details,
            "gate2_score": round(gate2_score, 6),
            "gate2_details": gate2_details,
            "gate3_score": gate3_score,
            "gate3_details": gate3_details,
            "total_score": total_score,
            "tier": tier,
            "created_at": base_report.get("created_at"),
        }

    # ------------------------------------------------------------------
    def evaluate_batch(
        self,
        candidates: Iterable[Dict[str, Any]],
        *,
        usl_storage: Optional[Any] = None,
        domain_terms_hint: Optional[Iterable[str]] = None,
        disjoint_pairs_hint: Optional[Iterable[Tuple[str, str]]] = None,
    ) -> List[Dict[str, Any]]:
        """批量评估 candidate（22 子指标）。

        默认逐次调用 evaluate_candidate，可子类优化并发。
        """
        return [
            self.evaluate_candidate(
                c,
                usl_storage=usl_storage,
                domain_terms_hint=domain_terms_hint,
                disjoint_pairs_hint=disjoint_pairs_hint,
            )
            for c in candidates
        ]

    # ------------------------------------------------------------------
    # 内部辅助：22 子指标 gate 分数计算
    # ------------------------------------------------------------------
    def _compute_gate1_score_22(
        self, gate1_details: List[Dict[str, Any]]
    ) -> float:
        """计算 G1 × 10 子项加权平均分。

        权重 G1_SUB_WEIGHTS_22 = (5,1,5,1,1,1,1,1,1,1)
        G1.1/G1.3 FAIL 类（×5），其余 WARN/INFO 类（×1）。

        若 details 不足 10 项，缺失项按 0.0 处理（保守降级）。
        """
        if not gate1_details:
            return 0.0
        # 取前 10 项（防御性：避免传入过多项导致权重错位）
        details = gate1_details[:10]
        scores = [float(d.get("score") or 0.0) for d in details]
        # 补齐到 10 项（缺失项默认 0.0）
        while len(scores) < 10:
            scores.append(0.0)
        weights = self.g1_sub_weights_22
        total_w = sum(weights)
        if total_w <= 0:
            return 0.0
        numer = sum(w * s for w, s in zip(weights, scores))
        return numer / total_w

    def _compute_gate2_score_22(
        self, gate2_details: List[Dict[str, Any]]
    ) -> float:
        """计算 G2 × 8 子项简单平均分。

        G2.1-G2.8 各 1.0 权重（硬门槛 G2.1/G2.3 命中即 0.0 → 拉低平均；
        G2.8 shacl_compliance 为 ADR-077 §5 新增）。
        """
        if not gate2_details:
            return 0.0
        details = gate2_details[:8]
        scores = [float(d.get("score") or 0.0) for d in details]
        return sum(scores) / max(1, len(scores))


# ======================================================================
# 模块级便捷函数（无需实例化类即可调用）
# ======================================================================

_calculator_singleton: Optional[QualityCalculator] = None


def evaluate_candidate_22(
    candidate: Dict[str, Any],
    *,
    usl_storage: Optional[Any] = None,
    domain_terms_hint: Optional[Iterable[str]] = None,
    disjoint_pairs_hint: Optional[Iterable[Tuple[str, str]]] = None,
) -> Dict[str, Any]:
    """模块级便捷调用：22 子指标评估单条 candidate。

    返回可直接 save 到 usl_quality_reports 的 dict。
    """
    global _calculator_singleton
    if _calculator_singleton is None:
        _calculator_singleton = QualityCalculator()
    return _calculator_singleton.evaluate_candidate(
        candidate,
        usl_storage=usl_storage,
        domain_terms_hint=domain_terms_hint,
        disjoint_pairs_hint=disjoint_pairs_hint,
    )


def evaluate_batch_22(
    candidates: Iterable[Dict[str, Any]],
    *,
    usl_storage: Optional[Any] = None,
    domain_terms_hint: Optional[Iterable[str]] = None,
    disjoint_pairs_hint: Optional[Iterable[Tuple[str, str]]] = None,
) -> List[Dict[str, Any]]:
    """模块级便捷调用：批量 22 子指标评估。"""
    global _calculator_singleton
    if _calculator_singleton is None:
        _calculator_singleton = QualityCalculator()
    return _calculator_singleton.evaluate_batch(
        candidates,
        usl_storage=usl_storage,
        domain_terms_hint=domain_terms_hint,
        disjoint_pairs_hint=disjoint_pairs_hint,
    )


__all__ = [
    "QualityCalculator",
    "evaluate_candidate_22",
    "evaluate_batch_22",
    "G1_SUB_WEIGHTS_22",
    "G1_8_FILL_RATE_THRESHOLD",
    "G1_9_EMPTY_RATE_THRESHOLD",
    "G1_10_ORPHAN_RATIO_THRESHOLD",
    "G2_8_SHACL_COMPLIANCE_THRESHOLD",
]
