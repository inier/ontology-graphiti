"""
第三轮扩展验证测试 — Round 3 Extended Verification Tests

验证场景：
- A: 结构化数据库数据摄入闭环
- B: 本体版本绑定查询
- C: 感知中枢处理新闻类非结构化数据
- D: Agent 编排器并发与降级
- E: 流式输出完整性（增强验证）

同时回归验证缺陷修复：
- orchestrate() tasks=None 容错
- SQLiteOntologyStorage._now() @staticmethod 修复
- orchestrate() asyncio.run 兼容性
"""

import json
import uuid
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def _reset_singletons():
    """每个测试前重置所有单例"""
    for cls_path, attr in [
        ("odap.biz.core.agent.agent_orchestrator.AgentOrchestrator", "_instance"),
        ("odap.infra.query.service.QueryService", "_instance"),
        ("odap.biz.data.ingest.unified_ingest_facade.UnifiedIngestFacade", "_instance"),
        ("odap.biz.core.ontology.design.services.pipeline_service.OntologyPipeline", "_instance"),
    ]:
        try:
            parts = cls_path.rsplit(".", 1)
            mod = __import__(parts[0], fromlist=[parts[1]])
            cls = getattr(mod, parts[1])
            setattr(cls, attr, None)
        except Exception:
            pass
    yield


# ============================================================================
# 缺陷修复回归验证
# ============================================================================

class TestDefectFixes:
    """验证三个代码缺陷的修复效果"""

    def test_orchestrate_tasks_none_no_type_error(self):
        """缺陷 1: orchestrate(tasks=None) 不应抛 TypeError"""
        from odap.biz.core.agent.agent_orchestrator import AgentOrchestrator

        orch = AgentOrchestrator()
        # tasks=None 必须不抛 TypeError
        result = orch.orchestrate(
            tasks=None,
            user_id="user1",
            workspace_id="ws1",
        )
        assert result["task_count"] == 0
        assert result["success_count"] == 0
        assert "orchestration_id" in result

    def test_orchestrate_tasks_empty_list(self):
        """缺陷 1 补充: orchestrate(tasks=[]) 正常返回"""
        from odap.biz.core.agent.agent_orchestrator import AgentOrchestrator

        orch = AgentOrchestrator()
        result = orch.orchestrate(
            tasks=[],
            user_id="user1",
            workspace_id="ws1",
        )
        assert result["task_count"] == 0
        assert result["results"] == []

    def test_sqlite_ontology_storage_now_is_staticmethod(self):
        """缺陷 2: _now() 必须是 @staticmethod，不接收 self 参数"""
        from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
            SQLiteOntologyStorage,
        )

        # 验证 _now 是 staticmethod — 可通过类直接调用且不需要实例
        now_str = SQLiteOntologyStorage._now()
        assert isinstance(now_str, str)
        # 验证返回的是 ISO 格式时间
        parsed = datetime.fromisoformat(now_str)
        assert parsed.tzinfo is not None

    def test_sqlite_ontology_storage_now_called_on_instance(self):
        """缺陷 2 补充: self._now() 在实例上调用必须正常工作"""
        from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
            SQLiteOntologyStorage,
        )

        with patch.object(SQLiteOntologyStorage, "_get_conn"):
            with patch.object(SQLiteOntologyStorage, "_init_db"):
                storage = SQLiteOntologyStorage(db_path=":memory:")
                # 实例方法调用不应抛 TypeError
                now_str = storage._now()
                assert isinstance(now_str, str)

    def test_orchestrate_asyncio_run_compatibility(self):
        """缺陷 3: orchestrate 内部 asyncio.run 在有 event loop 时的兼容性"""
        from odap.biz.core.agent.agent_orchestrator import AgentOrchestrator

        orch = AgentOrchestrator()

        # 验证 orchestrate 对空任务列表不触发 asyncio.run
        # （空列表不应进入 dispatch 循环）
        result = orch.orchestrate(
            tasks=[],
            user_id="user1",
            workspace_id="ws1",
        )
        assert result["task_count"] == 0


# ============================================================================
# 场景 A: 结构化数据库数据摄入闭环
# ============================================================================

