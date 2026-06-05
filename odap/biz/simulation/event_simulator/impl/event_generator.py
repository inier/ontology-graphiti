import logging
import uuid
import random
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

EVENT_DATA_TEMPLATES = {
    "attack": {
        "intensity": (0.6, 1.0),
        "combat_power_delta": (-0.3, -0.1),
        "morale_delta": (-0.2, -0.05),
    },
    "defend": {
        "intensity": (0.4, 0.8),
        "combat_power_delta": (-0.1, 0.0),
        "morale_delta": (0.05, 0.15),
    },
    "retreat": {
        "intensity": (0.3, 0.6),
        "combat_power_delta": (-0.15, -0.05),
        "morale_delta": (-0.25, -0.1),
    },
    "reinforce": {
        "intensity": (0.5, 0.9),
        "morale_delta": (0.1, 0.2),
    },
    "supply": {
        "intensity": (0.2, 0.5),
        "supply_level_delta": (0.1, 0.3),
    },
    "transport": {
        "intensity": (0.2, 0.4),
        "supply_level_delta": (-0.05, 0.05),
    },
    "deploy": {
        "intensity": (0.5, 0.8),
        "supply_level_delta": (-0.15, -0.05),
    },
    "observe": {
        "intensity": (0.1, 0.3),
        "intelligence_gain": (0.3, 0.8),
    },
    "patrol": {
        "intensity": (0.2, 0.4),
        "intelligence_gain": (0.2, 0.5),
    },
    "scan": {
        "intensity": (0.3, 0.6),
        "intelligence_gain": (0.5, 1.0),
    },
    "communicate": {
        "intensity": (0.1, 0.3),
        "communication_quality": (0.7, 1.0),
    },
    "broadcast": {
        "intensity": (0.2, 0.4),
        "communication_quality": (0.6, 0.9),
    },
}

EVENT_TYPE_CATEGORY = {
    "attack": "combat", "defend": "combat", "retreat": "combat", "reinforce": "combat",
    "supply": "logistics", "transport": "logistics", "deploy": "logistics", "withdraw": "logistics",
    "observe": "recon", "patrol": "recon", "scan": "recon", "report": "recon",
    "communicate": "comm", "broadcast": "comm", "relay": "comm", "interrupt": "comm",
    "create": "crud", "update": "crud", "delete": "crud", "move": "crud", "interact": "crud",
}

CATEGORY_BASE_RELEVANCE = {
    "combat": 0.7,
    "logistics": 0.5,
    "recon": 0.55,
    "comm": 0.45,
    "crud": 0.5,
}


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
        self._storage = None
        try:
            from ..storage import SQLiteEventStorage
            self._storage = SQLiteEventStorage()
        except Exception:
            logger.warning("SQLiteEventStorage not available, using in-memory only")
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

        result = {
            "sequence_id": sequence_id,
            "template_id": template_id,
            "workspace_id": workspace_id,
            "total_events": len(events),
            "events": events,
            "entity_types_used": ontology_entity_types,
        }

        if self._storage:
            try:
                self._storage.save_sequence({
                    "sequence_id": sequence_id,
                    "template_id": template_id,
                    "workspace_id": workspace_id,
                    "events": events,
                    "total_events": len(events),
                })
            except Exception:
                logger.warning("Failed to persist sequence to storage")

        return result

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
            from odap.biz.core.ontology.design.model.services.model_service import ModelService
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

        template = EVENT_DATA_TEMPLATES.get(event_type)
        if template:
            for field, (low, high) in template.items():
                data[field] = round(random.uniform(low, high), 3)
        else:
            data["intensity"] = round(random.uniform(0.1, 1.0), 2)
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
            ("attack", "entity"): 0.9, ("attack", "relation"): 0.7,
            ("defend", "entity"): 0.85, ("defend", "relation"): 0.6,
            ("move", "entity"): 0.7, ("move", "event"): 0.5,
            ("create", "entity"): 0.8, ("create", "attribute"): 0.5,
            ("update", "attribute"): 0.6, ("update", "entity"): 0.5,
            ("delete", "entity"): 0.75, ("delete", "relation"): 0.6,
            ("interact", "relation"): 0.8, ("interact", "entity"): 0.6,
            ("supply", "entity"): 0.7, ("supply", "attribute"): 0.5,
            ("observe", "entity"): 0.6, ("observe", "event"): 0.7,
            ("communicate", "relation"): 0.7, ("communicate", "entity"): 0.4,
            ("reinforce", "entity"): 0.85, ("reinforce", "relation"): 0.6,
            ("retreat", "entity"): 0.8, ("retreat", "event"): 0.6,
            ("patrol", "entity"): 0.5, ("patrol", "event"): 0.6,
            ("scan", "entity"): 0.6, ("scan", "attribute"): 0.7,
        }
        key = (event_type, target_type)
        if key in relevance_map:
            return relevance_map[key]
        category = EVENT_TYPE_CATEGORY.get(event_type)
        base = CATEGORY_BASE_RELEVANCE.get(category, 0.5) if category else 0.5
        type_modifier = {"entity": 0.1, "relation": 0.0, "event": 0.05, "attribute": -0.05}.get(target_type, 0.0)
        return round(max(0.1, min(1.0, base + type_modifier)), 2)

    def get_sequence(self, sequence_id: str) -> Dict[str, Any]:
        events = self._generated_sequences.get(sequence_id)
        if events:
            return {"sequence_id": sequence_id, "events": events, "total": len(events)}

        if self._storage:
            try:
                stored = self._storage.get_sequence(sequence_id)
                if stored:
                    return {
                        "sequence_id": stored["sequence_id"],
                        "events": stored.get("events", []),
                        "total": stored.get("total_events", 0),
                    }
            except Exception:
                logger.warning("Failed to load sequence from storage")

        return {"status": "error", "message": f"Sequence {sequence_id} not found"}

    def list_templates(self) -> List[Dict[str, Any]]:
        if self._storage:
            try:
                return self._storage.list_templates()
            except Exception:
                logger.warning("Failed to list templates from storage")
        return []


def get_event_generator() -> EventGenerator:
    return EventGenerator()
