"""NL 本体查询服务单元测试"""

import json
import os
import tempfile

import pytest

# ── Models 测试 ────────────────────────────────────────────────────────


class TestModels:
    """核心数据模型测试"""

    def test_query_intent_enum(self):
        from odap.biz.data.qa.models import QueryIntent
        assert QueryIntent.KEYWORD_LOOKUP.value == "keyword_lookup"
        assert QueryIntent.SEMANTIC_SEARCH.value == "semantic_search"
        assert QueryIntent.GRAPH_TRAVERSE.value == "graph_traverse"
        assert QueryIntent.COMPLEX_ANALYSIS.value == "complex_analysis"
        assert QueryIntent.TEMPORAL_QUERY.value == "temporal_query"
        assert QueryIntent.ACTION.value == "action"

    def test_query_intent_str_enum(self):
        """Enum 必须 (str, Enum) 双继承"""
        from odap.biz.data.qa.models import QueryIntent
        intent = QueryIntent.KEYWORD_LOOKUP
        assert isinstance(intent, str)
        assert intent == "keyword_lookup"

    def test_retrieval_result_default_factory(self):
        """容器字段必须 default_factory"""
        from odap.biz.data.qa.models import RetrievalResult
        r1 = RetrievalResult(doc_id="1", content="test", score=0.5, pillar="bm25", source="test")
        r2 = RetrievalResult(doc_id="2", content="test", score=0.5, pillar="bm25", source="test")
        assert r1.entities is not r2.entities
        assert r1.metadata is not r2.metadata

    def test_query_understanding_defaults(self):
        from odap.biz.data.qa.models import QueryUnderstanding
        u = QueryUnderstanding(original_query="test")
        assert u.intent.value == "semantic_search"
        assert u.extracted_entities == []
        assert u.confidence == 0.0
        assert u.needs_clarification is False

    def test_query_plan_defaults(self):
        from odap.biz.data.qa.models import QueryPlan
        p = QueryPlan()
        assert p.pillars == []
        assert p.sub_queries == []
        assert p.top_k == 10

    def test_query_audit_record_defaults(self):
        from odap.biz.data.qa.models import QueryAuditRecord
        a = QueryAuditRecord()
        assert a.user_id == ""
        assert a.total_time_ms == 0.0
        assert a.pillar_results_count == {}

    def test_query_request_mode_validation(self):
        from odap.biz.data.qa.models import QueryRequest
        r = QueryRequest(query="test", mode="graph")
        assert r.mode == "graph"


# ── BM25 测试 ──────────────────────────────────────────────────────────