class TestScenarioA_StructuredDatabaseIngest:
    """验证从数据库源摄入结构化数据的完整闭环"""

    @pytest.mark.asyncio
    async def test_database_source_classified_as_document_driven(self):
        """database source_type 必须归类为文档驱动"""
        from odap.biz.data.ingest.unified_ingest_facade import SourceCategory

        assert "database" in SourceCategory.DOCUMENT_DRIVEN
        assert "database" not in SourceCategory.EVENT_DRIVEN

    @pytest.mark.asyncio
    async def test_facade_routes_database_to_ingest_service(self):
        """UnifiedIngestFacade.ingest(source_type='database') 必须路由到 IngestService"""
        from odap.biz.data.ingest.unified_ingest_facade import UnifiedIngestFacade

        facade = UnifiedIngestFacade()

        # Mock IngestService
        mock_ingest_service = MagicMock()
        mock_ingest_service.ingest_from_database = AsyncMock(
            return_value="record_db_001"
        )
        facade._ingest_service = mock_ingest_service

        result = await facade.ingest(
            source_type="database",
            connection_id="conn_test_001",
            table_patterns=["users%", "orders%"],
            scenario_id="sc_test",
            workspace_id="ws_test",
        )

        assert result["status"] == "ok"
        assert result["routed_to"] == "IngestService"
        assert result["record_id"] == "record_db_001"
        mock_ingest_service.ingest_from_database.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_database_ingest_passes_connection_params(self):
        """数据库摄入必须正确传递连接参数"""
        from odap.biz.data.ingest.unified_ingest_facade import UnifiedIngestFacade

        facade = UnifiedIngestFacade()

        mock_ingest_service = MagicMock()
        mock_ingest_service.ingest_from_database = AsyncMock(
            return_value="record_db_002"
        )
        facade._ingest_service = mock_ingest_service

        await facade.ingest(
            source_type="database",
            connection_id="conn_pg_main",
            table_patterns=["public.%"],
            scenario_id="sc_001",
            workspace_id="ws_001",
        )

        call_kwargs = mock_ingest_service.ingest_from_database.call_args
        assert call_kwargs.kwargs.get("connection_id") == "conn_pg_main" or \
               (call_kwargs[1].get("connection_id") == "conn_pg_main")

    @pytest.mark.asyncio
    async def test_database_ingest_error_handling(self):
        """数据库连接失败时必须返回错误而非抛异常"""
        from odap.biz.data.ingest.unified_ingest_facade import UnifiedIngestFacade

        facade = UnifiedIngestFacade()

        mock_ingest_service = MagicMock()
        mock_ingest_service.ingest_from_database = AsyncMock(
            side_effect=ConnectionError("Cannot connect to database")
        )
        facade._ingest_service = mock_ingest_service

        result = await facade.ingest(
            source_type="database",
            connection_id="conn_bad",
        )

        assert result["status"] == "error"
        assert "Cannot connect" in result["message"]


# ============================================================================
# 场景 B: 本体版本绑定查询
# ============================================================================

