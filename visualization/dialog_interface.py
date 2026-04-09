"""
基于openHarness的对话界面
"""

import sys
import os
from openharness import Harness

# 确保当前目录在Python路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.orchestrator import SelfCorrectingOrchestrator

class BattlefieldDialogInterface:
    """
    战场对话界面
    """
    
    def __init__(self, user_role="pilot"):
        """
        初始化对话界面
        
        Args:
            user_role: 用户角色
        """
        self.user_role = user_role
        self.orchestrator = SelfCorrectingOrchestrator(user_role=user_role)
        self.harness = Harness()
        print(f"对话界面初始化成功，用户角色: {user_role}")
    
    def start_dialog(self):
        """
        开始对话
        """
        print("🚀 战场指挥系统对话界面")
        print("====================================")
        print("请输入您的命令，输入 'exit' 退出")
        print("====================================")
        
        while True:
            user_input = input("您: ")
            
            if user_input.lower() == "exit":
                print("系统: 再见！")
                break
            
            # 使用编排器处理用户输入
            result = self.orchestrator.run(user_input)
            
            # 显示结果
            self._display_result(result)
    
    def _display_result(self, result):
        """
        显示结果
        
        Args:
            result: 执行结果
        """
        print("系统: ")
        
        if isinstance(result, list):
            # 列表结果（如搜索雷达）
            for item in result:
                if isinstance(item, dict) and "properties" in item:
                    name = item["properties"].get("name", "未知目标")
                    print(f"  - {name}")
                else:
                    print(f"  - {item}")
        elif isinstance(result, dict):
            # 字典结果（如攻击结果）
            status = result.get("status", "unknown")
            message = result.get("message", "")
            print(f"  状态: {status}")
            print(f"  消息: {message}")
            
            if "target" in result:
                target_name = result["target"]["properties"].get("name", "未知目标")
                print(f"  目标: {target_name}")
        else:
            # 其他类型结果
            print(f"  {result}")
        
        print()

if __name__ == "__main__":
    # 测试对话界面
    print("选择用户角色:")
    print("1. 飞行员 (pilot)")
    print("2. 指挥官 (commander)")
    print("3. 情报分析师 (intelligence_analyst)")
    
    choice = input("请输入选择 (1-3): ")
    
    role_map = {
        "1": "pilot",
        "2": "commander",
        "3": "intelligence_analyst"
    }
    
    user_role = role_map.get(choice, "pilot")
    
    dialog = BattlefieldDialogInterface(user_role=user_role)
    dialog.start_dialog()