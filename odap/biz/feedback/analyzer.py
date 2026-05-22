import logging
from typing import Dict, Any, List

from odap.biz.feedback.models import Feedback, FeedbackType, FeedbackSeverity

logger = logging.getLogger(__name__)


class FeedbackAnalyzer:
    def analyze_deviation(self, feedback: Feedback) -> Feedback:
        if feedback.feedback_type == FeedbackType.ACTION_RESULT:
            feedback = self._analyze_action_result(feedback)
        elif feedback.feedback_type == FeedbackType.OUTCOME_DEVIATION:
            feedback = self._analyze_outcome_deviation(feedback)
        elif feedback.feedback_type == FeedbackType.DECISION_FEEDBACK:
            feedback = self._analyze_decision_feedback(feedback)
        elif feedback.feedback_type == FeedbackType.LESSON_LEARNED:
            feedback = self._analyze_lesson_learned(feedback)
        return feedback

    def _analyze_action_result(self, feedback: Feedback) -> Feedback:
        outcome = feedback.data.get("outcome", "")
        error_message = feedback.data.get("error_message")
        if outcome == "failure":
            feedback.deviation_score = 1.0
            feedback.severity = FeedbackSeverity.CRITICAL
            if error_message:
                msg_lower = error_message.lower()
                if "timeout" in msg_lower:
                    feedback.root_causes.append("timeout")
                    feedback.deviation_score = 0.7
                    feedback.deviation_factors.append(f"execution_error: timeout")
                elif "permission" in msg_lower:
                    feedback.root_causes.append("permission_denied")
                    feedback.deviation_score = 0.5
                    feedback.deviation_factors.append(f"execution_error: permission_denied")
                elif "not found" in msg_lower:
                    feedback.root_causes.append("target_missing")
                    feedback.deviation_score = 0.6
                    feedback.deviation_factors.append(f"execution_error: target_missing")
                else:
                    feedback.root_causes.append("unknown_execution_failure")
                    feedback.deviation_factors.append(f"execution_error: {error_message[:100]}")
        elif outcome == "success":
            feedback.deviation_score = 0.0
            feedback.severity = FeedbackSeverity.INFO
        return feedback

    def _analyze_outcome_deviation(self, feedback: Feedback) -> Feedback:
        expected = feedback.data.get("expected", {})
        actual = feedback.data.get("actual", {})
        mismatched_keys = feedback.data.get("mismatched_keys", [])
        deviation_ratio = feedback.data.get("deviation_ratio", 0.0)
        feedback.deviation_score = deviation_ratio
        for key in mismatched_keys:
            expected_val = expected.get(key)
            actual_val = actual.get(key)
            if actual_val is None:
                feedback.deviation_factors.append(f"missing_field: {key} (expected={expected_val})")
                feedback.root_causes.append(f"missing_data: {key}")
            elif isinstance(expected_val, (int, float)) and isinstance(actual_val, (int, float)):
                if expected_val != 0:
                    pct_diff = abs(actual_val - expected_val) / abs(expected_val)
                    feedback.deviation_factors.append(
                        f"numeric_deviation: {key} expected={expected_val}, actual={actual_val}, diff={pct_diff:.1%}"
                    )
                else:
                    feedback.deviation_factors.append(
                        f"value_mismatch: {key} expected={expected_val}, actual={actual_val}"
                    )
                feedback.root_causes.append(f"parameter_drift: {key}")
            else:
                feedback.deviation_factors.append(
                    f"state_mismatch: {key} expected={expected_val}, actual={actual_val}"
                )
                feedback.root_causes.append(f"state_divergence: {key}")
        if deviation_ratio > 0.5:
            feedback.severity = FeedbackSeverity.CRITICAL
        elif deviation_ratio > 0.1:
            feedback.severity = FeedbackSeverity.WARNING
        else:
            feedback.severity = FeedbackSeverity.INFO
        return feedback

    def _analyze_decision_feedback(self, feedback: Feedback) -> Feedback:
        rating = feedback.data.get("rating")
        if rating is not None:
            feedback.deviation_score = 1.0 - rating
            if rating < 0.3:
                feedback.root_causes.append("poor_decision_quality")
                feedback.deviation_factors.append(f"low_rating: {rating}")
            elif rating < 0.7:
                feedback.root_causes.append("suboptimal_decision")
                feedback.deviation_factors.append(f"medium_rating: {rating}")
        return feedback

    def _analyze_lesson_learned(self, feedback: Feedback) -> Feedback:
        feedback.deviation_score = 0.0
        return feedback

    def identify_patterns(self, feedbacks: List[Feedback]) -> Dict[str, Any]:
        if not feedbacks:
            return {"total": 0, "patterns": []}
        type_counts: Dict[str, int] = {}
        source_counts: Dict[str, int] = {}
        root_cause_counts: Dict[str, int] = {}
        severity_counts: Dict[str, int] = {}
        total_deviation = 0.0
        for fb in feedbacks:
            type_key = fb.feedback_type.value
            type_counts[type_key] = type_counts.get(type_key, 0) + 1
            source_counts[fb.source_id] = source_counts.get(fb.source_id, 0) + 1
            severity_counts[fb.severity.value] = severity_counts.get(fb.severity.value, 0) + 1
            total_deviation += fb.deviation_score
            for rc in fb.root_causes:
                root_cause_counts[rc] = root_cause_counts.get(rc, 0) + 1
        avg_deviation = total_deviation / len(feedbacks)
        patterns = []
        sorted_root_causes = sorted(root_cause_counts.items(), key=lambda x: x[1], reverse=True)
        for cause, count in sorted_root_causes[:5]:
            patterns.append({"type": "recurring_root_cause", "cause": cause, "count": count})
        sorted_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)
        for source_id, count in sorted_sources[:5]:
            if count > 1:
                patterns.append({"type": "repeated_source", "source_id": source_id, "count": count})
        return {
            "total": len(feedbacks),
            "type_distribution": type_counts,
            "severity_distribution": severity_counts,
            "avg_deviation_score": avg_deviation,
            "top_root_causes": dict(sorted_root_causes[:5]),
            "patterns": patterns,
        }

    def generate_lesson(self, feedback: Feedback) -> str:
        if feedback.feedback_type == FeedbackType.ACTION_RESULT:
            return self._generate_action_lesson(feedback)
        elif feedback.feedback_type == FeedbackType.OUTCOME_DEVIATION:
            return self._generate_deviation_lesson(feedback)
        elif feedback.feedback_type == FeedbackType.DECISION_FEEDBACK:
            return self._generate_decision_lesson(feedback)
        elif feedback.feedback_type == FeedbackType.LESSON_LEARNED:
            return feedback.lesson_learned or feedback.description
        return ""

    def _generate_action_lesson(self, feedback: Feedback) -> str:
        outcome = feedback.data.get("outcome", "")
        if outcome == "success":
            return f"Action {feedback.source_id} completed successfully."
        parts = [f"Action {feedback.source_id} failed."]
        if feedback.deviation_factors:
            parts.append(f"Factors: {', '.join(feedback.deviation_factors)}")
        if feedback.root_causes:
            parts.append(f"Root causes: {', '.join(feedback.root_causes)}")
        return " ".join(parts)

    def _generate_deviation_lesson(self, feedback: Feedback) -> str:
        mismatched = feedback.data.get("mismatched_keys", [])
        parts = [f"Deviation detected for {feedback.source_id}."]
        if mismatched:
            parts.append(f"Mismatched fields: {', '.join(mismatched)}")
        if feedback.root_causes:
            parts.append(f"Root causes: {', '.join(feedback.root_causes)}")
        return " ".join(parts)

    def _generate_decision_lesson(self, feedback: Feedback) -> str:
        rating = feedback.data.get("rating")
        parts = [f"Decision {feedback.source_id} feedback."]
        if rating is not None:
            parts.append(f"Rating: {rating:.2f}")
        if feedback.description:
            parts.append(feedback.description)
        return " ".join(parts)
