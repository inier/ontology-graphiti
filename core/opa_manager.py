"""
OPA权限管理模块
"""

import sys
import os
import json
from opa import OPAClient

# 确保当前目录在Python路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class OPAManager:
    """
    OPA权限管理器
    """
    
    def __init__(self):
        """
        初始化OPA权限管理器
        """
        # 由于OPA服务可能未启动，直接使用模拟模式
        self.use_mock = True
        print("使用模拟模式进行权限检查")
        # 策略版本管理
        self.policy_versions = {
            "current": "1.0.0",
            "previous": "0.9.0"
        }
    
    def load_policy(self):
        """
        加载OPA策略文件
        """
        # 模拟模式下不需要加载策略文件
        pass
    
    def check_permission(self, user_role, action, resource):
        """
        检查用户权限
        
        Args:
            user_role: 用户角色
            action: 操作类型
            resource: 资源对象
            
        Returns:
            bool: 是否允许操作
        """
        # 直接使用模拟模式进行权限检查
        return self._mock_check_permission(user_role, action, resource)
    
    def _mock_check_permission(self, user_role, action, resource):
        """
        模拟权限检查
        
        Args:
            user_role: 用户角色
            action: 操作类型
            resource: 资源对象
            
        Returns:
            bool: 是否允许操作
        """
        # 角色权限定义
        roles = {
            "pilot": {
                "permissions": ["view_intelligence", "request_support"],
                "restrictions": ["cannot_attack", "cannot_command"]
            },
            "commander": {
                "permissions": ["view_intelligence", "command_units", "authorize_attacks", "approve_missions"],
                "restrictions": ["cannot_attack_civilian_infrastructure"]
            },
            "intelligence_analyst": {
                "permissions": ["view_intelligence", "analyze_data", "generate_reports"],
                "restrictions": ["cannot_command", "cannot_attack"]
            }
        }
        
        # 权限映射
        permission_mapping = {
            "attack": ["authorize_attacks"],
            "command": ["command_units"],
            "view_intelligence": ["view_intelligence"],
            "request_support": ["request_support"],
            "analyze_data": ["analyze_data"],
            "generate_reports": ["generate_reports"],
            "approve_missions": ["approve_missions"]
        }
        
        # 检查角色是否存在
        if user_role not in roles:
            return False
        
        # 检查是否有相应的权限
        has_perm = False
        required_permissions = permission_mapping.get(action, [action])
        for perm in required_permissions:
            if perm in roles[user_role]["permissions"]:
                has_perm = True
                break
        if not has_perm:
            return False
        
        # 检查是否有特殊限制
        # 检查是否禁止攻击
        if "cannot_attack" in roles[user_role]["restrictions"] and action == "attack":
            return False
        
        # 检查是否禁止指挥
        if "cannot_command" in roles[user_role]["restrictions"] and action == "command":
            return False
        
        # 检查是否禁止攻击民用设施
        if "cannot_attack_civilian_infrastructure" in roles[user_role]["restrictions"]:
            if action == "attack" and resource.get("type") == "CivilianInfrastructure":
                return False
        
        return True
    
    def simulate_policy(self, user_role, action, resource):
        """
        模拟策略执行
        
        Args:
            user_role: 用户角色
            action: 操作类型
            resource: 资源对象
            
        Returns:
            dict: 模拟执行结果
        """
        # 构建输入数据
        input_data = {
            "user_role": user_role,
            "action": action,
            "resource": resource
        }
        
        # 检查权限
        allowed = self.check_permission(user_role, action, resource)
        
        # 构建模拟结果
        simulation_result = {
            "action": action,
            "resource": resource.get("id", "unknown"),
            "user_role": user_role,
            "result": "allowed" if allowed else "denied",
            "timestamp": "2026-04-09T00:00:00"
        }
        
        return simulation_result
    
    def rollback_policy(self):
        """
        回退策略版本
        
        Returns:
            str: 回退后的版本
        """
        # 切换版本
        self.policy_versions["current"], self.policy_versions["previous"] = \
            self.policy_versions["previous"], self.policy_versions["current"]
        
        # 重新加载策略
        self.load_policy()
        
        return self.policy_versions["current"]
    
    def get_policy_version(self):
        """
        获取当前策略版本
        
        Returns:
            str: 当前策略版本
        """
        return self.policy_versions["current"]

if __name__ == "__main__":
    # 测试OPA管理器
    manager = OPAManager()
    
    # 测试权限检查
    print("测试权限检查:")
    
    # 测试飞行员查看情报
    pilot_view = manager.check_permission(
        "pilot",
        "view_intelligence",
        {"id": "RADAR_01", "type": "WeaponSystem", "properties": {"type": "雷达"}}
    )
    print(f"飞行员查看情报: {pilot_view}")
    
    # 测试飞行员攻击
    pilot_attack = manager.check_permission(
        "pilot",
        "attack",
        {"id": "RADAR_01", "type": "WeaponSystem", "properties": {"type": "雷达"}}
    )
    print(f"飞行员攻击: {pilot_attack}")
    
    # 测试指挥官攻击雷达
    commander_attack_radar = manager.check_permission(
        "commander",
        "attack",
        {"id": "RADAR_01", "type": "WeaponSystem", "properties": {"type": "雷达"}}
    )
    print(f"指挥官攻击雷达: {commander_attack_radar}")
    
    # 测试指挥官攻击医院
    commander_attack_hospital = manager.check_permission(
        "commander",
        "attack",
        {"id": "HOSPITAL_01", "type": "CivilianInfrastructure", "properties": {"type": "医院"}}
    )
    print(f"指挥官攻击医院: {commander_attack_hospital}")
    
    # 测试策略模拟
    print("\n测试策略模拟:")
    simulation = manager.simulate_policy(
        "commander",
        "attack",
        {"id": "RADAR_01", "type": "WeaponSystem", "properties": {"type": "雷达"}}
    )
    print(f"策略模拟结果: {simulation}")
    
    # 测试版本回退
    print("\n测试版本回退:")
    current_version = manager.get_policy_version()
    print(f"当前版本: {current_version}")
    rolled_back_version = manager.rollback_policy()
    print(f"回退后版本: {rolled_back_version}")