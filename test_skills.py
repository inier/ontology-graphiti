#!/usr/bin/env python3
"""
测试技能注册
"""

import sys
import os

# 确保当前目录在Python路径中
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("=== 测试技能注册 ===")

# 导入技能注册表
from odap.tools import SKILL_CATALOG, register_skill
print(f"初始技能数量: {len(SKILL_CATALOG)}")

# 导入 operations 模块
try:
    print("导入 operations 模块...")
    from odap.tools.operations import operations
    print(f"operations 模块导入成功")
except Exception as e:
    print(f"导入 operations 模块失败: {e}")

print(f"导入 operations 后技能数量: {len(SKILL_CATALOG)}")
print(f"技能列表: {list(SKILL_CATALOG.keys())}")

# 导入 intelligence 模块
try:
    print("\n导入 intelligence 模块...")
    from odap.tools.intelligence import intelligence
    print(f"intelligence 模块导入成功")
except Exception as e:
    print(f"导入 intelligence 模块失败: {e}")

print(f"导入 intelligence 后技能数量: {len(SKILL_CATALOG)}")
print(f"技能列表: {list(SKILL_CATALOG.keys())}")

print("\n=== 测试完成 ===")
