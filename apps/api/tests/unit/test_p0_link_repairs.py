"""P0 断链修复的成功路径回归测试（圆桌结论·代码实证版 QA 门禁）。

背景：ODAP 的核心问题不是"没写功能"，而是"写了但大面积断链"——被静默 bug +
测试盲区 + 谎报健康检查掩盖成伪绿灯。本文件为已修复的 P0 断链绑定**成功路径断言**，
作为变异测试锚点：一旦有人回退修复（改错方法名 / 改错签名 / 重新缩进成死代码），
这些测试必须变红。

覆盖：
- D1  GraphRetriever：死函数复位 + neighbors/traverse 委托 _search_cypher + validate 生效
- D5  GraphWriteStep：add_entity(entity_id, entity_type, properties) / add_relationship(..., relationship=...)
- D5  ProvenanceLinker：get_provenance(entity_id)->Optional[Dict]（非幻影 get_by_entity_id）
- 健康检查 /retrieval/pillars：如实反映 GraphManager.mode，不再谎报

规则（AGENTS.md）：
- Mock 外部服务（GraphManager / ProvenanceTracker / sqlite_client），不 mock 被测逻辑本身
- async 测试用 pytest.mark.asyncio
"""

import pytest
from unittest.mock import MagicMock, patch


# ── D1：GraphRetriever 成功路径 ──────────────────────────────────────

class TestGraphRetrieverSuccessPath:
    """D1：graph 支柱曾是死代码（转换函数被缩进进模块函数、get_neighbors 传名字恒空）。

    修复后 neighbors/traverse 委托 _search_cypher，用确定性模板按名字查询，
    经 validate() 白名单校验后执行，并把记录转换为 RetrievalResult。
    """

    def _fake_gm(self, records):
        gm = MagicMock()
        gm.execute_cypher = MagicMock(return_value=records)
        return gm

    def test_neighbors_mode_returns_graph_results(self):
        from odap.biz.data.qa.retrieval.graph_retriever import GraphRetriever

        records = [
            {"n": {"name": "Alice"}, "rel_type": "knows", "m": {"name": "Bob"}},
        ]
        gm = self._fake_gm(records)
        retriever = GraphRetriever(graph_manager=gm)

        results = retriever.search("查询Alice的关联", top_k=5, mode="neighbors")

        assert len(results) == 1
        assert results[0].pillar == "graph"
        assert results[0].source == "cypher"
        assert "Alice" in results[0].content
        # 成功路径必须真正执行了 Cypher（证明不是恒返回 []）
        gm.execute_cypher.assert_called_once()

    def test_traverse_mode_delegates_to_cypher(self):
        from odap.biz.data.qa.retrieval.graph_retriever import GraphRetriever

        gm = self._fake_gm([{"n": {"name": "北斗"}, "rel_type": "uses", "m": {"name": "卫星"}}])
        retriever = GraphRetriever(graph_manager=gm)

        # traverse 关键词触发 _search_traverse → 委托 _search_cypher
        results = retriever.search("北斗的路径", top_k=5, mode="traverse")

        assert len(results) == 1
        assert results[0].pillar == "graph"
        gm.execute_cypher.assert_called_once()

    def test_no_graph_manager_returns_empty(self):
        from odap.biz.data.qa.retrieval.graph_retriever import GraphRetriever

        retriever = GraphRetriever(graph_manager=None)
        assert retriever.search("查询Alice的关联", mode="neighbors") == []


# ── D5：GraphWriteStep 签名修复成功路径 ──────────────────────────────

class TestGraphWriteStepSuccessPath:
    """D5：GraphWriteStep 曾是唯一给边赋溯源 ID 的设计，但签名错误使每次写入 TypeError
    被逐条吞进 result.errors。修复后节点/边真实写入并携带 batch_id/pipeline_run_id。
    """

    @pytest.mark.asyncio
    async def test_execute_writes_nodes_and_edges_with_correct_signatures(self):
        from odap.biz.core.ontology.construction.pipeline.services.step_handlers.graph_write import (
            GraphWriteStep,
        )

        fake_gm = MagicMock()
        fake_gm.add_entity = MagicMock(return_value=True)
        fake_gm.add_relationship = MagicMock(return_value=True)

        entities = [
            {"id": "e1", "entity_type": "Person", "name": "Alice", "properties": {}},
        ]
        relations = [
            {
                "id": "r1",
                "relation_type": "knows",
                "source_entity_id": "e1",
                "target_entity_id": "e2",
                "properties": {},
            },
        ]

        with patch(
            "odap.infra.graph.graph_service.GraphManager", return_value=fake_gm
        ):
            step = GraphWriteStep()
            result = await step.execute(
                entities=entities,
                relations=relations,
                pipeline_run_id="run_1",
                workspace_id="ws_1",
            )

        # 成功路径：无错误、节点与边各写入 1
        assert result.is_success, f"unexpected errors: {result.errors}"
        assert result.nodes_written == 1
        assert result.edges_written == 1
        assert result.node_ids == ["e1"]
        assert result.edge_ids == ["r1"]

        # add_entity 真实签名 (entity_id, entity_type, properties)，name 合入 properties
        fake_gm.add_entity.assert_called_once()
        ekw = fake_gm.add_entity.call_args.kwargs
        assert ekw["entity_id"] == "e1"
        assert ekw["entity_type"] == "Person"
        assert ekw["properties"]["name"] == "Alice"
        # 溯源字段随节点落图
        assert ekw["properties"]["batch_id"] == result.batch_id
        assert ekw["properties"]["pipeline_run_id"] == "run_1"
        assert "transaction_time" in ekw["properties"]

        # add_relationship 真实参数名是 relationship（不是 relationship_type）
        fake_gm.add_relationship.assert_called_once()
        rkw = fake_gm.add_relationship.call_args.kwargs
        assert rkw["source_id"] == "e1"
        assert rkw["target_id"] == "e2"
        assert rkw["relationship"] == "knows"
        # 边级溯源 ID 真实落图（这正是修复前从未生效的部分）
        assert rkw["properties"]["batch_id"] == result.batch_id
        assert rkw["properties"]["pipeline_run_id"] == "run_1"