class TestBM25Retriever:
    """BM25 检索器测试"""

    def test_tokenize_chinese(self):
        from odap.biz.data.qa.retrieval.bm25_retriever import _tokenize_chinese
        tokens = _tokenize_chinese("孙悟空三打白骨精")
        assert "孙悟" in tokens or "悟空" in tokens
        assert "白骨" in tokens or "骨精" in tokens

    def test_tokenize_english(self):
        from odap.biz.data.qa.retrieval.bm25_retriever import _tokenize_chinese
        tokens = _tokenize_chinese("find WeaponSystem entity")
        assert "weaponsystem" in tokens
        assert "entity" in tokens

    def test_tokenize_mixed(self):
        from odap.biz.data.qa.retrieval.bm25_retriever import _tokenize_chinese
        tokens = _tokenize_chinese("查找孙悟空的关联实体")
        assert len(tokens) > 0

    def test_bm25_index_build_and_search(self, tmp_path):
        """使用真实临时 DB 测试 BM25 索引构建和检索"""
        from odap.biz.data.qa.retrieval.bm25_retriever import BM25IndexManager, BM25Retriever

        index_dir = str(tmp_path / "bm25_indices")
        manager = BM25IndexManager(index_dir=index_dir)

        # 构建索引
        documents = [
            {"doc_id": "1", "content": "孙悟空是齐天大圣", "source": "test"},
            {"doc_id": "2", "content": "猪八戒是天蓬元帅", "source": "test"},
            {"doc_id": "3", "content": "唐僧是取经人", "source": "test"},
            {"doc_id": "4", "content": "沙和尚是卷帘大将", "source": "test"},
        ]
        manager.build_index("ws1", "s1", documents)

        # 检索
        retriever = BM25Retriever(manager)
        results = retriever.search("孙悟空", top_k=3, workspace_id="ws1", scenario_id="s1")
        assert len(results) > 0
        assert results[0].pillar == "bm25"
        assert "孙悟空" in results[0].content

    def test_bm25_index_persistence(self, tmp_path):
        """测试索引持久化到磁盘"""
        from odap.biz.data.qa.retrieval.bm25_retriever import BM25IndexManager

        index_dir = str(tmp_path / "bm25_indices")
        manager1 = BM25IndexManager(index_dir=index_dir)
        documents = [{"doc_id": "1", "content": "测试文档", "source": "test"}]
        manager1.build_index("ws1", None, documents)

        # 新 manager 从磁盘加载
        manager2 = BM25IndexManager(index_dir=index_dir)
        index, corpus = manager2.get_index("ws1", None)
        assert index is not None
        assert len(corpus) == 1

    def test_bm25_empty_query(self, tmp_path):
        from odap.biz.data.qa.retrieval.bm25_retriever import BM25Retriever
        retriever = BM25Retriever()
        results = retriever.search("", workspace_id="ws1")
        assert results == []

    def test_bm25_no_workspace(self, tmp_path):
        from odap.biz.data.qa.retrieval.bm25_retriever import BM25Retriever
        retriever = BM25Retriever()
        results = retriever.search("test", workspace_id="")
        assert results == []


# ── Understanding 测试 ─────────────────────────────────────────────────


class TestUnderstandingStage:
    """查询理解阶段测试"""

    def test_intent_keyword_lookup(self):
        from odap.biz.data.qa.pipeline.understanding.intent_recognizer import IntentRecognizer
        recognizer = IntentRecognizer()
        intent, confidence = recognizer.recognize("查找孙悟空")
        assert intent.value == "keyword_lookup"
        assert confidence > 0

    def test_intent_graph_traverse(self):
        from odap.biz.data.qa.pipeline.understanding.intent_recognizer import IntentRecognizer
        recognizer = IntentRecognizer()
        intent, confidence = recognizer.recognize("孙悟空的关联实体有哪些")
        assert intent.value == "graph_traverse"

    def test_intent_temporal_query(self):
        from odap.biz.data.qa.pipeline.understanding.intent_recognizer import IntentRecognizer
        recognizer = IntentRecognizer()
        intent, confidence = recognizer.recognize("上周发生了什么变化")
        assert intent.value == "temporal_query"

    def test_intent_action(self):
        from odap.biz.data.qa.pipeline.understanding.intent_recognizer import IntentRecognizer
        recognizer = IntentRecognizer()
        intent, confidence = recognizer.recognize("执行模拟演练")
        assert intent.value == "action"

    def test_entity_extract_quoted(self):
        from odap.biz.data.qa.pipeline.understanding.intent_recognizer import EntityExtractor
        extractor = EntityExtractor()
        entities = extractor.extract('查找"孙悟空"的关联实体')
        assert "孙悟空" in entities

    def test_entity_extract_de_pattern(self):
        from odap.biz.data.qa.pipeline.understanding.intent_recognizer import EntityExtractor
        extractor = EntityExtractor()
        entities = extractor.extract("孙悟空的敌人有哪些")
        assert "孙悟空" in entities

    def test_coreference_resolution(self):
        from odap.biz.data.qa.pipeline.understanding.intent_recognizer import EntityExtractor
        extractor = EntityExtractor()
        resolved = extractor.resolve_coreferences("它的属性是什么", ["孙悟空"])
        assert "孙悟空" in resolved
        assert "它" not in resolved

    def test_clarification_too_short(self):
        from odap.biz.data.qa.pipeline.understanding.intent_recognizer import UnderstandingStage
        stage = UnderstandingStage()
        result = stage.analyze("它")
        assert result.needs_clarification is True
        # "它" 同时匹配代词和过短，代词优先检测
        assert result.clarification_reason in ("too_short", "ambiguous_pronoun")

    def test_clarification_ambiguous_pronoun(self):
        from odap.biz.data.qa.pipeline.understanding.intent_recognizer import UnderstandingStage
        stage = UnderstandingStage()
        result = stage.analyze("它的关联关系")
        assert result.needs_clarification is True
        assert result.clarification_reason == "ambiguous_pronoun"

    def test_normal_query_no_clarification(self):
        from odap.biz.data.qa.pipeline.understanding.intent_recognizer import UnderstandingStage
        stage = UnderstandingStage()
        result = stage.analyze("查找孙悟空的关联实体")
        assert result.needs_clarification is False


