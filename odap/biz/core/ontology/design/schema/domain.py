"""
领域本体模型
基于本体论方法定义领域实体的类型和关系
"""

# Domain 模型定位说明 (ADR-056):
# 本模块的 ENTITY_TYPES / DOMAIN_CONFIG 等定义已降级为 OMS 的种子数据源。
# 运行时类型查询应统一走 OMS (odap.biz.core.ontology.oms)，
# 不再直接使用本模块的 ENTITY_TYPES 进行类型判断。
# import_ontology() / export_ontology() 中的 global 修改已标记为不推荐使用。

# 领域实体类型定义
ENTITY_TYPES = {
    "Unit": {
        "display_name": "单位",
        "description": "军事或组织单位",
        "basic_properties": [
            {"name": "unit_id", "display_name": "单位ID", "property_type": "string", "required": True},
            {"name": "name", "display_name": "名称", "property_type": "string", "required": True},
            {"name": "side", "display_name": "阵营", "property_type": "string", "required": True,
             "enum_values": ["red", "blue", "neutral"]},
            {"name": "unit_type", "display_name": "单位类型", "property_type": "string", "required": True,
             "enum_values": ["infantry", "armor", "artillery", "air", "naval", "special"]},
            {"name": "status", "display_name": "状态", "property_type": "string",
             "enum_values": ["active", "deployed", "resting", "destroyed", "unknown"]},
            {"name": "location", "display_name": "位置", "property_type": "string"},
            {"name": "coordinates", "display_name": "坐标", "property_type": "geopoint"},
        ],
        "statistical_properties": [
            {"name": "combat_power", "display_name": "战斗力", "property_type": "integer"},
            {"name": "morale", "display_name": "士气", "property_type": "float"},
            {"name": "supply_level", "display_name": "补给水平", "property_type": "float"},
            {"name": "casualty_rate", "display_name": "伤亡率", "property_type": "float"},
            {"name": "strength", "display_name": "兵力", "property_type": "integer"},
        ],
        "capabilities": [
            {"name": "range", "display_name": "射程", "property_type": "float"},
            {"name": "armor_penetration", "display_name": "穿甲能力", "property_type": "float"},
            {"name": "air_defense", "display_name": "防空能力", "property_type": "float"},
        ],
        "constraints": [
            {"name": "max_speed", "display_name": "最大速度", "property_type": "float"},
            {"name": "min_supply", "display_name": "最低补给", "property_type": "float"},
        ],
        "links": [
            {"name": "located_at", "display_name": "驻扎于", "target_type": "Location", "cardinality": "N:1"},
            {"name": "attached_to", "display_name": "隶属于", "target_type": "Unit", "cardinality": "N:1"},
            {"name": "engaged_with", "display_name": "交战中", "target_type": "Unit", "cardinality": "N:N"},
        ],
        "actions": ["move", "attack", "defend", "reinforce", "retreat"],
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
        "description": "武器系统或装备",
        "basic_properties": [
            {"name": "equipment_id", "display_name": "装备ID", "property_type": "string", "required": True},
            {"name": "name", "display_name": "名称", "property_type": "string", "required": True},
            {"name": "equipment_type", "display_name": "装备类型", "property_type": "string",
             "enum_values": ["vehicle", "weapon", "sensor", "communication", "protection"]},
            {"name": "operational_status", "display_name": "运行状态", "property_type": "string",
             "enum_values": ["operational", "degraded", "non_operational"]},
        ],
        "statistical_properties": [],
        "capabilities": [
            {"name": "range", "display_name": "射程", "property_type": "float"},
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
             "enum_values": ["contact", "attack", "movement", "communication", "observation"]},
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
    "CivilianInfrastructure": {
        "display_name": "民用设施",
        "description": "民用基础设施",
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
        "description": "军事或行动任务",
        "basic_properties": [
            {"name": "mission_id", "display_name": "任务ID", "property_type": "string", "required": True},
            {"name": "mission_type", "display_name": "任务类型", "property_type": "string",
             "enum_values": ["attack", "reconnaissance", "defense", "logistics", "electronic_warfare", "humanitarian"]},
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
        "display_name": "交战方",
        "description": "参战阵营或组织",
        "basic_properties": [
            {"name": "faction_id", "display_name": "阵营ID", "property_type": "string", "required": True},
            {"name": "name", "display_name": "名称", "property_type": "string", "required": True},
            {"name": "faction_type", "display_name": "阵营类型", "property_type": "string",
             "enum_values": ["nation", "coalition", "proxy_force", "terrorist_organization"]},
        ],
        "statistical_properties": [
            {"name": "strength", "display_name": "兵力", "property_type": "integer"},
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
    "MilitaryUnit": "Unit",
    "WeaponSystem": "Equipment",
    "BattleEvent": "Event",
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
        "required_roles": ["commander", "operator"],
        "confirmation_required": False,
    },
    {
        "action_type_id": "attack",
        "name": "attack",
        "display_name": "攻击",
        "description": "对目标发起攻击",
        "target_object_type": "Unit",
        "parameters": [
            {"name": "target_id", "display_name": "目标ID", "param_type": "string", "required": True},
            {"name": "weapon_type", "display_name": "武器类型", "param_type": "string", "required": False},
        ],
        "opa_policy": "policies/attack/authorize",
        "required_roles": ["commander"],
        "confirmation_required": True,
    },
    {
        "action_type_id": "defend",
        "name": "defend",
        "display_name": "防御",
        "description": "在当前位置建立防御",
        "target_object_type": "Unit",
        "parameters": [
            {"name": "defense_type", "display_name": "防御类型", "param_type": "string", "required": False,
             "enum_values": ["perimeter", "point", "mobile"]},
        ],
        "required_roles": ["commander", "operator"],
        "confirmation_required": False,
    },
    {
        "action_type_id": "reinforce",
        "name": "reinforce",
        "display_name": "增援",
        "description": "向目标位置增派兵力",
        "target_object_type": "Unit",
        "parameters": [
            {"name": "reinforcement_type", "display_name": "增援类型", "param_type": "string", "required": False},
            {"name": "units", "display_name": "增援单位", "param_type": "json", "required": False},
        ],
        "required_roles": ["commander"],
        "confirmation_required": True,
    },
    {
        "action_type_id": "retreat",
        "name": "retreat",
        "display_name": "撤退",
        "description": "从当前位置撤退",
        "target_object_type": "Unit",
        "parameters": [
            {"name": "destination", "display_name": "撤退目标", "param_type": "string", "required": True},
            {"name": "orderly", "display_name": "有序撤退", "param_type": "boolean", "required": False},
        ],
        "required_roles": ["commander"],
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
        "required_roles": ["intelligence_officer", "operator"],
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
    "pilot": {
        "permissions": ["view_intelligence", "request_support"],
        "restrictions": ["cannot_attack", "cannot_command"]
    },
    "commander": {
        "permissions": ["view_intelligence", "command_units", "authorize_attacks", "approve_missions"],
        "restrictions": ["cannot_attack_civilian_infrastructure"]
    },
    "intelligence_analyst": {
        "permissions": ["view_intelligence", "analyze_data", "generate_reports"],
        "restrictions": ["cannot_command", "cannot_attack"]
    }
}

# 领域环境配置 - 2026 美伊战争场景
DOMAIN_CONFIG = {
    "factions": [
        {
            "name": "US-led Coalition",
            "type": "coalition",
            "description": "美国主导的联军，包括美国和以色列",
            "strength": 150000,
            "allies": ["Israel"],
            "enemies": ["Iran", "Hezbollah", "IRGC-Iraq", "Houthis"]
        },
        {
            "name": "Israel",
            "type": "nation",
            "description": "以色列国防军，地面行动主力",
            "strength": 170000,
            "allies": ["US-led Coalition"],
            "enemies": ["Iran", "Hezbollah", "IRGC-Iraq", "Houthis"]
        },
        {
            "name": "Iran",
            "type": "nation",
            "description": "伊朗伊斯兰革命卫队，主要对手",
            "strength": 200000,
            "allies": ["Hezbollah", "IRGC-Iraq", "Houthis"],
            "enemies": ["US-led Coalition", "Israel"]
        },
        {
            "name": "Hezbollah",
            "type": "proxy_force",
            "description": "黎巴嫩真主党，伊朗代理人",
            "strength": 45000,
            "allies": ["Iran", "IRGC-Iraq"],
            "enemies": ["US-led Coalition", "Israel"]
        },
        {
            "name": "IRGC-Iraq",
            "type": "proxy_force",
            "description": "伊朗革命卫队伊拉克分支",
            "strength": 20000,
            "allies": ["Iran", "Hezbollah"],
            "enemies": ["US-led Coalition", "Israel"]
        },
        {
            "name": "Houthis",
            "type": "proxy_force",
            "description": "也门胡塞武装，伊朗代理人",
            "strength": 80000,
            "allies": ["Iran"],
            "enemies": ["US-led Coalition", "Israel"]
        }
    ],
    "areas": [
        {"id": "A", "name": "波斯湾", "description": "美军海军部署区，伊朗海军活动区"},
        {"id": "B", "name": "伊朗西部", "description": "以色列空袭目标区，伊朗核设施集中区"},
        {"id": "C", "name": "伊拉克", "description": "美伊边境，IRGC活动区"},
        {"id": "D", "name": "黎巴嫩/以色列北部", "description": "真主党火箭弹发射区"},
        {"id": "E", "name": "红海/也门", "description": "胡塞武装袭击区"}
    ],
    "random_events": [
        "iranian_missile_launch",
        "uav_swarm_attack",
        "iron_dome_interception",
        "electronic_warfare",
        "cyber_attack",
        "intelligence_update",
        "civilian_casualties",
        "humanitarian_crisis",
        "prisoner_exchange",
        "ceasefire_proposal"
    ]
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