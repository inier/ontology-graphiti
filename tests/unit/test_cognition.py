import pytest
import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.cognition.user_cognition_engine import (
    IntentType,
    RoleType,
    ConfidenceLevel,
    Intent,
    ParsedIntent,
    KnowledgeResult,
    ReasoningStep,
    ReasoningChain,
    Explanation,
    RoleView,
    UserContext,
    IntentRecognizer,
    KnowledgeNavigator,
    ReasoningPathTracker,
    ExplanationEngine,
    RoleViewManager,
    UserCognitionEngine,
)


class TestIntentRecognizer:
    @pytest.fixture
    def recognizer(self):
        return IntentRecognizer()

    def test_recognize_query_intent(self, recognizer):
        result = recognizer.recognize("查询雷达站A的状态", RoleType.COMMANDER)
        assert result.primary_intent == IntentType.QUERY
        assert result.confidence > 0

    def test_recognize_action_intent(self, recognizer):
        result = recognizer.recognize("执行防御方案", RoleType.OPERATOR)
        assert result.primary_intent == IntentType.ACTION
        assert result.confidence > 0

    def test_recognize_explain_intent(self, recognizer):
        result = recognizer.recognize("解释当前态势的原因", RoleType.ANALYST)
        assert result.primary_intent == IntentType.EXPLAIN
        assert result.confidence > 0

    def test_recognize_recommend_intent(self, recognizer):
        result = recognizer.recognize("推荐最佳应对方案", RoleType.COMMANDER)
        assert result.primary_intent == IntentType.RECOMMEND
        assert result.confidence > 0

    def test_recognize_navigate_intent(self, recognizer):
        result = recognizer.recognize("导航到目标区域", RoleType.OPERATOR)
        assert result.primary_intent == IntentType.NAVIGATE
        assert result.confidence > 0

    def test_recognize_compare_intent(self, recognizer):
        result = recognizer.recognize("比较两个方案的差异", RoleType.ANALYST)
        assert result.primary_intent == IntentType.COMPARE
        assert result.confidence > 0

    def test_recognize_analyze_intent(self, recognizer):
        result = recognizer.recognize("分析当前态势", RoleType.INTELLIGENCE)
        assert result.primary_intent == IntentType.ANALYZE
        assert result.confidence > 0

    def test_recognize_returns_parsed_intent(self, recognizer):
        result = recognizer.recognize("查询雷达站A的状态", RoleType.GUEST)
        assert isinstance(result, ParsedIntent)
        assert isinstance(result.primary_intent, IntentType)
        assert isinstance(result.confidence, float)
        assert isinstance(result.entities, list)
        assert isinstance(result.attributes, dict)
        assert isinstance(result.alternative_intents, list)

    def test_recognize_confidence_capped_at_one(self, recognizer):
        result = recognizer.recognize("查询搜索检索什么", RoleType.GUEST)
        assert result.confidence <= 1.0

    def test_recognize_alternative_intents(self, recognizer):
        result = recognizer.recognize("查询雷达站A的状态", RoleType.GUEST)
        assert len(result.alternative_intents) <= 2

    def test_extract_radar_entities(self, recognizer):
        entities = recognizer._extract_entities("雷达站A的状态和雷达1的信号")
        assert any("雷达" in e for e in entities)

    def test_extract_target_entities(self, recognizer):
        entities = recognizer._extract_entities("目标一和目标A的位置")
        assert any("目标" in e for e in entities)

    def test_extract_unit_entities(self, recognizer):
        entities = recognizer._extract_entities("A连和B营的部署情况")
        assert any("连" in e or "营" in e for e in entities)

    def test_extract_location_entities(self, recognizer):
        entities = recognizer._extract_entities("A区的坐标12.5,30.1")
        assert any("区" in e or "坐标" in e for e in entities)

    def test_extract_entities_deduplication(self, recognizer):
        entities = recognizer._extract_entities("雷达站A和雷达站A")
        radar_entities = [e for e in entities if "雷达" in e]
        assert len(radar_entities) == len(set(radar_entities))

    def test_extract_entities_empty_query(self, recognizer):
        entities = recognizer._extract_entities("普通文本没有实体")
        assert isinstance(entities, list)

    def test_extract_attributes_time_today(self, recognizer):
        attrs = recognizer._extract_attributes("今天的态势报告")
        assert attrs.get("time") == "today"

    def test_extract_attributes_time_yesterday(self, recognizer):
        attrs = recognizer._extract_attributes("昨天的情报")
        assert attrs.get("time") == "yesterday"

    def test_extract_attributes_time_last_week(self, recognizer):
        attrs = recognizer._extract_attributes("上周的分析结果")
        assert attrs.get("time") == "last_week"

    def test_extract_attributes_time_this_month(self, recognizer):
        attrs = recognizer._extract_attributes("本月的统计")
        assert attrs.get("time") == "this_month"

    def test_extract_attributes_time_recent(self, recognizer):
        attrs = recognizer._extract_attributes("最近的动态")
        assert attrs.get("time") == "recent"

    def test_extract_attributes_detail_level_high(self, recognizer):
        attrs = recognizer._extract_attributes("给我详细报告")
        assert attrs.get("detail_level") == "high"

    def test_extract_attributes_detail_level_low(self, recognizer):
        attrs = recognizer._extract_attributes("简要说明即可")
        assert attrs.get("detail_level") == "low"

    def test_extract_attributes_empty(self, recognizer):
        attrs = recognizer._extract_attributes("普通查询")
        assert isinstance(attrs, dict)
        assert len(attrs) == 0


