"""
战场实体模拟数据生成模块
"""

import random
import json
import sys
import os
from datetime import datetime, timedelta

# 确保当前目录在Python路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ontology.battlefield_ontology import BATTLEFIELD_CONFIG

# 生成随机坐标
def generate_coordinates():
    """
    生成随机坐标
    """
    return (random.uniform(0, 100), random.uniform(0, 100))

# 生成随机时间戳
def generate_timestamp():
    """
    生成随机时间戳
    """
    start = datetime.now() - timedelta(days=7)
    end = datetime.now()
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)

# 生成战场实体模拟数据
def generate_simulation_data():
    """
    生成战场实体模拟数据
    """
    data = {
        "locations": [],
        "military_units": [],
        "weapon_systems": [],
        "civilian_infrastructures": [],
        "battle_events": [],
        "missions": []
    }
    
    # 生成地理位置
    areas = BATTLEFIELD_CONFIG["areas"]
    for area in areas:
        for i in range(1, 4):
            location = {
                "id": f"LOC_{area}_{i}",
                "type": "Location",
                "properties": {
                    "name": f"{area}区地点{i}",
                    "coordinates": generate_coordinates(),
                    "area": area,
                    "terrain": random.choice(["平原", "山地", "森林", "城市"])
                },
                "relationships": {
                    "contains": [],
                    "adjacent_to": []
                }
            }
            data["locations"].append(location)
    
    # 生成军事单位
    factions = BATTLEFIELD_CONFIG["factions"]
    unit_types = ["步兵", "装甲", "炮兵", "防空", "侦察"]
    for faction in factions:
        for i in range(1, 4):
            unit = {
                "id": f"UNIT_{faction['name'][:2]}_{i}",
                "type": "MilitaryUnit",
                "properties": {
                    "name": f"{faction['name']} {unit_types[i-1]}部队{i}",
                    "type": unit_types[i-1],
                    "strength": random.randint(100, 1000),
                    "equipment": random.sample(["步枪", "坦克", "火炮", "导弹", "雷达"], random.randint(1, 3)),
                    "status": random.choice(["待命", "行动中", "受损"]),
                    "affiliation": faction['name']
                },
                "relationships": {
                    "located_at": random.choice(data["locations"])["id"] if data["locations"] else None,
                    "attached_to": None,
                    "engaged_with": []
                }
            }
            data["military_units"].append(unit)
    
    # 生成武器系统
    weapon_types = ["雷达", "导弹", "火炮", "防空系统", "无人机"]
    for faction in factions:
        for i in range(1, 3):
            weapon = {
                "id": f"WEAPON_{faction['name'][:2]}_{i}",
                "type": "WeaponSystem",
                "properties": {
                    "name": f"{faction['name']} {weapon_types[i-1]}{i}",
                    "type": weapon_types[i-1],
                    "range": random.uniform(5, 100),
                    "status": random.choice(["正常", "受损", "维修中"]),
                    "affiliation": faction['name']
                },
                "relationships": {
                    "located_at": random.choice(data["locations"])["id"] if data["locations"] else None,
                    "operated_by": random.choice(data["military_units"])["id"] if data["military_units"] else None
                }
            }
            data["weapon_systems"].append(weapon)
    
    # 生成民用设施
    civ_types = ["医院", "学校", "工厂", "机场", "港口"]
    for area in areas:
        for i in range(1, 3):
            civ = {
                "id": f"CIV_{area}_{i}",
                "type": "CivilianInfrastructure",
                "properties": {
                    "name": f"{area}区{civ_types[i-1]}{i}",
                    "type": civ_types[i-1],
                    "status": random.choice(["正常", "受损", "关闭"])
                },
                "relationships": {
                    "located_at": random.choice(data["locations"])["id"] if data["locations"] else None
                }
            }
            data["civilian_infrastructures"].append(civ)
    
    # 生成战场事件
    event_types = ["攻击", "防御", "侦察", "补给", "撤退"]
    for i in range(1, 11):
        event = {
            "id": f"EVENT_{i}",
            "type": "BattleEvent",
            "properties": {
                "type": random.choice(event_types),
                "timestamp": generate_timestamp().isoformat(),
                "description": f"战场事件{i}",
                "outcome": random.choice(["成功", "失败", "平局"])
            },
            "relationships": {
                "involves": [random.choice(data["military_units"])["id"] for _ in range(random.randint(1, 2))] if data["military_units"] else [],
                "occurs_at": random.choice(data["locations"])["id"] if data["locations"] else None
            }
        }
        data["battle_events"].append(event)
    
    # 生成任务
    mission_types = ["攻击", "侦察", "防御", "补给", "救援"]
    for i in range(1, 6):
        mission = {
            "id": f"MISSION_{i}",
            "type": "Mission",
            "properties": {
                "type": random.choice(mission_types),
                "status": random.choice(["计划中", "进行中", "完成", "失败"]),
                "priority": random.choice(["高", "中", "低"]),
                "deadline": (datetime.now() + timedelta(days=random.randint(1, 7))).isoformat()
            },
            "relationships": {
                "assigned_to": random.choice(data["military_units"])["id"] if data["military_units"] else None,
                "targets": [random.choice(data["weapon_systems"])["id"] for _ in range(random.randint(1, 2))] if data["weapon_systems"] else [],
                "located_at": random.choice(data["locations"])["id"] if data["locations"] else None
            }
        }
        data["missions"].append(mission)
    
    return data

# 生成战场随机事件
def generate_random_event():
    """
    生成战场随机事件
    """
    event_types = BATTLEFIELD_CONFIG["random_events"]
    event_type = random.choice(event_types)
    
    event = {
        "id": f"RANDOM_EVENT_{int(datetime.now().timestamp())}",
        "type": event_type,
        "timestamp": datetime.now().isoformat(),
        "description": f"随机事件: {event_type}",
        "impact": random.choice(["轻微", "中等", "严重"])
    }
    
    return event

# 保存模拟数据到文件
def save_simulation_data():
    """
    保存模拟数据到文件
    """
    data = generate_simulation_data()
    with open("data/simulation_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return data

# 加载模拟数据
def load_simulation_data():
    """
    加载模拟数据
    """
    try:
        with open("data/simulation_data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return save_simulation_data()

if __name__ == "__main__":
    # 生成并保存模拟数据
    data = save_simulation_data()
    print("模拟数据生成完成，包含以下实体:")
    print(f"- 地理位置: {len(data['locations'])}")
    print(f"- 军事单位: {len(data['military_units'])}")
    print(f"- 武器系统: {len(data['weapon_systems'])}")
    print(f"- 民用设施: {len(data['civilian_infrastructures'])}")
    print(f"- 战场事件: {len(data['battle_events'])}")
    print(f"- 任务: {len(data['missions'])}")
    
    # 生成随机事件
    random_event = generate_random_event()
    print(f"\n生成的随机事件: {random_event}")