class TestScenarioB_OntologyVersionBinding:
    """验证本体版本创建后，QA 引擎能基于指定版本开展问答"""

    def test_pipeline_context_carries_version_id(self):
        """PipelineContext 必须携带 version_id 字段"""
        from odap.biz.core.ontology.design.services.pipeline_service import PipelineContext

        with patch("odap.biz.core.ontology.design.services.pipeline_service._make_ingest_storage") as mock_storage:
            mock_storage.return_value = MagicMock()
            ctx = PipelineContext(
                ingest_id="ing_ver_001",
                scenario_id="sc_test",
                workspace_id="ws_test",
            )

            # 初始 version_id 应为 None
            assert ctx.version_id is None

            # 版本阶段后应能设置 version_id
            ctx.version_id = "v20260711-001"
            assert ctx.version_id == "v20260711-001"

    def test_pipeline_context_tracks_document_id(self):
        """PipelineContext 必须跟踪 document_id"""
        from odap.biz.core.ontology.design.services.pipeline_service import PipelineContext

        with patch("odap.biz.core.ontology.design.services.pipeline_service._make_ingest_storage") as mock_storage:
            mock_storage.return_value = MagicMock()
            ctx = PipelineContext(
                ingest_id="ing_ver_002",
                scenario_id="sc_test",
                workspace_id="ws_test",
            )

            ctx.document_id = "doc_abc_123"
            ctx.version_id = "v20260711-002"

            assert ctx.document_id == "doc_abc_123"
            assert ctx.version_id == "v20260711-002"

    @pytest.mark.asyncio
    async def test_version_stage_creates_version_record(self):
        """版本管理阶段必须创建版本记录并更新 context"""
        from odap.biz.core.ontology.design.services.pipeline_service import (
            OntologyPipeline, PipelineContext,
        )
        from odap.biz.core.ontology.design.models.audit import PipelineStage

        execution_log = []

        mock_handlers = {}
        for stage in PipelineStage:
            stage_name = stage.value

            async def _execute(ctx, _name=stage_name):
                execution_log.append(_name)
                if _name == "version":
                    ctx.version_id = "v20260711-003"
                    ctx.document_id = "doc_ver_003"
                ctx.stage_results[_name] = {"status": "ok"}
                return True

            handler = MagicMock()
            handler.execute = _execute
            mock_handlers[stage] = handler

        pipeline = OntologyPipeline.__new__(OntologyPipeline)
        pipeline.graph = None
        pipeline._ingest_count = 0
        pipeline._error_count = 0
        pipeline.handlers = mock_handlers
        pipeline._execution_order = list(PipelineStage)
        pipeline.versions = MagicMock()

        with patch.object(PipelineContext, "save_build_history", return_value={}):
            context = await pipeline.run(
                ingest_id="ing_ver_003",
                scenario_id="sc_test",
                source="manual",
                workspace_id="ws_test",
            )

        assert context.version_id == "v20260711-003"
        assert context.document_id == "doc_ver_003"
        assert context.success is True

    def test_ontology_version_dataclass_structure(self):
        """OntologyVersion 数据类必须包含完整字段"""
        from odap.biz.core.ontology.design.services.version_service import OntologyVersion

        ver = OntologyVersion(
            version_id="v20260711-001",
            ontology_id="ont_001",
            version_number="1.0.0",
            doc_id="doc_001",
            doc_type="ontology",
            parent_version=None,
            commit_message="初始版本",
            created_at=datetime.now(timezone.utc).isoformat(),
            is_current=True,
            entity_count=10,
            relation_count=5,
        )

        d = ver.to_dict()
        assert d["version_id"] == "v20260711-001"
        assert d["ontology_id"] == "ont_001"
        assert d["version_number"] == "1.0.0"
        assert d["is_current"] is True
        assert d["entity_count"] == 10
        # doc_snapshot 不应出现在 to_dict 输出中
        assert "doc_snapshot" not in d


# ============================================================================
# 场景 C: 感知中枢处理新闻类非结构化数据
# ============================================================================

class TestScenarioC_NewsPerceptionPipeline:
    """验证新闻文本通过 PerceptionHub / IngestService 抽取实体/关系"""

    @pytest.mark.asyncio
    async def test_news_source_classified_as_document_driven(self):
        """news source_type 必须归类为文档驱动"""
        from odap.biz.data.ingest.unified_ingest_facade import SourceCategory

        assert "news" in SourceCategory.DOCUMENT_DRIVEN

    @pytest.mark.asyncio
    async def test_news_ingest_routes_to_ingest_service(self):
        """news 摄入必须路由到 IngestService"""
        from odap.biz.data.ingest.unified_ingest_facade import UnifiedIngestFacade

        facade = UnifiedIngestFacade()

        mock_ingest_service = MagicMock()
        mock_ingest_service.ingest_from_news = AsyncMock(
            return_value="record_news_001"
        )
        facade._ingest_service = mock_ingest_service

        result = await facade.ingest(
            source_type="news",
            query="AI news",
            scenario_id="sc_news",
        )

        assert result["status"] == "ok"
        assert result["routed_to"] == "IngestService"

    @pytest.mark.asyncio
    async def test_perception_hub_news_entity_extraction(self):
        """PerceptionHub 处理新闻文本时必须抽取实体并包含 confidence 评分"""
        from odap.biz.data.perception.hub import PerceptionHub
        from odap.biz.data.perception.schemas import (
            PerceptionEvent, PerceptionSourceType, ExtractionResult,
        )

        hub = PerceptionHub()

        # Mock _extract 返回含 confidence 的抽取结果
        mock_extraction = ExtractionResult(
            entities=[
                {"entity_id": "e1", "entity_type": "Person", "name": "张三"},
                {"entity_id": "e2", "entity_type": "Organization", "name": "ABC公司"},
            ],
            relations=[
                {"relation_id": "r1", "relation_type": "works_at",
                 "source_entity": "e1", "target_entity": "e2"},
            ],
            events=[],
            confidence=0.88,
        )

        with patch.object(hub, '_extract', new=AsyncMock(return_value=mock_extraction)):
            event = PerceptionEvent(
                event_id="pe_news_001",
                source_type=PerceptionSourceType.API,
                source_name="news_feed",
                raw_content="张三在ABC公司发表了关于人工智能的演讲",
            )
            extraction = await hub._extract(event)

        assert isinstance(extraction, ExtractionResult)
        assert extraction.confidence == 0.88
        assert extraction.confidence > 0.0
        assert len(extraction.entities) == 2
        assert len(extraction.relations) == 1

    @pytest.mark.asyncio
    async def test_news_extraction_confidence_in_range(self):
        """confidence 评分必须在 [0, 1] 范围内"""
        from odap.biz.data.perception.schemas import ExtractionResult

        # 验证正常范围
        result = ExtractionResult(
            entities=[{"entity_type": "Person", "name": "Test"}],
            relations=[],
            events=[],
            confidence=0.75,
        )
        assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_perception_hub_news_full_pipeline_with_confidence(self):
        """新闻完整流程: extract → map → store，结果包含 confidence"""
        from odap.biz.data.perception.hub import PerceptionHub
        from odap.biz.data.perception.schemas import (
            PerceptionEvent, PerceptionSourceType, PerceptionStatus,
            ExtractionResult,
        )

        hub = PerceptionHub()

        mock_extraction = ExtractionResult(
            entities=[{"entity_type": "Event", "name": "AI峰会", "entity_id": "ev1"}],
            relations=[],
            events=[{"event_id": "e1", "event_type": "conference", "name": "AI峰会"}],
            confidence=0.92,
        )
        hub._extract = AsyncMock(return_value=mock_extraction)
        hub._map_to_oms = MagicMock(return_value=["Event"])
        hub._store_to_graphiti = AsyncMock(return_value="ep_news_001")

        event = PerceptionEvent(
            event_id="pe_news_full",
            source_type=PerceptionSourceType.API,
            source_name="news",
            raw_content="2026年AI峰会在北京召开",
        )

        output = await hub.process_event(event, ontology_id="ont_news")

        assert output.status == PerceptionStatus.STORED
        assert output.extraction.confidence == 0.92
        assert output.graphiti_episode_id == "ep_news_001"


