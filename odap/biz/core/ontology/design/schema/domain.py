"""
领域本体模型
基于本体论方法定义领域实体的类型和关系
"""

from typing import Any, Dict

# Domain 模型定位说明 (ADR-056):
# 本模块的 ENTITY_TYPES / DOMAIN_CONFIG 等定义已降级为 OMS 的种子数据源。
# 运行时类型查询应统一走 OMS (odap.biz.core.ontology.oms)，
# 不再直接使用本模块的 ENTITY_TYPES 进行类型判断。
# import_ontology() / export_ontology() 中的 global 修改已标记为不推荐使用。

# 领域实体类型定义
ENTITY_TYPES = {
    "Unit": {
        "display_name": "单位",
        "description": "组织单位或行动实体",
        "basic_properties": [
            {"name": "unit_id", "display_name": "单位ID", "property_type": "string", "required": True},
            {"name": "name", "display_name": "名称", "property_type": "string", "required": True},
            {"name": "side", "display_name": "阵营", "property_type": "string", "required": True,
             "enum_values": ["party_a", "party_b", "neutral"]},
            {"name": "unit_type", "display_name": "单位类型", "property_type": "string", "required": True,
             "enum_values": ["team", "department", "brigade", "battalion", "division", "special"]},
            {"name": "status", "display_name": "状态", "property_type": "string",
             "enum_values": ["active", "deployed", "resting", "destroyed", "unknown"]},
            {"name": "location", "display_name": "位置", "property_type": "string"},
            {"name": "coordinates", "display_name": "坐标", "property_type": "geopoint"},
        ],
        "statistical_properties": [
            {"name": "capability_index", "display_name": "能力指数", "property_type": "integer"},
            {"name": "readiness", "display_name": "就绪度", "property_type": "float"},
            {"name": "resource_level", "display_name": "资源水平", "property_type": "float"},
            {"name": "attrition_rate", "display_name": "损耗率", "property_type": "float"},
            {"name": "personnel", "display_name": "人员", "property_type": "integer"},
        ],
        "capabilities": [
            {"name": "operational_range", "display_name": "作业范围", "property_type": "float"},
            {"name": "penetration_capacity", "display_name": "穿透能力", "property_type": "float"},
            {"name": "defense_capability", "display_name": "防御能力", "property_type": "float"},
        ],
        "constraints": [
            {"name": "max_speed", "display_name": "最大速度", "property_type": "float"},
            {"name": "min_supply", "display_name": "最低补给", "property_type": "float"},
        ],
        "links": [
            {"name": "located_at", "display_name": "驻扎于", "target_type": "Location", "cardinality": "N:1"},
            {"name": "attached_to", "display_name": "隶属于", "target_type": "Unit", "cardinality": "N:1"},
            {"name": "interacting_with", "display_name": "交互中", "target_type": "Unit", "cardinality": "N:N"},
        ],
        "actions": ["move", "engage", "hold", "support", "withdraw"],
    },
    "Location": {
        "display_name": "位置",
        "description": "地理位置或区域",
        "basic_properties": [
            {"name": "location_id", "display_name": "位置ID", "property_type": "string", "required": True},
            {"name": "name", "display_name": "名称", "property_type": "string", "required": True},
            {"name": "location_type", "display_name": "位置类型", "property_type": "string",
             "enum_values": ["zone", "sector", "point", "area"]},
            {"name": "coordinates", "display_name": "坐标", "property_type": "geopoint"},
            {"name": "parent_location", "display_name": "上级位置", "property_type": "string"},
            {"name": "classification", "display_name": "分类", "property_type": "string"},
        ],
        "statistical_properties": [],
        "capabilities": [],
        "constraints": [],
        "links": [
            {"name": "adjacent_to", "display_name": "相邻", "target_type": "Location", "cardinality": "N:N"},
            {"name": "contains", "display_name": "包含", "target_type": "Unit", "cardinality": "1:N"},
        ],
        "actions": [],
    },
    "Equipment": {
        "display_name": "装备",
        "description": "设备或装备",
        "basic_properties": [
            {"name": "equipment_id", "display_name": "装备ID", "property_type": "string", "required": True},
            {"name": "name", "display_name": "名称", "property_type": "string", "required": True},
            {"name": "equipment_type", "display_name": "装备类型", "property_type": "string",
             "enum_values": ["vehicle", "tool", "sensor", "communication", "protection"]},
            {"name": "operational_status", "display_name": "运行状态", "property_type": "string",
             "enum_values": ["operational", "degraded", "non_operational"]},
        ],
        "statistical_properties": [],
        "capabilities": [
            {"name": "operational_range", "display_name": "作业范围", "property_type": "float"},
            {"name": "accuracy", "display_name": "精度", "property_type": "float"},
        ],
        "constraints": [],
        "links": [
            {"name": "assigned_to", "display_name": "分配给", "target_type": "Unit", "cardinality": "N:1"},
        ],
        "actions": [],
    },
    "Event": {
        "display_name": "事件",
        "description": "领域事件",
        "basic_properties": [
            {"name": "event_id", "display_name": "事件ID", "property_type": "string", "required": True},
            {"name": "event_type", "display_name": "事件类型", "property_type": "string",
             "enum_values": ["interaction", "confrontation", "movement", "communication", "observation"]},
            {"name": "timestamp", "display_name": "时间戳", "property_type": "datetime", "required": True},
            {"name": "location", "display_name": "位置", "property_type": "string"},
            {"name": "description", "display_name": "描述", "property_type": "string"},
            {"name": "phase", "display_name": "阶段", "property_type": "string"},
        ],
        "statistical_properties": [],
        "capabilities": [],
        "constraints": [],
        "links": [
            {"name": "participants", "display_name": "参与方", "target_type": "Unit", "cardinality": "N:N"},
            {"name": "occurs_at", "display_name": "发生于", "target_type": "Location", "cardinality": "N:1"},
        ],
        "actions": ["observe", "communicate"],
    },
    "PublicAsset": {
        "display_name": "公共资产",
        "description": "公共基础设施",
        "basic_properties": [
            {"name": "facility_id", "display_name": "设施ID", "property_type": "string", "required": True},
            {"name": "name", "display_name": "名称", "property_type": "string", "required": True},
            {"name": "facility_type", "display_name": "设施类型", "property_type": "string",
             "enum_values": ["hospital", "school", "factory", "power_plant", "refugee_camp"]},
            {"name": "status", "display_name": "状态", "property_type": "string",
             "enum_values": ["normal", "damaged", "evacuating", "overloaded"]},
        ],
        "statistical_properties": [],
        "capabilities": [],
        "constraints": [],
        "links": [
            {"name": "located_at", "display_name": "位于", "target_type": "Location", "cardinality": "N:1"},
        ],
        "actions": [],
    },
    "Mission": {
        "display_name": "任务",
        "description": "行动任务",
        "basic_properties": [
            {"name": "mission_id", "display_name": "任务ID", "property_type": "string", "required": True},
            {"name": "mission_type", "display_name": "任务类型", "property_type": "string",
             "enum_values": ["offensive", "survey", "hold", "logistics", "electronic_operation", "humanitarian"]},
            {"name": "status", "display_name": "状态", "property_type": "string",
             "enum_values": ["planned", "in_progress", "completed", "failed", "aborted"]},
            {"name": "priority", "display_name": "优先级", "property_type": "string",
             "enum_values": ["urgent", "high", "medium", "low"]},
            {"name": "deadline", "display_name": "截止时间", "property_type": "datetime"},
        ],
        "statistical_properties": [],
        "capabilities": [],
        "constraints": [],
        "links": [
            {"name": "assigned_to", "display_name": "分配给", "target_type": "Unit", "cardinality": "N:1"},
            {"name": "targets", "display_name": "目标", "target_type": "Unit", "cardinality": "N:N"},
            {"name": "located_at", "display_name": "位于", "target_type": "Location", "cardinality": "N:1"},
        ],
        "actions": [],
    },
    "Faction": {
        "display_name": "参与方",
        "description": "参与阵营或组织",
        "basic_properties": [
            {"name": "faction_id", "display_name": "阵营ID", "property_type": "string", "required": True},
            {"name": "name", "display_name": "名称", "property_type": "string", "required": True},
            {"name": "faction_type", "display_name": "阵营类型", "property_type": "string",
             "enum_values": ["nation", "coalition", "affiliate", "non_state_actor"]},
        ],
        "statistical_properties": [
            {"name": "personnel", "display_name": "人员", "property_type": "integer"},
        ],
        "capabilities": [],
        "constraints": [],
        "links": [
            {"name": "controls", "display_name": "控制", "target_type": "Location", "cardinality": "1:N"},
            {"name": "has_unit", "display_name": "拥有单位", "target_type": "Unit", "cardinality": "1:N"},
            {"name": "has_equipment", "display_name": "拥有装备", "target_type": "Equipment", "cardinality": "1:N"},
        ],
        "actions": [],
    },
}