class TestKnowledgeNavigator:
    @pytest.fixture
    def navigator(self):
        return KnowledgeNavigator()

    def test_search_without_graph_client(self, navigator):
        results = navigator.search("测试查询")
        assert isinstance(results, list)
        assert len(results) >= 1
        assert results[0].source == "none"
        assert results[0].relevance_score == 0

    def test_search_with_graph_client(self):
        mock_client = MagicMock()
        mock_client.search.return_value = [
            {"id": "1", "score": 0.9, "text": "雷达数据"},
            {"id": "2", "score": 0.7, "text": "目标信息"}
        ]
        nav = KnowledgeNavigator(graph_client=mock_client)
        results = nav.search("雷达")
        assert len(results) == 2
        assert results[0].source == "graph"
        assert results[0].relevance_score == 0.9

    def test_search_with_graph_client_exception(self):
        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("connection error")
        nav = KnowledgeNavigator(graph_client=mock_client)
        results = nav.search("测试")
        assert len(results) >= 1
        assert results[0].source == "none"

    def test_search_caches_results(self, navigator):
        results = navigator.search("测试查询")
        assert len(navigator._cache) > 0

    def test_navigate_path_without_graph_client(self, navigator):
        path = navigator.navigate_path("entity-1")
        assert isinstance(path, list)
        assert path[0] == "entity-1"

    def test_navigate_path_with_graph_client(self):
        mock_client = MagicMock()
        mock_client.get_neighbors.return_value = [
            {"id": "neighbor-1"},
            {"id": "neighbor-2"},
            {"id": "neighbor-3"}
        ]
        nav = KnowledgeNavigator(graph_client=mock_client)
        path = nav.navigate_path("entity-1", "outbound")
        assert path[0] == "entity-1"
        assert "neighbor-1" in path

    def test_navigate_path_with_graph_client_exception(self):
        mock_client = MagicMock()
        mock_client.get_neighbors.side_effect = Exception("error")
        nav = KnowledgeNavigator(graph_client=mock_client)
        path = nav.navigate_path("entity-1")
        assert path == ["entity-1"]

    def test_get_related_entities_without_client(self, navigator):
        related = navigator.get_related_entities("entity-1")
        assert isinstance(related, list)
        assert len(related) == 0

    def test_get_related_entities_with_client(self):
        mock_client = MagicMock()
        mock_client.get_related_entities.return_value = [{"id": "r1"}]
        nav = KnowledgeNavigator(graph_client=mock_client)
        related = nav.get_related_entities("entity-1", depth=2)
        assert len(related) == 1

    def test_get_entity_context_without_client(self, navigator):
        context = navigator.get_entity_context("entity-1")
        assert context["entity_id"] == "entity-1"
        assert "neighbors" in context
        assert "attributes" in context
        assert "history" in context


