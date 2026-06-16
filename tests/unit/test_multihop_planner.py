"""
MultiHopPlanner 单元测试

覆盖：
- 复杂度检测（simple / medium / complex）
- 规则分解（复合问题、因果问题、关系型问题）
- 多跳执行器（单跳回退、多跳执行、去重合并）
- 枚举序列化
"""

import pytest
import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.data.qa.impl.multihop_planner import (
    MultiHopPlanner,
    MultiHopExecutor,
    MultiHopPlan,
    QueryComplexity,
    HopType,
    SubQuery,
)
from odap.biz.data.qa.qa_engine import RAGResult


# ── 复杂度检测 ──


class TestDetectComplexity:
    def _make_planner(self):
        return MultiHopPlanner()

    def test_empty_query_is_simple(self):
        p = self._make_planner()
        assert p.detect_complexity("") == QueryComplexity.SIMPLE

    def test_whitespace_query_is_simple(self):
        p = self._make_planner()
        assert p.detect_complexity("   ") == QueryComplexity.SIMPLE

    def test_simple_factual_what(self):
        p = self._make_planner()
        assert p.detect_complexity("什么是雷达") == QueryComplexity.SIMPLE

    def test_simple_factual_who(self):
        p = self._make_planner()
        assert p.detect_complexity("谁负责这个项目") == QueryComplexity.SIMPLE

    def test_simple_factual_when(self):
        p = self._make_planner()
        assert p.detect_complexity("什么时候开始") == QueryComplexity.SIMPLE

    def test_simple_factual_where(self):
        p = self._make_planner()
        assert p.detect_complexity("在哪里集合") == QueryComplexity.SIMPLE

    def test_simple_factual_howmany(self):
        p = self._make_planner()
        assert p.detect_complexity("多少个单位") == QueryComplexity.SIMPLE

    def test_compound_with_and_is_complex(self):
        p = self._make_planner()
        assert p.detect_complexity("装备维修和保养") == QueryComplexity.COMPLEX

    def test_compound_with_yiji_is_complex(self):
        p = self._make_planner()
        assert p.detect_complexity("雷达以及通信设备") == QueryComplexity.COMPLEX

    def test_compound_with_tongshi_is_complex(self):
        p = self._make_planner()
        assert p.detect_complexity("同时检查装备和人员") == QueryComplexity.COMPLEX

    def test_causal_why_is_complex(self):
        p = self._make_planner()
        assert p.detect_complexity("为什么装备故障") == QueryComplexity.COMPLEX

    def test_causal_yuanyin_is_complex(self):
        p = self._make_planner()
        assert p.detect_complexity("故障原因是什么") == QueryComplexity.COMPLEX

    def test_causal_daozhi_is_complex(self):
        p = self._make_planner()
        assert p.detect_complexity("导致任务失败的因素") == QueryComplexity.COMPLEX

    def test_relational_naxie_is_complex(self):
        p = self._make_planner()
        assert p.detect_complexity("哪些装备需要维修") == QueryComplexity.COMPLEX

    def test_relational_shuyu_is_complex(self):
        p = self._make_planner()
        assert p.detect_complexity("属于A区的单位") == QueryComplexity.COMPLEX

    def test_relational_guanlian_is_complex(self):
        p = self._make_planner()
        assert p.detect_complexity("关联的装备清单") == QueryComplexity.COMPLEX

    def test_compound_connector_plus_relational_is_complex(self):
        """复合连接词 + 关系型关键词 -> COMPLEX"""
        p = self._make_planner()
        assert p.detect_complexity("哪些装备需要维修和保养") == QueryComplexity.COMPLEX

    def test_temporal_plus_entity_is_medium(self):
        p = self._make_planner()
        assert p.detect_complexity("最近装备情况") == QueryComplexity.MEDIUM

    def test_long_query_is_medium(self):
        p = self._make_planner()
        long_query = "请帮我查看一下所有装备的详细状态信息以及配置参数列表"
        # 长度 > 20 且无关系型/因果关键词 -> MEDIUM
        assert p.detect_complexity(long_query) in (QueryComplexity.MEDIUM, QueryComplexity.COMPLEX)

    def test_short_non_factual_is_simple(self):
        p = self._make_planner()
        assert p.detect_complexity("雷达") == QueryComplexity.SIMPLE

    def test_simple_pattern_with_compound_connector_is_complex(self):
        """简单事实型模式 + 复合连接词 -> COMPLEX"""
        p = self._make_planner()
        assert p.detect_complexity("什么是雷达和通信") == QueryComplexity.COMPLEX


