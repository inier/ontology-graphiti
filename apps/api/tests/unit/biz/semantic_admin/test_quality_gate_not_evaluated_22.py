"""ADR-084 F2/F7 回归：22 子指标计算器不得用默认满分冒充评估。

覆盖：
1. 缺失/非法字段 → evaluated=False 且剔除出 gate 分母；
2. 全部缺失 → gate 分数诚实归零 + evaluation_complete=False；
3. SHACL provider 注入：返回 None → 未评估；返回数值 → 真值计分；
4. 占位子项不得稀释失败项（gate2 反向探针）。
"""

from __future__ import annotations

import pytest

from odap.biz.semantic_admin.quality_gate.services.quality_calculator import (
    QualityCalculator,
    _eval_g2_shacl_compliance,
)
from odap.biz.semantic_admin.quality_gate.services.shacl_compliance import (
    compliance_ratio,
    make_storage_provider,
)


def _cand(**overrides):
    base = {
        "id": "cand-f2-022",
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


def _by_name(details, name):
    for d in details:
        if d.get("submetric") == name:
            return d
    raise AssertionError(f"缺少子指标 {name}")


CALC = QualityCalculator()


class TestMissingFieldsAreNotEvaluated:
    @pytest.mark.parametrize(
        "field,submetric",
        [
            ("fill_rate", "g1_fill_rate"),
            ("empty_rate", "g1_empty_rate"),
            ("orphan_ratio", "g1_orphan_ratio"),
        ],
    )
    def test_g1_missing_field_marked_not_evaluated(self, field, submetric):
        cand = _cand()
        assert field not in cand
        rep = CALC.evaluate_candidate(cand)
        sub = _by_name(rep["gate1_details"], submetric)
        assert sub["evaluated"] is False
        assert sub["score"] == 0.0
        assert "[未评估]" in sub["reason"]

    @pytest.mark.parametrize(
        "field,submetric",
        [
            ("dangling_relations", "g2_dangling_relations"),
            ("invalid_action_targets", "g2_invalid_action_targets"),
            ("invalid_rule_references", "g2_invalid_rule_references"),
        ],
    )
    def test_g2_missing_field_marked_not_evaluated(self, field, submetric):
        cand = _cand()
        assert field not in cand
        rep = CALC.evaluate_candidate(cand)
        sub = _by_name(rep["gate2_details"], submetric)
        assert sub["evaluated"] is False
        assert sub["score"] == 0.0

    def test_shacl_absent_marked_not_evaluated(self):
        rep = CALC.evaluate_candidate(_cand())
        sub = _by_name(rep["gate2_details"], "g2_shacl_compliance")
        assert sub["evaluated"] is False
        assert sub["score"] == 0.0
        assert "未接入 SHACL" in sub["reason"]

    def test_report_exposes_incomplete_and_missing_list(self):
        rep = CALC.evaluate_candidate(_cand())
        assert rep["evaluation_complete"] is False
        assert set(rep["not_evaluated_submetrics"]) >= {
            "g1_fill_rate", "g1_empty_rate", "g1_orphan_ratio",
            "g2_dangling_relations", "g2_invalid_action_targets",
            "g2_invalid_rule_references", "g2_shacl_compliance",
        }


class TestAggregationExcludesNotEvaluated:
    def test_g1_denominator_excludes_missing(self):
        """只给 fill_rate，其余 5 项未评估：G1 只需 8 个已评估项参与加权。"""
        rep = CALC.evaluate_candidate(_cand(fill_rate=0.0))
        # fill_rate=0 参与计算，权重 1.0；未评估项不进入分母
        assert rep["gate1_score"] < 1.0
        assert rep["gate1_score"] == pytest.approx(
            CALC._compute_gate1_score_22(rep["gate1_details"])
        )

    def test_g2_placeholder_does_not_dilute_failure(self):
        """g2_5 失败时，gate2 应为 mean(g2_1, g2_5)=0.5，而非被占位满分稀释。"""
        rep = CALC.evaluate_candidate(
            _cand(dangling_relations=[{"s": "a", "r": "b", "o": "c"}])
        )
        sub = _by_name(rep["gate2_details"], "g2_dangling_relations")
        assert sub["evaluated"] is True
        assert sub["score"] == 0.0
        assert rep["gate2_score"] == pytest.approx(0.5)

    def test_all_placeholders_gate_goes_zero(self):
        details = [
            {"submetric": "x", "score": 1.0, "evaluated": False},
            {"submetric": "y", "score": 1.0, "evaluated": False},
        ]
        assert CALC._compute_gate2_score_22(details) == 0.0
        assert CALC._compute_gate1_score_22(details) == 0.0


class TestShaclProvider:
    def test_provider_none_means_not_evaluated(self):
        sub = _eval_g2_shacl_compliance(_cand(), provider=lambda c: None)
        assert sub["evaluated"] is False
        assert sub["score"] == 0.0
        assert "无法产出" in sub["reason"]

    def test_provider_value_is_scored(self):
        sub = _eval_g2_shacl_compliance(_cand(), provider=lambda c: 0.6)
        assert sub["evaluated"] is True
        assert sub["score"] == pytest.approx(0.6)
        assert "needs_review" in sub["reason"]

    def test_provider_value_passes_threshold(self):
        sub = _eval_g2_shacl_compliance(_cand(), provider=lambda c: 0.9)
        assert sub["evaluated"] is True
        assert sub["score"] == pytest.approx(0.9)

    def test_candidate_field_takes_precedence(self):
        sub = _eval_g2_shacl_compliance(
            _cand(shacl_compliance=0.95), provider=lambda c: 0.1
        )
        assert sub["score"] == pytest.approx(0.95)
        assert sub["evaluated"] is True

    def test_invalid_field_marked_not_evaluated(self):
        sub = _eval_g2_shacl_compliance(_cand(shacl_compliance="abc"))
        assert sub["evaluated"] is False
        assert sub["score"] == 0.0


class TestComplianceRatio:
    SHAPES = """
    @prefix sh: <http://www.w3.org/ns/shacl#> .
    @prefix ex: <http://example.org/> .
    ex:PersonShape a sh:NodeShape ;
        sh:targetClass ex:Person ;
        sh:property [ sh:path ex:name ; sh:minCount 1 ] .
    """

    def test_ratio_counts_violating_focus_nodes(self):
        data = """
        @prefix ex: <http://example.org/> .
        ex:alice a ex:Person ; ex:name "A" .
        ex:bob a ex:Person .
        """
        assert compliance_ratio(self.SHAPES, data) == pytest.approx(0.5)

    def test_all_conforming_is_one(self):
        data = """
        @prefix ex: <http://example.org/> .
        ex:alice a ex:Person ; ex:name "A" .
        """
        assert compliance_ratio(self.SHAPES, data) == pytest.approx(1.0)

    def test_no_target_class_returns_none(self):
        shapes = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix ex: <http://example.org/> .
        ex:S a sh:NodeShape .
        """
        assert compliance_ratio(shapes, "@prefix ex: <http://example.org/> .") is None

    def test_unparsable_returns_none(self):
        assert compliance_ratio(self.SHAPES, "not turtle {{{") is None

    def test_storage_provider_requires_workspace(self):
        class _Storage:
            def list_shapes(self, **kwargs):
                return [], 0

        with pytest.raises(ValueError):
            make_storage_provider(
                _Storage(), workspace_id="", ontology_version_id=None,
                graph_builder=lambda c: None,
            )

    def test_storage_provider_without_shapes_returns_none(self):
        class _Storage:
            def list_shapes(self, **kwargs):
                return [], 0

        provider = make_storage_provider(
            _Storage(), workspace_id="ws-1", ontology_version_id=None,
            graph_builder=lambda c: None,
        )
        assert provider(_cand()) is None
