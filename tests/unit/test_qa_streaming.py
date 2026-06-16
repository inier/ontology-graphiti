"""
QA 引擎流式问答与相关性阈值测试

覆盖:
- TestStreamingEvents: 流式事件类型顺序与内容
- TestStreamingClarification: 流式模式下的澄清机制
- TestStreamingMultihop: 流式模式下的多跳检索
- TestRelevanceThreshold: RAG 相关性硬阈值过滤
"""

import os
import pytest
import sys
from unittest.mock import MagicMock, patch, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.data.qa.qa_engine import (
    QAEngineV2, RAGResult, RAGPipeline, DialogState,
)


# ── 辅助工具 ──


def _make_rag_result(content: str, source: str = "src", score: float = 0.8,
                     metadata: dict = None) -> RAGResult:
    """工厂函数：快速构造 RAGResult"""
    return RAGResult(content=content, source=source, score=score,
                     metadata=metadata or {})


def _make_engine_with_rag(rag_results, use_mock: bool = True):
    """构造 QAEngineV2 并 mock RAG pipeline 返回指定结果"""
    engine = QAEngineV2(use_mock=use_mock)
    engine.rag_pipeline.retrieve = MagicMock(return_value=rag_results)
    engine.rag_pipeline.generate_context = MagicMock(
        return_value="\n".join(r.content for r in rag_results) if rag_results else "未找到相关信息。"
    )
    return engine


async def _collect_stream(engine, query: str, **kwargs):
    """收集 ask_stream 的所有事件"""
    events = []
    async for event in engine.ask_stream(query, user_id="test", **kwargs):
        events.append(event)
    return events


# ── TestStreamingEvents ──


class TestStreamingEvents:
    """测试 ask_stream 产生的事件类型与顺序"""

    @pytest.mark.asyncio
    async def test_session_id_is_first_event(self):
        """session_id 事件必须是第一个"""
        engine = _make_engine_with_rag([_make_rag_result("实体A", score=0.8)])
        events = await _collect_stream(engine, "实体A是什么")
        assert len(events) >= 2
        assert events[0]["type"] == "session_id"
        assert events[0]["value"] is not None
        assert isinstance(events[0]["value"], str)

    @pytest.mark.asyncio
    async def test_thinking_events_present(self):
        """流式输出中应包含 thinking 事件"""
        engine = _make_engine_with_rag([_make_rag_result("实体A", score=0.8)])
        events = await _collect_stream(engine, "实体A是什么")
        thinking_events = [e for e in events if e["type"] == "thinking"]
        assert len(thinking_events) >= 1
        # 至少包含 "正在检索相关知识..." 和 "正在生成回答..."
        thinking_values = [e["value"] for e in thinking_events]
        assert any("检索" in v for v in thinking_values)

    @pytest.mark.asyncio
    async def test_sources_event_contains_source_data(self):
        """sources 事件应包含检索来源数据"""
        results = [
            _make_rag_result("实体A | 类型:人物", source="s1", score=0.9),
            _make_rag_result("实体B | 类型:事件", source="s2", score=0.7),
        ]
        engine = _make_engine_with_rag(results)
        events = await _collect_stream(engine, "实体A是什么")
        sources_events = [e for e in events if e["type"] == "sources"]
        assert len(sources_events) >= 1
        sources_value = sources_events[0]["value"]
        assert isinstance(sources_value, list)
        assert len(sources_value) >= 1
        # 每条来源应包含 source, excerpt, confidence
        for src in sources_value:
            assert "source" in src
            assert "excerpt" in src
            assert "confidence" in src

    @pytest.mark.asyncio
    async def test_content_events_contain_text(self):
        """content 事件应包含文本内容"""
        engine = _make_engine_with_rag([_make_rag_result("实体A", score=0.8)])
        events = await _collect_stream(engine, "实体A是什么")
        content_events = [e for e in events if e["type"] == "content"]
        assert len(content_events) >= 1
        # 合并所有 content 应为非空字符串
        full_content = "".join(e["value"] for e in content_events)
        assert len(full_content) > 0

    @pytest.mark.asyncio
    async def test_end_event_is_last(self):
        """end 事件必须是最后一个"""
        engine = _make_engine_with_rag([_make_rag_result("实体A", score=0.8)])
        events = await _collect_stream(engine, "实体A是什么")
        assert events[-1]["type"] == "end"
        assert "session_id" in events[-1]["value"]

    @pytest.mark.asyncio
    async def test_reasoning_events_present_with_cot(self):
        """当 CoT 可用时，应包含 reasoning 事件"""
        engine = _make_engine_with_rag([_make_rag_result("实体A", score=0.8)])
        with patch("odap.biz.data.qa.qa_engine._COT_AVAILABLE", True), \
             patch("odap.biz.data.qa.qa_engine.CoTBuilder") as MockCoTBuilder, \
             patch("odap.biz.data.qa.qa_engine.CoTNodeType"):
            # 构造 mock CoT builder
            mock_builder = MagicMock()
            mock_root = MagicMock()
            mock_root.id = "root-1"
            mock_builder.start.return_value = mock_root
            mock_builder.add_child.return_value = MagicMock(
                id="child-1", metadata={}, timing=None
            )
            mock_builder.get_tree.return_value = MagicMock(nodes={})
            MockCoTBuilder.return_value = mock_builder

            # 重新启用 CoT
            engine._cot_enabled = True

            events = await _collect_stream(engine, "实体A是什么")
            reasoning_events = [e for e in events if e["type"] == "reasoning"]
            # CoT 集成应产生 reasoning 事件
            assert len(reasoning_events) >= 1
            # 每条 reasoning 事件应包含 step 和 description
            for re_event in reasoning_events:
                assert "step" in re_event["value"]
                assert "description" in re_event["value"]


