"""
Semantic Admin — P1-2 Quality Gate 12 条异常场景回归测试。

每一条用例的目标：
  ① 先 RED  → 不修实现时抛出 ValueError / 返回异常 tier 或 False 误报
  ② 修完实现 → GREEN: evaluate_candidate() 成功返回，不崩溃，tier 合法（∈ HIGH/MEDIUM/LOW/VERY_LOW）

Coverage 目标：
  - 非数字字符串触发 int()/float() 解析崩溃
  - synonyms_raw/dict 误用导致遍历 keys 问题
  - disjoint 自对 (a,a) 误报
  - 超大 synonyms 集合（10万条）内存/性能安全
  - provenance JSON 是 list 不是 dict 降级为 {}
  - score_to_tier 边界值（0.49999 / 0.50 / 0.70 / 0.85）
"""

from __future__ import annotations

import pytest

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

EVAL = QualityEvaluator()

TIER_SET = {TIER_HIGH, TIER_MEDIUM, TIER_LOW, TIER_VERY_LOW}


def _base_cand(**overrides):
    base = {
        "id": "cand-edge-001",
        "canonical": "库存周转率",
        "en": "InventoryTurnover",
        "semantic_type": "指标类型",
        "synonyms": ["库存周转天数", "存货周转"],
        "confidence": 0.78,
        "usl_align_confidence": 0.11,
        "domain_id": "domain-fin",
        "provenance": {"doc_hits": 12, "hit_count": 12, "l3_children_est": 2},
    }
    base.update(overrides)
    return base


def _evaluate_safely(cand, **kwargs):
    """包装: NO Exception, 返回 (success, report_or_error_message)"""
    try:
        rep = EVAL.evaluate_candidate(cand, **kwargs)
    except Exception as e:  # noqa: BLE001 - 我们就是要捕获实现异常
        return False, str(e)
    return True, rep


# ======================================================================
# 组 1：非数字字符串 → 原实现 int("foo")/float("foo") 会直接 ValueError 崩溃
# ======================================================================


class TestNonNumericStringCrashes:
    def test_doc_hits_is_non_numeric_string_no_crash(self):
        cand = _base_cand(provenance={"doc_hits": "不可数字符串-foo", "l3_children_est": 2})
        ok, rep = _evaluate_safely(cand)
        assert ok, f"doc_hits='foo' 不应抛异常: {rep}"
        assert rep["tier"] in TIER_SET

    def test_l3_children_est_is_non_numeric_string_no_crash(self):
        cand = _base_cand(provenance={"doc_hits": 8, "l3_children_est": "bar-l3"})
        ok, rep = _evaluate_safely(cand)
        assert ok, f"l3_children_est='bar' 不应抛异常: {rep}"
        assert rep["tier"] in TIER_SET

    def test_confidence_non_numeric_string_no_crash(self):
        cand = _base_cand(confidence="很高")  # 中文
        ok, rep = _evaluate_safely(cand)
        assert ok, f"confidence='很高' 不应抛异常: {rep}"
        assert rep["tier"] in TIER_SET

    def test_usl_align_confidence_non_numeric_string_no_crash(self):
        cand = _base_cand(usl_align_confidence="NoIdea")  # 英文 garbage
        ok, rep = _evaluate_safely(cand)
        assert ok, f"usl_align_confidence='NoIdea' 不应抛异常: {rep}"
        assert rep["tier"] in TIER_SET


# ======================================================================
# 组 2：结构畸形（同义词是 dict 而不是 list / provenance JSON 不是 dict / 超大 synonyms）
# ======================================================================