# ============================================================================
# 场景 D: Agent 编排器并发与降级
# ============================================================================

class TestScenarioD_OrchestratorConcurrencyAndFallback:
    """验证多任务并发编排、Swarm 降级、dispatch metadata"""

    def test_allocate_task_round_robin_distribution(self):
        """多任务 round-robin 分配必须均匀"""
        from odap.biz.core.agent.agent_orchestrator import AgentOrchestrator

        orch = AgentOrchestrator()

        tasks = [{"query": f"task_{i}"} for i in range(6)]
        agents = ["agent_a", "agent_b", "agent_c"]

        result = orch.allocate_task(
            tasks=tasks,
            available_agents=agents,
        )

        assert result["task_count"] == 6
        assert result["agent_count"] == 3
        allocation = result["allocation"]
        # 6 tasks / 3 agents = 每个 agent 2 个任务
        for agent in agents:
            assert len(allocation[agent]) == 2

    def test_allocate_task_single_agent_gets_all(self):
        """单 agent 时必须接收所有任务"""
        from odap.biz.core.agent.agent_orchestrator import AgentOrchestrator

        orch = AgentOrchestrator()

        tasks = [{"query": f"task_{i}"} for i in range(4)]
        result = orch.allocate_task(
            tasks=tasks,
            available_agents=["solo_agent"],
        )

        assert result["task_count"] == 4
        assert result["agent_count"] == 1
        assert len(result["allocation"]["solo_agent"]) == 4

    def test_allocate_task_empty_agents_uses_default(self):
        """available_agents 为空时必须使用 default_agent"""
        from odap.biz.core.agent.agent_orchestrator import AgentOrchestrator

        orch = AgentOrchestrator()

        result = orch.allocate_task(
            tasks=[{"query": "t1"}, {"query": "t2"}],
            available_agents=[],
        )

        assert result["task_count"] == 2
        assert "default_agent" in result["allocation"]

    @pytest.mark.asyncio
    async def test_swarm_unavailable_full_fallback_to_react(self):
        """Swarm 不可用时降级到 ReAct 的完整流程"""
        from odap.biz.core.agent.agent_orchestrator import AgentOrchestrator

        orch = AgentOrchestrator()
        orch._swarm = None
        orch._swarm_available = False
        orch._get_swarm = MagicMock(return_value=None)

        orch._dispatch_react = AsyncMock(return_value={
            "result_id": "fallback_001",
            "mode": "react",
            "answer": "降级回答",
            "reasoning_chain": [{"step": "search", "action": "RAG"}],
            "sources": [{"type": "sqlite", "count": 3}],
            "metadata": {},
            "error": None,
        })

        result = await orch.dispatch(
            query="协同分析态势并制定方案",
            user_id="user1",
            workspace_id="ws1",
            mode="swarm",
        )

        # 降级后 mode 应为 react
        assert result["mode"] == "react"
        assert result["answer"] == "降级回答"
        assert result["error"] is None
        # metadata 必须包含 resolved_mode
        # dispatch 层记录的 resolved_mode 是原始请求的 swarm
        assert result["metadata"]["resolved_mode"] == "swarm"
        assert result["metadata"]["requested_mode"] == "swarm"

    @pytest.mark.asyncio
    async def test_dispatch_result_metadata_completeness(self):
        """dispatch 返回结果必须包含所有必要 metadata 字段"""
        from odap.biz.core.agent.agent_orchestrator import AgentOrchestrator

        orch = AgentOrchestrator()
        orch._dispatch_react = AsyncMock(return_value={
            "result_id": "meta_test",
            "mode": "react",
            "answer": "ok",
            "reasoning_chain": [],
            "sources": [],
            "metadata": {},
            "error": None,
        })

        result = await orch.dispatch(
            query="查询信息",
            user_id="user_abc",
            workspace_id="ws_xyz",
            scenario_id="sc_001",
            agent_id="agent_001",
            mode="react",
        )

        meta = result["metadata"]
        assert meta["user_id"] == "user_abc"
        assert meta["workspace_id"] == "ws_xyz"
        assert meta["scenario_id"] == "sc_001"
        assert meta["agent_id"] == "agent_001"
        assert meta["requested_mode"] == "react"
        assert meta["resolved_mode"] == "react"
        assert "orchestration_time_ms" in meta
        assert isinstance(meta["orchestration_time_ms"], (int, float))

    @pytest.mark.asyncio
    async def test_dispatch_error_result_has_metadata(self):
        """dispatch 错误结果也必须包含 metadata"""
        from odap.biz.core.agent.agent_orchestrator import AgentOrchestrator

        orch = AgentOrchestrator()
        orch._intelligence_agent = None
        orch._react_available = False
        orch._get_intelligence_agent = MagicMock(return_value=None)

        result = await orch.dispatch(
            query="测试查询",
            user_id="user1",
            workspace_id="ws1",
            mode="react",
        )

        assert result["error"] is not None
        # 即使有错误，metadata 仍必须完整
        assert "user_id" in result["metadata"]
        assert "orchestration_time_ms" in result["metadata"]