# ── TestStreamingClarification ──


class TestStreamingClarification:
    """测试流式模式下的澄清机制"""

    @pytest.mark.asyncio
    async def test_no_rag_results_yields_clarification(self):
        """RAG 返回空结果时，应产生 clarification 事件"""
        engine = _make_engine_with_rag([])
        events = await _collect_stream(engine, "模糊问题")
        clarification_events = [e for e in events if e["type"] == "clarification"]
        assert len(clarification_events) == 1

    @pytest.mark.asyncio
    async def test_clarification_event_contains_questions(self):
        """clarification 事件应包含 questions 列表"""
        engine = _make_engine_with_rag([])
        events = await _collect_stream(engine, "模糊问题")
        clarification_events = [e for e in events if e["type"] == "clarification"]
        assert len(clarification_events) == 1
        value = clarification_events[0]["value"]
        assert "questions" in value
        assert isinstance(value["questions"], list)
        assert len(value["questions"]) >= 1

    @pytest.mark.asyncio
    async def test_end_event_has_waiting_for_clarification_state(self):
        """澄清时 end 事件应包含 waiting_for_clarification 状态"""
        engine = _make_engine_with_rag([])
        events = await _collect_stream(engine, "模糊问题")
        end_events = [e for e in events if e["type"] == "end"]
        assert len(end_events) == 1
        assert end_events[0]["value"]["dialog_state"] == "waiting_for_clarification"

    @pytest.mark.asyncio
    async def test_clarification_no_content_events(self):
        """澄清模式下不应产生 content 事件"""
        engine = _make_engine_with_rag([])
        events = await _collect_stream(engine, "模糊问题")
        content_events = [e for e in events if e["type"] == "content"]
        assert len(content_events) == 0


# ── TestStreamingMultihop ──


