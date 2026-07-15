import pytest
from unittest.mock import MagicMock, patch

from odap.biz.simulation.feedback.models import Feedback, FeedbackType, FeedbackSeverity, FeedbackQuery
from odap.biz.simulation.feedback.collector import FeedbackCollector
from odap.biz.simulation.feedback.analyzer import FeedbackAnalyzer
from odap.biz.simulation.feedback.aggregator import FeedbackAggregator
from odap.biz.simulation.feedback.loop import FeedbackLoop


class TestFeedbackModels:
    def test_feedback_default_values(self):
        fb = Feedback(feedback_type=FeedbackType.ACTION_RESULT, source_id="act-1")
        assert fb.id
        assert fb.feedback_type == FeedbackType.ACTION_RESULT
        assert fb.source_id == "act-1"
        assert fb.severity == FeedbackSeverity.INFO
        assert fb.deviation_score == 0.0
        assert fb.deviation_factors == []
        assert fb.root_causes == []
        assert fb.lesson_learned == ""
        assert fb.data == {}

    def test_feedback_type_enum(self):
        assert FeedbackType.ACTION_RESULT.value == "action_result"
        assert FeedbackType.DECISION_FEEDBACK.value == "decision_feedback"
        assert FeedbackType.OUTCOME_DEVIATION.value == "outcome_deviation"
        assert FeedbackType.LESSON_LEARNED.value == "lesson_learned"

    def test_feedback_severity_enum(self):
        assert FeedbackSeverity.INFO.value == "info"
        assert FeedbackSeverity.WARNING.value == "warning"
        assert FeedbackSeverity.CRITICAL.value == "critical"

    def test_feedback_query_defaults(self):
        q = FeedbackQuery()
        assert q.source_id is None
        assert q.feedback_type is None
        assert q.severity is None
        assert q.limit == 50


class TestFeedbackCollector:
    def test_collect_action_result_success(self):
        collector = FeedbackCollector()
        fb = collector.collect_action_result("act-1", "success", result_data={"status": "done"})
        assert fb.feedback_type == FeedbackType.ACTION_RESULT
        assert fb.source_id == "act-1"
        assert fb.severity == FeedbackSeverity.INFO
        assert fb.data["outcome"] == "success"
        assert fb.data["result_data"] == {"status": "done"}

    def test_collect_action_result_failure(self):
        collector = FeedbackCollector()
        fb = collector.collect_action_result("act-2", "failure", error_message="timeout exceeded")
        assert fb.severity == FeedbackSeverity.CRITICAL
        assert fb.data["outcome"] == "failure"
        assert fb.data["error_message"] == "timeout exceeded"

    def test_collect_decision_feedback_high_rating(self):
        collector = FeedbackCollector()
        fb = collector.collect_decision_feedback("dec-1", "Good decision", rating=0.9)
        assert fb.feedback_type == FeedbackType.DECISION_FEEDBACK
        assert fb.source_id == "dec-1"
        assert fb.severity == FeedbackSeverity.INFO
        assert fb.data["rating"] == 0.9

    def test_collect_decision_feedback_low_rating(self):
        collector = FeedbackCollector()
        fb = collector.collect_decision_feedback("dec-2", "Bad decision", rating=0.1)
        assert fb.severity == FeedbackSeverity.CRITICAL

    def test_collect_decision_feedback_medium_rating(self):
        collector = FeedbackCollector()
        fb = collector.collect_decision_feedback("dec-3", "OK decision", rating=0.5)
        assert fb.severity == FeedbackSeverity.WARNING

    def test_collect_outcome_deviation(self):
        collector = FeedbackCollector()
        fb = collector.collect_outcome_deviation(
            "src-1",
            expected={"status": "running", "count": 10},
            actual={"status": "stopped", "count": 10},
        )
        assert fb.feedback_type == FeedbackType.OUTCOME_DEVIATION
        assert fb.source_id == "src-1"
        assert fb.deviation_score == 0.5
        assert "status" in fb.data["mismatched_keys"]

    def test_collect_outcome_deviation_no_mismatch(self):
        collector = FeedbackCollector()
        fb = collector.collect_outcome_deviation(
            "src-2",
            expected={"status": "running"},
            actual={"status": "running"},
        )
        assert fb.deviation_score == 0.0
        assert fb.data["mismatched_keys"] == []
        assert fb.severity == FeedbackSeverity.INFO

    def test_collect_lesson_learned(self):
        collector = FeedbackCollector()
        fb = collector.collect_lesson_learned("src-3", "Always validate inputs before processing")
        assert fb.feedback_type == FeedbackType.LESSON_LEARNED
        assert fb.source_id == "src-3"
        assert fb.lesson_learned == "Always validate inputs before processing"
        assert fb.severity == FeedbackSeverity.INFO

    def test_query_feedback_by_source_id(self):
        collector = FeedbackCollector()
        collector.collect_action_result("act-a", "success")
        collector.collect_action_result("act-b", "failure", error_message="err")
        collector.collect_decision_feedback("dec-a", "ok", rating=0.5)
        results = collector.query_feedback(FeedbackQuery(source_id="act-a"))
        assert len(results) == 1
        assert results[0].source_id == "act-a"

    def test_query_feedback_by_type(self):
        collector = FeedbackCollector()
        collector.collect_action_result("act-1", "success")
        collector.collect_decision_feedback("dec-1", "ok")
        results = collector.query_feedback(FeedbackQuery(feedback_type=FeedbackType.DECISION_FEEDBACK))
        assert len(results) == 1
        assert results[0].feedback_type == FeedbackType.DECISION_FEEDBACK

    def test_query_feedback_by_severity(self):
        collector = FeedbackCollector()
        collector.collect_action_result("act-1", "failure", error_message="err")
        collector.collect_action_result("act-2", "success")
        results = collector.query_feedback(FeedbackQuery(severity=FeedbackSeverity.CRITICAL))
        assert len(results) == 1
        assert results[0].severity == FeedbackSeverity.CRITICAL

    def test_query_feedback_limit(self):
        collector = FeedbackCollector()
        for i in range(10):
            collector.collect_action_result(f"act-{i}", "success")
        results = collector.query_feedback(FeedbackQuery(limit=3))
        assert len(results) == 3

    def test_get_by_id(self):
        collector = FeedbackCollector()
        fb = collector.collect_action_result("act-1", "success")
        found = collector.get_by_id(fb.id)
        assert found is fb

    def test_get_by_id_not_found(self):
        collector = FeedbackCollector()
        assert collector.get_by_id("nonexistent") is None


