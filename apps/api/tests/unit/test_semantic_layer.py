import pytest

from odap.biz.data.qa.nl_pipeline.intent_parser import IntentParser, StructuredQuery
from odap.biz.data.qa.nl_pipeline.query_planner import QueryPlanner
from odap.biz.data.qa.nl_pipeline.disambiguator import Disambiguator


class TestIntentParser:
    @pytest.fixture
    def parser(self):
        return IntentParser()

    def test_parse_query_intent(self, parser):
        result = parser.parse("查询雷达站的状态")
        assert isinstance(result, StructuredQuery)
        assert result.intent == "query"

    def test_parse_action_intent(self, parser):
        result = parser.parse("执行防御方案")
        assert result.intent == "action"

    def test_parse_explain_intent(self, parser):
        result = parser.parse("解释这个决策的原因")
        assert result.intent == "explain"

    def test_parse_recommend_intent(self, parser):
        result = parser.parse("推荐最佳应对方案")
        assert result.intent == "recommend"

    def test_parse_analyze_intent(self, parser):
        result = parser.parse("分析当前态势")
        assert result.intent == "analyze"

    def test_parse_compare_intent(self, parser):
        result = parser.parse("比较两个方案的差异")
        assert result.intent == "compare"

    def test_parse_default_intent(self, parser):
        result = parser.parse("普通文本")
        assert result.intent == "query"

    def test_parse_extracts_entities(self, parser):
        result = parser.parse("查询雷达站A的状态")
        assert len(result.entities) > 0
        assert any("雷达" in e for e in result.entities)

    def test_parse_extracts_time_filters(self, parser):
        result = parser.parse("今天的态势报告")
        assert result.filters.get("time") == "today"

    def test_parse_extracts_yesterday_filter(self, parser):
        result = parser.parse("昨天的情报")
        assert result.filters.get("time") == "yesterday"

    def test_parse_extracts_recent_filter(self, parser):
        result = parser.parse("最近的动态")
        assert result.filters.get("time") == "recent"

    def test_parse_extracts_detail_level_high(self, parser):
        result = parser.parse("给我详细报告")
        assert result.filters.get("detail_level") == "high"

    def test_parse_extracts_detail_level_low(self, parser):
        result = parser.parse("简要说明即可")
        assert result.filters.get("detail_level") == "low"

    def test_parse_extracts_sort_newest(self, parser):
        result = parser.parse("最新的报告")
        assert result.sort == "time_desc"

    def test_parse_extracts_sort_important(self, parser):
        result = parser.parse("重要的事项")
        assert result.sort == "priority_desc"

    def test_structured_query_to_dict(self, parser):
        result = parser.parse("查询雷达站A的状态")
        d = result.to_dict()
        assert "query_id" in d
        assert "intent" in d
        assert "entities" in d
        assert "filters" in d