class TestStreamingMultihop:
    """测试流式模式下的多跳检索"""

    @pytest.mark.asyncio
    async def test_complex_query_triggers_multihop_event(self):
        """复杂查询应触发 multihop 事件"""
        results = [_make_rag_result("结果A", score=0.8)]
        engine = _make_engine_with_rag(results)

        # Mock multihop executor 返回多跳结果
        engine._multihop_executor.execute = MagicMock(return_value={
            "results": [{"content": "结果A", "source": "s1", "score": 0.8, "metadata": {}}],
            "hop_count": 2,
            "hop_details": [
                {"hop_index": 0, "query": "子查询1", "result_count": 3},
                {"hop_index": 1, "query": "子查询2", "result_count": 2},
            ],
            "plan": {"plan_id": "plan-1", "complexity": "complex"},
        })

        # Mock planner 检测为复杂查询
        from odap.biz.data.qa.impl.multihop_planner import QueryComplexity
        engine._multihop_planner.detect_complexity = MagicMock(
            return_value=QueryComplexity.COMPLEX
        )

        events = await _collect_stream(engine, "如果A事件发生会导致B和C怎样变化")
        multihop_events = [e for e in events if e["type"] == "multihop"]
        assert len(multihop_events) == 1
        assert multihop_events[0]["value"]["multihop_used"] is True
        assert multihop_events[0]["value"]["hop_count"] == 2

    @pytest.mark.asyncio
    async def test_simple_query_no_multihop_event(self):
        """简单查询不应触发 multihop 事件"""
        results = [_make_rag_result("实体A", score=0.8)]
        engine = _make_engine_with_rag(results)

        # Mock planner 检测为简单查询
        from odap.biz.data.qa.impl.multihop_planner import QueryComplexity
        engine._multihop_planner.detect_complexity = MagicMock(
            return_value=QueryComplexity.SIMPLE
        )

        events = await _collect_stream(engine, "实体A是什么")
        multihop_events = [e for e in events if e["type"] == "multihop"]
        assert len(multihop_events) == 0


# ── TestRelevanceThreshold ──