class TestReasoningPathTracker:
    @pytest.fixture
    def tracker(self):
        return ReasoningPathTracker()

    def test_create_chain(self, tracker):
        chain = tracker.create_chain("为什么选择这个方案?")
        assert isinstance(chain, ReasoningChain)
        assert chain.query == "为什么选择这个方案?"
        assert chain.chain_id
        assert len(chain.steps) == 0
        assert chain.conclusion == ""
        assert chain.confidence == 1.0

    def test_add_step(self, tracker):
        chain = tracker.create_chain("测试查询")
        step = tracker.add_step(
            chain.chain_id,
            step_type="premise",
            description="已知事实: 目标距离100km",
            input_facts=["目标距离100km"],
            output_facts=["距离较近"]
        )
        assert isinstance(step, ReasoningStep)
        assert step.step_type == "premise"
        assert step.description == "已知事实: 目标距离100km"
        assert len(chain.steps) == 1

    def test_add_step_with_rule(self, tracker):
        chain = tracker.create_chain("测试查询")
        step = tracker.add_step(
            chain.chain_id,
            step_type="inference",
            description="推导结论",
            rule="modus_ponens"
        )
        assert step.rule_applied == "modus_ponens"

    def test_add_step_invalid_chain(self, tracker):
        with pytest.raises(ValueError, match="Chain not found"):
            tracker.add_step("invalid-chain-id", "premise", "test")

    def test_complete_chain(self, tracker):
        chain = tracker.create_chain("测试查询")
        tracker.add_step(chain.chain_id, "premise", "事实1")
        tracker.complete_chain(chain.chain_id, "最终结论", 0.85)
        assert chain.conclusion == "最终结论"
        assert chain.confidence == 0.85

    def test_complete_chain_nonexistent(self, tracker):
        tracker.complete_chain("nonexistent", "结论", 0.5)

    def test_get_chain(self, tracker):
        chain = tracker.create_chain("测试查询")
        retrieved = tracker.get_chain(chain.chain_id)
        assert retrieved is chain

    def test_get_chain_nonexistent(self, tracker):
        result = tracker.get_chain("nonexistent")
        assert result is None

    def test_get_chain_visualization(self, tracker):
        chain = tracker.create_chain("测试查询")
        tracker.add_step(chain.chain_id, "premise", "事实1")
        tracker.add_step(chain.chain_id, "inference", "推导1")
        tracker.complete_chain(chain.chain_id, "结论", 0.9)

        viz = tracker.get_chain_visualization(chain.chain_id)
        assert "nodes" in viz
        assert "edges" in viz
        assert "confidence" in viz
        assert len(viz["nodes"]) == 3
        assert len(viz["edges"]) == 2

    def test_get_chain_visualization_single_step(self, tracker):
        chain = tracker.create_chain("测试查询")
        tracker.add_step(chain.chain_id, "premise", "事实1")
        tracker.complete_chain(chain.chain_id, "结论", 0.9)

        viz = tracker.get_chain_visualization(chain.chain_id)
        assert len(viz["nodes"]) == 2
        assert len(viz["edges"]) == 1

    def test_get_chain_visualization_nonexistent(self, tracker):
        viz = tracker.get_chain_visualization("nonexistent")
        assert viz == {}

    def test_chain_visualization_conclusion_node(self, tracker):
        chain = tracker.create_chain("测试查询")
        tracker.add_step(chain.chain_id, "premise", "事实1")
        tracker.complete_chain(chain.chain_id, "最终结论", 0.9)

        viz = tracker.get_chain_visualization(chain.chain_id)
        conclusion_node = [n for n in viz["nodes"] if n["type"] == "conclusion"]
        assert len(conclusion_node) == 1
        assert conclusion_node[0]["description"] == "最终结论"


