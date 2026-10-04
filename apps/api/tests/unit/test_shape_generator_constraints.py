"""ADR-085 S4a-2：ShapeGenerator 消费持久化约束。

F7-b：
  · usl_cardinalities(min,max) → sh:minCount / sh:maxCount（+ sh:class 指向 range_term）
  · usl_disjoint_pairs / L6 disjoint_classes → sh:not [ sh:class 对方 ]

约束以**参数**传入（plain data），ShapeGenerator 不 import semantic_admin
（守 import-linter C3：semantic_admin 与 ontology.design 互不直接依赖）。
向后兼容：不传新参时行为与 ADR-077 原版一致。
"""

from __future__ import annotations

from odap.biz.core.ontology.design.engine.shacl.shape_generator import ShapeGenerator

# 生成文本里 SHACL 术语以完整 IRI 出现，断言用 "#术语>" 避免与 NodeShape 等误匹配
_NOT = "#not>"
_CLASS = "#class>"
_MIN = "#minCount>"
_MAX = "#maxCount>"


def _et(name, **kw):
    base = {
        "type_id": name,
        "name": name,
        "properties": [],
        "links": [],
        "primary_key": [],
    }
    base.update(kw)
    return base


class TestCardinalityConstraints:
    def test_usl_cardinality_emits_min_and_max_count(self):
        ets = [_et("订单")]
        cards = [
            {
                "rel_name": "包含",
                "domain_term": "订单",
                "range_term": "商品",
                "min_card": 1,
                "max_card": 1,
            }
        ]
        ttl = ShapeGenerator().generate(ets, cardinalities=cards)
        assert f"{_MIN} 1" in ttl
        assert f"{_MAX} 1" in ttl
        # 关系路径含 rel_name，sh:class 指向 range_term
        assert "包含" in ttl
        assert _CLASS in ttl
        assert "商品" in ttl

    def test_cardinality_bound_value_reflected(self):
        ets = [_et("订单"), _et("用户")]
        cards = [
            {
                "rel_name": "包含",
                "domain_term": "订单",
                "range_term": "商品",
                "min_card": 2,
                "max_card": 5,
            }
        ]
        ttl = ShapeGenerator().generate(ets, cardinalities=cards)
        assert f"{_MIN} 2" in ttl
        assert f"{_MAX} 5" in ttl

    def test_unbounded_max_cardinality_omits_maxcount(self):
        ets = [_et("订单")]
        cards = [
            {
                "rel_name": "包含",
                "domain_term": "订单",
                "range_term": "商品",
                "min_card": 1,
                "max_card": None,
            }
        ]
        ttl = ShapeGenerator().generate(ets, cardinalities=cards)
        assert f"{_MIN} 1" in ttl
        assert _MAX not in ttl

    def test_cardinality_only_attached_to_matching_domain(self):
        # domain_term=订单，只有「订单」实体类型应得到该关系约束；「用户」不应
        ets = [_et("订单"), _et("用户")]
        cards = [
            {
                "rel_name": "包含",
                "domain_term": "订单",
                "range_term": "商品",
                "min_card": 1,
                "max_card": 3,
            }
        ]
        ttl = ShapeGenerator().generate(ets, cardinalities=cards)
        order_shape, user_shape = ttl.split("用户Shape")
        assert "包含" in order_shape
        assert "包含" not in user_shape

    def test_backward_compatible_without_new_args(self):
        ets = [
            _et("Unit", properties=[{"name": "name", "data_type": "string", "required": True}])
        ]
        ttl = ShapeGenerator().generate(ets)
        assert f"{_MIN} 1" in ttl  # required 仍生效
        assert _NOT not in ttl  # 无不相交约束


class TestDisjointConstraints:
    def test_usl_disjoint_pair_emits_sh_not(self):
        ets = [_et("指标"), _et("维度")]
        dps = [{"term_a": "指标", "term_b": "维度"}]
        ttl = ShapeGenerator().generate(ets, disjoint_pairs=dps)
        assert _NOT in ttl
        assert _CLASS in ttl

    def test_disjoint_is_symmetric(self):
        ets = [_et("指标"), _et("维度")]
        dps = [{"term_a": "指标", "term_b": "维度"}]
        ttl = ShapeGenerator().generate(ets, disjoint_pairs=dps)
        # 指标 shape 排除 维度、维度 shape 排除 指标 → 两处 sh:not
        assert ttl.count(_NOT) == 2

    def test_disjoint_pair_on_absent_type_is_ignored(self):
        # 只有「指标」实体类型；term_b=维度 无对应 shape，但指标仍应排除维度
        ets = [_et("指标")]
        dps = [{"term_a": "指标", "term_b": "维度"}]
        ttl = ShapeGenerator().generate(ets, disjoint_pairs=dps)
        assert ttl.count(_NOT) == 1
        assert "维度" in ttl


class TestAxiomDisjoint:
    def test_l6_disjoint_classes_axiom_emits_sh_not(self):
        ets = [_et("A"), _et("B")]
        axioms = [
            {"axiom_type": "disjoint_classes", "subject": "A", "object": "B", "confidence": 0.9}
        ]
        ttl = ShapeGenerator().generate(ets, axioms=axioms)
        assert _NOT in ttl
        assert ttl.count(_NOT) == 2  # 对称

    def test_non_disjoint_axioms_do_not_emit_sh_not(self):
        # sub_class_of 在本切片不派生 sh:not（仅 disjoint_classes 进不相交通道）
        ets = [_et("A"), _et("B")]
        axioms = [
            {"axiom_type": "sub_class_of", "subject": "A", "object": "B", "confidence": 0.9}
        ]
        ttl = ShapeGenerator().generate(ets, axioms=axioms)
        assert _NOT not in ttl

    def test_axiom_and_usl_disjoint_dedup(self):
        # 同一对 (A,B) 同时来自 usl 与 L6 公理 → 只出一处 sh:not（去重，不重复约束）
        ets = [_et("A"), _et("B")]
        dps = [{"term_a": "A", "term_b": "B"}]
        axioms = [
            {"axiom_type": "disjoint_classes", "subject": "A", "object": "B", "confidence": 0.9}
        ]
        ttl = ShapeGenerator().generate(ets, disjoint_pairs=dps, axioms=axioms)
        assert ttl.count(_NOT) == 2  # A→B 与 B→A 各一，不因双源翻倍


class TestCombinedAndValidity:
    def test_cardinality_and_disjoint_together(self):
        ets = [_et("订单"), _et("发票")]
        cards = [
            {
                "rel_name": "开具",
                "domain_term": "订单",
                "range_term": "发票",
                "min_card": 1,
                "max_card": 1,
            }
        ]
        dps = [{"term_a": "订单", "term_b": "发票"}]
        ttl = ShapeGenerator().generate(ets, cardinalities=cards, disjoint_pairs=dps)
        assert f"{_MIN} 1" in ttl
        assert _NOT in ttl

    def test_output_is_rdflib_parseable(self):
        # 生成的 Turtle 必须能被 rdflib 解析（SHACLValidator 依赖此前提）
        rdflib = __import__("rdflib")
        ets = [_et("订单"), _et("发票")]
        cards = [
            {
                "rel_name": "开具",
                "domain_term": "订单",
                "range_term": "发票",
                "min_card": 1,
                "max_card": 2,
            }
        ]
        dps = [{"term_a": "订单", "term_b": "发票"}]
        ttl = ShapeGenerator().generate(ets, cardinalities=cards, disjoint_pairs=dps)
        g = rdflib.Graph()
        g.parse(data=ttl, format="turtle")  # 抛异常即失败
        assert len(g) > 0
