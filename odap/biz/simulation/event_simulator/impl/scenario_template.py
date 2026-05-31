import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

PREDEFINED_TEMPLATES = [
    {
        "template_id": "tpl_conflict_escalation",
        "name": "冲突升级",
        "description": "模拟冲突逐步升级的事件序列",
        "category": "conflict",
        "event_types": ["skirmish", "engagement", "escalation", "full_conflict"],
        "default_count": 8,
        "parameters": {
            "escalation_rate": {"type": "float", "default": 0.3, "min": 0.1, "max": 1.0},
            "initial_intensity": {"type": "float", "default": 0.2, "min": 0.0, "max": 1.0},
        },
    },
    {
        "template_id": "tpl_logistics_disruption",
        "name": "后勤中断",
        "description": "模拟供应链中断事件序列",
        "category": "logistics",
        "event_types": ["delay", "shortage", "reroute", "recovery"],
        "default_count": 6,
        "parameters": {
            "disruption_severity": {"type": "float", "default": 0.5, "min": 0.1, "max": 1.0},
            "recovery_time_steps": {"type": "int", "default": 3, "min": 1, "max": 10},
        },
    },
    {
        "template_id": "tpl_reconnaissance_sweep",
        "name": "侦察扫描",
        "description": "模拟区域侦察事件序列",
        "category": "reconnaissance",
        "event_types": ["deploy_sensor", "patrol", "scan_area", "report_findings"],
        "default_count": 10,
        "parameters": {
            "coverage_area": {"type": "float", "default": 0.6, "min": 0.1, "max": 1.0},
            "detection_probability": {"type": "float", "default": 0.7, "min": 0.0, "max": 1.0},
        },
    },
    {
        "template_id": "tpl_communication_failure",
        "name": "通信故障",
        "description": "模拟通信系统中断与恢复",
        "category": "communication",
        "event_types": ["interference", "partial_failure", "total_failure", "restoration"],
        "default_count": 5,
        "parameters": {
            "failure_duration": {"type": "int", "default": 4, "min": 1, "max": 20},
            "backup_available": {"type": "bool", "default": True},
        },
    },
    {
        "template_id": "tpl_resource_allocation",
        "name": "资源调配",
        "description": "模拟资源重新分配事件序列",
        "category": "management",
        "event_types": ["assess", "reallocate", "deploy", "monitor"],
        "default_count": 7,
        "parameters": {
            "resource_type": {"type": "string", "default": "personnel"},
            "reallocation_scope": {"type": "float", "default": 0.4, "min": 0.1, "max": 1.0},
        },
    },
]


class ScenarioTemplateManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._templates: Dict[str, Dict[str, Any]] = {}
        for tpl in PREDEFINED_TEMPLATES:
            self._templates[tpl["template_id"]] = tpl
        self._custom_templates: Dict[str, Dict[str, Any]] = {}
        self._initialized = True

    def list_templates(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        all_templates = list(self._templates.values()) + list(self._custom_templates.values())
        if category:
            all_templates = [t for t in all_templates if t.get("category") == category]
        return [
            {
                "template_id": t["template_id"],
                "name": t["name"],
                "description": t.get("description", ""),
                "category": t.get("category", ""),
                "event_types": t.get("event_types", []),
                "default_count": t.get("default_count", 5),
            }
            for t in all_templates
        ]

    def get_template(self, template_id: str) -> Dict[str, Any]:
        template = self._templates.get(template_id) or self._custom_templates.get(template_id)
        if not template:
            return {"status": "error", "message": f"Template {template_id} not found"}
        return template

    def create_template(self, data: Dict[str, Any]) -> Dict[str, Any]:
        name = data.get("name", "")
        if not name:
            return {"status": "error", "message": "name is required"}

        template_id = data.get("template_id", f"tpl_custom_{uuid.uuid4().hex[:8]}")
        template = {
            "template_id": template_id,
            "name": name,
            "description": data.get("description", ""),
            "category": data.get("category", "custom"),
            "event_types": data.get("event_types", []),
            "default_count": data.get("default_count", 5),
            "parameters": data.get("parameters", {}),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_custom": True,
        }
        self._custom_templates[template_id] = template
        return {
            "template_id": template_id,
            "name": name,
            "category": template["category"],
        }

    def delete_template(self, template_id: str) -> Dict[str, Any]:
        if template_id in self._custom_templates:
            self._custom_templates.pop(template_id)
            return {"status": "ok", "template_id": template_id}
        if template_id in self._templates:
            return {"status": "error", "message": "Cannot delete predefined template"}
        return {"status": "error", "message": f"Template {template_id} not found"}


def get_scenario_template_manager() -> ScenarioTemplateManager:
    return ScenarioTemplateManager()