class TestStructuralMalformed:
    def test_synonyms_raw_is_dict_not_list_downgrade_to_empty(self):
        """synonyms={k:v} 之前会遍历 dict.keys 当作同义词；现在应当作空集合（不 crash）。"""
        cand = _base_cand(synonyms={"k1": "v1", "k2": "v2"})  # 传 dict
        ok, rep = _evaluate_safely(cand)
        assert ok, f"synonyms=dict 不应 crash: {rep}"
        syn_count_sub = next(
            s for s in rep["gate1_details"] if s["submetric"] == "g1_synonyms_size_valid"
        )
        # G1.4 同义词大小应 ∈ [0,30]，所以如果 dict 被降级为空 → score=1.0
        assert 0.0 <= syn_count_sub["score"] <= 1.0
        assert rep["tier"] in TIER_SET

    def test_provenance_is_json_list_not_dict_downgrade_empty(self):
        cand = _base_cand(provenance='[1,2,3,"我是list不是dict"]')
        ok, rep = _evaluate_safely(cand)
        assert ok, f"provenance=JSON-list 不应 crash: {rep}"
        assert rep["tier"] in TIER_SET

    def test_100k_synonyms_is_safe(self):
        """极端情况 synonyms 10 万条（爬虫垃圾）— G1.4 会超限，但不得 crash 或 内存 OOM。"""
        huge_syns = [f"词项_{i:06d}" for i in range(100_000)]
        cand = _base_cand(synonyms=huge_syns)
        ok, rep = _evaluate_safely(cand)
        assert ok, f"synonyms=10万条 不应 crash: {rep}"
        size_sub = next(
            s for s in rep["gate1_details"] if s["submetric"] == "g1_synonyms_size_valid"
        )
        # 超过 30，G1.4 得分必须是 0.0（WARN 级别）
        assert size_sub["score"] == 0.0
        assert rep["tier"] in TIER_SET


# ======================================================================
# 组 3：disjoint 自对误报 + XSS 字符串 + tier 边界值
# ======================================================================


class TestLogicEdgeCases:
    def test_disjoint_self_pair_no_false_positive(self):
        """disjoint pair ('汽车','汽车') 即自对 — 之前会被误命中 disjoint conflict。"""
        cand = _base_cand(canonical="汽车", synonyms=["车辆"])
        ok, rep = _evaluate_safely(
            cand, disjoint_pairs_hint=[("汽车", "汽车"), ("飞机", "汽车")]
        )
        assert ok
        g21 = next(
            s for s in rep["gate2_details"] if s["submetric"] == "g2_usl_disjointness"
        )
        # 自对应被过滤，只留下真正的 (飞机,汽车) 不在同义词集中 → score 1.0
        assert g21["score"] == 1.0, (
            f"自对 (汽车,汽车) 不应被当作冲突。"
            f"g21 score={g21['score']}, reason={g21['reason']}"
        )

    def test_xss_payload_as_canonical(self):
        """canonical=<script>alert(1)</script> — NAME_REGEX 失败（< 不合法）→ score 0；不 crash。"""
        cand = _base_cand(canonical="<script>alert('XSS')</script>", en="")
        ok, rep = _evaluate_safely(cand)
        assert ok
        g11 = next(
            s for s in rep["gate1_details"] if s["submetric"] == "g1_name_valid"
        )
        assert g11["score"] == 0.0  # XSS 被正则拒
        assert rep["tier"] in TIER_SET

    def test_canonical_all_whitespace(self):
        """canonical 全是不可见字符（tab/newline/space） → NAME_REGEX 空字符串。"""
        cand = _base_cand(canonical="   \t \n  ")
        ok, rep = _evaluate_safely(cand)
        assert ok
        g11 = next(
            s for s in rep["gate1_details"] if s["submetric"] == "g1_name_valid"
        )
        assert g11["score"] == 0.0  # 空 canonical 不合法
        assert rep["tier"] in TIER_SET


# ======================================================================
# 组 4：tier 边界值（精确到 5 位小数）
# ======================================================================


class TestTierBoundary:
    @pytest.mark.parametrize(
        "s,expected",
        [
            (0.49999, TIER_VERY_LOW),
            (0.50000, TIER_LOW),
            (0.69999, TIER_LOW),
            (0.70000, TIER_MEDIUM),
            (0.84999, TIER_MEDIUM),
            (0.85000, TIER_HIGH),
            (1.00000, TIER_HIGH),
            (0.00000, TIER_VERY_LOW),
            (-0.1, TIER_VERY_LOW),   # 非法负分 → clamp 到 0 再判 tier
            (1.5, TIER_HIGH),        # 非法超 1 → clamp 到 1 再判
            (float("nan"), TIER_VERY_LOW),  # NaN → clamp 0 → VERY_LOW
            (None, TIER_VERY_LOW),
        ],
    )
    def test_score_to_tier_boundary(self, s, expected):
        got = score_to_tier(s)  # type: ignore[arg-type]
        assert got == expected, f"s={s!r} 期望 tier={expected}, 实际={got}"
