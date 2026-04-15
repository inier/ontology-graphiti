"""
智能体编排器模块
实现任务路由和执行逻辑
"""

import sys
import os
import re

# 确保当前目录在Python路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odap.tools import SKILL_CATALOG
from odap.infra.opa import OPAManager

class SelfCorrectingOrchestrator:
    """
    自校正编排器
    负责路由和执行任务
    """
    
    def __init__(self, user_role="pilot"):
        """
        初始化编排器
        
        Args:
            user_role: 用户角色
        """
        self.user_role = user_role
        self.opa_manager = OPAManager()
        print(f"编排器初始化成功，用户角色: {user_role}")
    
    def run(self, query):
        """
        运行查询
        
        Args:
            query: 用户查询
            
        Returns:
            执行结果
        """
        print(f"收到查询: {query}")
        
        # 解析查询，确定需要的技能
        skill_name, args = self._parse_query(query)
        
        if not skill_name:
            return {"status": "error", "message": "无法识别的查询"}
        
        # 检查技能是否存在
        if skill_name not in SKILL_CATALOG:
            return {"status": "error", "message": f"技能不存在: {skill_name}"}
        
        # 执行技能
        try:
            result = SKILL_CATALOG[skill_name]["handler"](**args)
            print(f"技能执行结果: {result}")
            return result
        except Exception as e:
            print(f"技能执行失败: {e}")
            return {"status": "error", "message": f"技能执行失败: {str(e)}"}
    
    def _parse_query(self, query):
        """
        解析查询，确定需要的技能和参数

        Args:
            query: 用户查询

        Returns:
            (skill_name, args): 技能名称和参数
        """
        original_query = query
        query_lower = query.lower()

        if "雷达" in query_lower:
            area_match = re.search(r'([A-E])\s*区', query)
            area = area_match.group(1) if area_match else None
            return "search_radar", {"area": area}

        elif "战场" in query_lower and "分析" in query_lower:
            return "analyze_domain", {}

        elif "打击" in query_lower and ("推荐" in query_lower or "目标" in query_lower):
            area_match = re.search(r'([A-E])\s*区', query)
            area = area_match.group(1) if area_match else None
            target_type_match = re.search(r'(雷达|导弹|坦克|火炮)', query)
            target_type = target_type_match.group(1) if target_type_match else None
            return "recommend_strike_targets", {"user_role": self.user_role, "area": area, "target_type": target_type}

        elif "力量" in query_lower and "对比" in query_lower:
            area_match = re.search(r'([A-E])\s*区', query)
            area = area_match.group(1) if area_match else None
            return "analyze_force_comparison", {"area": area}

        elif "攻击" in query_lower:
            target_match = re.search(r'[A-Za-z_0-9]+', original_query)
            target_id = target_match.group(0) if target_match else None
            if not target_id:
                if "医院" in query_lower:
                    target_id = "CIV_A_1"
                elif "雷达" in query_lower:
                    target_id = "WEAPON_Bl_1"
            return "attack_target", {"target_id": target_id, "user_role": self.user_role}

        elif "指挥" in query_lower or "命令" in query_lower:
            unit_match = re.search(r'[A-Za-z_0-9]+', original_query)
            unit_id = unit_match.group(0) if unit_match else None
            command = original_query
            return "command_unit", {"unit_id": unit_id, "command": command, "user_role": self.user_role}

        else:
            return "analyze_domain", {}

if __name__ == "__main__":
    # 测试编排器
    print("测试智能体编排器")
    
    # 测试飞行员角色
    print("\n=== 测试飞行员角色 ===")
    pilot = SelfCorrectingOrchestrator(user_role="pilot")
    
    # 测试搜索雷达
    print("\n1. 测试搜索雷达:")
    result = pilot.run("帮我看看 B 区有没有雷达")
    print(f"结果: {result}")
    
    # 测试攻击目标（应该被拦截）
    print("\n2. 测试飞行员攻击目标:")
    result = pilot.run("攻击 WEAPON_Bl_1")
    print(f"结果: {result}")
    
    # 测试指挥官角色
    print("\n=== 测试指挥官角色 ===")
    commander = SelfCorrectingOrchestrator(user_role="commander")
    
    # 测试指挥官攻击雷达
    print("\n1. 测试指挥官攻击雷达:")
    result = commander.run("我是指挥官，攻击 WEAPON_Bl_1")
    print(f"结果: {result}")
    
    # 测试指挥官攻击医院（应该被拦截）
    print("\n2. 测试指挥官攻击医院:")
    result = commander.run("攻击 CIV_A_1")
    print(f"结果: {result}")
    
    # 测试分析战场态势
    print("\n3. 测试分析战场态势:")
    result = commander.run("分析当前战场态势")
    print(f"结果: {result}")