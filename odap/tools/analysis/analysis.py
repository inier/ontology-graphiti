"""
分析技能模块
实现领域态势分析和实体状态分析功能
"""

import sys
import os
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odap.tools import register_skill
from odap.infra.graph import GraphManager
from odap.biz.core.ontology.design.mock_data.data_generator import load_simulation_data

logger = logging.getLogger(__name__)

manager = GraphManager()

def analyze_entity_status(entity_id=None, entity_type=None):
    """
    分析实体状态

    Args:
        entity_id: 实体ID（可选）
        entity_type: 实体类型（可选）

    Returns:
        实体状态分析结果
    """
    # 1. 尝试从图谱获取真实数据
    try:
        if entity_id:
            entity = manager.get_entity(entity_id)
            if entity:
                return {
                    "status": "success",
                    "entity": entity,
                    "data_source": "graph",
                    "analysis": f"实体 {entity_id} 状态正常"
                }
        if entity_type:
            entities = manager.query_entities(entity_type=entity_type)
            if entities:
                return {
                    "status": "success",
                    "entity_type": entity_type,
                    "count": len(entities),
                    "entities": entities,
                    "data_source": "graph"
                }
    except Exception as e:
        logger.warning("Graph query failed, falling back to simulation data: %s", e)

    # 2. 降级到模拟数据
    data = load_simulation_data()

    if entity_id:
        for entity in data.get("locations", []) + data.get("units", []) + \
                      data.get("equipment", []) + data.get("public_assets", []):
            if entity["id"] == entity_id:
                return {
                    "status": "success",
                    "entity": entity,
                    "data_source": "simulation",
                    "analysis": f"实体 {entity_id} 状态正常"
                }
        return {"status": "error", "message": f"实体 {entity_id} 不存在"}

    if entity_type:
        entities = []
        type_map = {
            "Location": "locations",
            "OrganizationUnit": "units",
            "ToolSystem": "equipment",
            "PublicAsset": "public_assets"
        }
        for etype, key in type_map.items():
            if entity_type == etype or entity_type == key:
                entities = data.get(key, [])
                break

        return {
            "status": "success",
            "entity_type": entity_type,
            "count": len(entities),
            "entities": entities,
            "data_source": "simulation"
        }

    return {"status": "error", "message": "请提供 entity_id 或 entity_type"}

def analyze_incident_events(time_range=None):
    """
    分析领域事件

    Args:
        time_range: 时间范围（可选）

    Returns:
        领域事件分析结果
    """
    # 1. 尝试从图谱获取真实数据
    try:
        if time_range:
            events = manager.query_temporal(valid_time=time_range)
        else:
            events = manager.query_entities(entity_type="IncidentEvent")
        if events:
            event_types = {}
            for event in events:
                event_type = event.get("type", "Unknown")
                event_types[event_type] = event_types.get(event_type, 0) + 1
            return {
                "status": "success",
                "total_events": len(events),
                "event_types": event_types,
                "events": events[:10],
                "data_source": "graph"
            }
    except Exception as e:
        logger.warning("Graph query failed, falling back to simulation data: %s", e)

    # 2. 降级到模拟数据
    data = load_simulation_data()
    events = data.get("events", [])

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
        "events": events[:10],
        "data_source": "simulation"
    }

