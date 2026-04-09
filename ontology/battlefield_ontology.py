"""
战场本体模型
基于本体论方法定义战场实体的类型和关系
"""

# 战场实体类型定义
ENTITY_TYPES = {
    # 地理位置
    "Location": {
        "properties": {
            "name": "string",
            "coordinates": "tuple",
            "area": "string",
            "terrain": "string"
        },
        "relationships": {
            "contains": "Entity",
            "adjacent_to": "Location"
        }
    },
    
    # 军事单位
    "MilitaryUnit": {
        "properties": {
            "name": "string",
            "type": "string",  # 步兵、装甲、炮兵等
            "strength": "integer",
            "equipment": "list",
            "status": "string",  # 待命、行动中、受损等
            "affiliation": "string"  # 所属方
        },
        "relationships": {
            "located_at": "Location",
            "attached_to": "MilitaryUnit",
            "engaged_with": "MilitaryUnit"
        }
    },
    
    # 武器系统
    "WeaponSystem": {
        "properties": {
            "name": "string",
            "type": "string",  # 雷达、导弹、火炮等
            "range": "float",
            "status": "string",
            "affiliation": "string"
        },
        "relationships": {
            "located_at": "Location",
            "operated_by": "MilitaryUnit"
        }
    },
    
    # 民用设施
    "CivilianInfrastructure": {
        "properties": {
            "name": "string",
            "type": "string",  # 医院、学校、工厂等
            "status": "string"
        },
        "relationships": {
            "located_at": "Location"
        }
    },
    
    # 战场事件
    "BattleEvent": {
        "properties": {
            "id": "string",
            "type": "string",  # 攻击、防御、侦察等
            "timestamp": "datetime",
            "description": "string",
            "outcome": "string"
        },
        "relationships": {
            "involves": "Entity",
            "occurs_at": "Location"
        }
    },
    
    # 任务
    "Mission": {
        "properties": {
            "id": "string",
            "type": "string",  # 攻击、侦察、防御等
            "status": "string",  # 计划中、进行中、完成、失败
            "priority": "string",
            "deadline": "datetime"
        },
        "relationships": {
            "assigned_to": "MilitaryUnit",
            "targets": "Entity",
            "located_at": "Location"
        }
    },
    
    # 交战方
    "Faction": {
        "properties": {
            "name": "string",
            "type": "string",  # 国家、叛军、恐怖组织等
            "strength": "integer",
            "allies": "list",
            "enemies": "list"
        },
        "relationships": {
            "controls": "Location",
            "has_unit": "MilitaryUnit",
            "has_weapon": "WeaponSystem"
        }
    }
}

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

# 战场环境配置
BATTLEFIELD_CONFIG = {
    "factions": [
        {
            "name": "Blue Force",
            "type": "coalition",
            "strength": 10000,
            "allies": [],
            "enemies": ["Red Force", "Green Insurgents"]
        },
        {
            "name": "Red Force",
            "type": "opposing force",
            "strength": 8000,
            "allies": ["Green Insurgents"],
            "enemies": ["Blue Force"]
        },
        {
            "name": "Green Insurgents",
            "type": "insurgent group",
            "strength": 3000,
            "allies": ["Red Force"],
            "enemies": ["Blue Force"]
        },
        {
            "name": "Yellow Neutral",
            "type": "neutral",
            "strength": 5000,
            "allies": [],
            "enemies": []
        }
    ],
    "areas": ["A", "B", "C", "D", "E"],
    "random_events": [
        "enemy_reinforcement",
        "equipment_failure",
        "weather_change",
        "civilian_protest",
        "intelligence_update"
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
    import json
    ontology_data = {
        "entity_types": ENTITY_TYPES,
        "roles": ROLES,
        "battlefield_config": BATTLEFIELD_CONFIG,
        "version": ONTOLOGY_VERSION,
        "last_updated": ONTOLOGY_LAST_UPDATED
    }
    return json.dumps(ontology_data, indent=2, ensure_ascii=False)

# 导入本体模型

def import_ontology(json_data):
    """
    从JSON格式导入本体模型
    """
    import json
    data = json.loads(json_data)
    global ENTITY_TYPES, ROLES, BATTLEFIELD_CONFIG, ONTOLOGY_VERSION, ONTOLOGY_LAST_UPDATED
    ENTITY_TYPES = data.get("entity_types", ENTITY_TYPES)
    ROLES = data.get("roles", ROLES)
    BATTLEFIELD_CONFIG = data.get("battlefield_config", BATTLEFIELD_CONFIG)
    ONTOLOGY_VERSION = data.get("version", ONTOLOGY_VERSION)
    ONTOLOGY_LAST_UPDATED = data.get("last_updated", ONTOLOGY_LAST_UPDATED)
    return True