class TestRelevanceThreshold:
    """测试 RAG 相关性硬阈值过滤"""

    def test_results_below_threshold_filtered_out(self):
        """分数低于阈值的结果应被过滤"""
        pipeline = RAGPipeline()
        # Mock 所有数据源返回混合分数结果
        pipeline._retrieve_from_graphiti = MagicMock(return_value=[
            _make_rag_result("高分结果", score=0.9),
            _make_rag_result("低分结果1", score=0.03),
            _make_rag_result("低分结果2", score=0.05),
        ])
        pipeline.graphiti = True  # 启用 graphiti 分支

        results = pipeline.retrieve("测试查询", min_score=0.10)
        assert len(results) == 1
        assert results[0].score == 0.9

    def test_results_above_threshold_kept(self):
        """分数高于阈值的结果应保留"""
        pipeline = RAGPipeline()
        pipeline._retrieve_from_graphiti = MagicMock(return_value=[
            _make_rag_result("结果A", score=0.9),
            _make_rag_result("结果B", score=0.5),
            _make_rag_result("结果C", score=0.15),
        ])
        pipeline.graphiti = True

        results = pipeline.retrieve("测试查询", min_score=0.10)
        assert len(results) == 3
        scores = [r.score for r in results]
        assert 0.9 in scores
        assert 0.5 in scores
        assert 0.15 in scores

    def test_default_threshold_is_0_10(self):
        """默认阈值应为 0.10"""
        pipeline = RAGPipeline()
        pipeline._retrieve_from_graphiti = MagicMock(return_value=[
            _make_rag_result("刚好在阈值上", score=0.10),
            _make_rag_result("低于阈值", score=0.09),
        ])
        pipeline.graphiti = True

        # 不传 min_score，使用默认值
        results = pipeline.retrieve("测试查询")
        scores = [r.score for r in results]
        assert 0.10 in scores
        assert 0.09 not in scores

    def test_custom_threshold_from_env_variable(self):
        """通过环境变量 QA_MIN_RELEVANCE_SCORE 设置自定义阈值"""
        pipeline = RAGPipeline()
        pipeline._retrieve_from_graphiti = MagicMock(return_value=[
            _make_rag_result("结果A", score=0.30),
            _make_rag_result("结果B", score=0.20),
            _make_rag_result("结果C", score=0.05),
        ])
        pipeline.graphiti = True

        with patch.dict(os.environ, {"QA_MIN_RELEVANCE_SCORE": "0.25"}):
            results = pipeline.retrieve("测试查询")
            scores = [r.score for r in results]
            assert 0.30 in scores
            assert 0.20 not in scores
            assert 0.05 not in scores

    def test_all_results_below_threshold_returns_empty(self):
        """所有结果低于阈值时返回空列表"""
        pipeline = RAGPipeline()
        pipeline._retrieve_from_graphiti = MagicMock(return_value=[
            _make_rag_result("低分1", score=0.02),
            _make_rag_result("低分2", score=0.05),
        ])
        pipeline.graphiti = True

        results = pipeline.retrieve("测试查询", min_score=0.10)
        assert results == []

    def test_explicit_min_score_parameter_overrides_env(self):
        """显式 min_score 参数应优先于环境变量"""
        pipeline = RAGPipeline()
        pipeline._retrieve_from_graphiti = MagicMock(return_value=[
            _make_rag_result("结果A", score=0.20),
            _make_rag_result("结果B", score=0.05),
        ])
        pipeline.graphiti = True

        with patch.dict(os.environ, {"QA_MIN_RELEVANCE_SCORE": "0.30"}):
            # 显式传入 min_score=0.10 应覆盖环境变量 0.30
            results = pipeline.retrieve("测试查询", min_score=0.10)
            scores = [r.score for r in results]
            assert 0.20 in scores
            assert 0.05 not in scores

    def test_invalid_env_value_falls_back_to_default(self):
        """环境变量值无效时回退到默认 0.10"""
        pipeline = RAGPipeline()
        pipeline._retrieve_from_graphiti = MagicMock(return_value=[
            _make_rag_result("结果A", score=0.10),
            _make_rag_result("结果B", score=0.05),
        ])
        pipeline.graphiti = True

        with patch.dict(os.environ, {"QA_MIN_RELEVANCE_SCORE": "not_a_number"}):
            results = pipeline.retrieve("测试查询")
            scores = [r.score for r in results]
            assert 0.10 in scores
            assert 0.05 not in scores

    def test_threshold_boundary_exact_match(self):
        """分数恰好等于阈值的结果应保留"""
        pipeline = RAGPipeline()
        pipeline._retrieve_from_graphiti = MagicMock(return_value=[
            _make_rag_result("恰好阈值", score=0.10),
            _make_rag_result("低于阈值", score=0.099),
        ])
        pipeline.graphiti = True

        results = pipeline.retrieve("测试查询", min_score=0.10)
        scores = [r.score for r in results]
        assert 0.10 in scores
        assert 0.099 not in scores

    def test_ask_logs_warning_for_low_top_score(self):
        """ask() 中最高分低于 0.15 时应记录警告"""
        results = [_make_rag_result("低分结果", score=0.12)]
        engine = _make_engine_with_rag(results)

        with patch("odap.biz.data.qa.qa_engine.logger") as mock_logger:
            engine.ask("测试问题", user_id="test")
            # 应有 warning 调用提及低分
            warning_calls = [
                call for call in mock_logger.warning.call_args_list
                if "below 0.15" in str(call) or "0.12" in str(call)
            ]
            assert len(warning_calls) >= 1

    def test_ask_no_warning_for_high_top_score(self):
        """ask() 中最高分高于 0.15 时不应记录低分警告"""
        results = [_make_rag_result("高分结果", score=0.8)]
        engine = _make_engine_with_rag(results)

        with patch("odap.biz.data.qa.qa_engine.logger") as mock_logger:
            engine.ask("测试问题", user_id="test")
            # 不应有 "below 0.15" 的警告
            warning_calls = [
                call for call in mock_logger.warning.call_args_list
                if "below 0.15" in str(call)
            ]
            assert len(warning_calls) == 0
