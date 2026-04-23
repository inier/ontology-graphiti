#!/usr/bin/env python3
"""测试场景管理功能"""

from odap.biz.frontend_compat.api.routes import scenario_store

print('=== 测试场景管理功能 ===')

# 测试列出场景
print('1. 列出场景...')
try:
    scenarios = scenario_store.list_scenarios()
    print(f'   找到 {len(scenarios)} 个场景:')
    for scenario in scenarios:
        print(f'   - {scenario.get("name")} (ID: {scenario.get("scenario_id")})')
except Exception as e:
    print(f'   错误: {e}')

# 测试创建场景
print('\n2. 创建场景...')
try:
    scenario_id = scenario_store.create('测试场景', '测试场景描述')
    print(f'   创建成功! 场景ID: {scenario_id}')
except Exception as e:
    print(f'   错误: {e}')

# 测试再次列出场景
print('\n3. 再次列出场景...')
try:
    scenarios = scenario_store.list_scenarios()
    print(f'   找到 {len(scenarios)} 个场景:')
    for scenario in scenarios:
        print(f'   - {scenario.get("name")} (ID: {scenario.get("scenario_id")})')
except Exception as e:
    print(f'   错误: {e}')

# 测试获取场景
print('\n4. 获取场景详情...')
try:
    if scenarios:
        scenario = scenario_store.get_scenario(scenarios[0].get('scenario_id'))
        print(f'   场景详情:')
        print(f'   名称: {scenario.get("name")}')
        print(f'   描述: {scenario.get("description")}')
        print(f'   创建时间: {scenario.get("created_at")}')
except Exception as e:
    print(f'   错误: {e}')

print('\n=== 测试完成 ===')