ENTITY_TYPE_ALIASES = {
    "OrganizationUnit": "Unit",
    "ToolSystem": "Equipment",
    "IncidentEvent": "Event",
    "CivilianInfrastructure": "PublicAsset",
}

ACTION_TYPES = [
    {
        "action_type_id": "move",
        "name": "move",
        "display_name": "移动",
        "description": "将单位移动到指定位置",
        "target_object_type": "Unit",
        "parameters": [
            {"name": "destination", "display_name": "目标位置", "param_type": "string", "required": True},
            {"name": "speed", "display_name": "速度", "param_type": "float", "required": False},
        ],
        "required_roles": ["director", "operator"],
        "confirmation_required": False,
    },
    {
        "action_type_id": "engage",
        "name": "engage",
        "display_name": "交战",
        "description": "对目标发起交战",
        "target_object_type": "Unit",
        "parameters": [
            {"name": "target_id", "display_name": "目标ID", "param_type": "string", "required": True},
            {"name": "tool_type", "display_name": "工具类型", "param_type": "string", "required": False},
        ],
        "opa_policy": "policies/engage/authorize",
        "required_roles": ["director"],
        "confirmation_required": True,
    },
    {
        "action_type_id": "hold",
        "name": "hold",
        "display_name": "坚守",
        "description": "在当前位置建立坚守",
        "target_object_type": "Unit",
        "parameters": [
            {"name": "hold_type", "display_name": "坚守类型", "param_type": "string", "required": False,
             "enum_values": ["perimeter", "point", "mobile"]},
        ],
        "required_roles": ["director", "operator"],
        "confirmation_required": False,
    },
    {
        "action_type_id": "support",
        "name": "support",
        "display_name": "支援",
        "description": "向目标位置提供支援",
        "target_object_type": "Unit",
        "parameters": [
            {"name": "support_type", "display_name": "支援类型", "param_type": "string", "required": False},
            {"name": "units", "display_name": "支援单位", "param_type": "json", "required": False},
        ],
        "required_roles": ["director"],
        "confirmation_required": True,
    },
    {
        "action_type_id": "withdraw",
        "name": "withdraw",
        "display_name": "撤出",
        "description": "从当前位置撤出",
        "target_object_type": "Unit",
        "parameters": [
            {"name": "destination", "display_name": "撤出目标", "param_type": "string", "required": True},
            {"name": "orderly", "display_name": "有序撤出", "param_type": "boolean", "required": False},
        ],
        "required_roles": ["director"],
        "confirmation_required": True,
    },
    {
        "action_type_id": "observe",
        "name": "observe",
        "display_name": "观察",
        "description": "对目标区域进行观察",
        "target_object_type": "Event",
        "parameters": [
            {"name": "area", "display_name": "观察区域", "param_type": "string", "required": True},
            {"name": "duration", "display_name": "持续时间", "param_type": "float", "required": False},
        ],
        "required_roles": ["analyst", "operator"],
        "confirmation_required": False,
    },
    {
        "action_type_id": "communicate",
        "name": "communicate",
        "display_name": "通信",
        "description": "发送或接收通信",
        "target_object_type": "Event",
        "parameters": [
            {"name": "recipient", "display_name": "接收方", "param_type": "string", "required": True},
            {"name": "message", "display_name": "消息内容", "param_type": "string", "required": True},
            {"name": "priority", "display_name": "优先级", "param_type": "string", "required": False,
             "enum_values": ["routine", "priority", "immediate", "flash"]},
        ],
        "required_roles": ["operator"],
        "confirmation_required": False,
    },
]

