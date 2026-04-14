"""
战场实体模拟数据生成模块 - 2026 美伊战争场景
"""

import random
import json
import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ontology.battlefield_ontology import BATTLEFIELD_CONFIG

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
        "military_units": [],
        "weapon_systems": [],
        "civilian_infrastructures": [],
        "battle_events": [],
        "missions": []
    }

    areas = BATTLEFIELD_CONFIG["areas"]
    factions = BATTLEFIELD_CONFIG["factions"]

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
        "US-led Coalition": ["步兵师", "装甲旅", "航空团", "海军陆战队"],
        "Israel": ["步兵旅", "装甲师", "空军中队", "特种部队"],
        "Iran": ["革命卫队步兵", "装甲师", "导弹旅", "无人机中队"],
        "Hezbollah": ["火箭弹部队", "隧道武装", "特种突击队", "防空小组"],
        "IRGC-Iraq": ["什叶派民兵", "装甲部队", "炮兵", "情报小组"],
        "Houthis": ["步兵", "导弹部队", "无人机小组", "海岸巡逻队"]
    }

    equipment_map = {
        "US-led Coalition": ["M1艾布拉姆斯坦克", "F-35战机", "阿帕奇直升机", "标枪导弹"],
        "Israel": ["梅卡瓦坦克", "F-16战机", "铁穹系统", "大卫投石索"],
        "Iran": ["苏式坦克", "Shahed-136无人机", "弹道导弹", "海豚潜艇"],
        "Hezbollah": ["反坦克导弹", "火箭弹", "AK-47", "RPG"],
        "IRGC-Iraq": ["摩托车突击队", "简易爆炸装置", "迫击炮", "轻武器"],
        "Houthis": ["巡航导弹", "无人机", "水雷", "反舰导弹"]
    }

    for faction in factions:
        unit_types = unit_type_map.get(faction['name'], ["步兵", "装甲", "航空", "特种部队"])
        equipment = equipment_map.get(faction['name'], ["步枪", "坦克", "火炮", "导弹"])

        for i in range(1, 3):
            location = random.choice(data["locations"]) if data["locations"] else None
            location_id = location["id"] if location else None
            area = location_id.split("_")[1] if location_id and len(location_id.split("_")) > 1 else None

            unit = {
                "id": f"UNIT_{faction['name'].replace(' ', '_')}_{i}",
                "type": "MilitaryUnit",
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
            data["military_units"].append(unit)

    weapon_type_map = {
        "US-led Coalition": ["宙斯盾雷达", "战斧巡航导弹", "萨德系统", "MQ-9死神无人机"],
        "Israel": ["铁穹拦截弹", "杰里科导弹", "翠鸟雷达", "Heron无人机"],
        "Iran": ["Shahed-136无人机", "弹道导弹", "S-300防空导弹", "海耳无人机"],
        "Hezbollah": ["短程火箭弹", "反坦克导弹", "简易迫击炮", "肩扛式防空导弹"],
        "IRGC-Iraq": ["火箭弹", "简易爆炸装置", "迫击炮", "摩托车运载火箭"],
        "Houthis": ["巡航导弹", "弹道导弹", "武装渔船", "水雷"]
    }

    for faction in factions:
        weapon_types = weapon_type_map.get(faction['name'], ["雷达", "导弹", "火炮", "无人机"])

        for i in range(1, 3):
            location = random.choice(data["locations"]) if data["locations"] else None
            location_id = location["id"] if location else None
            area = location_id.split("_")[1] if location_id and len(location_id.split("_")) > 1 else None

            weapon = {
                "id": f"WEAPON_{faction['name'].replace(' ', '_')}_{i}",
                "type": "WeaponSystem",
                "properties": {
                    "name": f"{faction['name']} {weapon_types[i-1]}",
                    "weapon_type": weapon_types[i-1],
                    "range": random.uniform(10, 500),
                    "status": random.choice(["正常", "待发", "受损", "维修中"]),
                    "affiliation": faction['name'],
                    "area": area
                },
                "relationships": {
                    "located_at": location_id,
                    "operated_by": random.choice(data["military_units"])["id"] if data["military_units"] else None
                }
            }
            data["weapon_systems"].append(weapon)

    civ_types = ["医院", "学校", "油罐区", "发电厂", "难民营"]
    for area in areas:
        for i in range(1, 3):
            civ = {
                "id": f"CIV_{area['id']}_{i}",
                "type": "CivilianInfrastructure",
                "properties": {
                    "name": f"{area['name']}{civ_types[i-1]}",
                    "facility_type": civ_types[i-1],
                    "status": random.choice(["正常", "受损", "疏散中", "满负荷"])
                },
                "relationships": {
                    "located_at": random.choice(data["locations"])["id"] if data["locations"] else None
                }
            }
            data["civilian_infrastructures"].append(civ)

    event_type_map = [
        "iranian_missile_launch",
        "uav_swarm_attack",
        "iron_dome_interception",
        "electronic_warfare",
        "air_strike",
        "ground_engagement",
        "intelligence_update",
        "civilian_evacuation"
    ]

    for i in range(1, 11):
        involved_units = random.sample([u["id"] for u in data["military_units"]], min(2, len(data["military_units"])))
        event = {
            "id": f"EVENT_{i}",
            "type": "BattleEvent",
            "properties": {
                "event_type": random.choice(event_type_map),
                "timestamp": generate_timestamp().isoformat(),
                "description": f"战场事件: {event_type_map[i % len(event_type_map)]}",
                "outcome": random.choice(["成功拦截", "目标命中", "任务中止", "双方僵持"])
            },
            "relationships": {
                "involves": involved_units,
                "occurs_at": random.choice(data["locations"])["id"] if data["locations"] else None
            }
        }
        data["battle_events"].append(event)

    mission_types = ["精确打击", "防空任务", "侦察监视", "后勤补给", "电子干扰", "人道救援"]
    for i in range(1, 6):
        target_unit = random.choice(data["military_units"])["id"] if data["military_units"] else None
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
                "assigned_to": random.choice(data["military_units"])["id"] if data["military_units"] else None,
                "targets": [target_unit] if target_unit else [],
                "located_at": random.choice(data["locations"])["id"] if data["locations"] else None
            }
        }
        data["missions"].append(mission)

    return data

