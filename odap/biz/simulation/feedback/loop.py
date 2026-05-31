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
        self._propagate_hooks: List[Dict[str, Any]] = []

    def close_loop(self, feedback: Feedback) -> Dict[str, Any]:
        analyzed = self.analyzer.analyze_deviation(feedback)
        lesson = self.analyzer.generate_lesson(analyzed)
        analyzed.lesson_learned = lesson
        result = self.aggregator.aggregate_and_update(analyzed)
        result["lesson_learned"] = lesson

        propagate_result = self._propagate(analyzed)
        result["propagated"] = propagate_result.get("propagated", False)
        result["propagate_targets"] = propagate_result.get("targets", [])

        logger.info(
            "FeedbackLoop closed for %s (type=%s, deviation=%.2f)",
            feedback.source_id,
            feedback.feedback_type.value,
            analyzed.deviation_score,
        )
        return result

    def _propagate(self, feedback: Feedback) -> Dict[str, Any]:
        targets = []
        try:
            from odap.biz.integration.openharness_agent.adapter.hook_adapter import HookAdapter
            adapter = HookAdapter()
            result = adapter.emit_event(
                f"feedback.propagate.{feedback.feedback_type.value}",
                context={
                    "feedback_id": feedback.id,
                    "source_id": feedback.source_id,
                    "deviation_score": feedback.deviation_score,
                    "lesson_learned": feedback.lesson_learned,
                },
            )
            if result.get("status") == "success":
                for hr in result.get("hook_results", []):
                    targets.append(hr.get("hook_id"))
        except Exception as e:
            logger.debug("FeedbackLoop propagate fallback: %s", e)

        for hook in self._propagate_hooks:
            try:
                hook["handler"](feedback)
                targets.append(hook.get("name", "unknown"))
            except Exception as e:
                logger.debug("Propagate hook %s error: %s", hook.get("name"), e)

        return {"propagated": len(targets) > 0, "targets": targets}

    def register_propagate_hook(self, name: str, handler) -> Dict[str, Any]:
        self._propagate_hooks.append({"name": name, "handler": handler})
        return {"status": "success", "name": name}

    def get_feedback_history(self, source_id: str) -> List[Feedback]:
        query = FeedbackQuery(source_id=source_id)
        return self.collector.query_feedback(query)

    def collect_feedback(self, source_id: str, feedback_type: str, data: Dict[str, Any],
                         outcome: str = "success") -> Feedback:
        from odap.biz.simulation.feedback.models import FeedbackType
        try:
            ft = FeedbackType(feedback_type)
        except ValueError:
            ft = FeedbackType.ACTION_RESULT

        if ft == FeedbackType.ACTION_RESULT:
            return self.collector.collect_action_result(
                action_id=source_id,
                outcome=outcome,
                result_data=data,
            )
        elif ft == FeedbackType.DECISION_FEEDBACK:
            return self.collector.collect_decision_feedback(
                decision_id=source_id,
                feedback_text=data.get("feedback_text", ""),
                rating=data.get("rating"),
            )
        elif ft == FeedbackType.OUTCOME_DEVIATION:
            return self.collector.collect_outcome_deviation(
                source_id=source_id,
                expected=data.get("expected", {}),
                actual=data.get("actual", {}),
            )
        else:
            return self.collector.collect_lesson_learned(
                source_id=source_id,
                lesson=data.get("lesson", ""),
            )

    def analyze_feedback(self, task_id: str) -> Dict[str, Any]:
        feedbacks = self.get_feedback_history(task_id)
        if not feedbacks:
            return {"status": "error", "message": f"No feedback found for task: {task_id}"}
        patterns = self.analyzer.identify_patterns(feedbacks)
        return {
            "status": "success",
            "task_id": task_id,
            "feedback_count": len(feedbacks),
            "patterns": patterns,
        }

    def aggregate_feedback(self, ontology_id: str) -> Dict[str, Any]:
        all_feedbacks = self.collector.get_all()
        related = [f for f in all_feedbacks if ontology_id in f.source_id]
        if not related:
            return {"status": "success", "ontology_id": ontology_id, "aggregated": {}}
        patterns = self.analyzer.identify_patterns(related)
        return {
            "status": "success",
            "ontology_id": ontology_id,
            "feedback_count": len(related),
            "patterns": patterns,
        }


_feedback_loop_instance = None


def get_feedback_loop() -> FeedbackLoop:
    global _feedback_loop_instance
    if _feedback_loop_instance is None:
        _feedback_loop_instance = FeedbackLoop()
    return _feedback_loop_instance
