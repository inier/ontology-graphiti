"""ADR-085 S4c：质量闸 G2.2 基数 / G2.3 is_a 无环真值替换占位。

背景（ADR-084 F2 → ADR-085 D6）：`_gate2_subscores` 的 G2.2 基数约束、G2.3 is_a
无环曾长期为占位 1.0 且 `evaluated=False`（剔出均分，诚实但无真值）。S4c 把它们
接到真实 USL 数据源（`usl_cardinalities` / `usl_hierarchies`）：

  - 注入了数据源（usl_storage 且候选有 domain_id）→ 真查、真算、`evaluated=True`；
  - 未注入数据源 → 保持 `evaluated=False` + `[未评估]`（诚实，不回退伪绿满分）。

本测试用真实 tmp_path SQLiteUslStorage（规则 9：禁 MagicMock 模拟 DB），并走
`QualityEvaluator.evaluate_candidate` 真实函数体（规则 14.6：测试必须执行真实实现）。
"""

from __future__ import annotations

import pytest

from odap.biz.semantic_admin.quality_gate.services.quality_evaluator import (
    QualityEvaluator,
)
from odap.biz.semantic_admin.usl_manager.storage.sqlite_usl_storage import (
    SQLiteUslStorage,
)

EVAL = QualityEvaluator()


def _cand(**overrides):
    base = {
        "id": "cand-g2-001",
        "canonical": "库存周转率",
        "en": "InventoryTurnover",
        "semantic_type": "指标类型",
        "synonyms": ["存货周转"],
        "confidence": 0.8,
        "domain_id": "domain-fin",
        "provenance": {"doc_hits": 5, "l3_children_est": 1},
    }
    base.update(overrides)
    return base


def _g2_by_name(rep):
    return {d["submetric"]: d for d in rep["gate2_details"]}


@pytest.fixture
def usl(tmp_path):
    """真实 tmp_path SQLite USL 存储（规则 9）。"""
    return SQLiteUslStorage(db_path=str(tmp_path / "usl.db"))


# ======================================================================
# G2.2 基数约束真值（usl_cardinalities）
# ======================================================================
class TestG22CardinalityTruth:
    def test_contradictory_cardinality_fails(self, usl):
        """min_card > max_card 的矛盾基数约束涉及候选 → evaluated=True 且 score=0.0。"""
        usl.save_cardinality({
            "domain_id": "domain-fin",
            "rel_name": "has_part",
            "domain_term": "库存周转率",
            "range_term": "存货",
            "min_card": 3,
            "max_card": 1,  # 矛盾：min > max，不可满足
        })
        rep = EVAL.evaluate_candidate(_cand(), usl_storage=usl)
        g22 = _g2_by_name(rep)["g2_cardinality_constraint"]
        assert g22["evaluated"] is True, "注入数据源后应真评估"
        assert g22["score"] == 0.0, "矛盾基数约束应 FAIL"

    def test_consistent_cardinality_passes(self, usl):
        """min<=max 的一致基数约束涉及候选 → evaluated=True 且 score=1.0。"""
        usl.save_cardinality({
            "domain_id": "domain-fin",
            "rel_name": "has_part",
            "domain_term": "库存周转率",
            "range_term": "存货",
            "min_card": 1,
            "max_card": 3,
        })
        rep = EVAL.evaluate_candidate(_cand(), usl_storage=usl)
        g22 = _g2_by_name(rep)["g2_cardinality_constraint"]
        assert g22["evaluated"] is True
        assert g22["score"] == 1.0

    def test_unbounded_max_cardinality_passes(self, usl):
        """max_card=None（无上界）且 min>=0 → 可满足，score=1.0。"""
        usl.save_cardinality({
            "domain_id": "domain-fin",
            "rel_name": "has_part",
            "domain_term": "库存周转率",
            "range_term": "存货",
            "min_card": 0,
            "max_card": None,
        })
        rep = EVAL.evaluate_candidate(_cand(), usl_storage=usl)
        g22 = _g2_by_name(rep)["g2_cardinality_constraint"]
        assert g22["evaluated"] is True
        assert g22["score"] == 1.0

    def test_empty_domain_still_evaluated(self, usl):
        """数据源已注入但域内无基数行 → 真查过，平凡满足，evaluated=True。"""
        rep = EVAL.evaluate_candidate(_cand(), usl_storage=usl)
        g22 = _g2_by_name(rep)["g2_cardinality_constraint"]
        assert g22["evaluated"] is True
        assert g22["score"] == 1.0

    def test_no_storage_not_evaluated(self):
        """未注入数据源 → 保持诚实占位 evaluated=False + [未评估]（不回退伪绿）。"""
        rep = EVAL.evaluate_candidate(_cand())  # usl_storage=None
        g22 = _g2_by_name(rep)["g2_cardinality_constraint"]
        assert g22["evaluated"] is False
        assert "[未评估]" in g22["reason"]