class TestFeedbackAnalyzer:
    def test_analyze_action_result_failure_timeout(self):
        fb = Feedback(
            feedback_type=FeedbackType.ACTION_RESULT,
            source_id="act-1",
            data={"outcome": "failure", "error_message": "Connection timeout occurred"},
        )
        analyzer = FeedbackAnalyzer()
        result = analyzer.analyze_deviation(fb)
        assert result.deviation_score == 0.7
        assert "timeout" in result.root_causes
        assert result.severity == FeedbackSeverity.CRITICAL

    def test_analyze_action_result_failure_permission(self):
        fb = Feedback(
            feedback_type=FeedbackType.ACTION_RESULT,
            source_id="act-2",
            data={"outcome": "failure", "error_message": "Permission denied for resource"},
        )
        analyzer = FeedbackAnalyzer()
        result = analyzer.analyze_deviation(fb)
        assert result.deviation_score == 0.5
        assert "permission_denied" in result.root_causes

    def test_analyze_action_result_failure_not_found(self):
        fb = Feedback(
            feedback_type=FeedbackType.ACTION_RESULT,
            source_id="act-3",
            data={"outcome": "failure", "error_message": "Target not found"},
        )
        analyzer = FeedbackAnalyzer()
        result = analyzer.analyze_deviation(fb)
        assert result.deviation_score == 0.6
        assert "target_missing" in result.root_causes

    def test_analyze_action_result_failure_unknown(self):
        fb = Feedback(
            feedback_type=FeedbackType.ACTION_RESULT,
            source_id="act-4",
            data={"outcome": "failure", "error_message": "Something went wrong"},
        )
        analyzer = FeedbackAnalyzer()
        result = analyzer.analyze_deviation(fb)
        assert result.deviation_score == 1.0
        assert "unknown_execution_failure" in result.root_causes

    def test_analyze_action_result_success(self):
        fb = Feedback(
            feedback_type=FeedbackType.ACTION_RESULT,
            source_id="act-5",
            data={"outcome": "success"},
        )
        analyzer = FeedbackAnalyzer()
        result = analyzer.analyze_deviation(fb)
        assert result.deviation_score == 0.0
        assert result.severity == FeedbackSeverity.INFO

    def test_analyze_outcome_deviation(self):
        fb = Feedback(
            feedback_type=FeedbackType.OUTCOME_DEVIATION,
            source_id="src-1",
            data={
                "expected": {"status": "running", "count": 10},
                "actual": {"status": "stopped", "count": 5},
                "mismatched_keys": ["status", "count"],
                "deviation_ratio": 1.0,
            },
        )
        analyzer = FeedbackAnalyzer()
        result = analyzer.analyze_deviation(fb)
        assert result.deviation_score == 1.0
        assert len(result.deviation_factors) == 2
        assert len(result.root_causes) == 2
        assert result.severity == FeedbackSeverity.CRITICAL

    def test_analyze_outcome_deviation_missing_field(self):
        fb = Feedback(
            feedback_type=FeedbackType.OUTCOME_DEVIATION,
            source_id="src-2",
            data={
                "expected": {"status": "running", "count": 10},
                "actual": {"status": "running"},
                "mismatched_keys": ["count"],
                "deviation_ratio": 0.5,
            },
        )
        analyzer = FeedbackAnalyzer()
        result = analyzer.analyze_deviation(fb)
        assert "missing_data: count" in result.root_causes

    def test_analyze_decision_feedback(self):
        fb = Feedback(
            feedback_type=FeedbackType.DECISION_FEEDBACK,
            source_id="dec-1",
            data={"rating": 0.2, "feedback_text": "Poor choice"},
        )
        analyzer = FeedbackAnalyzer()
        result = analyzer.analyze_deviation(fb)
        assert result.deviation_score == 0.8
        assert "poor_decision_quality" in result.root_causes

    def test_analyze_lesson_learned(self):
        fb = Feedback(
            feedback_type=FeedbackType.LESSON_LEARNED,
            source_id="src-1",
            lesson_learned="Test lesson",
        )
        analyzer = FeedbackAnalyzer()
        result = analyzer.analyze_deviation(fb)
        assert result.deviation_score == 0.0

    def test_identify_patterns_empty(self):
        analyzer = FeedbackAnalyzer()
        result = analyzer.identify_patterns([])
        assert result["total"] == 0
        assert result["patterns"] == []

    def test_identify_patterns_with_data(self):
        feedbacks = [
            Feedback(
                feedback_type=FeedbackType.ACTION_RESULT,
                source_id="act-1",
                root_causes=["timeout"],
                deviation_score=0.7,
            ),
            Feedback(
                feedback_type=FeedbackType.ACTION_RESULT,
                source_id="act-1",
                root_causes=["timeout"],
                deviation_score=0.5,
            ),
            Feedback(
                feedback_type=FeedbackType.OUTCOME_DEVIATION,
                source_id="src-2",
                root_causes=["parameter_drift"],
                deviation_score=0.3,
            ),
        ]
        analyzer = FeedbackAnalyzer()
        result = analyzer.identify_patterns(feedbacks)
        assert result["total"] == 3
        assert result["type_distribution"]["action_result"] == 2
        assert result["type_distribution"]["outcome_deviation"] == 1
        assert result["avg_deviation_score"] == pytest.approx(0.5, abs=0.01)
        recurring = [p for p in result["patterns"] if p["type"] == "recurring_root_cause"]
        assert len(recurring) > 0
        repeated = [p for p in result["patterns"] if p["type"] == "repeated_source"]
        assert any(p["source_id"] == "act-1" for p in repeated)

    def test_generate_lesson_action_success(self):
        fb = Feedback(
            feedback_type=FeedbackType.ACTION_RESULT,
            source_id="act-ok",
            data={"outcome": "success"},
        )
        analyzer = FeedbackAnalyzer()
        lesson = analyzer.generate_lesson(fb)
        assert "completed successfully" in lesson

    def test_generate_lesson_action_failure(self):
        fb = Feedback(
            feedback_type=FeedbackType.ACTION_RESULT,
            source_id="act-fail",
            data={"outcome": "failure"},
            deviation_factors=["execution_error: timeout"],
            root_causes=["timeout"],
        )
        analyzer = FeedbackAnalyzer()
        lesson = analyzer.generate_lesson(fb)
        assert "failed" in lesson
        assert "timeout" in lesson

    def test_generate_lesson_deviation(self):
        fb = Feedback(
            feedback_type=FeedbackType.OUTCOME_DEVIATION,
            source_id="src-1",
            data={"mismatched_keys": ["status"]},
            root_causes=["state_divergence: status"],
        )
        analyzer = FeedbackAnalyzer()
        lesson = analyzer.generate_lesson(fb)
        assert "Deviation detected" in lesson
        assert "status" in lesson

    def test_generate_lesson_decision(self):
        fb = Feedback(
            feedback_type=FeedbackType.DECISION_FEEDBACK,
            source_id="dec-1",
            data={"rating": 0.5},
            description="Suboptimal",
        )
        analyzer = FeedbackAnalyzer()
        lesson = analyzer.generate_lesson(fb)
        assert "0.50" in lesson
        assert "Suboptimal" in lesson

    def test_generate_lesson_learned_type(self):
        fb = Feedback(
            feedback_type=FeedbackType.LESSON_LEARNED,
            source_id="src-1",
            lesson_learned="Always check inputs",
        )
        analyzer = FeedbackAnalyzer()
        lesson = analyzer.generate_lesson(fb)
        assert lesson == "Always check inputs"