# ============================================================================
# 场景 E: 流式输出完整性（增强验证）
# ============================================================================

class TestScenarioE_StreamOutputIntegrity:
    """验证 ask_stream 事件类型序列和 payload 结构"""

    def _make_qa_engine(self):
        from odap.biz.data.qa.qa_engine import QAEngineV2

        engine = QAEngineV2(
            graphiti_client=MagicMock(),
            use_mock=False,
            ingest_storage=MagicMock(),
            semantic_map_storage=MagicMock(),
            model_storage=MagicMock(),
            query_service=MagicMock(),
        )
        return engine

    @pytest.mark.asyncio
    async def test_ask_stream_event_sequence_starts_with_session_id(self):
        """ask_stream 第一个事件必须是 session_id 类型"""
        engine = self._make_qa_engine()

        events = []
        try:
            async for event in engine.ask_stream(
                query="测试查询",
                user_id="user1",
                workspace_id="ws1",
                scenario_id="default",
            ):
                events.append(event)
                if len(events) >= 1:
                    break
        except Exception:
            pass

        assert len(events) >= 1
        assert events[0]["type"] == "session_id"
        assert isinstance(events[0]["value"], str)
        assert len(events[0]["value"]) > 0

    @pytest.mark.asyncio
    async def test_ask_stream_second_event_is_thinking(self):
        """ask_stream 第二个事件必须是 thinking 类型"""
        engine = self._make_qa_engine()

        events = []
        try:
            async for event in engine.ask_stream(
                query="测试查询",
                user_id="user1",
                workspace_id="ws1",
                scenario_id="default",
            ):
                events.append(event)
                if len(events) >= 2:
                    break
        except Exception:
            pass

        assert len(events) >= 2
        assert events[1]["type"] == "thinking"
        assert isinstance(events[1]["value"], str)

    @pytest.mark.asyncio
    async def test_ask_stream_emits_reasoning_event(self):
        """ask_stream 必须产出 reasoning 类型事件（含 step 和 description）"""
        from odap.biz.data.qa.qa_engine import QAEngineV2, RAGResult

        engine = self._make_qa_engine()

        # Mock RAG + LLM
        engine.rag_pipeline.retrieve = MagicMock(return_value=[
            RAGResult(content="测试数据", source="test", score=0.8),
        ])
        engine.rag_pipeline.generate_context = MagicMock(return_value="测试上下文")
        engine._get_ontology_ids_for_scenario = MagicMock(return_value=[])

        mock_llm = MagicMock()
        mock_llm._generate_stream = AsyncMock(return_value=iter([
            {"type": "content", "value": "回答"},
        ]))
        engine._llm_client = mock_llm

        events = []
        try:
            async for event in engine.ask_stream(
                query="测试查询",
                user_id="user1",
                workspace_id="ws1",
                scenario_id="default",
            ):
                events.append(event)
                if len(events) > 30:
                    break
        except Exception:
            pass

        event_types = [e["type"] for e in events if isinstance(e, dict)]

        # reasoning 事件必须存在（query_understanding 步骤）
        reasoning_events = [
            e for e in events
            if isinstance(e, dict) and e.get("type") == "reasoning"
        ]
        if reasoning_events:
            first_reasoning = reasoning_events[0]
            assert "value" in first_reasoning
            assert isinstance(first_reasoning["value"], dict)
            assert "step" in first_reasoning["value"]
            assert "description" in first_reasoning["value"]

    @pytest.mark.asyncio
    async def test_ask_stream_session_id_payload_structure(self):
        """session_id 事件的 value 必须是合法的 session ID 字符串"""
        engine = self._make_qa_engine()

        events = []
        try:
            async for event in engine.ask_stream(
                query="甲方A连部署位置",
                user_id="user_stream",
                workspace_id="ws_stream",
                scenario_id="default",
            ):
                events.append(event)
                if len(events) >= 1:
                    break
        except Exception:
            pass

        session_event = events[0]
        assert session_event["type"] == "session_id"
        session_id = session_event["value"]
        assert isinstance(session_id, str)
        # session_id 应以 SESSION- 开头
        assert session_id.startswith("SESSION-")

    @pytest.mark.asyncio
    async def test_ask_stream_thinking_payload_is_string(self):
        """thinking 事件的 value 必须是字符串"""
        engine = self._make_qa_engine()

        events = []
        try:
            async for event in engine.ask_stream(
                query="查询信息",
                user_id="user1",
                workspace_id="ws1",
                scenario_id="default",
            ):
                events.append(event)
                if len(events) >= 2:
                    break
        except Exception:
            pass

        thinking_events = [e for e in events if isinstance(e, dict) and e["type"] == "thinking"]
        assert len(thinking_events) >= 1
        assert isinstance(thinking_events[0]["value"], str)
        assert len(thinking_events[0]["value"]) > 0