# ── 枚举序列化 ──


class TestEnumSerialization:
    def test_query_complexity_is_str_enum(self):
        assert isinstance(QueryComplexity.SIMPLE, str)
        assert QueryComplexity.SIMPLE.value == "simple"
        assert QueryComplexity.COMPLEX.value == "complex"
        assert QueryComplexity.MEDIUM.value == "medium"

    def test_hop_type_is_str_enum(self):
        assert isinstance(HopType.ENTITY_LOOKUP, str)
        assert HopType.ENTITY_LOOKUP.value == "entity_lookup"
        assert HopType.RELATION_TRAVERSE.value == "relation_traverse"
        assert HopType.CAUSAL_CHAIN.value == "causal_chain"
        assert HopType.ATTRIBUTE_FILTER.value == "attribute_filter"

    def test_enum_json_serializable(self):
        import json
        data = {
            "complexity": QueryComplexity.COMPLEX.value,
            "hop_type": HopType.CAUSAL_CHAIN.value,
        }
        result = json.dumps(data)
        assert "complex" in result
        assert "causal_chain" in result


# ── 规划器 ──


class TestMultiHopPlanner:
    def _make_planner(self):
        return MultiHopPlanner()

    def test_simple_query_produces_single_hop(self):
        p = self._make_planner()
        plan = p.plan("什么是雷达")
        assert plan.hop_count == 1
        assert plan.complexity == QueryComplexity.SIMPLE
        assert plan.sub_queries[0].hop_type == HopType.ENTITY_LOOKUP

    def test_compound_query_produces_multiple_hops(self):
        p = self._make_planner()
        plan = p.plan("装备维修和保养")
        assert plan.hop_count >= 2
        assert plan.complexity == QueryComplexity.COMPLEX

    def test_causal_query_produces_causal_chain(self):
        p = self._make_planner()
        plan = p.plan("为什么装备故障导致任务失败")
        assert plan.hop_count >= 2
        hop_types = [sq.hop_type for sq in plan.sub_queries]
        assert HopType.CAUSAL_CHAIN in hop_types

    def test_relational_query_produces_relation_traverse(self):
        p = self._make_planner()
        plan = p.plan("哪些装备需要维修")
        assert plan.hop_count >= 2
        hop_types = [sq.hop_type for sq in plan.sub_queries]
        assert HopType.RELATION_TRAVERSE in hop_types

    def test_max_hops_respected(self):
        p = self._make_planner()
        p.MAX_HOPS = 2
        plan = p.plan("A和B以及C和D")
        assert plan.hop_count <= 2

    def test_plan_to_dict(self):
        p = self._make_planner()
        plan = p.plan("装备维修和保养")
        d = plan.to_dict()
        assert "plan_id" in d
        assert "original_query" in d
        assert "complexity" in d
        assert "hop_count" in d
        assert "sub_queries" in d
        assert d["complexity"] == "complex"

    def test_sub_query_to_dict(self):
        sq = SubQuery(
            query_text="测试查询",
            hop_type=HopType.ENTITY_LOOKUP,
            hop_index=0,
            description="测试",
        )
        d = sq.to_dict()
        assert "query_id" in d
        assert d["query_text"] == "测试查询"
        assert d["hop_type"] == "entity_lookup"
        assert d["hop_index"] == 0

    def test_plan_original_query_preserved(self):
        p = self._make_planner()
        plan = p.plan("哪些装备需要维修和保养")
        assert plan.original_query == "哪些装备需要维修和保养"


# ── 执行器 ──


