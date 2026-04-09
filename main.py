"""
AIP Project Entry Point
"""
import sys
import os

# 确保当前目录在 Python 路径中 (如果是直接运行此文件)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ==========================================
# 🚀 关键步骤：触发技能注册
# ==========================================

# 1. 导入 skills 包
# 这会自动触发 skills/__init__.py 的执行
# __init__.py 会依次导入 intelligence 和 operations 模块
# 进而触发这些模块中的 register_skill() 函数调用
import skills

# 2. 导入编排器
from core.orchestrator import SelfCorrectingOrchestrator

# ==========================================
# 🎬 运行演示
# ==========================================

def main():
    print("🚀 AIP 系统启动...")
    print(f"📦 已加载技能目录: {list(skills.SKILL_CATALOG.keys())}")
    
    # --- 场景 1: 情报查询 ---
    # 预期：路由到 Intelligence -> 调用 search_radar -> 成功
    pilot = SelfCorrectingOrchestrator(user_role="pilot")
    pilot.run("帮我看看 B 区有没有雷达")
    
    # --- 场景 2: 越权攻击 ---
    # 预期：路由到 Operations -> 调用 attack_target -> OPA 拦截 (权限不足)
    print("\n--- 测试权限拦截 ---")
    pilot.run("攻击 WEAPON_Bl_1")
    
    # --- 场景 3: 指挥官攻击 ---
    # 预期：路由到 Operations -> 调用 attack_target -> 成功
    print("\n--- 测试指挥官权限 ---")
    commander = SelfCorrectingOrchestrator(user_role="commander")
    commander.run("我是指挥官，攻击 WEAPON_Bl_1")
    
    # --- 场景 4: 策略拦截 ---
    # 预期：路由到 Operations -> 调用 attack_target -> OPA 拦截 (禁止攻击民用设施)
    print("\n--- 测试策略拦截 ---")
    commander.run("攻击 CIV_A_1")

if __name__ == "__main__":
    main()