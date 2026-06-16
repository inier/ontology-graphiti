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
from odap.biz.core.ontology.design.mock_data.data_generator import load_simulation_data

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
    units = data.get("units", [])
    weapons = data.get("equipment", [])

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
        color = "#ff7f0e" if affiliation == "Party B" else "#d62728"

        overlay_features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": unit["properties"].get("coordinates", [0, 0])
            },
            "properties": {
                "id": unit["id"],
                "name": unit["properties"].get("name", ""),
                "category": "organizational_unit",
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

    party_b_units = len([u for u in data.get("units", []) if u.get("properties", {}).get("affiliation") == "Party B"])
    party_a_units = len([u for u in data.get("units", []) if u.get("properties", {}).get("affiliation") in ["Party A", "Party C"]])

    party_b_equipment = len([w for w in data.get("equipment", []) if w.get("properties", {}).get("affiliation") == "Party B"])
    party_a_equipment = len([w for w in data.get("equipment", []) if w.get("properties", {}).get("affiliation") in ["Party A", "Party C"]])

    active_radars = len([w for w in data.get("equipment", []) if w.get("properties", {}).get("type") == "传感器" and w.get("properties", {}).get("status") == "正常"])

    report = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "report_title": "领域态势综合报告",
        "summary": {
            "total_entities": stats.get("total_entities", 0),
            "force_comparison": {
                "party_b": {"units": party_b_units, "equipment": party_b_equipment},
                "party_a": {"units": party_a_units, "equipment": party_a_equipment}
            },
            "active_sensors": active_radars,
            "graph_mode": stats.get("mode", "unknown")
        },
        "recommendations": [
            "持续监控对手传感器活动",
            "加强对公共资产的保护",
            "优化资源部署"
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
                "party_b_units": 0,
                "party_a_units": 0,
                "party_b_equipment": 0,
                "party_a_equipment": 0,
                "public_assets": 0,
                "control_level": "unknown"
            }

        for unit in data.get("units", []):
            if unit["properties"].get("area") == loc_area:
                affiliation = unit["properties"].get("affiliation", "")
                if affiliation == "Party B":
                    areas[loc_area]["party_b_units"] += 1
                elif affiliation in ["Party A", "Party C"]:
                    areas[loc_area]["party_a_units"] += 1

        for weapon in data.get("equipment", []):
            if weapon["properties"].get("area") == loc_area:
                affiliation = weapon["properties"].get("affiliation", "")
                if affiliation == "Party B":
                    areas[loc_area]["party_b_equipment"] += 1
                elif affiliation in ["Party A", "Party C"]:
                    areas[loc_area]["party_a_equipment"] += 1

        for civ in data.get("public_assets", []):
            if civ["properties"].get("area") == loc_area:
                areas[loc_area]["public_assets"] += 1

    for loc_area, stats in areas.items():
        party_b_total = stats["party_b_units"] + stats["party_b_equipment"]
        party_a_total = stats["party_a_units"] + stats["party_a_equipment"]

        if party_b_total > party_a_total * 1.5:
            stats["control_level"] = "party_b_dominant"
        elif party_a_total > party_b_total * 1.5:
            stats["control_level"] = "party_a_dominant"
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
