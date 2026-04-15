"""
计算与推理Skill模块
实现战场态势计算和预测功能
"""

import sys
import os
import math
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odap.tools import register_skill
from odap.infra.graph import GraphManager
from odap.biz.simulator.data_generator import load_simulation_data

manager = GraphManager()

def calculate_distance(entity1_id, entity2_id):
    """
    计算两个实体之间的距离

    Args:
        entity1_id: 实体1 ID
        entity2_id: 实体2 ID

    Returns:
        距离计算结果
    """
    data = load_simulation_data()

    entity1 = None
    entity2 = None

    for location in data.get("locations", []):
        if location["id"] == entity1_id:
            entity1 = location
        if location["id"] == entity2_id:
            entity2 = location

    if not entity1 or not entity2:
        return {"status": "error", "message": "实体不存在"}

    coords1 = entity1["properties"].get("coordinates", [0, 0])
    coords2 = entity2["properties"].get("coordinates", [0, 0])

    distance = math.sqrt(
        (coords1[0] - coords2[0]) ** 2 + (coords1[1] - coords2[1]) ** 2
    )

    return {
        "status": "success",
        "entity1": entity1_id,
        "entity2": entity2_id,
        "distance": round(distance, 2),
        "unit": "km",
        "entity1_coords": coords1,
        "entity2_coords": coords2
    }

def predict_outcome(attack_type, target_id, weapon_type=None):
    """
    预测攻击结果

    Args:
        attack_type: 攻击类型
        target_id: 目标ID
        weapon_type: 武器类型

    Returns:
        预测结果
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
        return {"status": "error", "message": "目标不存在"}

    target_type = target.get("properties", {}).get("type", "未知")
    target_status = target.get("properties", {}).get("status", "未知")

    base_success_rate = 0.7
    if target_type == "雷达":
        base_success_rate = 0.85
    elif target_type == "医院":
        base_success_rate = 0.95
    elif target_type == "指挥中心":
        base_success_rate = 0.6

    if target_status == "受损":
        base_success_rate += 0.1
    elif target_status == "摧毁":
        base_success_rate = 0.0

    outcome = {
        "status": "success",
        "attack_type": attack_type,
        "target_id": target_id,
        "target_type": target_type,
        "predicted_success_rate": min(base_success_rate, 0.99),
        "risk_level": "high" if base_success_rate < 0.7 else "medium" if base_success_rate < 0.85 else "low",
        "estimated_time": "5-10分钟",
        "recommendation": "建议执行" if base_success_rate > 0.6 else "风险较高，建议重新评估"
    }

    return outcome

def analyze_threat_level(area=None):
    """
    分析威胁等级

    Args:
        area: 区域

    Returns:
        威胁等级分析结果
    """
    data = load_simulation_data()
    units = data.get("military_units", [])
    weapons = data.get("weapon_systems", [])

    if area:
        units = [u for u in units if u.get("properties", {}).get("area") == area]
        weapons = [w for w in weapons if w.get("properties", {}).get("area") == area]

    threat_score = 0
    threat_factors = []

    for unit in units:
        affiliation = unit.get("properties", {}).get("affiliation", "")
        strength = unit.get("properties", {}).get("strength", 0)
        if affiliation in ["Red Force", "Green Insurgents"]:
            threat_score += strength * 0.1
            threat_factors.append(f"敌方部队: {unit.get('properties', {}).get('name', unit['id'])}")

    for weapon in weapons:
        affiliation = weapon.get("properties", {}).get("affiliation", "")
        power = weapon.get("properties", {}).get("power", 0)
        if affiliation in ["Red Force", "Green Insurgents"]:
            threat_score += power * 0.05
            threat_factors.append(f"敌方武器: {weapon.get('properties', {}).get('name', weapon['id'])}")

    threat_level = "low"
    if threat_score > 50:
        threat_level = "critical"
    elif threat_score > 30:
        threat_level = "high"
    elif threat_score > 10:
        threat_level = "medium"

    return {
        "status": "success",
        "area": area or "全部区域",
        "threat_level": threat_level,
        "threat_score": round(threat_score, 2),
        "threat_factors": threat_factors,
        "recommendation": "立即撤离" if threat_level == "critical" else "保持警惕" if threat_level == "high" else "正常作业"
    }

def calculate_strike_damage(weapon_id, target_id):
    """
    计算打击毁伤

    Args:
        weapon_id: 武器ID
        target_id: 目标ID

    Returns:
        毁伤评估结果
    """
    data = load_simulation_data()

    weapon = None
    target = None

    for w in data.get("weapon_systems", []):
        if w["id"] == weapon_id:
            weapon = w
            break

    for t in data.get("weapon_systems", []) + data.get("military_units", []):
        if t["id"] == target_id:
            target = t
            break

    if not weapon or not target:
        return {"status": "error", "message": "武器或目标不存在"}

    weapon_power = weapon.get("properties", {}).get("power", 50)
    target_armor = target.get("properties", {}).get("armor", 30)

    damage = (weapon_power * 0.8) - (target_armor * 0.3)
    damage_percent = min(max(damage / 100, 0), 1) * 100

    damage_level = "摧毁"
    if damage_percent < 30:
        damage_level = "轻微"
    elif damage_percent < 60:
        damage_level = "中等"
    elif damage_percent < 90:
        damage_level = "严重"

    return {
        "status": "success",
        "weapon": weapon.get("properties", {}).get("name", weapon_id),
        "target": target.get("properties", {}).get("name", target_id),
        "damage_percent": round(damage_percent, 1),
        "damage_level": damage_level,
        "remaining_strength": round(100 - damage_percent, 1)
    }

register_skill(
    name="calculate_distance",
    description="计算两个实体之间的距离",
    handler=calculate_distance,
    category="computation")


register_skill(
    name="predict_outcome",
    description="预测攻击结果",
    handler=predict_outcome,
    category="computation")


register_skill(
    name="analyze_threat_level",
    description="分析威胁等级",
    handler=analyze_threat_level,
    category="computation")


register_skill(
    name="calculate_strike_damage",
    description="计算打击毁伤",
    handler=calculate_strike_damage,
    category="computation")
