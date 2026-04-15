"""
领域本体模型
基于本体论方法定义领域实体的类型和关系
"""

# 领域实体类型定义
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
    
    # 领域事件
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
    import json
    data = json.loads(json_data)
    global ENTITY_TYPES, ROLES, DOMAIN_CONFIG, ONTOLOGY_VERSION, ONTOLOGY_LAST_UPDATED
    ENTITY_TYPES = data.get("entity_types", ENTITY_TYPES)
    ROLES = data.get("roles", ROLES)
    DOMAIN_CONFIG = data.get("domain_config", DOMAIN_CONFIG)
    ONTOLOGY_VERSION = data.get("version", ONTOLOGY_VERSION)
    ONTOLOGY_LAST_UPDATED = data.get("last_updated", ONTOLOGY_LAST_UPDATED)
    return True