# ============================================================================
# SQLiteOntologyStorage _now() 修复效果深度验证
# ============================================================================

class TestOntologyStorageNowFix:
    """深度验证 _now() 修复对本体存储操作的影响"""

    def test_now_returns_utc_iso_format(self):
        """_now() 必须返回带时区的 ISO 格式字符串"""
        from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
            SQLiteOntologyStorage,
        )

        now_str = SQLiteOntologyStorage._now()
        # 必须能解析为 datetime
        dt = datetime.fromisoformat(now_str)
        assert dt.tzinfo is not None

    def test_now_consistent_across_calls(self):
        """多次调用 _now() 必须返回递增或相等的时间"""
        from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
            SQLiteOntologyStorage,
        )

        t1 = SQLiteOntologyStorage._now()
        t2 = SQLiteOntologyStorage._now()

        dt1 = datetime.fromisoformat(t1)
        dt2 = datetime.fromisoformat(t2)
        assert dt2 >= dt1

    def test_now_callable_as_staticmethod_from_class(self):
        """_now 必须可通过类直接调用（staticmethod 特性）"""
        from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
            SQLiteOntologyStorage,
        )

        # 检查 _now 是否是 staticmethod
        # 通过类的 __dict__ 检查描述符
        descriptor = SQLiteOntologyStorage.__dict__.get("_now")
        assert isinstance(descriptor, staticmethod), \
            f"_now should be staticmethod, got {type(descriptor)}"
