"""
打击决策智能推荐模块
"""

import sys
import os
import random

# 确保当前目录在Python路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odap.infra.graph import GraphManager

class DecisionRecommender:
    """
    打击决策推荐器
    """
    
    def __init__(self):
        """
        初始化决策推荐器
        """
        self.graph_manager = GraphManager()
        print("打击决策推荐器初始化成功")
    
    def generate_recommendations(self, user_role="pilot", area=None):
        """
        生成打击决策推荐
        
        Args:
            user_role: 用户角色
            area: 区域
            
        Returns:
            推荐列表
        """
        # 收集领域情报
        domain_intel = self._collect_domain_intel(area)
        
        # 分析领域态势
        analysis = self._analyze_domain(domain_intel)
        
        # 生成推荐
        recommendations = self._generate_recommendations(analysis, user_role)
        
        return recommendations
    
    def _collect_domain_intel(self, area=None):
        """
        收集领域情报
        
        Args:
            area: 区域
            
        Returns:
            领域情报
        """
        # 查询军事单位
        military_units = self.graph_manager.query_entities(entity_type="MilitaryUnit", area=area)
        
        # 查询武器系统
        weapon_systems = self.graph_manager.query_entities(entity_type="WeaponSystem", area=area)
        
        # 查询民用设施
        civilian_infrastructures = self.graph_manager.query_entities(entity_type="CivilianInfrastructure", area=area)
        
        # 查询领域事件
        battle_events = self.graph_manager.query_entities(entity_type="BattleEvent")
        
        return {
            "military_units": military_units,
            "weapon_systems": weapon_systems,
            "civilian_infrastructures": civilian_infrastructures,
            "battle_events": battle_events
        }
    
    def _analyze_domain(self, intel):
        """
        分析领域态势
        
        Args:
            intel: 领域情报
            
        Returns:
            领域分析结果
        """
        # 分析军事单位状态
        military_analysis = self._analyze_military_units(intel["military_units"])
        
        # 分析武器系统状态
        weapon_analysis = self._analyze_weapon_systems(intel["weapon_systems"])
        
        # 分析民用设施分布
        civilian_analysis = self._analyze_civilian_infrastructures(intel["civilian_infrastructures"])
        
        # 分析领域事件
        event_analysis = self._analyze_battle_events(intel["battle_events"])
        
        return {
            "military_analysis": military_analysis,
            "weapon_analysis": weapon_analysis,
            "civilian_analysis": civilian_analysis,
            "event_analysis": event_analysis
        }
    
    def _analyze_military_units(self, units):
        """
        分析军事单位
        
        Args:
            units: 军事单位列表
            
        Returns:
            分析结果
        """
        friendly_units = []
        enemy_units = []
        neutral_units = []
        
        for unit in units:
            affiliation = unit["properties"].get("affiliation", "Unknown")
            if affiliation == "Blue Force":
                friendly_units.append(unit)
            elif affiliation in ["Red Force", "Green Insurgents"]:
                enemy_units.append(unit)
            else:
                neutral_units.append(unit)
        
        return {
            "friendly_count": len(friendly_units),
            "enemy_count": len(enemy_units),
            "neutral_count": len(neutral_units),
            "friendly_units": friendly_units,
            "enemy_units": enemy_units,
            "neutral_units": neutral_units
        }
    
    def _analyze_weapon_systems(self, weapons):
        """
        分析武器系统
        
        Args:
            weapons: 武器系统列表
            
        Returns:
            分析结果
        """
        friendly_weapons = []
        enemy_weapons = []
        neutral_weapons = []
        
        for weapon in weapons:
            affiliation = weapon["properties"].get("affiliation", "Unknown")
            if affiliation == "Blue Force":
                friendly_weapons.append(weapon)
            elif affiliation in ["Red Force", "Green Insurgents"]:
                enemy_weapons.append(weapon)
            else:
                neutral_weapons.append(weapon)
        
        # 识别高价值目标
        high_value_targets = [w for w in enemy_weapons if w["properties"].get("type") == "雷达"]
        
        return {
            "friendly_count": len(friendly_weapons),
            "enemy_count": len(enemy_weapons),
            "neutral_count": len(neutral_weapons),
            "high_value_targets": high_value_targets
        }
    
    def _analyze_civilian_infrastructures(self, civs):
        """
        分析民用设施
        
        Args:
            civs: 民用设施列表
            
        Returns:
            分析结果
        """
        hospitals = [c for c in civs if c["properties"].get("type") == "医院"]
        schools = [c for c in civs if c["properties"].get("type") == "学校"]
        other_civs = [c for c in civs if c["properties"].get("type") not in ["医院", "学校"]]
        
        return {
            "total_count": len(civs),
            "hospitals": hospitals,
            "schools": schools,
            "other_civs": other_civs
        }
    
    def _analyze_battle_events(self, events):
        """
        分析领域事件
        
        Args:
            events: 领域事件列表
            
        Returns:
            分析结果
        """
        recent_events = sorted(events, key=lambda x: x["properties"].get("timestamp", ""), reverse=True)[:5]
        
        return {
            "total_count": len(events),
            "recent_events": recent_events
        }
    
    def _generate_recommendations(self, analysis, user_role):
        """
        生成推荐
        
        Args:
            analysis: 领域分析结果
            user_role: 用户角色
            
        Returns:
            推荐列表
        """
        recommendations = []
        
        # 基于武器系统的推荐
        if analysis["weapon_analysis"]["high_value_targets"]:
            for target in analysis["weapon_analysis"]["high_value_targets"]:
                recommendations.append({
                    "type": "attack",
                    "target": target,
                    "priority": "high",
                    "reason": "高价值雷达目标",
                    "risk": self._calculate_risk(target, analysis)
                })
        
        # 基于军事单位的推荐
        if analysis["military_analysis"]["enemy_count"] > 0:
            for unit in analysis["military_analysis"]["enemy_units"]:
                recommendations.append({
                    "type": "attack",
                    "target": unit,
                    "priority": "medium",
                    "reason": "敌方军事单位",
                    "risk": self._calculate_risk(unit, analysis)
                })
        
        # 基于领域事件的推荐
        if analysis["event_analysis"]["recent_events"]:
            for event in analysis["event_analysis"]["recent_events"]:
                if event["properties"].get("type") == "enemy_reinforcement":
                    recommendations.append({
                        "type": "alert",
                        "message": f"敌方增援: {event['properties'].get('description', '')}",
                        "priority": "high",
                        "reason": "敌方增援事件"
                    })
        
        # 按优先级排序
        recommendations.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}[x.get("priority", "low")])
        
        # 限制推荐数量
        return recommendations[:5]
    
    def _calculate_risk(self, target, analysis):
        """
        计算风险
        
        Args:
            target: 目标
            analysis: 领域分析结果
            
        Returns:
            风险等级
        """
        risk = "low"
        
        # 检查目标周围是否有民用设施
        target_area = target["properties"].get("area", "")
        civilian_in_area = [c for c in analysis["civilian_analysis"]["hospitals"] + analysis["civilian_analysis"]["schools"] if c["properties"].get("area") == target_area]
        
        if civilian_in_area:
            risk = "high"
        elif analysis["military_analysis"]["enemy_count"] > analysis["military_analysis"]["friendly_count"]:
            risk = "medium"
        
        return risk

if __name__ == "__main__":
    # 测试决策推荐器
    recommender = DecisionRecommender()
    
    # 生成推荐
    recommendations = recommender.generate_recommendations(user_role="commander", area="B")
    
    print("打击决策推荐:")
    print("====================================")
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. 类型: {rec['type']}")
        if "target" in rec:
            target_name = rec["target"]["properties"].get("name", "未知目标")
            print(f"   目标: {target_name}")
        if "message" in rec:
            print(f"   消息: {rec['message']}")
        print(f"   优先级: {rec['priority']}")
        print(f"   原因: {rec['reason']}")
        if "risk" in rec:
            print(f"   风险: {rec['risk']}")
        print()
    print("====================================")