def generate_random_event():
    event_types = BATTLEFIELD_CONFIG["random_events"]
    event_type = random.choice(event_types)

    descriptions = {
        "iranian_missile_launch": "伊朗发射弹道导弹",
        "uav_swarm_attack": "无人机群袭击",
        "iron_dome_interception": "铁穹系统成功拦截",
        "electronic_warfare": "电子战干扰",
        "cyber_attack": "网络攻击行动",
        "intelligence_update": "情报更新",
        "civilian_casualties": "平民伤亡报告",
        "humanitarian_crisis": "人道主义危机",
        "prisoner_exchange": "战俘交换",
        "ceasefire_proposal": "停火提议"
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
    print("=" * 50)
    print("2026 美伊战争模拟数据生成完成")
    print("=" * 50)
    print(f"参战方: {len(BATTLEFIELD_CONFIG['factions'])}")
    print(f"地理区域: {len(BATTLEFIELD_CONFIG['areas'])}")
    print(f"- 地理位置: {len(data['locations'])}")
    print(f"- 军事单位: {len(data['military_units'])}")
    print(f"- 武器系统: {len(data['weapon_systems'])}")
    print(f"- 民用设施: {len(data['civilian_infrastructures'])}")
    print(f"- 战场事件: {len(data['battle_events'])}")
    print(f"- 任务: {len(data['missions'])}")

    print("\n参战方详情:")
    for f in BATTLEFIELD_CONFIG["factions"]:
        print(f"  - {f['name']}: {f['description']}")

    random_event = generate_random_event()
    print(f"\n随机事件: {random_event['description']}")