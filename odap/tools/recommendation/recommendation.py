"""
推荐技能模块
实现执行决策和任务规划推荐功能
"""

import sys
import os
import random
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odap.tools import register_skill
from odap.infra.graph import GraphManager
from odap.infra.opa import OPAManager
from odap.biz.core.ontology.design.mock_data.data_generator import load_simulation_data

logger = logging.getLogger(__name__)

manager = GraphManager()
opa_manager = OPAManager()

def recommend_engage_targets(user_role, area=None, target_type=None):
    """
    推荐执行目标

    Args:
        user_role: 用户角色
        area: 区域（可选）
        target_type: 目标类型（可选）

    Returns:
        执行目标推荐列表
    """
    if user_role != "director":
        return {"status": "denied", "message": "只有负责人才能获取执行目标推荐"}

    # 1. 尝试从图谱获取真实数据
    try:
        weapons = manager.query_entities(entity_type="ToolSystem", area=area)
        units = manager.query_entities(entity_type="OrganizationUnit", area=area)
        if weapons or units:
            targets = []
            for weapon in weapons:
                props = weapon.get("properties", {})
                affiliation = props.get("affiliation", "")
                if affiliation in ["Party A", "Party C"]:
                    status = props.get("status", "正常")
                    if status == "损毁":
                        continue
                    targets.append({
                        "id": weapon["id"],
                        "name": props.get("name", "未知"),
                        "type": props.get("type", "未知"),
                        "affiliation": affiliation,
                        "priority": "high" if props.get("type") == "传感器" else "medium",
                        "area": props.get("area"),
                        "reason": f"对手{props.get('type', '目标')}"
                    })
            for unit in units:
                props = unit.get("properties", {})
                affiliation = props.get("affiliation", "")
                if affiliation in ["Party A", "Party C"]:
                    targets.append({
                        "id": unit["id"],
                        "name": props.get("name", "未知"),
                        "type": "组织单元",
                        "affiliation": affiliation,
                        "priority": "low",
                        "area": props.get("area"),
                        "reason": "对手组织单元"
                    })
            if target_type:
                targets = [t for t in targets if t.get("type") == target_type]
            targets.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["priority"]])
            return {
                "status": "success",
                "user_role": user_role,
                "targets": targets[:10],
                "total": len(targets),
                "data_source": "graph"
            }
    except Exception as e:
        logger.warning("Graph query failed, falling back to simulation data: %s", e)

    # 2. 降级到模拟数据
    data = load_simulation_data()
    weapons = data.get("equipment", [])
    units = data.get("units", [])

    targets = []

    for weapon in weapons:
        affiliation = weapon.get("properties", {}).get("affiliation", "")
        if affiliation in ["Party A", "Party C"]:
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
                "priority": "high" if weapon.get("properties", {}).get("type") == "传感器" else "medium",
                "area": weapon_area,
                "reason": f"对手{weapon.get('properties', {}).get('type', '目标')}"
            })

    for unit in units:
        affiliation = unit.get("properties", {}).get("affiliation", "")
        if affiliation in ["Party A", "Party C"]:
            unit_area = unit.get("properties", {}).get("area")
            if area and unit_area != area:
                continue

            targets.append({
                "id": unit["id"],
                "name": unit.get("properties", {}).get("name", "未知"),
                "type": "组织单元",
                "affiliation": affiliation,
                "priority": "low",
                "area": unit_area,
                "reason": "对手组织单元"
            })

    targets.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["priority"]])

    return {
        "status": "success",
        "user_role": user_role,
        "targets": targets[:10],
        "total": len(targets),
        "data_source": "simulation"
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
    if user_role not in ["director", "intelligence_analyst"]:
        return {"status": "denied", "message": "权限不足"}

    # 1. 尝试从图谱获取真实数据
    try:
        events = manager.query_entities(entity_type="IncidentEvent")
        if events:
            recent_events = sorted(
                events,
                key=lambda x: x.get("properties", {}).get("timestamp", ""),
                reverse=True
            )[:5]

            recommendations = []
            for event in recent_events:
                props = event.get("properties", {})
                event_type = props.get("type", "")
                if event_type == "opponent_support":
                    recommendations.append({
                        "mission_type": "侦察任务",
                        "priority": "high",
                        "reason": "对手支援活动频繁",
                        "suggested_targets": ["B区", "C区"]
                    })
                elif event_type == "sensor_detection":
                    recommendations.append({
                        "mission_type": "干预任务",
                        "priority": "medium",
                        "reason": "对手传感器探测到活动",
                        "suggested_targets": ["对手传感器站"]
                    })

            if not recommendations:
                recommendations.append({
                    "mission_type": mission_type or "常规巡查",
                    "priority": "low",
                    "reason": "无特殊事件",
                    "suggested_targets": ["A区", "B区", "C区"]
                })

            return {
                "status": "success",
                "user_role": user_role,
                "recommendations": recommendations,
                "recent_events_count": len(recent_events),
                "data_source": "graph"
            }
    except Exception as e:
        logger.warning("Graph query failed, falling back to simulation data: %s", e)

    # 2. 降级到模拟数据
    data = load_simulation_data()
    events = data.get("events", [])

    recent_events = sorted(events, key=lambda x: x.get("properties", {}).get("timestamp", ""), reverse=True)[:5]

    recommendations = []

    for event in recent_events:
        event_type = event.get("properties", {}).get("type", "")
        if event_type == "opponent_support":
            recommendations.append({
                "mission_type": "侦察任务",
                "priority": "high",
                "reason": "对手支援活动频繁",
                "suggested_targets": ["B区", "C区"]
            })
        elif event_type == "sensor_detection":
            recommendations.append({
                "mission_type": "干预任务",
                "priority": "medium",
                "reason": "对手传感器探测到活动",
                "suggested_targets": ["对手传感器站"]
            })

    if not recommendations:
        recommendations.append({
            "mission_type": mission_type or "常规巡查",
            "priority": "low",
            "reason": "无特殊事件",
            "suggested_targets": ["A区", "B区", "C区"]
        })

    return {
        "status": "success",
        "user_role": user_role,
        "recommendations": recommendations,
        "recent_events_count": len(recent_events),
        "data_source": "simulation"
    }

def recommend_resource_deployment(user_role, area):
    """
    推荐资源部署

    Args:
        user_role: 用户角色
        area: 区域

    Returns:
        资源部署推荐
    """
    if user_role != "director":
        return {"status": "denied", "message": "只有负责人才能获取资源部署推荐"}

    # 1. 尝试从图谱获取真实数据
    try:
        area_units = manager.query_entities(entity_type="OrganizationUnit", area=area)
        area_weapons = manager.query_entities(entity_type="ToolSystem", area=area)
        if area_units or area_weapons:
            blue_units = len([u for u in area_units if u.get("properties", {}).get("affiliation") == "Party B"])
            red_units = len([u for u in area_units if u.get("properties", {}).get("affiliation") in ["Party A", "Party C"]])

            deployment = {
                "area": area,
                "current_party_b_units": blue_units,
                "current_party_a_units": red_units,
                "recommendation": ""
            }

            if blue_units < red_units:
                deployment["recommendation"] = "建议增派团队，当前乙方力量不足"
                deployment["priority"] = "high"
            elif blue_units > red_units * 1.5:
                deployment["recommendation"] = "当前部署充足，可考虑调往其他区域"
                deployment["priority"] = "low"
            else:
                deployment["recommendation"] = "维持当前部署，密切监控态势"
                deployment["priority"] = "medium"

            return {
                "status": "success",
                "deployment": deployment,
                "data_source": "graph"
            }
    except Exception as e:
        logger.warning("Graph query failed, falling back to simulation data: %s", e)

    # 2. 降级到模拟数据
    data = load_simulation_data()
    units = data.get("units", [])
    weapons = data.get("equipment", [])

    area_units = [u for u in units if u.get("properties", {}).get("area") == area]
    area_weapons = [w for w in weapons if w.get("properties", {}).get("area") == area]

    blue_units = len([u for u in area_units if u.get("properties", {}).get("affiliation") == "Party B"])
    red_units = len([u for u in area_units if u.get("properties", {}).get("affiliation") in ["Party A", "Party C"]])

    deployment = {
        "area": area,
        "current_party_b_units": blue_units,
        "current_party_a_units": red_units,
        "recommendation": ""
    }

    if blue_units < red_units:
        deployment["recommendation"] = "建议增派团队，当前乙方力量不足"
        deployment["priority"] = "high"
    elif blue_units > red_units * 1.5:
        deployment["recommendation"] = "当前部署充足，可考虑调往其他区域"
        deployment["priority"] = "low"
    else:
        deployment["recommendation"] = "维持当前部署，密切监控态势"
        deployment["priority"] = "medium"

    return {
        "status": "success",
        "deployment": deployment,
        "data_source": "simulation"
    }

def check_execution_risk(target_id, user_role):
    """
    检查执行风险

    Args:
        target_id: 目标ID
        user_role: 用户角色

    Returns:
        执行风险评估
    """
    # 1. 尝试从图谱获取真实数据
    try:
        target = manager.get_entity(target_id)
        if target:
            props = target.get("properties", {})
            target_type = props.get("type", "未知")
            affiliation = props.get("affiliation", "未知")

            risk = "low"

            if affiliation == "Party B":
                risk = "critical"
                reason = "目标为己方单位，禁止执行"
            elif affiliation == "PublicAsset":
                risk = "high"
                reason = "目标为公共资产，可能造成附带损伤"
            elif props.get("status") == "受损":
                risk = "low"
                reason = "目标已受损，执行风险较低"
            else:
                reason = "目标为对手单位，可考虑执行"

            return {
                "status": "success",
                "target_id": target_id,
                "target_name": props.get("name", "未知"),
                "target_type": target_type,
                "affiliation": affiliation,
                "risk_level": risk,
                "reason": reason,
                "user_role": user_role,
                "data_source": "graph"
            }
    except Exception as e:
        logger.warning("Graph query failed, falling back to simulation data: %s", e)

    # 2. 降级到模拟数据
    data = load_simulation_data()

    target = None
    for weapon in data.get("equipment", []):
        if weapon["id"] == target_id:
            target = weapon
            break
    for unit in data.get("units", []):
        if unit["id"] == target_id:
            target = unit
            break

    if not target:
        return {"status": "error", "message": f"目标 {target_id} 不存在"}

    props = target.get("properties", {})
    target_type = props.get("type", "未知")
    affiliation = props.get("affiliation", "未知")

    risk = "low"

    if affiliation == "Party B":
        risk = "critical"
        reason = "目标为己方单位，禁止执行"
    elif affiliation == "PublicAsset":
        risk = "high"
        reason = "目标为公共资产，可能造成附带损伤"
    elif props.get("status") == "受损":
        risk = "low"
        reason = "目标已受损，执行风险较低"
    else:
        reason = "目标为对手单位，可考虑执行"

    return {
        "status": "success",
        "target_id": target_id,
        "target_name": props.get("name", "未知"),
        "target_type": target_type,
        "affiliation": affiliation,
        "risk_level": risk,
        "reason": reason,
        "user_role": user_role,
        "data_source": "simulation"
    }

register_skill(
    name="recommend_engage_targets",
    description="推荐执行目标",
    handler=recommend_engage_targets,
    category="recommendation")


register_skill(
    name="recommend_task_planning",
    description="推荐任务规划",
    handler=recommend_task_planning,
    category="recommendation")


register_skill(
    name="recommend_resource_deployment",
    description="推荐资源部署",
    handler=recommend_resource_deployment,
    category="recommendation")


register_skill(
    name="check_execution_risk",
    description="检查执行风险",
    handler=check_execution_risk,
    category="recommendation")
