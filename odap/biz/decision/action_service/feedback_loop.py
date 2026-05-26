import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ActionFeedback(BaseModel):
    action_id: str
    decision_id: Optional[str] = None
    outcome: str = ""
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    deviation_score: Optional[float] = None
    deviation_factors: Optional[List[str]] = None
    root_causes: Optional[List[str]] = None
    lesson_learned: Optional[str] = None
    timestamp: str = ""


class FeedbackCollector:
    def __init__(self):
        self._graph_manager = None

    @property
    def graph(self):
        if self._graph_manager is None:
            from odap.infra.graph.graph_service import GraphManager
            self._graph_manager = GraphManager()
        return self._graph_manager

    def collect(self, action_record: Dict[str, Any]) -> ActionFeedback:
        execution_result = action_record.get('execution_result') or {}
        success = execution_result.get('success', False)
        message = execution_result.get('message', '')
        data = execution_result.get('data')

        outcome = "success" if success else "failure"
        error_message = None if success else message

        return ActionFeedback(
            action_id=action_record.get('action_record_id', ''),
            decision_id=action_record.get('agent_id'),
            outcome=outcome,
            result_data=data,
            error_message=error_message,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


class FeedbackAnalyzer:
    def analyze_deviation(self, feedback: ActionFeedback, expected_outcome: Optional[Dict[str, Any]] = None) -> ActionFeedback:
        deviation_score = 0.0
        deviation_factors = []
        root_causes = []

        if feedback.outcome == "failure":
            deviation_score = 1.0
            if feedback.error_message:
                deviation_factors.append(f"execution_error: {feedback.error_message[:100]}")
                if "timeout" in (feedback.error_message or "").lower():
                    root_causes.append("timeout")
                    deviation_score = 0.7
                elif "permission" in (feedback.error_message or "").lower():
                    root_causes.append("permission_denied")
                    deviation_score = 0.5
                elif "not found" in (feedback.error_message or "").lower():
                    root_causes.append("target_missing")
                    deviation_score = 0.6
                else:
                    root_causes.append("unknown_execution_failure")

        if expected_outcome:
            actual_data = feedback.result_data or {}
            expected_score = self._compare_actual_vs_expected(actual_data, expected_outcome)
            if expected_score > 0:
                deviation_score = max(deviation_score, expected_score)
                deviation_factors.extend(self._deviation_factor_list)

        feedback.deviation_score = deviation_score
        feedback.deviation_factors = deviation_factors
        feedback.root_causes = root_causes
        return feedback

    def _compare_actual_vs_expected(self, actual_data: Dict[str, Any], expected_outcome: Dict[str, Any]) -> float:
        self._deviation_factor_list = []
        max_score = 0.0
        field_count = 0
        mismatch_count = 0

        for key, expected_value in expected_outcome.items():
            if key.startswith('_'):
                continue
            actual_value = actual_data.get(key)
            field_count += 1

            if actual_value is None:
                mismatch_count += 1
                self._deviation_factor_list.append(f"missing_field: {key} (expected={expected_value})")
                continue

            if isinstance(expected_value, (int, float)) and isinstance(actual_value, (int, float)):
                if expected_value != 0:
                    pct_diff = abs(actual_value - expected_value) / abs(expected_value)
                    if pct_diff > 0.5:
                        mismatch_count += 1
                        self._deviation_factor_list.append(
                            f"numeric_deviation: {key} expected={expected_value}, actual={actual_value}, diff={pct_diff:.1%}"
                        )
                    elif pct_diff > 0.1:
                        self._deviation_factor_list.append(
                            f"numeric_minor_deviation: {key} expected={expected_value}, actual={actual_value}, diff={pct_diff:.1%}"
                        )
                elif actual_value != expected_value:
                    mismatch_count += 1
                    self._deviation_factor_list.append(
                        f"value_mismatch: {key} expected={expected_value}, actual={actual_value}"
                    )
            elif isinstance(expected_value, str) and isinstance(actual_value, str):
                if expected_value.lower() != actual_value.lower():
                    mismatch_count += 1
                    self._deviation_factor_list.append(
                        f"state_mismatch: {key} expected={expected_value}, actual={actual_value}"
                    )
            elif isinstance(expected_value, list):
                if set(str(v) for v in (actual_value or [])) != set(str(v) for v in expected_value):
                    mismatch_count += 1
                    self._deviation_factor_list.append(
                        f"list_mismatch: {key} expected={expected_value}, actual={actual_value}"
                    )
            elif actual_value != expected_value:
                mismatch_count += 1
                self._deviation_factor_list.append(
                    f"value_mismatch: {key} expected={expected_value}, actual={actual_value}"
                )

        if field_count > 0:
            max_score = mismatch_count / field_count

        return max_score

    def generate_lesson(self, feedback: ActionFeedback) -> str:
        if feedback.outcome == "success":
            return f"Action {feedback.action_id} completed successfully."
        parts = [f"Action {feedback.action_id} failed."]
        if feedback.deviation_factors:
            parts.append(f"Factors: {', '.join(feedback.deviation_factors)}")
        if feedback.root_causes:
            parts.append(f"Root causes: {', '.join(feedback.root_causes)}")
        return " ".join(parts)


class FeedbackAggregator:
    def __init__(self):
        self._graph_manager = None
        self._hook_registry = None

    @property
    def graph(self):
        if self._graph_manager is None:
            from odap.infra.graph.graph_service import GraphManager
            self._graph_manager = GraphManager()
        return self._graph_manager

    @property
    def hook_registry(self):
        if self._hook_registry is None:
            try:
                from odap.infra.events.hook_system import HookRegistry
                self._hook_registry = HookRegistry()
            except Exception:
                self._hook_registry = None
        return self._hook_registry

    def aggregate_and_update(self, feedback: ActionFeedback, action_record: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            'action_id': feedback.action_id,
            'graph_updated': False,
            'episode_created': False,
            'hook_emitted': False,
        }

        target_id = action_record.get('target_object_id', '')
        target_type = action_record.get('target_object_type', '')

        if feedback.outcome == "success" and feedback.result_data:
            try:
                properties_to_update = {}
                for key in ('status', 'state', 'phase', 'outcome'):
                    if key in (feedback.result_data or {}):
                        properties_to_update[key] = feedback.result_data[key]
                if properties_to_update:
                    self.graph.update_entity(target_id, properties_to_update)
                    result['graph_updated'] = True
            except Exception as e:
                logger.warning(f"FeedbackAggregator: graph update failed: {e}")

        try:
            self._create_feedback_episode(feedback, action_record)
            result['episode_created'] = True
        except Exception as e:
            logger.warning(f"FeedbackAggregator: episode creation failed: {e}")

        try:
            self._emit_feedback_event(feedback, action_record)
            result['hook_emitted'] = True
        except Exception as e:
            logger.warning(f"FeedbackAggregator: hook emission failed: {e}")

        return result

    def _create_feedback_episode(self, feedback: ActionFeedback, action_record: Dict[str, Any]):
        action_type = action_record.get('action_type_id', '')
        target_id = action_record.get('target_object_id', '')
        requested_by = action_record.get('requested_by', 'system')

        try:
            from odap.biz.core.ontology.schema.document import (
                OntologyDocument, OntologyAction, DataSource, DocumentMeta,
                VersionRef, ActionStatus,
            )
            now = datetime.now(timezone.utc).isoformat()
            doc = OntologyDocument(
                doc_type="event",
                source=DataSource(source_type="action_feedback"),
                meta=DocumentMeta(title=f"Action Feedback: {action_type}"),
                entities=[],
                relations=[],
                events=[],
                actions=[OntologyAction(
                    action_id=feedback.action_id,
                    action_type=action_type,
                    actor=requested_by,
                    target=target_id,
                    timestamp=now,
                    parameters=action_record.get('parameters', {}),
                    opa_required=False,
                    status=ActionStatus.EXECUTED.value if feedback.outcome == "success" else ActionStatus.FAILED.value,
                )],
                rules=[],
                constraints=[],
                ontology_version=VersionRef(version_id=f"feedback_{feedback.action_id}"),
            )

            episode_text = doc.to_episode_text()
            self.graph.add_entity(
                entity_id=f"feedback_{feedback.action_id}",
                entity_type="ActionFeedback",
                properties={
                    'action_type': action_type,
                    'target_id': target_id,
                    'outcome': feedback.outcome,
                    'deviation_score': feedback.deviation_score,
                    'lesson_learned': feedback.lesson_learned,
                    'timestamp': feedback.timestamp or now,
                },
            )
            logger.info(f"FeedbackAggregator: created feedback episode for {feedback.action_id}")
        except ImportError:
            logger.debug("OntologyDocument not available, using simple episode")
            self.graph.add_entity(
                entity_id=f"feedback_{feedback.action_id}",
                entity_type="ActionFeedback",
                properties={
                    'action_type': action_type,
                    'target_id': target_id,
                    'outcome': feedback.outcome,
                    'timestamp': feedback.timestamp or datetime.now(timezone.utc).isoformat(),
                },
            )

    def _emit_feedback_event(self, feedback: ActionFeedback, action_record: Dict[str, Any]):
        if not self.hook_registry:
            return
        event_name = f"action.feedback.{feedback.outcome}"
        try:
            self.hook_registry.emit(event_name, data={
                'action_id': feedback.action_id,
                'action_type': action_record.get('action_type_id'),
                'outcome': feedback.outcome,
                'deviation_score': feedback.deviation_score,
                'lesson_learned': feedback.lesson_learned,
            })
        except Exception as e:
            logger.warning(f"FeedbackAggregator: hook emit failed: {e}")


class FeedbackLoop:
    def __init__(self):
        self.collector = FeedbackCollector()
        self.analyzer = FeedbackAnalyzer()
        self.aggregator = FeedbackAggregator()

    async def close_loop(self, action_record: Dict[str, Any], expected_outcome: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        feedback = self.collector.collect(action_record)
        feedback = self.analyzer.analyze_deviation(feedback, expected_outcome)
        feedback.lesson_learned = self.analyzer.generate_lesson(feedback)
        return self.aggregator.aggregate_and_update(feedback, action_record)


_feedback_loop_instance = None


def get_feedback_loop() -> FeedbackLoop:
    global _feedback_loop_instance
    if _feedback_loop_instance is None:
        _feedback_loop_instance = FeedbackLoop()
    return _feedback_loop_instance
