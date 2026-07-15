"""
领域实体模拟数据生成模块 - 领域场景
"""

import random
import json
import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ..schema.domain import DOMAIN_CONFIG, ENTITY_TYPE_ALIASES


import logging

logger = logging.getLogger(__name__)
def generate_coordinates():
    return (random.uniform(0, 100), random.uniform(0, 100))

def generate_timestamp():
    start = datetime.now() - timedelta(days=7)
    end = datetime.now()
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)

def generate_simulation_data():
    data = {
        "locations": [],
        "units": [],
        "equipment": [],
        "public_assets": [],
        "events": [],
        "missions": []
    }

    areas = DOMAIN_CONFIG["areas"]
    factions = DOMAIN_CONFIG["factions"]

    for area in areas:
        for i in range(1, 4):
            location = {
                "id": f"LOC_{area['id']}_{i}",
                "type": "Location",
                "properties": {
                    "name": f"{area['name']}地点{i}",
                    "coordinates": generate_coordinates(),
                    "area": area['id'],
                    "terrain": random.choice(["平原", "山地", "森林", "城市", "沙漠"])
                },
                "relationships": {
                    "contains": [],
                    "adjacent_to": []
                }
            }
            data["locations"].append(location)

    unit_type_map = {
        "US-led Coalition": ["第1分队", "第2支队", "第3编队", "综合支援队"],
        "Israel": ["第1旅", "第2师", "第3中队", "特别行动组"],
        "Iran": ["第1支队", "第2师", "远程支队", "无人编队"],
        "Hezbollah": ["第1投射组", "第2潜行组", "第3突击组", "防护小组"],
        "IRGC-Iraq": ["第1地方队", "第2装甲组", "第3火力组", "情报小组"],
        "Houthis": ["第1步队", "第2投射组", "无人小组", "海岸巡查队"]
    }

    equipment_map = {
        "US-led Coalition": ["重型载具A", "空中平台A", "旋翼平台A", "精确投射系统A"],
        "Israel": ["重型载具B", "空中平台B", "防护系统A", "中程投射系统B"],
        "Iran": ["重型载具C", "无人载具A", "远程投射系统", "水下平台A"],
        "Hezbollah": ["反载具投射器", "短程投射器", "轻型装备A", "便携投射器"],
        "IRGC-Iraq": ["机动载具A", "简易装置A", "迫击投射器", "轻型装备B"],
        "Houthis": ["巡航投射系统", "无人载具B", "水域装置A", "反平台投射器"]
    }

    for faction in factions:
        unit_types = unit_type_map.get(faction['name'], ["第1分队", "第2支队", "第3编队", "综合支援队"])
        equipment = equipment_map.get(faction['name'], ["传感器", "投射器", "设备", "无人载具"])

        for i in range(1, 3):
            location = random.choice(data["locations"]) if data["locations"] else None
            location_id = location["id"] if location else None
            area = location_id.split("_")[1] if location_id and len(location_id.split("_")) > 1 else None

            unit = {
                "id": f"UNIT_{faction['name'].replace(' ', '_')}_{i}",
                "type": ENTITY_TYPE_ALIASES.get("OrganizationUnit", "OrganizationUnit"),
                "properties": {
                    "name": f"{faction['name']} {unit_types[i-1]}",
                    "unit_type": unit_types[i-1],
                    "strength": random.randint(500, 5000),
                    "equipment": random.sample(equipment, random.randint(2, 4)),
                    "status": random.choice(["待命", "行动中", "受损", "部署中"]),
                    "affiliation": faction['name'],
                    "area": area
                },
                "relationships": {
                    "located_at": location_id,
                    "attached_to": None,
                    "engaged_with": []
                }
            }
            data["units"].append(unit)

    equipment_type_map = {
        "US-led Coalition": ["综合监测系统", "精确投射系统", "区域防护系统", "无人载具A"],
        "Israel": ["拦截投射器", "中程投射系统", "监测系统A", "无人载具B"],
        "Iran": ["无人载具A", "远程投射系统", "防护投射系统", "无人载具C"],
        "Hezbollah": ["短程投射器", "反载具投射器", "简易迫击投射器", "便携防护投射器"],
        "IRGC-Iraq": ["投射器A", "简易装置A", "迫击投射器", "机动投射系统"],
        "Houthis": ["巡航投射系统", "远程投射系统", "水面载具A", "水域装置A"]
    }

    for faction in factions:
        equipment_types = equipment_type_map.get(faction['name'], ["传感器", "投射器", "设备", "无人载具"])

        for i in range(1, 3):
            location = random.choice(data["locations"]) if data["locations"] else None
            location_id = location["id"] if location else None
            area = location_id.split("_")[1] if location_id and len(location_id.split("_")) > 1 else None

            weapon = {
                "id": f"EQUIP_{faction['name'].replace(' ', '_')}_{i}",
                "type": ENTITY_TYPE_ALIASES.get("ToolSystem", "ToolSystem"),
                "properties": {
                    "name": f"{faction['name']} {equipment_types[i-1]}",
                    "equipment_type": equipment_types[i-1],
                    "range": random.uniform(10, 500),
                    "status": random.choice(["正常", "待发", "受损", "维修中"]),
                    "affiliation": faction['name'],
                    "area": area
                },
                "relationships": {
                    "located_at": location_id,
                    "operated_by": random.choice(data["units"])["id"] if data["units"] else None
                }
            }
            data["equipment"].append(weapon)

    civ_types = ["医院", "学校", "油罐区", "发电厂", "难民营"]
    for area in areas:
        for i in range(1, 3):
            civ = {
                "id": f"CIV_{area['id']}_{i}",
                "type": "PublicAsset",
                "properties": {
                    "name": f"{area['name']}{civ_types[i-1]}",
                    "facility_type": civ_types[i-1],
                    "status": random.choice(["正常", "受损", "疏散中", "满负荷"])
                },
                "relationships": {
                    "located_at": random.choice(data["locations"])["id"] if data["locations"] else None
                }
            }
            data["public_assets"].append(civ)

    event_type_map = [
        "long_range_launch",
        "uav_swarm_operation",
        "defense_interception",
        "electronic_operation",
        "air_operation",
        "ground_engagement",
        "intelligence_update",
        "public_evacuation"
    ]

    for i in range(1, 11):
        involved_units = random.sample([u["id"] for u in data["units"]], min(2, len(data["units"])))
        event = {
            "id": f"EVENT_{i}",
            "type": ENTITY_TYPE_ALIASES.get("IncidentEvent", "IncidentEvent"),
            "properties": {
                "event_type": random.choice(event_type_map),
                "timestamp": generate_timestamp().isoformat(),
                "description": f"领域事件: {event_type_map[i % len(event_type_map)]}",
                "outcome": random.choice(["成功拦截", "目标命中", "任务中止", "双方僵持"])
            },
            "relationships": {
                "involves": involved_units,
                "occurs_at": random.choice(data["locations"])["id"] if data["locations"] else None
            }
        }
        data["events"].append(event)

    mission_types = ["精确行动", "守卫任务", "监测巡查", "后勤补给", "电子操作", "人道救援"]
    for i in range(1, 6):
        target_unit = random.choice(data["units"])["id"] if data["units"] else None
        mission = {
            "id": f"MISSION_{i}",
            "type": "Mission",
            "properties": {
                "mission_type": random.choice(mission_types),
                "status": random.choice(["计划中", "进行中", "完成", "失败", "中止"]),
                "priority": random.choice(["紧急", "高", "中", "低"]),
                "deadline": (datetime.now() + timedelta(days=random.randint(1, 7))).isoformat()
            },
            "relationships": {
                "assigned_to": random.choice(data["units"])["id"] if data["units"] else None,
                "targets": [target_unit] if target_unit else [],
                "located_at": random.choice(data["locations"])["id"] if data["locations"] else None
            }
        }
        data["missions"].append(mission)

    return data