class TestExplanationEngine:
    @pytest.fixture
    def engine(self):
        return ExplanationEngine()

    def test_explain(self, engine):
        chain = ReasoningChain(
            chain_id="test-chain",
            query="测试问题",
            steps=[
                ReasoningStep(step_id="s1", step_type="premise", description="事实1")
            ],
            conclusion="测试结论",
            confidence=0.9
        )
        explanation = engine.explain("测试问题", ["雷达数据"], chain)
        assert isinstance(explanation, Explanation)
        assert explanation.query == "测试问题"
        assert explanation.answer == "测试结论"
        assert explanation.confidence == 0.9

    def test_explain_identifies_sources(self, engine):
        chain = ReasoningChain(
            chain_id="test-chain",
            query="测试",
            steps=[],
            conclusion="结论",
            confidence=0.8
        )
        explanation = engine.explain("测试", ["雷达信号", "目标追踪数据", "威胁评估"], chain)
        assert "radar_system" in explanation.sources
        assert "target_tracking" in explanation.sources
        assert "threat_analysis" in explanation.sources

    def test_explain_generates_alternatives(self, engine):
        chain = ReasoningChain(
            chain_id="test-chain",
            query="测试",
            steps=[],
            conclusion="结论",
            confidence=0.8
        )
        explanation = engine.explain("测试", ["事实1", "事实2"], chain)
        assert len(explanation.alternative_explanations) >= 1

    def test_explain_why(self, engine):
        explanation = engine.explain_why(
            "为什么选择这个方案?",
            {"facts": ["目标距离100km", "威胁等级高"]}
        )
        assert isinstance(explanation, Explanation)
        assert explanation.query == "为什么选择这个方案?"
        assert len(explanation.reasoning_chain.steps) > 0
        assert explanation.confidence > 0

    def test_explain_why_empty_facts(self, engine):
        explanation = engine.explain_why("为什么?", {"facts": []})
        assert isinstance(explanation, Explanation)
        assert "没有足够的信息" in explanation.answer

    def test_explain_why_with_conclusion(self, engine):
        explanation = engine.explain_why(
            "为什么?",
            {"facts": ["事实1", "事实2", "事实3"]}
        )
        assert "3 个事实" in explanation.answer

    def test_explain_no_conclusion_in_chain(self, engine):
        chain = ReasoningChain(
            chain_id="test-chain",
            query="测试",
            steps=[ReasoningStep(step_id="s1", step_type="premise", description="步骤1")],
            conclusion="",
            confidence=0.8
        )
        explanation = engine.explain("测试", [], chain)
        assert "1 个推理步骤" in explanation.answer


class TestRoleViewManager:
    @pytest.fixture
    def manager(self):
        return RoleViewManager()

    def test_get_commander_view(self, manager):
        view = manager.get_view(RoleType.COMMANDER)
        assert isinstance(view, RoleView)
        assert view.role_type == RoleType.COMMANDER
        assert view.name == "指挥官视图"
        assert "situation_awareness" in view.capabilities

    def test_get_intelligence_view(self, manager):
        view = manager.get_view(RoleType.INTELLIGENCE)
        assert isinstance(view, RoleView)
        assert view.role_type == RoleType.INTELLIGENCE
        assert view.name == "情报员视图"
        assert "data_analysis" in view.capabilities

    def test_get_operator_view(self, manager):
        view = manager.get_view(RoleType.OPERATOR)
        assert isinstance(view, RoleView)
        assert view.role_type == RoleType.OPERATOR
        assert view.name == "操作员视图"
        assert "task_execution" in view.capabilities

    def test_get_analyst_view(self, manager):
        view = manager.get_view(RoleType.ANALYST)
        assert view is None

    def test_get_guest_view(self, manager):
        view = manager.get_view(RoleType.GUEST)
        assert view is None

    def test_get_all_views(self, manager):
        views = manager.get_all_views()
        assert isinstance(views, list)
        assert len(views) == 3

    def test_create_custom_view(self, manager):
        custom = manager.create_custom_view(
            RoleType.ANALYST,
            "自定义分析视图",
            {
                "capabilities": ["custom_analysis", "report"],
                "layout_config": {"primary": "custom_dashboard"},
                "filters": {"type": ["custom"]}
            }
        )
        assert isinstance(custom, RoleView)
        assert custom.role_type == RoleType.ANALYST
        assert custom.name == "自定义分析视图"
        assert custom.description == "用户自定义视图"
        assert "custom_analysis" in custom.capabilities

    def test_create_custom_view_stored(self, manager):
        custom = manager.create_custom_view(
            RoleType.GUEST,
            "访客视图",
            {"capabilities": ["view_only"]}
        )
        all_views = manager.get_all_views()
        view_ids = [v.view_id for v in all_views]
        assert custom.view_id in view_ids