# ── Planning 测试 ──────────────────────────────────────────────────────


class TestPlanningStage:
    """查询规划阶段测试"""

    def test_keyword_lookup_plan(self):
        from odap.biz.data.qa.models import QueryIntent, QueryUnderstanding
        from odap.biz.data.qa.pipeline.planning.query_planner import PlanningStage
        stage = PlanningStage()
        understanding = QueryUnderstanding(original_query="查找孙悟空", intent=QueryIntent.KEYWORD_LOOKUP)
        plan = stage.create_plan(understanding)
        assert "bm25" in plan.pillars

    def test_semantic_search_plan(self):
        from odap.biz.data.qa.models import QueryIntent, QueryUnderstanding
        from odap.biz.data.qa.pipeline.planning.query_planner import PlanningStage
        stage = PlanningStage()
        understanding = QueryUnderstanding(original_query="什么是齐天大圣", intent=QueryIntent.SEMANTIC_SEARCH)
        plan = stage.create_plan(understanding)
        assert "vector" in plan.pillars

    def test_complex_analysis_plan(self):
        from odap.biz.data.qa.models import QueryIntent, QueryUnderstanding
        from odap.biz.data.qa.pipeline.planning.query_planner import PlanningStage
        stage = PlanningStage()
        understanding = QueryUnderstanding(original_query="分析对比", intent=QueryIntent.COMPLEX_ANALYSIS)
        plan = stage.create_plan(understanding)
        assert len(plan.pillars) == 3  # bm25 + vector + graph

    def test_manual_mode_keyword(self):
        from odap.biz.data.qa.models import QueryUnderstanding
        from odap.biz.data.qa.pipeline.planning.query_planner import PlanningStage
        stage = PlanningStage()
        understanding = QueryUnderstanding(original_query="test")
        plan = stage.create_plan(understanding, constraints={"mode": "keyword"})
        assert plan.pillars == ["bm25"]

    def test_manual_mode_graph(self):
        from odap.biz.data.qa.models import QueryUnderstanding
        from odap.biz.data.qa.pipeline.planning.query_planner import PlanningStage
        stage = PlanningStage()
        understanding = QueryUnderstanding(original_query="test")
        plan = stage.create_plan(understanding, constraints={"mode": "graph"})
        assert plan.pillars == ["graph"]


# ── Fusion 测试 ────────────────────────────────────────────────────────


