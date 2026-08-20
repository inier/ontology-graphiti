"""TDD 单元测试：确定性检索链路（移除 LLM 幻觉源）。

验证本体论原则：
- QueryRewriter：USL 字典确定性改写（同义词→canonical），无 LLM 生成
- CypherGenerator：确定性模板匹配，无 LLM 生成 Cypher
- Reranker：确定性排序（支柱优先级 + doc_id），score 不参与排序决定

覆盖：
  T-DET-1: QueryRewriter 同义词改写为 canonical（确定性）
  T-DET-2: QueryRewriter 未命中保持原样（不生成）
  T-DET-3: QueryRewriter multi_query 返回 [原查询, 改写]（无 LLM 生成）
  T-DET-4: CypherGenerator 确定性模板匹配（neighbors）
  T-DET-5: CypherGenerator path 模板无法填充 target → None（不猜测）
  T-DET-6: CypherGenerator type_count 需 schema 精确匹配
  T-DET-7: Reranker 确定性排序（graph > vector > bm25，同 pillar doc_id 稳定）
  T-DET-8: Reranker score 不参与排序决定
"""

from __future__ import annotations

import pytest

from odap.biz.data.qa.retrieval.vector_retriever import QueryRewriter
from odap.biz.data.qa.retrieval.graph_retriever import CypherGenerator
from odap.biz.data.qa.pipeline.fusion.result_fuser import Reranker
from odap.biz.data.qa.models import RetrievalResult, RetrievalPillar
from odap.biz.semantic_admin.usl_manager.services.usl_term_resolver import UslTermResolver


@pytest.fixture
def terms():
    return [
        {"canonical": "势力", "semantic_type": "对象类型",
         "synonyms": ["阵营", "国家"], "near_synonyms": [], "aliases": ["三国势力"],
         "stoplist_flag": False},
        {"canonical": "装备", "semantic_type": "对象类型",
         "synonyms": ["武器", "兵器"], "near_synonyms": [], "aliases": [],
         "stoplist_flag": False},
    ]


class TestQueryRewriter:
    def test_synonym_rewrite_to_canonical(self, terms):
        resolver = UslTermResolver()
        resolver.load_terms("d1", terms)
        rewriter = QueryRewriter(term_resolver=resolver)
        # "阵营" → "势力"
        assert rewriter.rewrite("阵营有哪些", "d1") == "势力有哪些"

    def test_unknown_keeps_original(self, terms):
        resolver = UslTermResolver()
        resolver.load_terms("d1", terms)
        rewriter = QueryRewriter(term_resolver=resolver)
        # 未命中 → 保持原样，不生成
        assert rewriter.rewrite("不明词有哪些", "d1") == "不明词有哪些"

    def test_multi_query_no_llm_generation(self, terms):
        resolver = UslTermResolver()
        resolver.load_terms("d1", terms)
        rewriter = QueryRewriter(term_resolver=resolver)
        queries = rewriter.multi_query("阵营的装备")
        # 仅 [原查询, 改写]，无 LLM 生成的额外查询
        assert len(queries) <= 2
        assert "阵营的装备" in queries  # 原查询保留
        assert "势力的装备" in queries  # 改写

    def test_hyde_rewrite_is_deterministic(self, terms):
        resolver = UslTermResolver()
        resolver.load_terms("d1", terms)
        rewriter = QueryRewriter(term_resolver=resolver)
        # hyde_rewrite 已改为确定性改写（同义），同输入同输出
        a = rewriter.hyde_rewrite("阵营有哪些")
        b = rewriter.hyde_rewrite("阵营有哪些")
        assert a == b == "势力有哪些"


class TestCypherGenerator:
    def test_neighbors_template(self):
        gen = CypherGenerator()
        cypher = gen.generate("查找曹操的关联")
        assert cypher is not None
        assert "MATCH" in cypher
        assert "曹操" in cypher
        assert "CREATE" not in cypher.upper()

    def test_path_template_returns_none(self):
        # path 模板含 {target}，无法确定性填充 → None（不猜测）
        gen = CypherGenerator()
        cypher = gen.generate("从A到B的最短路径")
        assert cypher is None

    def test_type_count_requires_schema_match(self):
        gen = CypherGenerator()
        schema = {"entity_types": ["人物"], "relation_types": []}
        cypher = gen.generate("有多少人物", schema=schema)
        assert cypher is not None
        assert "人物" in cypher

    def test_type_count_no_schema_match_returns_none(self):
        gen = CypherGenerator()
        schema = {"entity_types": ["地点"], "relation_types": []}
        # 查询问"人物"但 schema 无"人物" → None（不猜测）
        cypher = gen.generate("有多少人物", schema=schema)
        assert cypher is None

    def test_validate_rejects_write(self):
        gen = CypherGenerator()
        assert gen.validate("MATCH (n) RETURN n") is True
        assert gen.validate("CREATE (n)") is False
        assert gen.validate("MATCH (n) DELETE n") is False


class TestReranker:
    def _mk(self, doc_id, pillar, score):
        return RetrievalResult(
            doc_id=doc_id, content=doc_id, score=score, pillar=pillar, source="test",
        )

    def test_pillar_priority_deterministic(self):
        reranker = Reranker()
        results = [
            self._mk("b1", RetrievalPillar.BM25, 0.9),
            self._mk("v1", RetrievalPillar.VECTOR, 0.9),
            self._mk("g1", RetrievalPillar.GRAPH, 0.9),
        ]
        ranked = reranker.rerank("q", results, top_k=10)
        # graph 优先于 vector 优先于 bm25（与 score 无关，三者 score 相同）
        assert ranked[0].pillar == RetrievalPillar.GRAPH
        assert ranked[1].pillar == RetrievalPillar.VECTOR
        assert ranked[2].pillar == RetrievalPillar.BM25

    def test_score_not_used_for_ordering(self):
        reranker = Reranker()
        # bm25 高分 vs graph 低分 → graph 仍优先（score 不决定排序）
        results = [
            self._mk("b1", RetrievalPillar.BM25, 0.99),
            self._mk("g1", RetrievalPillar.GRAPH, 0.01),
        ]
        ranked = reranker.rerank("q", results, top_k=10)
        assert ranked[0].pillar == RetrievalPillar.GRAPH
        assert ranked[1].pillar == RetrievalPillar.BM25

    def test_same_pillar_stable_doc_id_order(self):
        reranker = Reranker()
        results = [
            self._mk("g2", RetrievalPillar.GRAPH, 0.5),
            self._mk("g1", RetrievalPillar.GRAPH, 0.9),
        ]
        ranked = reranker.rerank("q", results, top_k=10)
        # 同 pillar 按 doc_id 稳定序（g1 在 g2 前）
        assert [r.doc_id for r in ranked] == ["g1", "g2"]
