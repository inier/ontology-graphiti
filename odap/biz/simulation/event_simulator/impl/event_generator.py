import logging
import uuid
import random
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


def _ev_audit(action: str, *, result_status: str = "success",
              result_message: str = "", resource: str = None,
              details: Dict[str, Any] = None) -> None:
    """Event Simulator 审计便捷函数：失败仅 warning，不阻断业务"""
    try:
        from odap.infra.security.audit_helper import storage_audit
        storage_audit(
            action=action,
            result_status=result_status,
            result_message=result_message,
            resource=resource,
            details=details or {},
            service="event_simulator",
        )
    except Exception as e:
        logger.warning(f"Audit write failed (event_sim) action={action}: {e}")

EVENT_DATA_TEMPLATES = {
    "engage": {
        "intensity": (0.6, 1.0),
        "capability_index_delta": (-0.3, -0.1),
        "readiness_delta": (-0.2, -0.05),
    },
    "hold": {
        "intensity": (0.4, 0.8),
        "capability_index_delta": (-0.1, 0.0),
        "readiness_delta": (0.05, 0.15),
    },
    "withdraw": {
        "intensity": (0.3, 0.6),
        "capability_index_delta": (-0.15, -0.05),
        "readiness_delta": (-0.25, -0.1),
    },
    "support": {
        "intensity": (0.5, 0.9),
        "readiness_delta": (0.1, 0.2),
    },
    "supply": {
        "intensity": (0.2, 0.5),
        "resource_level_delta": (0.1, 0.3),
    },
    "transport": {
        "intensity": (0.2, 0.4),
        "resource_level_delta": (-0.05, 0.05),
    },
    "deploy": {
        "intensity": (0.5, 0.8),
        "resource_level_delta": (-0.15, -0.05),
    },
    "observe": {
        "intensity": (0.1, 0.3),
        "information_gain": (0.3, 0.8),
    },
    "patrol": {
        "intensity": (0.2, 0.4),
        "information_gain": (0.2, 0.5),
    },
    "scan": {
        "intensity": (0.3, 0.6),
        "information_gain": (0.5, 1.0),
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
    "engage": "conflict", "hold": "conflict", "withdraw": "conflict", "support": "conflict",
    "supply": "logistics", "transport": "logistics", "deploy": "logistics",
    "observe": "recon", "patrol": "recon", "scan": "recon", "report": "recon",
    "communicate": "comm", "broadcast": "comm", "relay": "comm", "interrupt": "comm",
    "create": "crud", "update": "crud", "delete": "crud", "move": "crud", "interact": "crud",
}

CATEGORY_BASE_RELEVANCE = {
    "conflict": 0.7,
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
        ontology_id: str = "",
    ) -> Dict[str, Any]:
        sequence_id = f"seq_{uuid.uuid4().hex[:12]}"
        ontology_entity_types = entity_types or self._get_entity_types(workspace_id)

        if not ontology_entity_types:
            ontology_entity_types = ["entity", "relation", "event", "attribute"]

        # 从本体加载事件类型（若提供 ontology_id）
        ontology_event_types = self._load_event_types_from_ontology(ontology_id, workspace_id)
        event_type_source = "ontology" if ontology_event_types else "hardcoded"

        events = []
        start_time = datetime.fromisoformat(base_time) if base_time else datetime.now(timezone.utc)
        generated_entity_deltas_count = 0

        try:
            for i in range(count):
                event_type = self._pick_event_type(template_id, ontology_entity_types, ontology_event_types)
                target_type = random.choice(ontology_entity_types)
                event = {
                    "event_id": f"evt_{uuid.uuid4().hex[:8]}",
                    "sequence_id": sequence_id,
                    "event_type": event_type,
                    "target_entity_type": target_type,
                    "timestamp": (start_time + timedelta(minutes=i)).isoformat(),
                    "data": self._generate_event_data(event_type, target_type, ontology_event_types),
                    "status": "pending",
                    "ontology_id": ontology_id,
                    "ontology_relevance": self._compute_ontology_relevance(
                        event_type, target_type, ontology_id=ontology_id, workspace_id=workspace_id
                    ),
                }
                events.append(event)
                data = event.get("data", {})
                generated_entity_deltas_count += sum(
                    1 for k in data.keys() if "delta" in k.lower() or "_delta" in k.lower()
                )

            self._generated_sequences[sequence_id] = events

            result = {
                "sequence_id": sequence_id,
                "template_id": template_id,
                "workspace_id": workspace_id,
                "ontology_id": ontology_id,
                "total_events": len(events),
                "events": events,
                "entity_types_used": ontology_entity_types,
                "event_type_source": event_type_source,
            }

            if self._storage:
                try:
                    self._storage.save_sequence({
                        "sequence_id": sequence_id,
                        "template_id": template_id,
                        "workspace_id": workspace_id,
                        "ontology_id": ontology_id,
                        "events": events,
                        "total_events": len(events),
                        "event_type_source": event_type_source,
                    })
                except Exception:
                    logger.warning("Failed to persist sequence to storage")

            _ev_audit(
                "event_generate_batch",
                result_status="success",
                resource=sequence_id,
                details={
                    "sequence_id": sequence_id,
                    "template_id": template_id,
                    "events_count": len(events),
                    "generated_entity_deltas_count": generated_entity_deltas_count,
                    "affected_relations_count": len(events),
                    "ontology_id": ontology_id,
                },
            )
            return result
        except Exception as e:
            _ev_audit(
                "event_generate_batch",
                result_status="failure",
                resource=sequence_id,
                result_message=str(e),
                details={
                    "sequence_id": sequence_id,
                    "template_id": template_id,
                    "events_count": count,
                },
            )
            raise

    def inject_event(
        self,
        event_type: str,
        target_entity_type: str,
        data: Dict[str, Any] = None,
        workspace_id: str = "default",
        timestamp: Optional[str] = None,
        ontology_id: str = "",
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
            "ontology_id": ontology_id,
            "ontology_relevance": self._compute_ontology_relevance(
                event_type, target_entity_type, ontology_id=ontology_id, workspace_id=workspace_id
            ),
        }
        generated_entity_deltas_count = sum(
            1 for k in (data or {}).keys() if "delta" in k.lower() or "_delta" in k.lower()
        )
        _ev_audit(
            "event_ingest",
            result_status="success",
            resource=event_id,
            details={
                "event_id": event_id,
                "event_type": event_type,
                "events_count": 1,
                "generated_entity_deltas_count": generated_entity_deltas_count,
                "affected_relations_count": 1,
                "ontology_id": ontology_id,
            },
        )
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

    def _pick_event_type(self, template_id: str, entity_types: List[str],
                         ontology_event_types: Optional[Dict[str, Any]] = None) -> str:
        # 优先使用本体事件类型
        if ontology_event_types:
            ontology_keys = list(ontology_event_types.keys())
            if ontology_keys:
                return random.choice(ontology_keys)

        template_event_map = {
            "conflict": ["engage", "hold", "withdraw", "support"],
            "logistics": ["supply", "transport", "deploy", "withdraw"],
            "reconnaissance": ["observe", "patrol", "scan", "report"],
            "communication": ["communicate", "broadcast", "relay", "interrupt"],
            "default": ["create", "update", "delete", "move", "interact"],
        }
        event_pool = template_event_map.get(template_id, template_event_map["default"])
        return random.choice(event_pool)

    def _generate_event_data(self, event_type: str, target_type: str,
                             ontology_event_types: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        data = {
            "event_type": event_type,
            "target_type": target_type,
        }

        # 优先使用本体事件模板
        if ontology_event_types and event_type in ontology_event_types:
            ontology_template = ontology_event_types[event_type]
            intensity_range = ontology_template.get("intensity", (0.1, 1.0))
            data["intensity"] = round(random.uniform(intensity_range[0], intensity_range[1]), 3)
            for field, range_val in ontology_template.items():
                if field in ("_source", "target_object_type", "intensity"):
                    continue
                if isinstance(range_val, (list, tuple)) and len(range_val) == 2:
                    data[field] = round(random.uniform(range_val[0], range_val[1]), 3)
            return data

        template = EVENT_DATA_TEMPLATES.get(event_type)
        if template:
            for field, (low, high) in template.items():
                data[field] = round(random.uniform(low, high), 3)
        else:
            data["intensity"] = round(random.uniform(0.1, 1.0), 2)
            if event_type in ("engage", "hold", "withdraw", "support"):
                data["capability_index_delta"] = round(random.uniform(-0.3, 0.3), 3)
                data["readiness_delta"] = round(random.uniform(-0.2, 0.2), 3)
            elif event_type in ("supply", "transport", "deploy", "withdraw"):
                data["resource_level_delta"] = round(random.uniform(-0.2, 0.2), 3)
            elif event_type in ("observe", "patrol", "scan", "report"):
                data["information_gain"] = round(random.uniform(0.0, 1.0), 3)
            elif event_type in ("communicate", "broadcast", "relay", "interrupt"):
                data["communication_quality"] = round(random.uniform(0.5, 1.0), 3)

        return data

    def _compute_ontology_relevance(self, event_type: str, target_type: str,
                                    ontology_id: str = "", workspace_id: str = "default") -> float:
        # 优先从本体查询相关性
        if ontology_id:
            oms_relevance = self._lookup_ontology_relevance(event_type, target_type, ontology_id, workspace_id)
            if oms_relevance is not None:
                return oms_relevance

        relevance_map = {
            ("engage", "entity"): 0.9, ("engage", "relation"): 0.7,
            ("hold", "entity"): 0.85, ("hold", "relation"): 0.6,
            ("move", "entity"): 0.7, ("move", "event"): 0.5,
            ("create", "entity"): 0.8, ("create", "attribute"): 0.5,
            ("update", "attribute"): 0.6, ("update", "entity"): 0.5,
            ("delete", "entity"): 0.75, ("delete", "relation"): 0.6,
            ("interact", "relation"): 0.8, ("interact", "entity"): 0.6,
            ("supply", "entity"): 0.7, ("supply", "attribute"): 0.5,
            ("observe", "entity"): 0.6, ("observe", "event"): 0.7,
            ("communicate", "relation"): 0.7, ("communicate", "entity"): 0.4,
            ("support", "entity"): 0.85, ("support", "relation"): 0.6,
            ("withdraw", "entity"): 0.8, ("withdraw", "event"): 0.6,
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

    def _load_event_types_from_ontology(self, ontology_id: str, workspace_id: str = "default") -> Dict[str, Any]:
        """从 OMS action_types 动态构建事件模板。"""
        if not ontology_id:
            return {}

        try:
            from odap.biz.core.ontology.application.oms.services.oms_service import OMSService
            oms = OMSService.get_instance()
            action_types = oms.list_action_types()

            templates = {}
            for at in action_types:
                name = at.get("name", "")
                if not name or not at.get("is_active", True):
                    continue

                template: Dict[str, Any] = {"_source": "ontology"}

                # 从 parameters 解析 intensity
                params = at.get("parameters", [])
                if isinstance(params, list):
                    for param in params:
                        pname = param.get("name", "")
                        if "intensity" in pname.lower():
                            default_val = param.get("default")
                            if isinstance(default_val, (int, float)):
                                template["intensity"] = (max(0.1, default_val - 0.3), min(1.0, default_val + 0.3))
                                break

                if "intensity" not in template:
                    template["intensity"] = (0.1, 1.0)

                # 从 writeback_config 解析 delta 字段
                writeback = at.get("writeback_config", {})
                if isinstance(writeback, dict):
                    for delta_field in ("capability_index_delta", "resource_level_delta", "readiness_delta"):
                        if delta_field in writeback:
                            val = writeback[delta_field]
                            if isinstance(val, (int, float)):
                                template[delta_field] = (min(val, 0), max(val, 0))

                target_obj_type = at.get("target_object_type", "")
                if target_obj_type:
                    template["target_object_type"] = target_obj_type

                templates[name] = template

            return templates
        except Exception as e:
            logger.debug(f"Failed to load event types from ontology: {e}")
            return {}

    def _lookup_ontology_relevance(self, event_type: str, target_type: str,
                                   ontology_id: str, workspace_id: str) -> Optional[float]:
        """从 OMS action_types 查询事件相关性。"""
        try:
            from odap.biz.core.ontology.application.oms.services.oms_service import OMSService
            oms = OMSService.get_instance()
            action_types = oms.list_action_types()

            for at in action_types:
                if at.get("name", "") != event_type:
                    continue

                # 优先从 writeback_config.relevance 读取
                writeback = at.get("writeback_config", {})
                if isinstance(writeback, dict) and "relevance" in writeback:
                    return float(writeback["relevance"])

                # 根据 target_object_type 与 target_type 的匹配度推断
                target_obj_type = at.get("target_object_type", "")
                if target_obj_type and target_type:
                    if target_obj_type.lower() == target_type.lower():
                        return 0.85
                    if target_obj_type.lower() in target_type.lower() or target_type.lower() in target_obj_type.lower():
                        return 0.65

                return None
            return None
        except Exception as e:
            logger.debug(f"Failed to lookup ontology relevance: {e}")
            return None

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
