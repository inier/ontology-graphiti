"""
可视化与报告Skill模块
实现领域态势可视化和报告生成功能
"""

import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odap.tools import register_skill
from odap.infra.graph import GraphManager
from odap.biz.simulator.data_generator import load_simulation_data

manager = GraphManager()

def generate_map_overlay(area=None, output_file="map_overlay.json"):
    """
    生成地图叠加层数据

    Args:
        area: 区域
        output_file: 输出文件

    Returns:
        地图叠加层数据
    """
    data = load_simulation_data()
    locations = data.get("locations", [])
    units = data.get("military_units", [])
    weapons = data.get("weapon_systems", [])

    overlay_features = []

    for location in locations:
        if area and location["properties"].get("area") != area:
            continue

        coords = location["properties"].get("coordinates", [0, 0])
        overlay_features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": coords
            },
            "properties": {
                "id": location["id"],
                "name": location["properties"].get("name", ""),
                "category": "location",
                "color": "#1f77b4"
            }
        })

    for unit in units:
        unit_area = unit["properties"].get("area")
        if area and unit_area != area:
            continue

        affiliation = unit["properties"].get("affiliation", "")
        color = "#ff7f0e" if affiliation == "Blue Force" else "#d62728"

        overlay_features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": unit["properties"].get("coordinates", [0, 0])
            },
            "properties": {
                "id": unit["id"],
                "name": unit["properties"].get("name", ""),
                "category": "military_unit",
                "color": color,
                "status": unit["properties"].get("status", "")
            }
        })

    geojson = {
        "type": "FeatureCollection",
        "features": overlay_features
    }

    return {
        "status": "success",
        "output_file": output_file,
        "feature_count": len(overlay_features),
        "geojson": geojson
    }

def summarize_mission(mission_id):
    """
    生成任务摘要

    Args:
        mission_id: 任务ID

    Returns:
        任务摘要
    """
    data = load_simulation_data()
    missions = data.get("missions", [])

    mission = None
    for m in missions:
        if m["id"] == mission_id:
            mission = m
            break

    if not mission:
        return {"status": "error", "message": f"任务 {mission_id} 不存在"}

    props = mission.get("properties", {})

    summary = {
        "status": "success",
        "mission_id": mission_id,
        "mission_name": props.get("name", "未命名任务"),
        "type": props.get("type", "未知"),
        "priority": props.get("priority", "未知"),
        "status": props.get("status", "未知"),
        "area": props.get("area", "未知"),
        "objectives": props.get("objectives", []),
        "start_time": props.get("start_time", "未知"),
        "report": f"任务 {props.get('name', mission_id)} 状态: {props.get('status', '未知')}"
    }

    return summary

def generate_domain_report():
    """
    生成领域态势报告

    Returns:
        领域态势报告
    """
    stats = manager.get_graph_statistics()
    data = load_simulation_data()

    blue_units = len([u for u in data.get("military_units", []) if u.get("properties", {}).get("affiliation") == "Blue Force"])
    red_units = len([u for u in data.get("military_units", []) if u.get("properties", {}).get("affiliation") in ["Red Force", "Green Insurgents"]])

    blue_weapons = len([w for w in data.get("weapon_systems", []) if w.get("properties", {}).get("affiliation") == "Blue Force"])
    red_weapons = len([w for w in data.get("weapon_systems", []) if w.get("properties", {}).get("affiliation") in ["Red Force", "Green Insurgents"]])

    active_radars = len([w for w in data.get("weapon_systems", []) if w.get("properties", {}).get("type") == "雷达" and w.get("properties", {}).get("status") == "正常"])

    report = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "report_title": "领域态势综合报告",
        "summary": {
            "total_entities": stats.get("total_entities", 0),
            "force_comparison": {
                "blue_force": {"units": blue_units, "weapons": blue_weapons},
                "red_force": {"units": red_units, "weapons": red_weapons}
            },
            "active_radars": active_radars,
            "graph_mode": stats.get("mode", "unknown")
        },
        "recommendations": [
            "持续监控敌方雷达活动",
            "加强对民用设施的保护",
            "优化兵力部署"
        ]
    }

    return report

def generate_situation_awareness(area=None):
    """
    生成态势感知数据

    Args:
        area: 区域

    Returns:
        态势感知数据
    """
    data = load_simulation_data()

    areas = {}
    for location in data.get("locations", []):
        loc_area = location["properties"].get("area", "未知")
        if area and loc_area != area:
            continue

        if loc_area not in areas:
            areas[loc_area] = {
                "blue_units": 0,
                "red_units": 0,
                "blue_weapons": 0,
                "red_weapons": 0,
                "civilian_facilities": 0,
                "control_level": "unknown"
            }

        for unit in data.get("military_units", []):
            if unit["properties"].get("area") == loc_area:
                affiliation = unit["properties"].get("affiliation", "")
                if affiliation == "Blue Force":
                    areas[loc_area]["blue_units"] += 1
                elif affiliation in ["Red Force", "Green Insurgents"]:
                    areas[loc_area]["red_units"] += 1

        for weapon in data.get("weapon_systems", []):
            if weapon["properties"].get("area") == loc_area:
                affiliation = weapon["properties"].get("affiliation", "")
                if affiliation == "Blue Force":
                    areas[loc_area]["blue_weapons"] += 1
                elif affiliation in ["Red Force", "Green Insurgents"]:
                    areas[loc_area]["red_weapons"] += 1

        for civ in data.get("civilian_infrastructures", []):
            if civ["properties"].get("area") == loc_area:
                areas[loc_area]["civilian_facilities"] += 1

    for loc_area, stats in areas.items():
        blue_total = stats["blue_units"] + stats["blue_weapons"]
        red_total = stats["red_units"] + stats["red_weapons"]

        if blue_total > red_total * 1.5:
            stats["control_level"] = "blue_dominant"
        elif red_total > blue_total * 1.5:
            stats["control_level"] = "red_dominant"
        else:
            stats["control_level"] = "contested"

    return {
        "status": "success",
        "area": area or "全部区域",
        "situation": areas,
        "timestamp": datetime.now().isoformat()
    }

register_skill(
    name="generate_map_overlay",
    description="生成地图叠加层数据",
    handler=generate_map_overlay,
    category="visualization")


register_skill(
    name="summarize_mission",
    description="生成任务摘要",
    handler=summarize_mission,
    category="visualization")


register_skill(
    name="generate_domain_report",
    description="生成领域态势报告",
    handler=generate_domain_report,
    category="visualization")


register_skill(
    name="generate_situation_awareness",
    description="生成态势感知数据",
    handler=generate_situation_awareness,
    category="visualization")
