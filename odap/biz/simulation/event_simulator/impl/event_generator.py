import logging
import uuid
import random
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class EventGenerator:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._generated_sequences: Dict[str, List[Dict[str, Any]]] = {}
        self._initialized = True

    def generate_event_sequence(
        self,
        template_id: str,
        workspace_id: str = "default",
        count: int = 5,
        base_time: Optional[str] = None,
        entity_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        sequence_id = f"seq_{uuid.uuid4().hex[:12]}"
        ontology_entity_types = entity_types or self._get_entity_types(workspace_id)

        if not ontology_entity_types:
            ontology_entity_types = ["entity", "relation", "event", "attribute"]

        events = []
        start_time = datetime.fromisoformat(base_time) if base_time else datetime.now(timezone.utc)

        for i in range(count):
            event_type = self._pick_event_type(template_id, ontology_entity_types)
            target_type = random.choice(ontology_entity_types)
            event = {
                "event_id": f"evt_{uuid.uuid4().hex[:8]}",
                "sequence_id": sequence_id,
                "event_type": event_type,
                "target_entity_type": target_type,
                "timestamp": datetime(
                    start_time.year, start_time.month, start_time.day,
                    start_time.hour, start_time.minute + i,
                    tzinfo=timezone.utc,
                ).isoformat(),
                "data": self._generate_event_data(event_type, target_type),
                "status": "pending",
                "ontology_relevance": self._compute_ontology_relevance(event_type, target_type),
            }
            events.append(event)

        self._generated_sequences[sequence_id] = events
        return {
            "sequence_id": sequence_id,
            "template_id": template_id,
            "workspace_id": workspace_id,
            "total_events": len(events),
            "events": events,
            "entity_types_used": ontology_entity_types,
        }

    def inject_event(
        self,
        event_type: str,
        target_entity_type: str,
        data: Dict[str, Any] = None,
        workspace_id: str = "default",
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        event_id = f"evt_{uuid.uuid4().hex[:8]}"
        event = {
            "event_id": event_id,
            "event_type": event_type,
            "target_entity_type": target_entity_type,
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "data": data or {},
            "status": "injected",
            "workspace_id": workspace_id,
            "ontology_relevance": self._compute_ontology_relevance(event_type, target_entity_type),
        }
        return event

    def _get_entity_types(self, workspace_id: str) -> List[str]:
        try:
            from odap.biz.core.ontology.model.services.model_service import ModelService
            service = ModelService()
            result = service.list_entity_types(filters=None, page=1, page_size=100)
            entity_types = []
            for et in result.get("entity_types", []):
                name = et.get("name", "")
                if name:
                    entity_types.append(name)
            return entity_types
        except Exception as e:
            logger.warning(f"Failed to get entity types from ModelService: {e}")
            return []

    def _pick_event_type(self, template_id: str, entity_types: List[str]) -> str:
        template_event_map = {
            "conflict": ["attack", "defend", "retreat", "reinforce"],
            "logistics": ["supply", "transport", "deploy", "withdraw"],
            "reconnaissance": ["observe", "patrol", "scan", "report"],
            "communication": ["communicate", "broadcast", "relay", "interrupt"],
            "default": ["create", "update", "delete", "move", "interact"],
        }
        event_pool = template_event_map.get(template_id, template_event_map["default"])
        return random.choice(event_pool)

    def _generate_event_data(self, event_type: str, target_type: str) -> Dict[str, Any]:
        data = {
            "event_type": event_type,
            "target_type": target_type,
        }

        intensity = round(random.uniform(0.1, 1.0), 2)
        data["intensity"] = intensity

        if event_type in ("attack", "defend", "retreat", "reinforce"):
            data["combat_power_delta"] = round(random.uniform(-0.3, 0.3), 3)
            data["morale_delta"] = round(random.uniform(-0.2, 0.2), 3)
        elif event_type in ("supply", "transport", "deploy", "withdraw"):
            data["supply_level_delta"] = round(random.uniform(-0.2, 0.2), 3)
        elif event_type in ("observe", "patrol", "scan", "report"):
            data["intelligence_gain"] = round(random.uniform(0.0, 1.0), 3)
        elif event_type in ("communicate", "broadcast", "relay", "interrupt"):
            data["communication_quality"] = round(random.uniform(0.5, 1.0), 3)

        return data

    def _compute_ontology_relevance(self, event_type: str, target_type: str) -> float:
        relevance_map = {
            ("attack", "entity"): 0.9,
            ("defend", "entity"): 0.85,
            ("move", "entity"): 0.7,
            ("create", "entity"): 0.8,
            ("update", "attribute"): 0.6,
            ("delete", "entity"): 0.75,
            ("interact", "relation"): 0.8,
        }
        return relevance_map.get((event_type, target_type), round(random.uniform(0.3, 0.7), 2))

    def get_sequence(self, sequence_id: str) -> Dict[str, Any]:
        events = self._generated_sequences.get(sequence_id)
        if not events:
            return {"status": "error", "message": f"Sequence {sequence_id} not found"}
        return {"sequence_id": sequence_id, "events": events, "total": len(events)}


def get_event_generator() -> EventGenerator:
    return EventGenerator()
