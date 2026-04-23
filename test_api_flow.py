#!/usr/bin/env python3
"""完整测试 API 端点流程"""

import sys
sys.path.insert(0, '/Users/caec/workspace/ontology/graphiti')

from odap.biz.frontend_compat.api.routes import scenario_store, workspace_service

print('=== 完整测试 API 端点流程 ===')

# 模拟 API 端点的完整流程
workspace_id = '384cac47-2ccd-42fe-b0b5-8164214c247f'

# 1. 获取工作空间
print('1. 获取工作空间...')
workspace = workspace_service.get_workspace(workspace_id)
if workspace.get("status") == "error":
    print('   错误: Workspace not found')
else:
    print(f'   工作空间 OK: {workspace.get("name")}')

# 2. 模拟请求数据
data = {"name": "新场景测试", "description": "测试描述"}
print(f'\n2. 请求数据: {data}')

# 3. 创建场景
print('\n3. 创建场景...')
scenario_id = scenario_store.create(
    name=data.get("name", "新场景"),
    description=data.get("description", "")
)
print(f'   场景ID: {scenario_id}')

# 4. 获取场景
print('\n4. 获取场景...')
scenario = scenario_store.get_scenario(scenario_id)
print(f'   场景: {scenario}')

# 5. 添加 workspace_id
if scenario:
    print('\n5. 添加 workspace_id...')
    # 确保移除 _id 字段
    scenario = {k: v for k, v in scenario.items() if k != '_id'}
    scenario['workspace_id'] = workspace_id
    print(f'   最终场景: {scenario}')

# 6. 验证场景类型
print('\n6. 验证场景类型...')
print(f'   类型: {type(scenario)}')
if scenario:
    for k, v in scenario.items():
        print(f'   {k}: {type(v)} - {v}')

print('\n=== 测试完成 ===')