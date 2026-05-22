import logging
from typing import Dict, Any, List, Optional

from odap.biz.feedback.models import Feedback, FeedbackType, FeedbackSeverity, FeedbackQuery

logger = logging.getLogger(__name__)


class FeedbackCollector:
    def __init__(self):
        self._store: Dict[str, Feedback] = {}

    def collect_action_result(
        self,
        action_id: str,
        outcome: str,
        result_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> Feedback:
        severity = FeedbackSeverity.INFO if outcome == "success" else FeedbackSeverity.CRITICAL
        description = error_message or f"Action {action_id} outcome: {outcome}"
        feedback = Feedback(
            feedback_type=FeedbackType.ACTION_RESULT,
            source_id=action_id,
            severity=severity,
            title=f"Action Result: {action_id}",
            description=description,
            data={
                "outcome": outcome,
                "result_data": result_data or {},
                "error_message": error_message,
            },
        )
        self._store[feedback.id] = feedback
        logger.info("Collected action_result feedback for %s", action_id)
        return feedback

    def collect_decision_feedback(
        self,
        decision_id: str,
        feedback_text: str,
        rating: Optional[float] = None,
    ) -> Feedback:
        if rating is not None and rating < 0.3:
            severity = FeedbackSeverity.CRITICAL
        elif rating is not None and rating < 0.7:
            severity = FeedbackSeverity.WARNING
        else:
            severity = FeedbackSeverity.INFO
        feedback = Feedback(
            feedback_type=FeedbackType.DECISION_FEEDBACK,
            source_id=decision_id,
            severity=severity,
            title=f"Decision Feedback: {decision_id}",
            description=feedback_text,
            data={
                "feedback_text": feedback_text,
                "rating": rating,
            },
        )
        self._store[feedback.id] = feedback
        logger.info("Collected decision_feedback for %s", decision_id)
        return feedback

    def collect_outcome_deviation(
        self,
        source_id: str,
        expected: Dict[str, Any],
        actual: Dict[str, Any],
    ) -> Feedback:
        mismatched_keys = []
        for key, expected_val in expected.items():
            actual_val = actual.get(key)
            if actual_val != expected_val:
                mismatched_keys.append(key)
        deviation_ratio = len(mismatched_keys) / max(len(expected), 1)
        if deviation_ratio > 0.5:
            severity = FeedbackSeverity.CRITICAL
        elif deviation_ratio > 0.1:
            severity = FeedbackSeverity.WARNING
        else:
            severity = FeedbackSeverity.INFO
        feedback = Feedback(
            feedback_type=FeedbackType.OUTCOME_DEVIATION,
            source_id=source_id,
            severity=severity,
            title=f"Outcome Deviation: {source_id}",
            description=f"Deviation detected: {len(mismatched_keys)}/{len(expected)} fields mismatched",
            data={
                "expected": expected,
                "actual": actual,
                "mismatched_keys": mismatched_keys,
                "deviation_ratio": deviation_ratio,
            },
            deviation_score=deviation_ratio,
            deviation_factors=[f"mismatch: {k}" for k in mismatched_keys],
        )
        self._store[feedback.id] = feedback
        logger.info("Collected outcome_deviation for %s", source_id)
        return feedback

    def collect_lesson_learned(
        self,
        source_id: str,
        lesson: str,
    ) -> Feedback:
        feedback = Feedback(
            feedback_type=FeedbackType.LESSON_LEARNED,
            source_id=source_id,
            severity=FeedbackSeverity.INFO,
            title=f"Lesson Learned: {source_id}",
            description=lesson,
            lesson_learned=lesson,
        )
        self._store[feedback.id] = feedback
        logger.info("Collected lesson_learned for %s", source_id)
        return feedback

    def query_feedback(self, query: FeedbackQuery) -> List[Feedback]:
        results = list(self._store.values())
        if query.source_id is not None:
            results = [f for f in results if f.source_id == query.source_id]
        if query.feedback_type is not None:
            results = [f for f in results if f.feedback_type == query.feedback_type]
        if query.severity is not None:
            results = [f for f in results if f.severity == query.severity]
        results.sort(key=lambda f: f.timestamp, reverse=True)
        return results[: query.limit]

    def get_by_id(self, feedback_id: str) -> Optional[Feedback]:
        return self._store.get(feedback_id)

    def get_all(self) -> List[Feedback]:
        return list(self._store.values())