class TestFusionStage:
    """结果融合阶段测试"""

    def _make_results(self):
        from odap.biz.data.qa.models import RetrievalResult, RetrievalResultSet
        results = [
            RetrievalResult(doc_id="1", content="doc1", score=0.9, pillar="bm25", source="test"),
            RetrievalResult(doc_id="2", content="doc2", score=0.8, pillar="vector", source="test"),
            RetrievalResult(doc_id="3", content="doc3", score=0.7, pillar="graph", source="test"),
            RetrievalResult(doc_id="4", content="doc4", score=0.6, pillar="bm25", source="test"),
        ]
        return RetrievalResultSet(results=results)

    def test_weighted_fusion(self):
        from odap.biz.data.qa.models import FusionStrategy
        from odap.biz.data.qa.pipeline.fusion.result_fuser import FusionStage
        stage = FusionStage()
        result_set = self._make_results()
        fused = stage.merge_and_rerank(result_set, "test", fusion_strategy=FusionStrategy.WEIGHTED, top_k=3)
        assert len(fused.results) <= 3
        assert fused.results[0].score >= fused.results[-1].score

    def test_rrf_fusion(self):
        from odap.biz.data.qa.models import FusionStrategy
        from odap.biz.data.qa.pipeline.fusion.result_fuser import FusionStage
        stage = FusionStage()
        result_set = self._make_results()
        fused = stage.merge_and_rerank(result_set, "test", fusion_strategy=FusionStrategy.RRF, top_k=3)
        assert len(fused.results) <= 3

    def test_cascade_fusion(self):
        from odap.biz.data.qa.models import FusionStrategy
        from odap.biz.data.qa.pipeline.fusion.result_fuser import FusionStage
        stage = FusionStage()
        result_set = self._make_results()
        fused = stage.merge_and_rerank(result_set, "test", fusion_strategy=FusionStrategy.CASCADE, top_k=2)
        assert len(fused.results) <= 2

    def test_empty_results(self):
        from odap.biz.data.qa.models import FusionStrategy, RetrievalResultSet
        from odap.biz.data.qa.pipeline.fusion.result_fuser import FusionStage
        stage = FusionStage()
        result_set = RetrievalResultSet()
        fused = stage.merge_and_rerank(result_set, "test", fusion_strategy=FusionStrategy.WEIGHTED)
        assert len(fused.results) == 0


# ── CypherGenerator 测试 ──────────────────────────────────────────────


class TestCypherGenerator:
    """Cypher 生成器测试"""

    def test_validate_safe_cypher(self):
        from odap.biz.data.qa.retrieval.graph_retriever import CypherGenerator
        gen = CypherGenerator()
        assert gen.validate("MATCH (n) RETURN n LIMIT 10") is True

    def test_validate_dangerous_cypher(self):
        from odap.biz.data.qa.retrieval.graph_retriever import CypherGenerator
        gen = CypherGenerator()
        assert gen.validate("CREATE (n:Test) RETURN n") is False
        assert gen.validate("MATCH (n) DELETE n") is False
        assert gen.validate("MATCH (n) SET n.name = 'hack'") is False

    def test_validate_empty(self):
        from odap.biz.data.qa.retrieval.graph_retriever import CypherGenerator
        gen = CypherGenerator()
        assert gen.validate("") is False
        assert gen.validate("   ") is False

    def test_validate_no_match(self):
        from odap.biz.data.qa.retrieval.graph_retriever import CypherGenerator
        gen = CypherGenerator()
        assert gen.validate("RETURN 1") is False


# ── AuditStorage 测试 ──────────────────────────────────────────────────


