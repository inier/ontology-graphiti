"""
分析技能模块
实现战场态势分析和实体状态分析功能
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills import register_skill
from core.graph_manager import BattlefieldGraphManager
from data.simulation_data import load_simulation_data

manager = BattlefieldGraphManager()

def analyze_entity_status(entity_id=None, entity_type=None):
    """
    分析实体状态

    Args:
        entity_id: 实体ID（可选）
        entity_type: 实体类型（可选）

    Returns:
        实体状态分析结果
    """
    data = load_simulation_data()

    if entity_id:
        for entity in data.get("locations", []) + data.get("military_units", []) + \
                      data.get("weapon_systems", []) + data.get("civilian_infrastructures", []):
            if entity["id"] == entity_id:
                return {
                    "status": "success",
                    "entity": entity,
                    "analysis": f"实体 {entity_id} 状态正常"
                }
        return {"status": "error", "message": f"实体 {entity_id} 不存在"}

    if entity_type:
        entities = []
        type_map = {
            "Location": "locations",
            "MilitaryUnit": "military_units",
            "WeaponSystem": "weapon_systems",
            "CivilianInfrastructure": "civilian_infrastructures"
        }
        for etype, key in type_map.items():
            if entity_type == etype or entity_type == key:
                entities = data.get(key, [])
                break

        return {
            "status": "success",
            "entity_type": entity_type,
            "count": len(entities),
            "entities": entities
        }

    return {"status": "error", "message": "请提供 entity_id 或 entity_type"}

def analyze_battle_events(time_range=None):
    """
    分析战场事件

    Args:
        time_range: 时间范围（可选）

    Returns:
        战场事件分析结果
    """
    data = load_simulation_data()
    events = data.get("battle_events", [])

    if time_range:
        filtered_events = [e for e in events if e.get("timestamp") >= time_range]
        events = filtered_events

    event_types = {}
    for event in events:
        event_type = event.get("properties", {}).get("type", "Unknown")
        event_types[event_type] = event_types.get(event_type, 0) + 1

    return {
        "status": "success",
        "total_events": len(events),
        "event_types": event_types,
        "events": events[:10]
    }

def analyze_force_comparison(area=None):
    """
    分析力量对比

    Args:
        area: 区域（可选）

    Returns:
        力量对比分析结果
    """
    data = load_simulation_data()
    units = data.get("military_units", [])
    weapons = data.get("weapon_systems", [])

    if area:
        units = [u for u in units if u.get("properties", {}).get("area") == area]
        weapons = [w for w in weapons if w.get("properties", {}).get("area") == area]

    force_by_affiliation = {}

    for unit in units:
        affiliation = unit.get("properties", {}).get("affiliation", "Unknown")
        if affiliation not in force_by_affiliation:
            force_by_affiliation[affiliation] = {"units": 0, "weapons": 0, "total_strength": 0}
        force_by_affiliation[affiliation]["units"] += 1
        force_by_affiliation[affiliation]["total_strength"] += unit.get("properties", {}).get("strength", 0)

    for weapon in weapons:
        affiliation = weapon.get("properties", {}).get("affiliation", "Unknown")
        if affiliation in force_by_affiliation:
            force_by_affiliation[affiliation]["weapons"] += 1
            force_by_affiliation[affiliation]["total_strength"] += weapon.get("properties", {}).get("power", 0)

    sorted_forces = sorted(force_by_affiliation.items(), key=lambda x: x[1]["total_strength"], reverse=True)

    return {
        "status": "success",
        "area": area or "全部区域",
        "force_comparison": dict(sorted_forces),
        "dominant_force": sorted_forces[0][0] if sorted_forces else None
    }

def analyze_weapon_capabilities(weapon_type=None):
    """
    分析武器能力

    Args:
        weapon_type: 武器类型（可选）

    Returns:
        武器能力分析结果
    """
    data = load_simulation_data()
    weapons = data.get("weapon_systems", [])

    if weapon_type:
        weapons = [w for w in weapons if w.get("properties", {}).get("type") == weapon_type]

    capabilities = []
    for weapon in weapons:
        props = weapon.get("properties", {})
        capabilities.append({
            "id": weapon["id"],
            "name": props.get("name", "未知"),
            "type": props.get("type", "未知"),
            "affiliation": props.get("affiliation", "未知"),
            "range": props.get("range", 0),
            "power": props.get("power", 0),
            "status": props.get("status", "未知")
        })

    sorted_by_power = sorted(capabilities, key=lambda x: x["power"], reverse=True)

    return {
        "status": "success",
        "total_weapons": len(capabilities),
        "capabilities": sorted_by_power,
        "most_powerful": sorted_by_power[0] if sorted_by_power else None
    }

def analyze_civilian_infrastructure():
    """
    分析民用基础设施分布

    Returns:
        民用基础设施分析结果
    """
    data = load_simulation_data()
    civs = data.get("civilian_infrastructures", [])

    by_type = {}
    by_area = {}
    protected = []

    for civ in civs:
        props = civ.get("properties", {})
        civ_type = props.get("type", "Unknown")
        area = props.get("area", "Unknown")

        by_type[civ_type] = by_type.get(civ_type, 0) + 1
        by_area[area] = by_area.get(area, 0) + 1

        if props.get("protected"):
            protected.append(civ["id"])

    return {
        "status": "success",
        "total": len(civs),
        "by_type": by_type,
        "by_area": by_area,
        "protected_count": len(protected),
        "protected_ids": protected
    }

def get_battlefield_summary():
    """
    获取战场态势摘要

    Returns:
        战场态势摘要
    """
    stats = manager.get_graph_statistics()

    return {
        "status": "success",
        "total_entities": stats.get("node_count", 0),
        "entity_types": stats.get("type_count", {}),
        "graph_mode": stats.get("mode", "unknown"),
        "recommendations": [
            "持续监控敌方雷达活动",
            "加强对民用设施的保护",
            "优化兵力部署"
        ]
    }

register_skill(
    name="analyze_entity_status",
    description="分析实体状态",
    handler=analyze_entity_status
)

register_skill(
    name="analyze_battle_events",
    description="分析战场事件",
    handler=analyze_battle_events
)

register_skill(
    name="analyze_force_comparison",
    description="分析力量对比",
    handler=analyze_force_comparison
)

register_skill(
    name="analyze_weapon_capabilities",
    description="分析武器能力",
    handler=analyze_weapon_capabilities
)

register_skill(
    name="analyze_civilian_infrastructure",
    description="分析民用基础设施",
    handler=analyze_civilian_infrastructure
)

register_skill(
    name="get_battlefield_summary",
    description="获取战场态势摘要",
    handler=get_battlefield_summary
)