def analyze_force_comparison(area=None):
    """
    分析力量对比

    Args:
        area: 区域（可选）

    Returns:
        力量对比分析结果
    """
    # 1. 尝试从图谱获取真实数据
    try:
        units = manager.query_entities(entity_type="OrganizationUnit", area=area)
        weapons = manager.query_entities(entity_type="ToolSystem", area=area)
        if units or weapons:
            force_by_affiliation = {}
            for unit in units:
                props = unit.get("properties", {})
                affiliation = props.get("affiliation", "Unknown")
                if affiliation not in force_by_affiliation:
                    force_by_affiliation[affiliation] = {"units": 0, "equipment": 0, "total_strength": 0}
                force_by_affiliation[affiliation]["units"] += 1
                force_by_affiliation[affiliation]["total_strength"] += props.get("strength", 0)
            for weapon in weapons:
                props = weapon.get("properties", {})
                affiliation = props.get("affiliation", "Unknown")
                if affiliation in force_by_affiliation:
                    force_by_affiliation[affiliation]["equipment"] += 1
                    force_by_affiliation[affiliation]["total_strength"] += props.get("power", 0)
                else:
                    force_by_affiliation[affiliation] = {"units": 0, "equipment": 1, "total_strength": props.get("power", 0)}
            sorted_forces = sorted(force_by_affiliation.items(), key=lambda x: x[1]["total_strength"], reverse=True)
            return {
                "status": "success",
                "area": area or "全部区域",
                "force_comparison": dict(sorted_forces),
                "dominant_force": sorted_forces[0][0] if sorted_forces else None,
                "data_source": "graph"
            }
    except Exception as e:
        logger.warning("Graph query failed, falling back to simulation data: %s", e)

    # 2. 降级到模拟数据
    data = load_simulation_data()
    units = data.get("units", [])
    weapons = data.get("equipment", [])

    if area:
        units = [u for u in units if u.get("properties", {}).get("area") == area]
        weapons = [w for w in weapons if w.get("properties", {}).get("area") == area]

    force_by_affiliation = {}

    for unit in units:
        affiliation = unit.get("properties", {}).get("affiliation", "Unknown")
        if affiliation not in force_by_affiliation:
            force_by_affiliation[affiliation] = {"units": 0, "equipment": 0, "total_strength": 0}
        force_by_affiliation[affiliation]["units"] += 1
        force_by_affiliation[affiliation]["total_strength"] += unit.get("properties", {}).get("strength", 0)

    for weapon in weapons:
        affiliation = weapon.get("properties", {}).get("affiliation", "Unknown")
        if affiliation in force_by_affiliation:
            force_by_affiliation[affiliation]["equipment"] += 1
            force_by_affiliation[affiliation]["total_strength"] += weapon.get("properties", {}).get("power", 0)

    sorted_forces = sorted(force_by_affiliation.items(), key=lambda x: x[1]["total_strength"], reverse=True)

    return {
        "status": "success",
        "area": area or "全部区域",
        "force_comparison": dict(sorted_forces),
        "dominant_force": sorted_forces[0][0] if sorted_forces else None,
        "data_source": "simulation"
    }

def analyze_equipment_capabilities(equipment_type=None):
    """
    分析设备能力

    Args:
        equipment_type: 设备类型（可选）

    Returns:
        设备能力分析结果
    """
    # 1. 尝试从图谱获取真实数据
    try:
        weapons = manager.query_entities(entity_type="ToolSystem")
        if weapons:
            if equipment_type:
                weapons = [w for w in weapons if w.get("properties", {}).get("type") == equipment_type]
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
                "total_equipment": len(capabilities),
                "capabilities": sorted_by_power,
                "most_powerful": sorted_by_power[0] if sorted_by_power else None,
                "data_source": "graph"
            }
    except Exception as e:
        logger.warning("Graph query failed, falling back to simulation data: %s", e)

    # 2. 降级到模拟数据
    data = load_simulation_data()
    weapons = data.get("equipment", [])

    if equipment_type:
        weapons = [w for w in weapons if w.get("properties", {}).get("type") == equipment_type]

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
        "total_equipment": len(capabilities),
        "capabilities": sorted_by_power,
        "most_powerful": sorted_by_power[0] if sorted_by_power else None,
        "data_source": "simulation"
    }

def analyze_public_asset():
    """
    分析公共资产分布

    Returns:
        公共资产分析结果
    """
    # 1. 尝试从图谱获取真实数据
    try:
        civs = manager.query_entities(entity_type="PublicAsset")
        if civs:
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
                "protected_ids": protected,
                "data_source": "graph"
            }
    except Exception as e:
        logger.warning("Graph query failed, falling back to simulation data: %s", e)

    # 2. 降级到模拟数据
    data = load_simulation_data()
    civs = data.get("public_assets", [])

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
        "protected_ids": protected,
        "data_source": "simulation"
    }

def get_domain_summary():
    """
    获取领域态势摘要

    Returns:
        领域态势摘要
    """
    stats = manager.get_graph_statistics()

    return {
        "status": "success",
        "total_entities": stats.get("total_entities", 0),
        "entity_types": stats.get("entity_types", {}),
        "graph_mode": stats.get("mode", "unknown"),
        "recommendations": [
            "持续监控对手传感器活动",
            "加强对公共资产的保护",
            "优化资源部署"
        ]
    }

register_skill(
    name="analyze_entity_status",
    description="分析实体状态",
    handler=analyze_entity_status,
    category="analysis")


register_skill(
    name="analyze_incident_events",
    description="分析领域事件",
    handler=analyze_incident_events,
    category="analysis")


register_skill(
    name="analyze_force_comparison",
    description="分析力量对比",
    handler=analyze_force_comparison,
    category="analysis")


register_skill(
    name="analyze_equipment_capabilities",
    description="分析设备能力",
    handler=analyze_equipment_capabilities,
    category="analysis")


register_skill(
    name="analyze_public_asset",
    description="分析公共资产",
    handler=analyze_public_asset,
    category="analysis")


register_skill(
    name="get_domain_summary",
    description="获取领域态势摘要",
    handler=get_domain_summary,
    category="analysis")