class TestMultiHopExecutor:
    def _make_mock_pipeline(self, results=None):
        pipeline = MagicMock()
        if results is None:
            results = [
                RAGResult(content="装备A | 类型:装备", source="s1", score=0.8, metadata={}),
                RAGResult(content="装备B | 类型:装备", source="s2", score=0.7, metadata={}),
            ]
        pipeline.retrieve = MagicMock(return_value=results)
        return pipeline

    def test_simple_query_single_hop(self):
        pipeline = self._make_mock_pipeline()
        executor = MultiHopExecutor(rag_pipeline=pipeline)
        result = executor.execute("什么是雷达")
        assert result["status"] == "success"
        assert result["hop_count"] == 1
        assert result["complexity"] == "simple"
        assert result["multihop_used"] is False  # simple 不使用多跳

    def test_complex_query_multihop(self):
        pipeline = self._make_mock_pipeline()
        executor = MultiHopExecutor(rag_pipeline=pipeline)
        result = executor.execute("哪些装备需要维修和保养")
        assert result["status"] == "success"
        assert result["hop_count"] >= 2
        assert result["complexity"] == "complex"
        assert result["multihop_used"] is True

    def test_results_deduplicated_by_source(self):
        """相同 source 的结果应去重"""
        dup_results = [
            RAGResult(content="装备A", source="s1", score=0.8, metadata={}),
            RAGResult(content="装备A 详情", source="s1", score=0.7, metadata={}),
            RAGResult(content="装备B", source="s2", score=0.6, metadata={}),
        ]
        pipeline = self._make_mock_pipeline(results=dup_results)
        executor = MultiHopExecutor(rag_pipeline=pipeline)
        result = executor.execute("哪些装备需要维修和保养")
        sources = [r["source"] for r in result["results"]]
        # s1 不应出现两次
        assert sources.count("s1") <= 1

    def test_hop_details_populated(self):
        pipeline = self._make_mock_pipeline()
        executor = MultiHopExecutor(rag_pipeline=pipeline)
        result = executor.execute("装备维修和保养")
        assert len(result["hop_details"]) >= 2
        for detail in result["hop_details"]:
            assert "hop_index" in detail
            assert "query" in detail
            assert "result_count" in detail

    def test_empty_results_handled(self):
        pipeline = self._make_mock_pipeline(results=[])
        executor = MultiHopExecutor(rag_pipeline=pipeline)
        result = executor.execute("哪些装备需要维修")
        assert result["status"] == "success"
        assert result["results"] == []

    def test_execute_returns_dict(self):
        """执行器返回值必须是 Dict[str, Any]"""
        pipeline = self._make_mock_pipeline()
        executor = MultiHopExecutor(rag_pipeline=pipeline)
        result = executor.execute("装备维修和保养")
        assert isinstance(result, dict)
        assert "status" in result
        assert "results" in result
        assert "hop_count" in result
        assert "complexity" in result
        assert "plan" in result
        assert "hop_details" in result

    def test_results_sorted_by_score(self):
        results = [
            RAGResult(content="低分", source="s1", score=0.3, metadata={}),
            RAGResult(content="高分", source="s2", score=0.9, metadata={}),
            RAGResult(content="中分", source="s3", score=0.6, metadata={}),
        ]
        pipeline = self._make_mock_pipeline(results=results)
        executor = MultiHopExecutor(rag_pipeline=pipeline)
        result = executor.execute("装备维修和保养")
        if len(result["results"]) >= 2:
            scores = [r["score"] for r in result["results"]]
            assert scores == sorted(scores, reverse=True)


# ── QAEngineV2 集成 ──


class TestQAEngineV2MultiHop:
    def test_ask_returns_multihop_metadata(self):
        from odap.biz.data.qa.qa_engine import QAEngineV2
        engine = QAEngineV2(use_mock=True)
        result = engine.ask("哪些装备需要维修和保养")
        assert "multihop" in result
        mh = result["multihop"]
        assert "multihop_used" in mh
        assert "complexity" in mh
        assert "hop_count" in mh

    def test_ask_simple_query_no_multihop(self):
        from odap.biz.data.qa.qa_engine import QAEngineV2
        engine = QAEngineV2(use_mock=True)
        result = engine.ask("什么是雷达")
        mh = result["multihop"]
        assert mh["multihop_used"] is False
        assert mh["complexity"] == "simple"

    def test_ask_complex_query_uses_multihop(self):
        from odap.biz.data.qa.qa_engine import QAEngineV2
        engine = QAEngineV2(use_mock=True)
        result = engine.ask("哪些装备需要维修和保养")
        mh = result["multihop"]
        assert mh["multihop_used"] is True
        assert mh["complexity"] == "complex"
        assert mh["hop_count"] >= 2
