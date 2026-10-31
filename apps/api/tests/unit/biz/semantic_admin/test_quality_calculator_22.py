"""Semantic Admin — 版块清理 22 子指标 QualityCalculator 单元测试。

本测试套件覆盖 2026-08-07 版块清理后新增的 QualityCalculator + 6 项 006 移交子指标：

  G1.8  fill_rate       [006 移交] 属性字段填充率 ≥ 0.5（WARN -0.10）
  G1.9  empty_rate      [006 移交] 必填字段空值率 ≤ 0.3（WARN -0.08）
  G1.10 orphan_ratio    [006 移交] 孤儿实体占比 ≤ 0.3（WARN -0.05）
  G2.5  dangling_relations      [006 移交] 悬空关系检查（布尔，WARN -0.15）
  G2.6  invalid_action_targets  [006 移交] 动作目标指向无效 ObjectType（布尔，WARN -0.10）
  G2.7  invalid_rule_references [006 移交] 规则引用实体不存在（布尔，WARN -0.10）

测试目标：
  1. 22 子指标完整产出（gate1_details 10 项 + gate2_details 7 项 + gate3_details 5 项）
  2. 6 项新子指标的边界判定（PASS / WARN 各档）
  3. 缺失/非法字段标 evaluated=False 并从 gate 均分剔除（ADR-084 F2），不再默认满分
  4. 权重公式：total_score = 0.35*g1 + 0.40*g2 + 0.25*g3
  5. tier 边界（HIGH≥0.85 / MEDIUM≥0.70 / LOW≥0.50 / VERY_LOW<0.50）
  6. G1 加权（FAIL 类×5 / WARN 类×1）对 gate1_score 的影响
  7. JSON 字符串容错（dangling_relations 传 JSON 字符串）
  8. 模块级便捷函数 evaluate_candidate_22 / evaluate_batch_22
  9. 与 base QualityEvaluator 结果的一致性（16 原有子指标不变）
"""
from __future__ import annotations

import pytest