class TestQueryAuditStorage:
    """审计存储测试（使用 tmp_path 真实 DB）"""

    def test_save_and_get(self, tmp_path):
        from odap.biz.data.qa.evaluation.audit_storage import QueryAuditStorage
        from odap.biz.data.qa.models import QueryAuditRecord

        db_path = str(tmp_path / "audit.db")
        storage = QueryAuditStorage(db_path=db_path)

        record = QueryAuditRecord(
            user_id="user1",
            workspace_id="ws1",
            original_query="查找孙悟空",
            intent="keyword_lookup",
            extracted_entities=["孙悟空"],
            total_time_ms=150.0,
        )
        storage.save(record)

        retrieved = storage.get(record.query_id)
        assert retrieved is not None
        assert retrieved["user_id"] == "user1"
        assert retrieved["original_query"] == "查找孙悟空"
        assert retrieved["intent"] == "keyword_lookup"
        assert retrieved["extracted_entities"] == ["孙悟空"]

    def test_list_records(self, tmp_path):
        from odap.biz.data.qa.evaluation.audit_storage import QueryAuditStorage
        from odap.biz.data.qa.models import QueryAuditRecord

        db_path = str(tmp_path / "audit.db")
        storage = QueryAuditStorage(db_path=db_path)

        for i in range(3):
            record = QueryAuditRecord(
                user_id=f"user{i}",
                workspace_id="ws1",
                original_query=f"query{i}",
            )
            storage.save(record)

        records = storage.list_records(workspace_id="ws1")
        assert len(records) == 3

    def test_get_stats(self, tmp_path):
        from odap.biz.data.qa.evaluation.audit_storage import QueryAuditStorage
        from odap.biz.data.qa.models import QueryAuditRecord

        db_path = str(tmp_path / "audit.db")
        storage = QueryAuditStorage(db_path=db_path)

        record = QueryAuditRecord(
            workspace_id="ws1",
            original_query="test",
            selected_pillars=["bm25", "vector"],
            total_time_ms=100.0,
        )
        storage.save(record)

        stats = storage.get_stats("ws1")
        assert stats["total_queries"] == 1
        assert stats["pillar_usage"]["bm25"] == 1

    def test_get_nonexistent(self, tmp_path):
        from odap.biz.data.qa.evaluation.audit_storage import QueryAuditStorage
        storage = QueryAuditStorage(db_path=str(tmp_path / "audit.db"))
        assert storage.get("nonexistent") is None


# ── QueryPipeline 集成测试 ─────────────────────────────────────────────


class TestQueryPipelineIntegration:
    """QueryPipeline 集成测试（无外部依赖）"""

    @pytest.mark.asyncio
    async def test_explain(self):
        from odap.biz.data.qa.models import QueryRequest
        from odap.biz.data.qa.pipeline.query_pipeline import QueryPipeline

        pipeline = QueryPipeline()
        request = QueryRequest(query="查找孙悟空的关联实体", mode="auto")
        explanation = pipeline.explain(request)
        assert explanation["original_query"] == "查找孙悟空的关联实体"
        assert "understanding" in explanation
        assert "plan" in explanation
        assert explanation["understanding"]["intent"] == "graph_traverse"

    @pytest.mark.asyncio
    async def test_search_empty(self):
        """无数据时检索返回空结果"""
        from odap.biz.data.qa.models import QueryRequest
        from odap.biz.data.qa.pipeline.query_pipeline import QueryPipeline

        pipeline = QueryPipeline()
        request = QueryRequest(query="查找孙悟空", workspace_id="nonexistent")
        result_set = await pipeline.search(request)
        # 无数据时结果为空（BM25 无索引、Vector/Graph 无连接）
        assert result_set.results is not None

    @pytest.mark.asyncio
    async def test_query_clarification(self):
        """短查询触发澄清"""
        from odap.biz.data.qa.models import QueryRequest
        from odap.biz.data.qa.pipeline.query_pipeline import QueryPipeline

        pipeline = QueryPipeline()
        request = QueryRequest(query="它")
        response = await pipeline.query(request)
        assert "抱歉" in response.answer or "请" in response.answer


# ── LLM Client 测试 ────────────────────────────────────────────────────


class TestNLQueryLLMClient:
    """LLM 客户端测试"""

    def test_mock_llm_client(self):
        from odap.biz.data.qa.pipeline.llm_client import MockLLMClient
        client = MockLLMClient(responses={"意图": "keyword_lookup", "Cypher": "MATCH (n) RETURN n"})
        assert client.is_available()
        result = client.generate("请分类意图")
        assert result == "keyword_lookup"

    def test_mock_llm_client_no_match(self):
        from odap.biz.data.qa.pipeline.llm_client import MockLLMClient
        client = MockLLMClient()
        result = client.generate("unmatched prompt")
        assert result is None

    def test_mock_llm_client_call_count(self):
        from odap.biz.data.qa.pipeline.llm_client import MockLLMClient
        client = MockLLMClient(responses={"test": "response"})
        client.generate("test")
        client.generate("test")
        assert client.call_count == 2


