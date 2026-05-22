import logging
from typing import Dict, Any

from odap.biz.feedback.models import Feedback, FeedbackType

logger = logging.getLogger(__name__)


class FeedbackAggregator:
    def __init__(self):
        self._graph_manager = None
        self._hook_registry = None

    @property
    def graph(self):
        if self._graph_manager is None:
            try:
                from odap.infra.graph.graph_service import GraphManager
                self._graph_manager = GraphManager()
            except Exception as e:
                logger.warning("FeedbackAggregator: GraphManager init failed: %s", e)
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

    def aggregate_and_update(self, feedback: Feedback) -> Dict[str, Any]:
        result = {
            "feedback_id": feedback.id,
            "source_id": feedback.source_id,
            "feedback_type": feedback.feedback_type.value,
            "graph_updated": False,
            "episode_created": False,
            "hook_emitted": False,
        }

        try:
            self._update_graph(feedback)
            result["graph_updated"] = True
        except Exception as e:
            logger.warning("FeedbackAggregator: graph update failed: %s", e)

        try:
            self._create_feedback_episode(feedback)
            result["episode_created"] = True
        except Exception as e:
            logger.warning("FeedbackAggregator: episode creation failed: %s", e)

        try:
            self._emit_feedback_event(feedback)
            result["hook_emitted"] = True
        except Exception as e:
            logger.warning("FeedbackAggregator: hook emission failed: %s", e)

        return result

    def _update_graph(self, feedback: Feedback):
        if self.graph is None:
            return
        if feedback.feedback_type == FeedbackType.ACTION_RESULT:
            outcome = feedback.data.get("outcome", "")
            result_data = feedback.data.get("result_data", {})
            if outcome == "success" and result_data:
                properties_to_update = {}
                for key in ("status", "state", "phase", "outcome"):
                    if key in result_data:
                        properties_to_update[key] = result_data[key]
                if properties_to_update:
                    self.graph.update_entity(feedback.source_id, properties_to_update)
        elif feedback.feedback_type == FeedbackType.OUTCOME_DEVIATION:
            actual = feedback.data.get("actual", {})
            if actual:
                self.graph.update_entity(feedback.source_id, actual)

    def _create_feedback_episode(self, feedback: Feedback):
        if self.graph is None:
            return
        self.graph.add_entity(
            entity_id=f"feedback_{feedback.id}",
            entity_type="Feedback",
            properties={
                "feedback_type": feedback.feedback_type.value,
                "source_id": feedback.source_id,
                "severity": feedback.severity.value,
                "deviation_score": feedback.deviation_score,
                "root_causes": feedback.root_causes,
                "lesson_learned": feedback.lesson_learned,
                "timestamp": feedback.timestamp.isoformat(),
            },
        )

    def _emit_feedback_event(self, feedback: Feedback):
        if not self.hook_registry:
            return
        event_name = f"feedback.{feedback.feedback_type.value}.{feedback.severity.value}"
        try:
            self.hook_registry.emit(event_name, data={
                "feedback_id": feedback.id,
                "feedback_type": feedback.feedback_type.value,
                "source_id": feedback.source_id,
                "severity": feedback.severity.value,
                "deviation_score": feedback.deviation_score,
                "lesson_learned": feedback.lesson_learned,
            })
        except Exception as e:
            logger.warning("FeedbackAggregator: hook emit failed: %s", e)