from odap.biz.semantic_admin.quality_gate.services.quality_calculator import (
    G1_10_ORPHAN_RATIO_THRESHOLD,
    G1_8_FILL_RATE_THRESHOLD,
    G1_9_EMPTY_RATE_THRESHOLD,
    G1_SUB_WEIGHTS_22,
    QualityCalculator,
    evaluate_batch_22,
    evaluate_candidate_22,
)
from odap.biz.semantic_admin.quality_gate.services.quality_evaluator import (
    QualityEvaluator,
    score_to_tier,
)
from odap.biz.semantic_admin.quality_gate.interfaces.quality_protocol import (
    TIER_HIGH,
    TIER_LOW,
    TIER_MEDIUM,
    TIER_VERY_LOW,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CALC = QualityCalculator()
TIER_SET = {TIER_HIGH, TIER_MEDIUM, TIER_LOW, TIER_VERY_LOW}


def _base_cand(**overrides):
    """构建合法 base candidate（与 quality_evaluator 期望对齐）。

    默认通过所有 16 原有子指标，便于聚焦测试 6 项新子指标。
    """
    base = {
        "id": "cand-22-001",
        "canonical": "库存周转率",
        "en": "InventoryTurnover",
        "semantic_type": "对象类型",  # 修正：必须是 6 枚举之一（base 用了"指标类型"会 G1.3 失败）
        "synonyms": ["库存周转天数", "存货周转"],
        "confidence": 0.78,
        "usl_align_confidence": 0.11,
        "domain_id": "domain-fin",
        "provenance": {"doc_hits": 12, "hit_count": 12, "l3_children_est": 2},
    }
    base.update(overrides)
    return base


def _sub_by_name(details, name: str):
    """从 details 列表中按 submetric 名查找单条子指标。"""
    matches = [d for d in details if d.get("submetric") == name]
    assert matches, f"未找到子指标 {name}"
    assert len(matches) == 1, f"子指标 {name} 出现多次: {len(matches)}"
    return matches[0]


def _evaluate_safely(cand, **kwargs):
    """包装：不抛异常时返回 (True, report)，抛异常返回 (False, error_str)。"""
    try:
        rep = CALC.evaluate_candidate(cand, **kwargs)
    except Exception as e:  # noqa: BLE001
        return False, str(e)
    return True, rep


# ======================================================================
# 组 1：22 子指标完整结构验证
# ======================================================================


class TestSubmetricCount:
    """验证 22 子指标完整产出。"""

    def test_gate1_has_10_submetrics(self):
        rep = CALC.evaluate_candidate(_base_cand())
        assert len(rep["gate1_details"]) == 10, (
            f"G1 应有 10 项子指标，实际 {len(rep['gate1_details'])}: "
            f"{[d['submetric'] for d in rep['gate1_details']]}"
        )

    def test_gate2_has_8_submetrics(self):
        rep = CALC.evaluate_candidate(_base_cand())
        assert len(rep["gate2_details"]) == 8, (
            f"G2 应有 8 项子指标（含 G2.8 shacl_compliance），实际 {len(rep['gate2_details'])}: "
            f"{[d['submetric'] for d in rep['gate2_details']]}"
        )

    def test_gate3_has_5_submetrics(self):
        rep = CALC.evaluate_candidate(_base_cand())
        assert len(rep["gate3_details"]) == 5

    def test_total_23_submetrics(self):
        rep = CALC.evaluate_candidate(_base_cand())
        total = (
            len(rep["gate1_details"])
            + len(rep["gate2_details"])
            + len(rep["gate3_details"])
        )
        assert total == 23, f"应有 23 项子指标，实际 {total}"

    def test_all_required_submetric_names_present(self):
        rep = CALC.evaluate_candidate(_base_cand())
        expected_names = {
            # G1 × 10
            "g1_name_valid", "g1_en_mapping_valid", "g1_semantic_type_valid",
            "g1_synonyms_size_valid", "g1_synonyms_dedup_ratio",
            "g1_circular_inclusion_free", "g1_usl_duplicate_check",
            "g1_fill_rate", "g1_empty_rate", "g1_orphan_ratio",
            # G2 × 8
            "g2_usl_disjointness", "g2_cardinality_constraint",
            "g2_isa_acyclic", "g2_llm_semantic_judge",
            "g2_dangling_relations", "g2_invalid_action_targets",
            "g2_invalid_rule_references", "g2_shacl_compliance",
            # G3 × 5
            "g3_property_density", "g3_term_frequency_coverage",
            "g3_synonym_richness", "g3_usl_alignment_novelty",
            "g3_hierarchy_contribution",
        }
        actual_names = {
            d["submetric"]
            for d in rep["gate1_details"] + rep["gate2_details"] + rep["gate3_details"]
        }
        missing = expected_names - actual_names
        assert not missing, f"缺失子指标: {missing}"


# ======================================================================
# 组 2：G1.8 fill_rate 边界
# ======================================================================


class TestG18FillRate:
    def test_fill_rate_pass_at_threshold(self):
        cand = _base_cand(fill_rate=G1_8_FILL_RATE_THRESHOLD)
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate1_details"], "g1_fill_rate")
        assert sub["score"] == G1_8_FILL_RATE_THRESHOLD
        assert "✓" in sub["reason"]
        assert sub["rule_name"] == "semadm_g1_8_fill_rate"

    def test_fill_rate_pass_above_threshold(self):
        cand = _base_cand(fill_rate=0.85)
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate1_details"], "g1_fill_rate")
        assert sub["score"] == 0.85
        assert "✓" in sub["reason"]

    def test_fill_rate_warn_below_threshold(self):
        cand = _base_cand(fill_rate=0.30)
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate1_details"], "g1_fill_rate")
        assert sub["score"] == 0.30
        assert "needs_review" in sub["reason"]
        assert "-0.10" in sub["reason"]

    def test_fill_rate_zero(self):
        cand = _base_cand(fill_rate=0.0)
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate1_details"], "g1_fill_rate")
        assert sub["score"] == 0.0

    def test_fill_rate_clamped_to_01(self):
        """fill_rate=2.0 应被 clamp 到 1.0。"""
        cand = _base_cand(fill_rate=2.0)
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate1_details"], "g1_fill_rate")
        assert sub["score"] == 1.0

    def test_fill_rate_non_numeric_string_marked_not_evaluated(self):
        """fill_rate='abc' 不应 crash；无法解析 → evaluated=False + score 0.0。"""
        cand = _base_cand(fill_rate="abc")
        ok, rep = _evaluate_safely(cand)
        assert ok, f"fill_rate='abc' 不应 crash: {rep}"
        sub = _sub_by_name(rep["gate1_details"], "g1_fill_rate")
        assert sub["score"] == 0.0
        assert sub["evaluated"] is False

    def test_fill_rate_absent_marked_not_evaluated(self):
        """candidate 不含 fill_rate → evaluated=False，不得默认满分（ADR-084 F2）。"""
        cand = _base_cand()
        assert "fill_rate" not in cand
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate1_details"], "g1_fill_rate")
        assert sub["score"] == 0.0
        assert sub["evaluated"] is False
        assert "[未评估]" in sub["reason"]


# ======================================================================
# 组 3：G1.9 empty_rate 边界
# ======================================================================


class TestG19EmptyRate:
    def test_empty_rate_pass_at_threshold(self):
        """empty_rate=0.3 ≤ 阈值 → 通过；score=1.0-0.3=0.7。"""
        cand = _base_cand(empty_rate=G1_9_EMPTY_RATE_THRESHOLD)
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate1_details"], "g1_empty_rate")
        assert sub["score"] == pytest.approx(1.0 - 0.3)
        assert "✓" in sub["reason"]

    def test_empty_rate_pass_zero(self):
        cand = _base_cand(empty_rate=0.0)
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate1_details"], "g1_empty_rate")
        assert sub["score"] == 1.0
        assert "✓" in sub["reason"]

    def test_empty_rate_warn_above_threshold(self):
        cand = _base_cand(empty_rate=0.50)
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate1_details"], "g1_empty_rate")
        assert sub["score"] == 0.50  # 1.0 - 0.50
        assert "needs_review" in sub["reason"]
        assert "-0.08" in sub["reason"]

    def test_empty_rate_full_bad(self):
        """empty_rate=1.0 → score=0.0，触发 WARN。"""
        cand = _base_cand(empty_rate=1.0)
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate1_details"], "g1_empty_rate")
        assert sub["score"] == 0.0
        assert "needs_review" in sub["reason"]

    def test_empty_rate_clamped(self):
        """empty_rate=1.5 → clamp 到 1.0，score=0.0。"""
        cand = _base_cand(empty_rate=1.5)
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate1_details"], "g1_empty_rate")
        assert sub["score"] == 0.0

    def test_empty_rate_absent_marked_not_evaluated(self):
        cand = _base_cand()
        assert "empty_rate" not in cand
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate1_details"], "g1_empty_rate")
        assert sub["score"] == 0.0
        assert sub["evaluated"] is False
        assert "[未评估]" in sub["reason"]


# ======================================================================
# 组 4：G1.10 orphan_ratio 边界
# ======================================================================


class TestG110OrphanRatio:
    def test_orphan_ratio_pass_at_threshold(self):
        cand = _base_cand(orphan_ratio=G1_10_ORPHAN_RATIO_THRESHOLD)
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate1_details"], "g1_orphan_ratio")
        assert sub["score"] == pytest.approx(1.0 - 0.3)
        assert "✓" in sub["reason"]

    def test_orphan_ratio_pass_zero(self):
        cand = _base_cand(orphan_ratio=0.0)
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate1_details"], "g1_orphan_ratio")
        assert sub["score"] == 1.0
        assert "✓" in sub["reason"]

    def test_orphan_ratio_warn_above_threshold(self):
        cand = _base_cand(orphan_ratio=0.60)
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate1_details"], "g1_orphan_ratio")
        assert sub["score"] == 0.40  # 1.0 - 0.60
        assert "needs_review" in sub["reason"]
        assert "-0.05" in sub["reason"]

    def test_orphan_ratio_full_bad(self):
        cand = _base_cand(orphan_ratio=1.0)
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate1_details"], "g1_orphan_ratio")
        assert sub["score"] == 0.0

    def test_orphan_ratio_absent_marked_not_evaluated(self):
        cand = _base_cand()
        assert "orphan_ratio" not in cand
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate1_details"], "g1_orphan_ratio")
        assert sub["score"] == 0.0
        assert sub["evaluated"] is False
        assert "[未评估]" in sub["reason"]


# ======================================================================
# 组 5：G2.5 dangling_relations 布尔检查
# ======================================================================


class TestG25DanglingRelations:
    def test_no_dangling_pass(self):
        cand = _base_cand(dangling_relations=[])
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate2_details"], "g2_dangling_relations")
        assert sub["score"] == 1.0
        assert "✓" in sub["reason"]

    def test_has_dangling_warn(self):
        cand = _base_cand(
            dangling_relations=[
                {"subject": "刘备", "relation": "击败", "object": "曹操"},
                {"subject": "关羽", "relation": "守", "object": "荆州"},
            ]
        )
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate2_details"], "g2_dangling_relations")
        assert sub["score"] == 0.0
        assert "2 条悬空关系" in sub["reason"]
        assert "-0.15" in sub["reason"]

    def test_dangling_as_json_string(self):
        """dangling_relations 传 JSON 字符串应能解析。"""
        import json
        cand = _base_cand(
            dangling_relations=json.dumps(
                [{"subject": "X", "relation": "r", "object": "Y"}]
            )
        )
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate2_details"], "g2_dangling_relations")
        assert sub["score"] == 0.0
        assert "1 条悬空关系" in sub["reason"]

    def test_dangling_invalid_json_string_marked_not_evaluated(self):
        """非法 JSON 字符串无法解析 → evaluated=False（不得当成"无悬空"）。"""
        cand = _base_cand(dangling_relations="not-json")
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate2_details"], "g2_dangling_relations")
        assert sub["score"] == 0.0
        assert sub["evaluated"] is False

    def test_dangling_invalid_type_marked_not_evaluated(self):
        """dangling_relations=123 不是列表 → evaluated=False，不得当成"无悬空"。"""
        cand = _base_cand(dangling_relations=123)
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate2_details"], "g2_dangling_relations")
        assert sub["score"] == 0.0
        assert sub["evaluated"] is False

    def test_dangling_absent_marked_not_evaluated(self):
        cand = _base_cand()
        assert "dangling_relations" not in cand
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate2_details"], "g2_dangling_relations")
        assert sub["score"] == 0.0
        assert sub["evaluated"] is False
        assert "[未评估]" in sub["reason"]


# ======================================================================
# 组 6：G2.6 invalid_action_targets 布尔检查
# ======================================================================


class TestG26InvalidActionTargets:
    def test_no_invalid_pass(self):
        cand = _base_cand(invalid_action_targets=[])
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate2_details"], "g2_invalid_action_targets")
        assert sub["score"] == 1.0
        assert "✓" in sub["reason"]

    def test_has_invalid_warn(self):
        cand = _base_cand(invalid_action_targets=["UnknownType1", "UnknownType2"])
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate2_details"], "g2_invalid_action_targets")
        assert sub["score"] == 0.0
        assert "2 个无效动作目标" in sub["reason"]
        assert "-0.10" in sub["reason"]

    def test_invalid_action_targets_as_json_string(self):
        import json
        cand = _base_cand(
            invalid_action_targets=json.dumps(["BadTarget"])
        )
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate2_details"], "g2_invalid_action_targets")
        assert sub["score"] == 0.0
        assert "1 个无效动作目标" in sub["reason"]

    def test_invalid_action_targets_absent_marked_not_evaluated(self):
        cand = _base_cand()
        assert "invalid_action_targets" not in cand
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate2_details"], "g2_invalid_action_targets")
        assert sub["score"] == 0.0
        assert sub["evaluated"] is False
        assert "[未评估]" in sub["reason"]


# ======================================================================
# 组 7：G2.7 invalid_rule_references 布尔检查
# ======================================================================


class TestG27InvalidRuleReferences:
    def test_no_invalid_pass(self):
        cand = _base_cand(invalid_rule_references=[])
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate2_details"], "g2_invalid_rule_references")
        assert sub["score"] == 1.0
        assert "✓" in sub["reason"]

    def test_has_invalid_warn(self):
        cand = _base_cand(invalid_rule_references=["GhostEntity1"])
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate2_details"], "g2_invalid_rule_references")
        assert sub["score"] == 0.0
        assert "1 个无效规则引用" in sub["reason"]
        assert "-0.10" in sub["reason"]

    def test_invalid_rule_references_as_json_string(self):
        import json
        cand = _base_cand(
            invalid_rule_references=json.dumps(["GhostA", "GhostB", "GhostC"])
        )
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate2_details"], "g2_invalid_rule_references")
        assert sub["score"] == 0.0
        assert "3 个无效规则引用" in sub["reason"]

    def test_invalid_rule_references_absent_marked_not_evaluated(self):
        cand = _base_cand()
        assert "invalid_rule_references" not in cand
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate2_details"], "g2_invalid_rule_references")
        assert sub["score"] == 0.0
        assert sub["evaluated"] is False
        assert "[未评估]" in sub["reason"]


# ======================================================================
# 组 8：权重公式与 tier 边界
# ======================================================================


class TestWeightAndTier:
    def test_weight_constants_match_data_model(self):
        """权重常量与 data-model.md §4.1 权威定义对齐。"""
        assert CALC.gate_weights == (0.35, 0.40, 0.25)
        assert G1_SUB_WEIGHTS_22 == (5.0, 1.0, 5.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
        assert len(G1_SUB_WEIGHTS_22) == 10

    def test_total_score_formula(self):
        """total_score = 0.35*g1 + 0.40*g2 + 0.25*g3（精度 6 位）。"""
        rep = CALC.evaluate_candidate(_base_cand())
        expected = round(
            0.35 * rep["gate1_score"]
            + 0.40 * rep["gate2_score"]
            + 0.25 * rep["gate3_score"],
            6,
        )
        assert rep["total_score"] == expected

    def test_total_score_within_0_1(self):
        rep = CALC.evaluate_candidate(_base_cand())
        assert 0.0 <= rep["total_score"] <= 1.0

    def test_tier_in_legal_set(self):
        rep = CALC.evaluate_candidate(_base_cand())
        assert rep["tier"] in TIER_SET

    def test_tier_consistent_with_score(self):
        """tier 与 total_score 必须满足阈值映射。"""
        rep = CALC.evaluate_candidate(_base_cand())
        s = rep["total_score"]
        expected_tier = score_to_tier(s)
        assert rep["tier"] == expected_tier

    def test_worst_candidate_gets_very_low_tier(self):
        """全失败 candidate → tier=VERY_LOW。"""
        bad = _base_cand(
            canonical="!!@#$",  # G1.1 失败
            en="",
            semantic_type="invalid_type",  # G1.3 失败
            synonyms=[f"x_{i}" for i in range(50)],  # G1.4 失败
            fill_rate=0.0,  # G1.8 失败
            empty_rate=1.0,  # G1.9 失败
            orphan_ratio=1.0,  # G1.10 失败
            dangling_relations=[{"s": "a", "r": "b", "o": "c"}],  # G2.5 失败
            invalid_action_targets=["BadTarget"],  # G2.6 失败
            invalid_rule_references=["Ghost"],  # G2.7 失败
            confidence=0.0,
            provenance={"doc_hits": 0, "hit_count": 0, "l3_children_est": 0},
        )
        ok, rep = _evaluate_safely(bad)
        assert ok
        assert rep["tier"] == TIER_VERY_LOW
        assert rep["total_score"] < 0.50


# ======================================================================
# 组 9：与 base QualityEvaluator 一致性（16 原有子指标不变）
# ======================================================================


class TestBaseEvaluatorConsistency:
    """QualityCalculator 委托 QualityEvaluator 计算 16 原有子指标，
    确保迁移后行为不回归。"""

    def test_base_evaluator_16_submetrics_unchanged(self):
        """同一 candidate，QualityCalculator 的 16 原有子指标应与
        QualityEvaluator 直接计算结果完全一致。"""
        cand = _base_cand(fill_rate=0.7, empty_rate=0.1, orphan_ratio=0.05)
        base_rep = QualityEvaluator().evaluate_candidate(cand)
        calc_rep = CALC.evaluate_candidate(cand)

        # G1 前 7 项一致
        for i in range(7):
            b = base_rep["gate1_details"][i]
            c = calc_rep["gate1_details"][i]
            assert b["submetric"] == c["submetric"]
            assert b["score"] == c["score"], (
                f"G1.{i+1} {b['submetric']} 分数不一致: "
                f"base={b['score']} calc={c['score']}"
            )

        # G2 前 4 项一致
        for i in range(4):
            b = base_rep["gate2_details"][i]
            c = calc_rep["gate2_details"][i]
            assert b["submetric"] == c["submetric"]
            assert b["score"] == c["score"]

        # G3 全 5 项一致
        assert len(base_rep["gate3_details"]) == len(calc_rep["gate3_details"]) == 5
        for i in range(5):
            b = base_rep["gate3_details"][i]
            c = calc_rep["gate3_details"][i]
            assert b["submetric"] == c["submetric"]
            assert b["score"] == c["score"]

        # gate3_score 必须一致（未重新计算）
        assert calc_rep["gate3_score"] == base_rep["gate3_score"]

    def test_gate1_score_recomputed_with_10_submetrics(self):
        """QualityCalculator 的 gate1_score 应基于 10 子项加权重新计算，
        与 base 的 7 子项 gate1_score 不同。"""
        cand = _base_cand(fill_rate=0.4, empty_rate=0.5, orphan_ratio=0.6)
        base_rep = QualityEvaluator().evaluate_candidate(cand)
        calc_rep = CALC.evaluate_candidate(cand)

        # 6 项新子指标至少有 1 项失败 → 加权后 gate1_score 应低于 base
        # （新子项拉低平均）
        assert calc_rep["gate1_score"] != base_rep["gate1_score"]

    def test_gate2_score_recomputed_with_7_submetrics(self):
        """QualityCalculator 的 gate2_score 应基于 7 子项平均重新计算。"""
        cand = _base_cand(dangling_relations=[{"s": "a", "r": "b", "o": "c"}])
        base_rep = QualityEvaluator().evaluate_candidate(cand)
        calc_rep = CALC.evaluate_candidate(cand)

        # G2.5 失败（score=0.0）→ 7 项平均低于 4 项平均
        assert calc_rep["gate2_score"] < base_rep["gate2_score"]


# ======================================================================
# 组 10：模块级便捷函数
# ======================================================================


class TestModuleLevelFunctions:
    def test_evaluate_candidate_22_returns_same_structure(self):
        cand = _base_cand(fill_rate=0.7, empty_rate=0.1)
        rep = evaluate_candidate_22(cand)
        assert "gate1_details" in rep
        assert len(rep["gate1_details"]) == 10
        assert len(rep["gate2_details"]) == 8
        assert rep["tier"] in TIER_SET

    def test_evaluate_batch_22_processes_multiple(self):
        cands = [
            _base_cand(id="c1", fill_rate=0.8),
            _base_cand(id="c2", fill_rate=0.4),  # G1.8 失败
            _base_cand(id="c3", fill_rate=0.7, dangling_relations=[]),
        ]
        reps = evaluate_batch_22(cands)
        assert len(reps) == 3
        assert reps[0]["candidate_id"] == "c1"
        assert reps[1]["candidate_id"] == "c2"
        assert reps[2]["candidate_id"] == "c3"
        # c2 的 G1.8 应失败
        c2_g18 = _sub_by_name(reps[1]["gate1_details"], "g1_fill_rate")
        assert c2_g18["score"] == 0.4

    def test_evaluate_batch_22_empty_input(self):
        reps = evaluate_batch_22([])
        assert reps == []

    def test_calculator_accepts_custom_base_evaluator(self):
        """QualityCalculator 接受自定义 base_evaluator 注入。"""
        custom_base = QualityEvaluator()
        calc = QualityCalculator(base_evaluator=custom_base)
        assert calc.base is custom_base
        rep = calc.evaluate_candidate(_base_cand())
        assert len(rep["gate1_details"]) == 10


# ======================================================================
# 组 11：内部 _compute_gate*_score_22 方法
# ======================================================================


class TestInternalScoreComputation:
    def test_compute_gate1_score_all_pass(self):
        """10 子项全部 1.0 → gate1_score=1.0。"""
        details = [
            {"submetric": f"g1_{i}", "score": 1.0} for i in range(10)
        ]
        s = CALC._compute_gate1_score_22(details)
        assert s == pytest.approx(1.0)

    def test_compute_gate1_score_all_fail(self):
        """10 子项全部 0.0 → gate1_score=0.0。"""
        details = [
            {"submetric": f"g1_{i}", "score": 0.0} for i in range(10)
        ]
        s = CALC._compute_gate1_score_22(details)
        assert s == 0.0

    def test_compute_gate1_score_weighted_by_fail_class(self):
        """G1.1（权重×5）失败 → 总分远低于其他项失败。"""
        # G1.1 失败（权重 5.0），其他全通过（权重 1.0）
        details_g11_fail = [
            {"submetric": "g1_1", "score": 0.0},  # ×5
        ] + [{"submetric": f"g1_{i}", "score": 1.0} for i in range(2, 11)]
        s_g11_fail = CALC._compute_gate1_score_22(details_g11_fail)

        # G1.8（权重×1）失败，其他全通过
        details_g18_fail = [
            {"submetric": "g1_1", "score": 1.0},
            {"submetric": "g1_2", "score": 1.0},
            {"submetric": "g1_3", "score": 1.0},
            {"submetric": "g1_4", "score": 1.0},
            {"submetric": "g1_5", "score": 1.0},
            {"submetric": "g1_6", "score": 1.0},
            {"submetric": "g1_7", "score": 1.0},
            {"submetric": "g1_8", "score": 0.0},  # ×1（新子项）
            {"submetric": "g1_9", "score": 1.0},
            {"submetric": "g1_10", "score": 1.0},
        ]
        s_g18_fail = CALC._compute_gate1_score_22(details_g18_fail)

        # G1.1 失败影响更大
        assert s_g11_fail < s_g18_fail

    def test_compute_gate1_score_short_details_ignores_missing(self):
        """传入 <10 项时，缺失项视为"未评估"而不参与分母（不按 0 分惩罚）。"""
        details = [{"submetric": "g1_1", "score": 1.0}]
        s = CALC._compute_gate1_score_22(details)
        # 只有 G1.1 已评估（权重 5.0，得分 1.0）→ 5/5 = 1.0
        assert s == pytest.approx(1.0)

    def test_compute_gate2_score_average(self):
        """G2 × 7 子项简单平均。"""
        details = [
            {"submetric": f"g2_{i}", "score": 1.0} for i in range(7)
        ]
        assert CALC._compute_gate2_score_22(details) == pytest.approx(1.0)

        details = [
            {"submetric": f"g2_{i}", "score": 0.0} for i in range(7)
        ]
        assert CALC._compute_gate2_score_22(details) == 0.0

        # 3 项失败（0.0）+ 4 项通过（1.0）→ 4/7
        details = [
            {"submetric": "g2_1", "score": 0.0},
            {"submetric": "g2_2", "score": 0.0},
            {"submetric": "g2_3", "score": 0.0},
            {"submetric": "g2_4", "score": 1.0},
            {"submetric": "g2_5", "score": 1.0},
            {"submetric": "g2_6", "score": 1.0},
            {"submetric": "g2_7", "score": 1.0},
        ]
        assert CALC._compute_gate2_score_22(details) == pytest.approx(4.0 / 7.0)

    def test_compute_gate_score_empty_details(self):
        """空 details 返回 0.0。"""
        assert CALC._compute_gate1_score_22([]) == 0.0
        assert CALC._compute_gate2_score_22([]) == 0.0


# ======================================================================
# 组 12：边界场景（XSS / 大量数据 / 类型容错）
# ======================================================================


class TestEdgeCases:
    def test_xss_payload_in_canonical_does_not_crash(self):
        cand = _base_cand(canonical="<script>alert('XSS')</script>")
        ok, rep = _evaluate_safely(cand)
        assert ok
        g11 = _sub_by_name(rep["gate1_details"], "g1_name_valid")
        assert g11["score"] == 0.0  # XSS 被正则拒
        assert rep["tier"] in TIER_SET

    def test_all_six_new_fields_simultaneously_fail(self):
        """6 项新子指标同时失败时不应 crash，且 tier 应正确降级。"""
        cand = _base_cand(
            fill_rate=0.1,
            empty_rate=0.9,
            orphan_ratio=0.8,
            dangling_relations=[{"s": "a", "r": "b", "o": "c"}] * 5,
            invalid_action_targets=["Bad1", "Bad2"],
            invalid_rule_references=["Ghost1"],
        )
        ok, rep = _evaluate_safely(cand)
        assert ok
        # G1.8/1.9/1.10 应都触发 WARN
        for name in ("g1_fill_rate", "g1_empty_rate", "g1_orphan_ratio"):
            sub = _sub_by_name(rep["gate1_details"], name)
            assert "needs_review" in sub["reason"], (
                f"{name} 应触发 WARN: {sub['reason']}"
            )
        # G2.5/2.6/2.7 应都为 0.0
        for name in (
            "g2_dangling_relations",
            "g2_invalid_action_targets",
            "g2_invalid_rule_references",
        ):
            sub = _sub_by_name(rep["gate2_details"], name)
            assert sub["score"] == 0.0
        assert rep["tier"] in TIER_SET

    def test_very_large_dangling_list_truncated_in_reason(self):
        """大量悬空关系时，reason 应只列前 3 条（避免日志爆炸）。"""
        huge = [
            {"subject": f"s{i}", "relation": "r", "object": f"o{i}"}
            for i in range(1000)
        ]
        cand = _base_cand(dangling_relations=huge)
        ok, rep = _evaluate_safely(cand)
        assert ok
        sub = _sub_by_name(rep["gate2_details"], "g2_dangling_relations")
        assert sub["score"] == 0.0
        assert "1000 条悬空关系" in sub["reason"]
        # reason 中不应包含全部 1000 条（应只列前 3 条）
        assert "o999" not in sub["reason"]

    def test_none_value_for_list_fields_no_crash(self):
        """list 字段传 None 应不 crash，且标记 evaluated=False（不得当成"无问题"）。"""
        cand = _base_cand(
            dangling_relations=None,
            invalid_action_targets=None,
            invalid_rule_references=None,
        )
        ok, rep = _evaluate_safely(cand)
        assert ok, f"None 值不应 crash: {rep}"
        for name in (
            "g2_dangling_relations",
            "g2_invalid_action_targets",
            "g2_invalid_rule_references",
        ):
            sub = _sub_by_name(rep["gate2_details"], name)
            assert sub["score"] == 0.0
            assert sub["evaluated"] is False