class TestQueryPlanner:
    @pytest.fixture
    def planner(self):
        return QueryPlanner()

    def test_plan_query_intent(self, planner):
        result = planner.plan({"intent": "query", "entities": [], "filters": {}})
        assert result["intent"] == "query"
        assert len(result["tasks"]) == 4
        assert result["total_steps"] == 4

    def test_plan_action_intent(self, planner):
        result = planner.plan({"intent": "action", "entities": [], "filters": {}})
        assert result["intent"] == "action"
        assert len(result["tasks"]) == 4
        task_types = [t["task_type"] for t in result["tasks"]]
        assert "permission_check" in task_types

    def test_plan_explain_intent(self, planner):
        result = planner.plan({"intent": "explain", "entities": [], "filters": {}})
        assert result["intent"] == "explain"
        task_types = [t["task_type"] for t in result["tasks"]]
        assert "reasoning_chain" in task_types

    def test_plan_recommend_intent(self, planner):
        result = planner.plan({"intent": "recommend", "entities": [], "filters": {}})
        assert result["intent"] == "recommend"
        task_types = [t["task_type"] for t in result["tasks"]]
        assert "ranking" in task_types

    def test_plan_analyze_intent(self, planner):
        result = planner.plan({"intent": "analyze", "entities": [], "filters": {}})
        assert result["intent"] == "analyze"
        task_types = [t["task_type"] for t in result["tasks"]]
        assert "pattern_analysis" in task_types

    def test_plan_compare_intent(self, planner):
        result = planner.plan({"intent": "compare", "entities": [], "filters": {}})
        assert result["intent"] == "compare"
        task_types = [t["task_type"] for t in result["tasks"]]
        assert "comparison_generation" in task_types

    def test_plan_default_to_query(self, planner):
        result = planner.plan({"intent": "unknown", "entities": [], "filters": {}})
        assert len(result["tasks"]) == 4

    def test_plan_tasks_have_ids(self, planner):
        result = planner.plan({"intent": "query", "entities": [], "filters": {}})
        for task in result["tasks"]:
            assert "task_id" in task
            assert task["status"] == "pending"

    def test_plan_first_task_has_input(self, planner):
        result = planner.plan({
            "intent": "query",
            "entities": ["radar-1"],
            "filters": {"time": "today"},
        })
        first_task = result["tasks"][0]
        assert first_task["input"]["intent"] == "query"
        assert "radar-1" in first_task["input"]["entities"]

    def test_plan_has_plan_id(self, planner):
        result = planner.plan({"intent": "query", "entities": [], "filters": {}})
        assert "plan_id" in result


class TestDisambiguator:
    @pytest.fixture
    def disambiguator(self):
        return Disambiguator()

    def test_disambiguate_known_term(self, disambiguator):
        result = disambiguator.disambiguate("传感器")
        assert result["original"] == "传感器"
        assert result["canonical"] == "传感器"
        assert len(result["synonyms"]) > 0

    def test_disambiguate_synonym(self, disambiguator):
        result = disambiguator.disambiguate("sensor")
        assert result["canonical"] == "传感器"

    def test_disambiguate_unknown_term(self, disambiguator):
        result = disambiguator.disambiguate("未知术语")
        assert result["original"] == "未知术语"
        assert result["canonical"] is None

    def test_disambiguate_with_expansion(self, disambiguator):
        result = disambiguator.disambiguate("状态")
        assert len(result["expansions"]) > 0

    def test_add_synonym(self, disambiguator):
        result = disambiguator.add_synonym("测试", "test")
        assert result["status"] == "success"
        assert result["canonical"] == "测试"
        assert result["synonym"] == "test"

    def test_add_synonym_duplicate(self, disambiguator):
        disambiguator.add_synonym("测试", "test")
        result = disambiguator.add_synonym("测试", "test")
        assert result["status"] == "success"

    def test_add_expansion_rule(self, disambiguator):
        result = disambiguator.add_expansion_rule("性能", "性能指标")
        assert result["status"] == "success"
        assert result["pattern"] == "性能"

    def test_add_expansion_rule_existing_pattern(self, disambiguator):
        disambiguator.add_expansion_rule("状态", "新状态")
        rules = disambiguator.get_expansion_rules()
        status_rule = [r for r in rules if r["pattern"] == "状态"][0]
        assert "新状态" in status_rule["expansion"]

    def test_get_synonyms(self, disambiguator):
        synonyms = disambiguator.get_synonyms()
        assert isinstance(synonyms, dict)
        assert "传感器" in synonyms

    def test_get_expansion_rules(self, disambiguator):
        rules = disambiguator.get_expansion_rules()
        assert isinstance(rules, list)
        assert len(rules) > 0

    def test_disambiguate_target_synonym(self, disambiguator):
        result = disambiguator.disambiguate("target")
        assert result["canonical"] == "目标"

    def test_disambiguate_threat_synonym(self, disambiguator):
        result = disambiguator.disambiguate("risk")
        assert result["canonical"] == "风险"