class TestUserCognitionEngine:
    @pytest.fixture
    def engine(self):
        return UserCognitionEngine()

    def test_process_query(self, engine):
        result = engine.process_query("查询雷达站A的状态", "user-001", RoleType.COMMANDER)
        assert isinstance(result, dict)
        assert "session_id" in result
        assert "intent" in result
        assert "knowledge_results" in result
        assert result["intent"]["type"] == IntentType.QUERY.value
        assert result["intent"]["confidence"] > 0

    def test_process_query_explain_intent(self, engine):
        result = engine.process_query("解释当前态势的原因", "user-002", RoleType.ANALYST)
        assert "explanation" in result
        assert "answer" in result["explanation"]
        assert "confidence" in result["explanation"]
        assert "reasoning_chain" in result["explanation"]

    def test_process_query_session_reuse(self, engine):
        result1 = engine.process_query("查询1", "user-001", RoleType.COMMANDER)
        result2 = engine.process_query("查询2", "user-001", RoleType.COMMANDER)
        assert result1["session_id"] == result2["session_id"]

    def test_process_query_different_users(self, engine):
        result1 = engine.process_query("查询1", "user-001", RoleType.COMMANDER)
        result2 = engine.process_query("查询2", "user-002", RoleType.ANALYST)
        assert result1["session_id"] != result2["session_id"]

    def test_process_query_records_history(self, engine):
        result = engine.process_query("查询雷达状态", "user-hist", RoleType.COMMANDER)
        session_id = result["session_id"]
        history = engine.get_conversation_history(session_id)
        assert len(history) >= 1
        assert history[0]["query"] == "查询雷达状态"

    def test_get_role_view_commander(self, engine):
        view = engine.get_role_view(RoleType.COMMANDER)
        assert isinstance(view, dict)
        assert view["role"] == "commander"
        assert view["name"] == "指挥官视图"
        assert "capabilities" in view

    def test_get_role_view_intelligence(self, engine):
        view = engine.get_role_view(RoleType.INTELLIGENCE)
        assert view["role"] == "intelligence"
        assert view["name"] == "情报员视图"

    def test_get_role_view_operator(self, engine):
        view = engine.get_role_view(RoleType.OPERATOR)
        assert view["role"] == "operator"
        assert view["name"] == "操作员视图"

    def test_get_role_view_nonexistent(self, engine):
        view = engine.get_role_view(RoleType.ANALYST)
        assert view == {}

    def test_explain_decision(self, engine):
        explanation = engine.explain_decision(
            "decision-001",
            {
                "query": "为什么选择这个方案?",
                "facts": [
                    "目标距离100km",
                    "威胁等级高",
                    "资源充足"
                ],
                "conclusion": "选择快速突击方案"
            }
        )
        assert isinstance(explanation, Explanation)
        assert explanation.query == "为什么选择这个方案?"
        assert explanation.answer == "选择快速突击方案"
        assert explanation.confidence == 0.85
        assert len(explanation.reasoning_chain.steps) == 3

    def test_explain_decision_default_conclusion(self, engine):
        explanation = engine.explain_decision(
            "decision-002",
            {
                "facts": ["事实1"],
            }
        )
        assert "基于现有信息" in explanation.answer

    def test_navigate_knowledge_graph(self, engine):
        result = engine.navigate_knowledge_graph("entity-1")
        assert isinstance(result, dict)
        assert result["entity_id"] == "entity-1"
        assert "navigation_path" in result
        assert "related_entities" in result
        assert "entity_context" in result


class TestIntentType:
    def test_intent_types(self):
        assert IntentType.QUERY.value == "query"
        assert IntentType.ACTION.value == "action"
        assert IntentType.EXPLAIN.value == "explain"
        assert IntentType.RECOMMEND.value == "recommend"
        assert IntentType.NAVIGATE.value == "navigate"
        assert IntentType.COMPARE.value == "compare"
        assert IntentType.ANALYZE.value == "analyze"


class TestRoleType:
    def test_role_types(self):
        assert RoleType.COMMANDER.value == "commander"
        assert RoleType.INTELLIGENCE.value == "intelligence"
        assert RoleType.OPERATOR.value == "operator"
        assert RoleType.ANALYST.value == "analyst"
        assert RoleType.GUEST.value == "guest"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