# ── D5：ProvenanceLinker 成功路径 ────────────────────────────────────

class TestProvenanceLinkerSuccessPath:
    """D5：ProvenanceLinker 曾调用不存在的 get_by_entity_id，AttributeError 被静默吞掉，
    4级溯源链永远返回空壳。修复后改用真实的 get_provenance(entity_id)->Optional[Dict]。
    """

    def test_link_chain_populates_all_levels(self):
        from odap.biz.core.ontology.construction.provenance.provenance_linker import (
            ProvenanceLinker,
        )

        fake_tracker = MagicMock()
        fake_tracker.get_provenance.return_value = {
            "entity_id": "e1",
            "entity_type": "Person",
            "entity_name": "Alice",
            "pipeline_run_id": "run_1",
            "step": "graph_write",
            "batch_id": "b1",
            "source_doc_id": "doc_1",
            "extraction_method": "HE",
            "confidence_score": 0.9,
            "session_id": "s1",
            "source_template": "t1",
        }

        fake_store = MagicMock()
        fake_store.find_document_by_id.return_value = {
            "doc_id": "doc_1",
            "title": "来源文档",
            "file_type": "pdf",
            "content": "Alice 是一名工程师……",
            "file_url": "http://example.com/doc_1",
        }

        with patch(
            "odap.biz.data.hyper_extract.impl.provenance_tracker.ProvenanceTracker",
            return_value=fake_tracker,
        ), patch(
            "odap.biz.data.knowledge_base.storage.sqlite_kb_storage.SQLiteKnowledgeBaseStorage",
            return_value=fake_store,
        ):
            linker = ProvenanceLinker()
            chain = linker.link_chain("e1")

        # 证明真实调用了 get_provenance（而非幻影 get_by_entity_id）
        fake_tracker.get_provenance.assert_called()
        # Level 0 走真实 KB 存储 find_document_by_id（而非幻影 get_sqlite_client）
        fake_store.find_document_by_id.assert_called_once_with("doc_1")
        # Level 2 构建 + Level 1 提取 + Level 0 文档全部填充
        assert chain.graph_entity_type == "Person"
        assert chain.build_pipeline_run_id == "run_1"
        assert chain.extraction_method == "HE"
        assert chain.extraction_confidence == 0.9
        assert chain.source_document_id == "doc_1"
        assert chain.source_document_name == "来源文档"
        assert chain.is_complete() is True


# ── 健康检查 /retrieval/pillars 如实探针 ─────────────────────────────

class TestPillarHealthCheckHonesty:
    """健康检查曾调用不存在的 GraphManager.is_available()（恒 AttributeError → 谎报），
    且 bm25 硬编码 available。修复后按真实 mode 属性如实报告。
    """

    @pytest.mark.asyncio
    async def test_reports_unavailable_when_graph_disconnected(self):
        from odap.biz.data.qa.api.nl_routes import get_pillar_status

        fake_gm = MagicMock()
        fake_gm.mode = "unavailable"
        with patch(
            "odap.infra.graph.graph_service.GraphManager", return_value=fake_gm
        ):
            resp = await get_pillar_status(user=None)

        status = {p["name"]: p["status"] for p in resp.pillars}
        assert status["graph"] == "unavailable"
        assert status["vector"] == "unavailable"
        assert resp.index_info["graph_connected"] is False
        assert resp.index_info["graph_mode"] == "unavailable"

    @pytest.mark.asyncio
    async def test_reports_available_when_graph_connected(self):
        from odap.biz.data.qa.api.nl_routes import get_pillar_status

        fake_gm = MagicMock()
        fake_gm.mode = "neo4j_driver"
        with patch(
            "odap.infra.graph.graph_service.GraphManager", return_value=fake_gm
        ):
            resp = await get_pillar_status(user=None)

        status = {p["name"]: p["status"] for p in resp.pillars}
        assert status["graph"] == "available"
        assert status["vector"] == "available"
        assert resp.index_info["graph_connected"] is True
        assert resp.index_info["graph_mode"] == "neo4j_driver"

    @pytest.mark.asyncio
    async def test_fallback_mode_is_not_reported_available(self):
        """fallback（NetworkX 内存降级）不算真实图连接，不应谎报 available。"""
        from odap.biz.data.qa.api.nl_routes import get_pillar_status

        fake_gm = MagicMock()
        fake_gm.mode = "fallback"
        with patch(
            "odap.infra.graph.graph_service.GraphManager", return_value=fake_gm
        ):
            resp = await get_pillar_status(user=None)

        status = {p["name"]: p["status"] for p in resp.pillars}
        assert status["graph"] == "unavailable"
        assert status["vector"] == "unavailable"
