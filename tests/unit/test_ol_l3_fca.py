"""L3 FCA (Formal Concept Analysis) 单元测试。

Zoo/Animal 小数据集验证概念格正确性 + stability 过滤。
"""

from __future__ import annotations

import pytest

from odap.biz.semantic_admin.ol_pipeline.impl.l3_formal_concept import (
    FormalConceptAnalyzer,
)


# ============================================================
# Fixtures: Zoo/Animal 标准小数据集
# ============================================================
@pytest.fixture
def zoo_animals():
    """5 个动物，每个动物有若干属性，FCA 应能分组出"猫科(哺乳动物/食肉/有毛)"等概念。"""
    return [
        {
            "canonical": "狮子",
            "semantic_type": "对象类型",
            "domain_id": "zoo",
            "tags": ["哺乳动物", "食肉", "有毛", "猛兽"],
        },
        {
            "canonical": "老虎",
            "semantic_type": "对象类型",
            "domain_id": "zoo",
            "tags": ["哺乳动物", "食肉", "有毛", "猛兽"],
        },
        {
            "canonical": "猫",
            "semantic_type": "对象类型",
            "domain_id": "zoo",
            "tags": ["哺乳动物", "有毛", "宠物"],
        },
        {
            "canonical": "金鱼",
            "semantic_type": "对象类型",
            "domain_id": "zoo",
            "tags": ["鱼类", "水生", "宠物"],
        },
        {
            "canonical": "鹰",
            "semantic_type": "对象类型",
            "domain_id": "zoo",
            "tags": ["鸟类", "会飞", "食肉"],
        },
    ]


@pytest.fixture
def analyzer():
    return FormalConceptAnalyzer()


# ============================================================
# Tests
# ============================================================
class TestFormalConceptAnalyzer:
    def test_empty_input_returns_empty(self, analyzer: FormalConceptAnalyzer):
        result = analyzer.analyze([])
        assert result["lattice_count"] == 0
        assert result["formal_concepts"] == []
        assert result["suggested_hierarchy_edges"] == []

    def test_zoo_concepts_count_reasonable(
        self, analyzer: FormalConceptAnalyzer, zoo_animals
    ):
        result = analyzer.analyze(
            zoo_animals,
            attribute_fields=("semantic_type", "domain_id", "tags"),
            min_stability=0.0,  # 低阈值，先看所有概念
        )
        n = result["lattice_count"]
        # 5 个对象 × 合理属性数，概念格数量至少包含 3 个（顶/1个共享/底）
        assert 3 <= n <= 500, f"概念数异常: {n}"

    def test_zoo_mammal_carnivore_concept_exists(
        self, analyzer: FormalConceptAnalyzer, zoo_animals
    ):
        result = analyzer.analyze(
            zoo_animals,
            attribute_fields=("tags",),
            min_stability=0.0,
        )
        # 至少有一个概念同时包含 {狮子,老虎}（共享属性"哺乳动物/食肉/有毛/猛兽"）
        found_tiger_lion = False
        for c in result["formal_concepts"]:
            ext = set(c["extent"])
            if {"狮子", "老虎"}.issubset(ext) and "金鱼" not in ext and "鹰" not in ext:
                found_tiger_lion = True
                # intent 应包含 "tags::哺乳动物" 等
                assert any("tags::" in str(x) for x in c["intent"])
                break
        assert found_tiger_lion, "狮子/老虎共享概念未找到"

    def test_zoo_stability_filter_works(
        self, analyzer: FormalConceptAnalyzer, zoo_animals
    ):
        low = analyzer.analyze(zoo_animals, min_stability=0.0)
        high = analyzer.analyze(zoo_animals, min_stability=0.8)
        # 高 stability 过滤后数量不应超过低阈值
        assert high["lattice_count"] <= low["lattice_count"]

    def test_suggested_edges_reasonable(
        self, analyzer: FormalConceptAnalyzer, zoo_animals
    ):
        result = analyzer.analyze(zoo_animals, min_stability=0.0)
        edges = result["suggested_hierarchy_edges"]
        # 边必须引用有效的概念索引
        n = result["lattice_count"]
        if edges:
            for e in edges:
                assert 0 <= e["from_concept_index"] < n
                assert 0 <= e["to_parent_index"] < n
                # parent != child
                assert e["from_concept_index"] != e["to_parent_index"]

    def test_context_size_matches_input(
        self, analyzer: FormalConceptAnalyzer, zoo_animals
    ):
        result = analyzer.analyze(zoo_animals, attribute_fields=("canonical", "tags"))
        ctx = result["context_size"]
        # objects = 5 unique canonical
        assert ctx["objects"] == 5
        assert ctx["attributes"] >= 5  # 至少 5 canonical + 若干 tags
        # incidence 至少每个对象至少一个属性
        assert ctx["incidence"] >= 5

    def test_duplicate_entities_merge_attributes(self, analyzer: FormalConceptAnalyzer):
        """两个相同 canonical 的 entity 应被合并（属性做并集）。"""
        data = [
            {"canonical": "狮", "semantic_type": "对象类型"},
            {"canonical": "狮", "domain_id": "african", "tags": ["猫科"]},
        ]
        result = analyzer.analyze(data, attribute_fields=("semantic_type", "domain_id", "tags"))
        assert result["context_size"]["objects"] == 1

    def test_large_input_capped_by_max_concepts(self, analyzer: FormalConceptAnalyzer):
        """大量 entity 时 max_concepts 生效（不指数爆炸）。"""
        import random
        rng = random.Random(0)
        entities = []
        for i in range(32):
            entities.append({
                "canonical": f"E{i:02d}",
                "tags": [f"t{rng.randint(0,6)}" for _ in range(3)],
            })
        result = analyzer.analyze(
            entities,
            attribute_fields=("tags",),
            max_concepts=100,
            min_stability=0.0,
        )
        assert result["lattice_count"] <= 100