# ======================================================================
# G2.3 is_a 无环真值（usl_hierarchies 拓扑排序）
# ======================================================================
class TestG23IsaAcyclicTruth:
    def test_parent_chain_cycle_fails(self, usl):
        """候选父链成环（库存周转率→存货→资产→库存周转率）→ evaluated=True 且 0.0。"""
        usl.save_hierarchy({"domain_id": "domain-fin", "rel_type": "IS_A",
                            "child_term": "库存周转率", "parent_term": "存货"})
        usl.save_hierarchy({"domain_id": "domain-fin", "rel_type": "IS_A",
                            "child_term": "存货", "parent_term": "资产"})
        usl.save_hierarchy({"domain_id": "domain-fin", "rel_type": "IS_A",
                            "child_term": "资产", "parent_term": "库存周转率"})
        rep = EVAL.evaluate_candidate(_cand(), usl_storage=usl)
        g23 = _g2_by_name(rep)["g2_isa_acyclic"]
        assert g23["evaluated"] is True
        assert g23["score"] == 0.0, "父链成环应 FAIL"

    def test_self_loop_fails(self, usl):
        """自环（库存周转率 is_a 库存周转率）→ score=0.0。"""
        usl.save_hierarchy({"domain_id": "domain-fin", "rel_type": "IS_A",
                            "child_term": "库存周转率", "parent_term": "库存周转率"})
        rep = EVAL.evaluate_candidate(_cand(), usl_storage=usl)
        g23 = _g2_by_name(rep)["g2_isa_acyclic"]
        assert g23["evaluated"] is True
        assert g23["score"] == 0.0

    def test_acyclic_chain_passes(self, usl):
        """无环父链（库存周转率→存货→资产）→ evaluated=True 且 1.0。"""
        usl.save_hierarchy({"domain_id": "domain-fin", "rel_type": "IS_A",
                            "child_term": "库存周转率", "parent_term": "存货"})
        usl.save_hierarchy({"domain_id": "domain-fin", "rel_type": "IS_A",
                            "child_term": "存货", "parent_term": "资产"})
        rep = EVAL.evaluate_candidate(_cand(), usl_storage=usl)
        g23 = _g2_by_name(rep)["g2_isa_acyclic"]
        assert g23["evaluated"] is True
        assert g23["score"] == 1.0

    def test_unrelated_cycle_does_not_fail_candidate(self, usl):
        """域内存在与候选无关的环 → 候选父链不经过它，不应误伤该候选（candidate-centric）。"""
        usl.save_hierarchy({"domain_id": "domain-fin", "rel_type": "IS_A",
                            "child_term": "甲", "parent_term": "乙"})
        usl.save_hierarchy({"domain_id": "domain-fin", "rel_type": "IS_A",
                            "child_term": "乙", "parent_term": "甲"})
        rep = EVAL.evaluate_candidate(_cand(), usl_storage=usl)
        g23 = _g2_by_name(rep)["g2_isa_acyclic"]
        assert g23["evaluated"] is True
        assert g23["score"] == 1.0

    def test_empty_domain_still_evaluated(self, usl):
        """数据源已注入但域内无层级边 → 真查过，平凡无环，evaluated=True。"""
        rep = EVAL.evaluate_candidate(_cand(), usl_storage=usl)
        g23 = _g2_by_name(rep)["g2_isa_acyclic"]
        assert g23["evaluated"] is True
        assert g23["score"] == 1.0

    def test_no_storage_not_evaluated(self):
        """未注入数据源 → 诚实占位 evaluated=False + [未评估]。"""
        rep = EVAL.evaluate_candidate(_cand())  # usl_storage=None
        g23 = _g2_by_name(rep)["g2_isa_acyclic"]
        assert g23["evaluated"] is False
        assert "[未评估]" in g23["reason"]

