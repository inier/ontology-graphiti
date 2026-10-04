"""ADR-084 F2 回归：质量闸占位子项标 not_evaluated 且剔出 gate 均分。

背景（F2）：`_gate2_subscores` 曾用 4 子项简单平均，其中 G2.2 基数、G2.3 is_a
无环、G2.4 LLM Judge 均为占位 1.0（未真正评估），以满分抬高 gate2_score 与
total_score，制造伪绿 KPI。

整改：占位子项标 `evaluated=False`，其 score 不计入均分（`_mean_evaluated`）。
本测试锁定该行为，防止回退到「占位满分计入均分」。
"""

from __future__ import annotations

from odap.biz.semantic_admin.quality_gate.services.quality_evaluator import (
    QualityEvaluator,
    _mean_evaluated,
)

EVAL = QualityEvaluator()


def _cand(**overrides):
    base = {
        "id": "cand-f2-001",
        "canonical": "库存周转率",
        "en": "InventoryTurnover",
        "semantic_type": "指标类型",
        "synonyms": ["库存周转天数", "存货周转"],
        "confidence": 0.78,
        "domain_id": "domain-fin",
        "provenance": {"doc_hits": 12, "hit_count": 12, "l3_children_est": 2},
    }
    base.update(overrides)
    return base


# 占位子项的 submetric 名（G2.2/G2.3/G2.4）
_PLACEHOLDER_SUBMETRICS = {
    "g2_cardinality_constraint",
    "g2_isa_acyclic",
    "g2_llm_semantic_judge",
}


class TestPlaceholderSubmetricsNotEvaluated:
    def test_g2_placeholders_marked_not_evaluated(self):
        rep = EVAL.evaluate_candidate(_cand())
        by_name = {d["submetric"]: d for d in rep["gate2_details"]}
        for name in _PLACEHOLDER_SUBMETRICS:
            assert name in by_name, f"缺少子项 {name}"
            assert by_name[name].get("evaluated") is False, (
                f"{name} 应标 evaluated=False（占位未评估）"
            )
            assert "[未评估]" in by_name[name]["reason"], (
                f"{name} reason 应含 [未评估] 前缀"
            )

    def test_g2_1_disjointness_is_evaluated(self):
        rep = EVAL.evaluate_candidate(_cand())
        by_name = {d["submetric"]: d for d in rep["gate2_details"]}
        assert by_name["g2_usl_disjointness"].get("evaluated", True) is True

    def test_gate1_submetrics_all_evaluated(self):
        rep = EVAL.evaluate_candidate(_cand())
        for d in rep["gate1_details"]:
            assert d.get("evaluated", True) is True, (
                f"G1 子项 {d['submetric']} 均为真值计算，应 evaluated=True"
            )


class TestGate2MeanExcludesPlaceholders:
    def test_no_disjoint_hit_gate2_is_one(self):
        """无 disjoint 命中：仅 g2_1 计入均分（=1.0），占位项不拉高也不拉低。"""
        rep = EVAL.evaluate_candidate(_cand())
        # 旧行为：(1+1+1+1)/4 = 1.0；新行为：仅 g2_1=1.0 → 1.0（数值同，但语义诚实）
        assert rep["gate2_score"] == 1.0

    def test_disjoint_hit_gate2_collapses_to_zero(self):
        """命中 disjoint（g2_1=0）：gate2 应为 0.0，而非旧的 (0+1+1+1)/4=0.75。

        这是 F2 的核心反向探针：占位满分不得再把失败项稀释成伪绿。
        """
        rep = EVAL.evaluate_candidate(
            _cand(),
            disjoint_pairs_hint=[("库存周转率", "存货周转")],
        )
        by_name = {d["submetric"]: d for d in rep["gate2_details"]}
        assert by_name["g2_usl_disjointness"]["score"] == 0.0
        assert rep["gate2_score"] == 0.0, (
            "占位项剔出均分后，g2_1=0 应使 gate2_score=0.0（旧行为为 0.75 伪绿）"
        )


class TestMeanEvaluatedHelper:
    def test_excludes_not_evaluated(self):
        subs = [
            {"submetric": "a", "score": 0.0, "evaluated": True},
            {"submetric": "b", "score": 1.0, "evaluated": False},
            {"submetric": "c", "score": 1.0, "evaluated": False},
        ]
        assert _mean_evaluated(subs) == 0.0

    def test_defaults_to_evaluated_when_flag_absent(self):
        subs = [{"submetric": "a", "score": 1.0}, {"submetric": "b", "score": 0.0}]
        assert _mean_evaluated(subs) == 0.5

    def test_all_placeholders_returns_zero_not_full(self):
        """全部未评估 → 诚实归零，禁止回退满分。"""
        subs = [
            {"submetric": "a", "score": 1.0, "evaluated": False},
            {"submetric": "b", "score": 1.0, "evaluated": False},
        ]
        assert _mean_evaluated(subs) == 0.0