class TestFeedbackAggregator:
    def test_aggregate_and_update_no_graph(self):
        aggregator = FeedbackAggregator()
        fb = Feedback(
            feedback_type=FeedbackType.ACTION_RESULT,
            source_id="act-1",
            data={"outcome": "success", "result_data": {"status": "done"}},
        )
        aggregator._update_graph = MagicMock(side_effect=Exception("no graph"))
        aggregator._create_feedback_episode = MagicMock(side_effect=Exception("no graph"))
        aggregator._emit_feedback_event = MagicMock(side_effect=Exception("no hook"))
        result = aggregator.aggregate_and_update(fb)
        assert result["feedback_id"] == fb.id
        assert result["source_id"] == "act-1"
        assert result["feedback_type"] == "action_result"
        assert result["graph_updated"] is False
        assert result["episode_created"] is False
        assert result["hook_emitted"] is False

    def test_aggregate_with_graph(self):
        mock_graph = MagicMock()
        aggregator = FeedbackAggregator()
        aggregator._graph_manager = mock_graph
        aggregator._hook_registry = None
        fb = Feedback(
            feedback_type=FeedbackType.ACTION_RESULT,
            source_id="act-1",
            data={"outcome": "success", "result_data": {"status": "done"}},
        )
        result = aggregator.aggregate_and_update(fb)
        assert result["graph_updated"] is True
        assert result["episode_created"] is True

    def test_aggregate_deviation_updates_actual(self):
        mock_graph = MagicMock()
        aggregator = FeedbackAggregator()
        aggregator._graph_manager = mock_graph
        aggregator._hook_registry = None
        fb = Feedback(
            feedback_type=FeedbackType.OUTCOME_DEVIATION,
            source_id="src-1",
            data={"actual": {"status": "degraded"}, "expected": {"status": "healthy"}},
        )
        result = aggregator.aggregate_and_update(fb)
        assert result["graph_updated"] is True
        mock_graph.update_entity.assert_called_once_with("src-1", {"status": "degraded"})


