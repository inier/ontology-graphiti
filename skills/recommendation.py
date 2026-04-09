"""
推荐技能模块
实现打击决策和任务规划推荐功能
"""

import sys
import os
import random

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills import register_skill
from core.graph_manager import BattlefieldGraphManager
from core.opa_manager import OPAManager
from data.simulation_data import load_simulation_data

manager = BattlefieldGraphManager()
opa_manager = OPAManager()

def recommend_strike_targets(user_role, area=None, target_type=None):
    """
    推荐打击目标

    Args:
        user_role: 用户角色
        area: 区域（可选）
        target_type: 目标类型（可选）

    Returns:
        打击目标推荐列表
    """
    if user_role != "commander":
        return {"status": "denied", "message": "只有指挥官才能获取打击目标推荐"}

    data = load_simulation_data()
    weapons = data.get("weapon_systems", [])
    units = data.get("military_units", [])

    targets = []

    for weapon in weapons:
        affiliation = weapon.get("properties", {}).get("affiliation", "")
        if affiliation in ["Red Force", "Green Insurgents"]:
            weapon_area = weapon.get("properties", {}).get("area")
            if area and weapon_area != area:
                continue

            status = weapon.get("properties", {}).get("status", "正常")
            if status == "损毁":
                continue

            targets.append({
                "id": weapon["id"],
                "name": weapon.get("properties", {}).get("name", "未知"),
                "type": weapon.get("properties", {}).get("type", "未知"),
                "affiliation": affiliation,
                "priority": "high" if weapon.get("properties", {}).get("type") == "雷达" else "medium",
                "area": weapon_area,
                "reason": f"敌方{weapon.get('properties', {}).get('type', '目标')}"
            })

    for unit in units:
        affiliation = unit.get("properties", {}).get("affiliation", "")
        if affiliation in ["Red Force", "Green Insurgents"]:
            unit_area = unit.get("properties", {}).get("area")
            if area and unit_area != area:
                continue

            targets.append({
                "id": unit["id"],
                "name": unit.get("properties", {}).get("name", "未知"),
                "type": "军事单位",
                "affiliation": affiliation,
                "priority": "low",
                "area": unit_area,
                "reason": "敌方军事单位"
            })

    targets.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["priority"]])

    return {
        "status": "success",
        "user_role": user_role,
        "targets": targets[:10],
        "total": len(targets)
    }

def recommend_task_planning(user_role, mission_type=None):
    """
    推荐任务规划

    Args:
        user_role: 用户角色
        mission_type: 任务类型（可选）

    Returns:
        任务规划推荐
    """
    if user_role not in ["commander", "intelligence_analyst"]:
        return {"status": "denied", "message": "权限不足"}

    data = load_simulation_data()
    events = data.get("battle_events", [])

    recent_events = sorted(events, key=lambda x: x.get("properties", {}).get("timestamp", ""), reverse=True)[:5]

    recommendations = []

    for event in recent_events:
        event_type = event.get("properties", {}).get("type", "")
        if event_type == "enemy_reinforcement":
            recommendations.append({
                "mission_type": "侦察任务",
                "priority": "high",
                "reason": "敌方增援活动频繁",
                "suggested_targets": ["B区", "C区"]
            })
        elif event_type == "radar_detection":
            recommendations.append({
                "mission_type": "压制任务",
                "priority": "medium",
                "reason": "敌方雷达探测到活动",
                "suggested_targets": ["敌方雷达站"]
            })

    if not recommendations:
        recommendations.append({
            "mission_type": mission_type or "常规巡逻",
            "priority": "low",
            "reason": "无特殊事件",
            "suggested_targets": ["A区", "B区", "C区"]
        })

    return {
        "status": "success",
        "user_role": user_role,
        "recommendations": recommendations,
        "recent_events_count": len(recent_events)
    }

def recommend_force_deployment(user_role, area):
    """
    推荐兵力部署

    Args:
        user_role: 用户角色
        area: 区域

    Returns:
        兵力部署推荐
    """
    if user_role != "commander":
        return {"status": "denied", "message": "只有指挥官才能获取兵力部署推荐"}

    data = load_simulation_data()
    units = data.get("military_units", [])
    weapons = data.get("weapon_systems", [])

    area_units = [u for u in units if u.get("properties", {}).get("area") == area]
    area_weapons = [w for w in weapons if w.get("properties", {}).get("area") == area]

    blue_units = len([u for u in area_units if u.get("properties", {}).get("affiliation") == "Blue Force"])
    red_units = len([u for u in area_units if u.get("properties", {}).get("affiliation") in ["Red Force", "Green Insurgents"]])

    deployment = {
        "area": area,
        "current_blue_units": blue_units,
        "current_red_units": red_units,
        "recommendation": ""
    }

    if blue_units < red_units:
        deployment["recommendation"] = "建议增派部队，当前蓝方力量不足"
        deployment["priority"] = "high"
    elif blue_units > red_units * 1.5:
        deployment["recommendation"] = "当前部署充足，可考虑调往其他区域"
        deployment["priority"] = "low"
    else:
        deployment["recommendation"] = "维持当前部署，密切监控态势"
        deployment["priority"] = "medium"

    return {
        "status": "success",
        "deployment": deployment
    }

def check_strike_risk(target_id, user_role):
    """
    检查打击风险

    Args:
        target_id: 目标ID
        user_role: 用户角色

    Returns:
        打击风险评估
    """
    data = load_simulation_data()

    target = None
    for weapon in data.get("weapon_systems", []):
        if weapon["id"] == target_id:
            target = weapon
            break
    for unit in data.get("military_units", []):
        if unit["id"] == target_id:
            target = unit
            break

    if not target:
        return {"status": "error", "message": f"目标 {target_id} 不存在"}

    props = target.get("properties", {})
    target_type = props.get("type", "未知")
    affiliation = props.get("affiliation", "未知")

    risk = "low"

    if affiliation == "Blue Force":
        risk = "critical"
        reason = "目标为友方单位，禁止打击"
    elif affiliation == "CivilianInfrastructure":
        risk = "high"
        reason = "目标为民用设施，可能造成附带损伤"
    elif props.get("status") == "受损":
        risk = "low"
        reason = "目标已受损，打击风险较低"
    else:
        reason = "目标为敌方单位，可考虑打击"

    return {
        "status": "success",
        "target_id": target_id,
        "target_name": props.get("name", "未知"),
        "target_type": target_type,
        "affiliation": affiliation,
        "risk_level": risk,
        "reason": reason,
        "user_role": user_role
    }

register_skill(
    name="recommend_strike_targets",
    description="推荐打击目标",
    handler=recommend_strike_targets
)

register_skill(
    name="recommend_task_planning",
    description="推荐任务规划",
    handler=recommend_task_planning
)

register_skill(
    name="recommend_force_deployment",
    description="推荐兵力部署",
    handler=recommend_force_deployment
)

register_skill(
    name="check_strike_risk",
    description="检查打击风险",
    handler=check_strike_risk
)