# ── Evaluation 测试 ────────────────────────────────────────────────────


class TestEvaluation:
    """评估体系测试"""

    def test_retrieval_evaluator_mrr(self):
        from odap.biz.data.qa.evaluation.benchmark import RetrievalEvaluator
        evaluator = RetrievalEvaluator()
        results = [{"doc_id": "3"}, {"doc_id": "1"}, {"doc_id": "2"}]
        metrics = evaluator.evaluate(results, ["1"], k=10)
        assert metrics.mrr == 0.5  # rank 2 → 1/2

    def test_retrieval_evaluator_perfect(self):
        from odap.biz.data.qa.evaluation.benchmark import RetrievalEvaluator
        evaluator = RetrievalEvaluator()
        results = [{"doc_id": "1"}, {"doc_id": "2"}]
        metrics = evaluator.evaluate(results, ["1"], k=10)
        assert metrics.mrr == 1.0  # rank 1 → 1/1
        assert metrics.recall_at_k == 1.0

    def test_retrieval_evaluator_no_relevant(self):
        from odap.biz.data.qa.evaluation.benchmark import RetrievalEvaluator
        evaluator = RetrievalEvaluator()
        results = [{"doc_id": "3"}, {"doc_id": "4"}]
        metrics = evaluator.evaluate(results, ["1", "2"], k=10)
        assert metrics.mrr == 0.0
        assert metrics.recall_at_k == 0.0

    def test_qa_evaluator_exact_match(self):
        from odap.biz.data.qa.evaluation.benchmark import QAEvaluator
        evaluator = QAEvaluator()
        metrics = evaluator.evaluate("孙悟空是齐天大圣", "孙悟空是齐天大圣")
        assert metrics.exact_match == 1.0

    def test_qa_evaluator_no_match(self):
        from odap.biz.data.qa.evaluation.benchmark import QAEvaluator
        evaluator = QAEvaluator()
        metrics = evaluator.evaluate("猪八戒", "孙悟空")
        assert metrics.exact_match == 0.0

    def test_qa_evaluator_faithfulness(self):
        from odap.biz.data.qa.evaluation.benchmark import QAEvaluator
        evaluator = QAEvaluator()
        sources = [{"content": "孙悟空是齐天大圣"}]
        metrics = evaluator.evaluate("孙悟空", "孙悟空是齐天大圣", sources)
        assert metrics.faithfulness > 0

    def test_default_benchmark(self):
        from odap.biz.data.qa.evaluation.benchmark import get_default_benchmark
        dataset = get_default_benchmark()
        assert dataset.name == "default_nl_query_benchmark"
        assert len(dataset.cases) > 0

    @pytest.mark.asyncio
    async def test_benchmark_runner(self):
        from odap.biz.data.qa.evaluation.benchmark import BenchmarkRunner, BenchmarkDataset, BenchmarkCase
        from odap.biz.data.qa.pipeline.llm_client import MockLLMClient
        from odap.biz.data.qa.pipeline.query_pipeline import QueryPipeline

        pipeline = QueryPipeline(llm_client=MockLLMClient())
        runner = BenchmarkRunner(pipeline)
        dataset = BenchmarkDataset(
            name="test",
            cases=[
                BenchmarkCase(query="查找孙悟空", expected_intent="keyword_lookup"),
                BenchmarkCase(query="它", expected_intent="keyword_lookup"),
            ]
        )
        report = await runner.run(dataset)
        assert report.total_cases == 2
        assert report.dataset_name == "test"
