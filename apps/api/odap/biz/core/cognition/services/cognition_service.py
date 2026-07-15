import logging
from typing import Dict, Any, Optional

from odap.biz.platform.roles.api.schemas import RoleType

logger = logging.getLogger(__name__)


class CognitionService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

    def recognize_intent(self, input_text: str, role: str = "guest", ontology_facts: Optional[list] = None) -> Dict[str, Any]:
        try:
            from odap.biz.core.cognition.impl.intent_recognizer import IntentRecognizer
            try:
                role_type = RoleType(role)
            except ValueError:
                role_type = RoleType.GUEST
            recognizer = IntentRecognizer()
            return recognizer.recognize(input_text, role_type, ontology_facts)
        except Exception as e:
            logger.error("CognitionService recognize_intent error: %s", e)
            return {"status": "error", "message": str(e)}

    def navigate(self, entity_id: str, direction: str = "outbound", depth: int = 1) -> Dict[str, Any]:
        try:
            from odap.biz.core.cognition.impl.knowledge_navigator import KnowledgeNavigator
            navigator = KnowledgeNavigator()
            return navigator.navigate(entity_id, direction, depth)
        except Exception as e:
            logger.error("CognitionService navigate error: %s", e)
            return {"status": "error", "message": str(e)}

    def explain(self, decision_id: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            from odap.biz.core.cognition.impl.explanation_engine import ExplanationEngine
            engine = ExplanationEngine()
            return engine.explain(decision_id, context)
        except Exception as e:
            logger.error("CognitionService explain error: %s", e)
            return {"status": "error", "message": str(e)}

    def get_role_view(self, role: str) -> Dict[str, Any]:
        try:
            from odap.biz.core.cognition.impl.role_view_manager import RoleViewManager
            try:
                role_type = RoleType(role)
            except ValueError:
                role_type = RoleType.GUEST
            manager = RoleViewManager()
            view = manager.get_view(role_type)
            if not view:
                return {"status": "error", "message": f"No view for role: {role}"}
            return view
        except Exception as e:
            logger.error("CognitionService get_role_view error: %s", e)
            return {"status": "error", "message": str(e)}

    def update_role_view(self, role: str, config: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from odap.biz.core.cognition.impl.role_view_manager import RoleViewManager
            try:
                role_type = RoleType(role)
            except ValueError:
                role_type = RoleType.GUEST
            manager = RoleViewManager()
            view = manager.get_view(role_type)
            if not view:
                return {"status": "error", "message": f"No view for role: {role}"}
            return manager.update_view(view["view_id"], config)
        except Exception as e:
            logger.error("CognitionService update_role_view error: %s", e)
            return {"status": "error", "message": str(e)}


_cognition_service: Optional[CognitionService] = None


def get_cognition_service() -> CognitionService:
    global _cognition_service
    if _cognition_service is None:
        _cognition_service = CognitionService()
    return _cognition_service
