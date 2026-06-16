import logging
import uuid
from typing import Dict, Any, List, Optional

from odap.biz.platform.roles.api.schemas import RoleType

logger = logging.getLogger(__name__)


class RoleViewManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._views: Dict[str, Dict[str, Any]] = {}
        self._setup_default_views()
        self._initialized = True

    def _setup_default_views(self):
        self._views["director-default"] = {
            "view_id": "director-default",
            "role": RoleType.COMMANDER.value,
            "name": "负责人视图",
            "description": "面向负责人的全局态势视图",
            "capabilities": ["situation_awareness", "decision_support", "resource_allocation", "threat_assessment"],
            "layout_config": {"primary": "situation_map", "secondary": ["timeline", "statistics"], "show_risk": True},
            "filters": {"threat_level": ["high", "critical"], "show_friendly": True, "show_enemy": True},
        }
        self._views["intelligence-default"] = {
            "view_id": "intelligence-default",
            "role": RoleType.INTELLIGENCE.value,
            "name": "情报员视图",
            "description": "面向情报分析员的信息视图",
            "capabilities": ["data_analysis", "pattern_recognition", "intel_gathering", "report_generation"],
            "layout_config": {"primary": "analysis_dashboard", "secondary": ["graph_view", "timeline"]},
            "filters": {"data_type": ["sensor", "signal", "human"], "time_range": "24h"},
        }
        self._views["operator-default"] = {
            "view_id": "operator-default",
            "role": RoleType.OPERATOR.value,
            "name": "操作员视图",
            "description": "面向操作员的执行视图",
            "capabilities": ["task_execution", "system_control", "monitoring", "alert_management"],
            "layout_config": {"primary": "task_list", "secondary": ["system_status", "alerts"]},
            "filters": {"status": ["pending", "in_progress"], "priority": ["high", "medium"]},
        }

    def get_view(self, role: RoleType) -> Optional[Dict[str, Any]]:
        view_id = f"{role.value}-default"
        return self._views.get(view_id)

    def get_all_views(self) -> List[Dict[str, Any]]:
        return list(self._views.values())

    def update_view(self, view_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        if view_id not in self._views:
            return {"status": "error", "message": f"View {view_id} not found"}
        view = self._views[view_id]
        if "capabilities" in config:
            view["capabilities"] = config["capabilities"]
        if "layout_config" in config:
            view["layout_config"] = config["layout_config"]
        if "filters" in config:
            view["filters"] = config["filters"]
        if "name" in config:
            view["name"] = config["name"]
        if "description" in config:
            view["description"] = config["description"]
        return {"status": "success", "view_id": view_id, "view": view}

    def create_custom_view(self, role: RoleType, name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        view_id = str(uuid.uuid4())
        view = {
            "view_id": view_id,
            "role": role.value,
            "name": name,
            "description": config.get("description", "自定义视图"),
            "capabilities": config.get("capabilities", []),
            "layout_config": config.get("layout_config", {}),
            "filters": config.get("filters", {}),
        }
        self._views[view_id] = view
        return view