# 角色定义
ROLES = {
    "field_operator": {
        "permissions": ["view_information", "request_support"],
        "restrictions": ["cannot_engage", "cannot_direct"]
    },
    "director": {
        "permissions": ["view_information", "coordinate_units", "authorize_operation", "approve_missions"],
        "restrictions": ["cannot_target_civilian"]
    },
    "analyst": {
        "permissions": ["view_information", "analyze_data", "generate_reports"],
        "restrictions": ["cannot_direct", "cannot_engage"]
    }
}

# 领域环境配置 - 通用场景模板
DOMAIN_CONFIG: Dict[str, Any] = {
    "description": "场景配置模板 - 由用户通过界面或配置文件定义",
    "factions": [],
    "regions": [],
    "random_events": [],
}

# 本体模型版本信息
ONTOLOGY_VERSION = "1.0.0"
ONTOLOGY_LAST_UPDATED = "2026-04-09"

# 导出本体模型为JSON格式
def export_ontology():
    """
    导出本体模型为JSON格式
    """
    import warnings
    warnings.warn(
        "export_ontology() 直接操作模块级变量，已不推荐使用。"
        "运行时类型管理应使用 OMS (odap.biz.core.ontology.oms)。",
        DeprecationWarning,
        stacklevel=2,
    )
    import json
    ontology_data = {
        "entity_types": ENTITY_TYPES,
        "roles": ROLES,
        "domain_config": DOMAIN_CONFIG,
        "version": ONTOLOGY_VERSION,
        "last_updated": ONTOLOGY_LAST_UPDATED
    }
    return json.dumps(ontology_data, indent=2, ensure_ascii=False)