class TestFeedbackLoop:
    def test_close_loop_action_result(self):
        loop = FeedbackLoop()
        loop.aggregator._graph_manager = None
        loop.aggregator._hook_registry = None
        fb = loop.collector.collect_action_result("act-1", "failure", error_message="timeout exceeded")
        result = loop.close_loop(fb)
        assert result["source_id"] == "act-1"
        assert result["feedback_type"] == "action_result"
        assert "lesson_learned" in result
        assert "timeout" in result["lesson_learned"]

    def test_close_loop_decision_feedback(self):
        loop = FeedbackLoop()
        loop.aggregator._graph_manager = None
        loop.aggregator._hook_registry = None
        fb = loop.collector.collect_decision_feedback("dec-1", "Poor decision", rating=0.2)
        result = loop.close_loop(fb)
        assert result["source_id"] == "dec-1"
        assert result["feedback_type"] == "decision_feedback"
        assert "lesson_learned" in result

    def test_close_loop_outcome_deviation(self):
        loop = FeedbackLoop()
        loop.aggregator._graph_manager = None
        loop.aggregator._hook_registry = None
        fb = loop.collector.collect_outcome_deviation(
            "src-1",
            expected={"status": "running"},
            actual={"status": "stopped"},
        )
        result = loop.close_loop(fb)
        assert result["source_id"] == "src-1"
        assert result["feedback_type"] == "outcome_deviation"

    def test_close_loop_lesson_learned(self):
        loop = FeedbackLoop()
        loop.aggregator._graph_manager = None
        loop.aggregator._hook_registry = None
        fb = loop.collector.collect_lesson_learned("src-1", "Always validate inputs")
        result = loop.close_loop(fb)
        assert result["source_id"] == "src-1"
        assert result["feedback_type"] == "lesson_learned"
        assert result["lesson_learned"] == "Always validate inputs"

    def test_get_feedback_history(self):
        loop = FeedbackLoop()
        loop.collector.collect_action_result("act-1", "success")
        loop.collector.collect_action_result("act-1", "failure", error_message="err")
        loop.collector.collect_decision_feedback("dec-1", "ok")
        history = loop.get_feedback_history("act-1")
        assert len(history) == 2
        assert all(f.source_id == "act-1" for f in history)

    def test_get_feedback_history_empty(self):
        loop = FeedbackLoop()
        history = loop.get_feedback_history("nonexistent")
        assert history == []
