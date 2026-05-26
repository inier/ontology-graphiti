import logging
from typing import Dict, Any, List

from odap.biz.simulation.feedback.models import Feedback, FeedbackQuery
from odap.biz.simulation.feedback.collector import FeedbackCollector
from odap.biz.simulation.feedback.analyzer import FeedbackAnalyzer
from odap.biz.simulation.feedback.aggregator import FeedbackAggregator

logger = logging.getLogger(__name__)


class FeedbackLoop:
    def __init__(self):
        self.collector = FeedbackCollector()
        self.analyzer = FeedbackAnalyzer()
        self.aggregator = FeedbackAggregator()

    def close_loop(self, feedback: Feedback) -> Dict[str, Any]:
        analyzed = self.analyzer.analyze_deviation(feedback)
        lesson = self.analyzer.generate_lesson(analyzed)
        analyzed.lesson_learned = lesson
        result = self.aggregator.aggregate_and_update(analyzed)
        result["lesson_learned"] = lesson
        logger.info(
            "FeedbackLoop closed for %s (type=%s, deviation=%.2f)",
            feedback.source_id,
            feedback.feedback_type.value,
            analyzed.deviation_score,
        )
        return result

    def get_feedback_history(self, source_id: str) -> List[Feedback]:
        query = FeedbackQuery(source_id=source_id)
        return self.collector.query_feedback(query)


_feedback_loop_instance = None


def get_feedback_loop() -> FeedbackLoop:
    global _feedback_loop_instance
    if _feedback_loop_instance is None:
        _feedback_loop_instance = FeedbackLoop()
    return _feedback_loop_instance