# 导入本体模型

def import_ontology(json_data):
    """
    从JSON格式导入本体模型
    """
    import warnings
    warnings.warn(
        "import_ontology() 使用 global 修改模块级变量，已不推荐使用。"
        "运行时类型管理应使用 OMS (odap.biz.core.ontology.oms)。",
        DeprecationWarning,
        stacklevel=2,
    )
    import json
    data = json.loads(json_data)
    global ENTITY_TYPES, ROLES, DOMAIN_CONFIG, ONTOLOGY_VERSION, ONTOLOGY_LAST_UPDATED
    ENTITY_TYPES = data.get("entity_types", ENTITY_TYPES)
    ROLES = data.get("roles", ROLES)
    DOMAIN_CONFIG = data.get("domain_config", DOMAIN_CONFIG)
    ONTOLOGY_VERSION = data.get("version", ONTOLOGY_VERSION)
    ONTOLOGY_LAST_UPDATED = data.get("last_updated", ONTOLOGY_LAST_UPDATED)
    return True


# NOTE: `generate_oms_seed_data` was moved to
# `odap.biz.core.ontology.application.oms.seed_data` to break the cross-boundary
# dependency. The design layer MUST NOT own OMS-specific seed data.
# See: odap/biz/core/ontology/application/oms/seed_data.py