def generate_random_event():
    event_types = DOMAIN_CONFIG["random_events"]
    event_type = random.choice(event_types)

    descriptions = {
        "long_range_launch": "远程投射系统发射",
        "uav_swarm_operation": "无人载具群行动",
        "defense_interception": "防护系统成功拦截",
        "electronic_operation": "电子操作干扰",
        "cyber_attack": "网络行动",
        "intelligence_update": "情报更新",
        "public_casualties": "公共损失报告",
        "humanitarian_crisis": "人道主义危机",
        "prisoner_exchange": "人员交换",
        "ceasefire_proposal": "停止行动提议"
    }

    event = {
        "id": f"RANDOM_EVENT_{int(datetime.now().timestamp())}",
        "type": event_type,
        "timestamp": datetime.now().isoformat(),
        "description": descriptions.get(event_type, f"随机事件: {event_type}"),
        "impact": random.choice(["轻微", "中等", "严重", "关键"])
    }

    return event

def save_simulation_data():
    data = generate_simulation_data()
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "simulation_data.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return data

def load_simulation_data():
    try:
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "simulation_data.json")
        with open(output_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return save_simulation_data()

if __name__ == "__main__":
    data = save_simulation_data()
    logger.info('=' * 50)
    logger.info('场景模拟数据生成完成')
    logger.info('=' * 50)
    logger.info(f"参战方: {len(DOMAIN_CONFIG['factions'])}")
    logger.info(f"地理区域: {len(DOMAIN_CONFIG['areas'])}")
    logger.info(f"- 地理位置: {len(data['locations'])}")
    logger.info(f"- 组织单位: {len(data['units'])}")
    logger.info(f"- 工具系统: {len(data['equipment'])}")
    logger.info(f"- 公共资产: {len(data['public_assets'])}")
    logger.info(f"- 领域事件: {len(data['events'])}")
    logger.info(f"- 任务: {len(data['missions'])}")

    logger.info('\n参战方详情:')
    for f in DOMAIN_CONFIG["factions"]:
        logger.info(f"  - {f['name']}: {f['description']}")

    random_event = generate_random_event()
    logger.info(f"\n随机事件: {random_event['description']}")
