#!/usr/bin/env python3
"""测试场景创建功能"""

import sys
sys.path.insert(0, '/Users/caec/workspace/ontology/graphiti')

from odap.biz.frontend_compat.api.routes import scenario_store, workspace_service

print('=== 测试场景创建功能 ===')

# 1. 获取工作空间
print('1. 获取工作空间...')
workspace_id = '384cac47-2ccd-42fe-b0b5-8164214c247f'
try:
    workspace = workspace_service.get_workspace(workspace_id)
    print(f'   工作空间: {workspace.get("name")}')
    print(f'   类型: {type(workspace)}')
except Exception as e:
    print(f'   错误: {e}')
    import traceback
    traceback.print_exc()

# 2. 创建场景
print('\n2. 创建场景...')
try:
    scenario_id = scenario_store.create(
        name='测试场景',
        description='测试描述'
    )
    print(f'   创建成功! 场景ID: {scenario_id}')
except Exception as e:
    print(f'   错误: {e}')
    import traceback
    traceback.print_exc()

# 3. 获取场景
print('\n3. 获取场景...')
try:
    scenario = scenario_store.get_scenario(scenario_id)
    print(f'   场景: {scenario}')
    print(f'   类型: {type(scenario)}')
    if scenario:
        # 过滤 _id 字段
        clean_scenario = {k: v for k, v in scenario.items() if k != '_id'}
        print(f'   清理后的场景: {clean_scenario}')
except Exception as e:
    print(f'   错误: {e}')
    import traceback
    traceback.print_exc()

print('\n=== 测试完成 ===')