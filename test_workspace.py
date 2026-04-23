#!/usr/bin/env python3
"""测试工作空间管理功能"""

from odap.biz.workspace.services.workspace_service import WorkspaceService

print('=== 测试工作空间管理功能 ===')

workspace_service = WorkspaceService()

# 测试列出工作空间
print('1. 列出工作空间...')
try:
    result = workspace_service.list_workspaces()
    workspaces = result.get('workspaces', [])
    print(f'   找到 {len(workspaces)} 个工作空间:')
    for workspace in workspaces:
        print(f'   - {workspace.get("name")} (ID: {workspace.get("workspace_id")})')
except Exception as e:
    print(f'   错误: {e}')

# 测试创建工作空间
print('\n2. 创建工作空间...')
try:
    result = workspace_service.create_workspace('测试工作空间', '测试工作空间描述')
    print(f'   创建成功! 工作空间ID: {result.get("workspace_id")}')
    print(f'   工作空间名称: {result.get("name")}')
except Exception as e:
    print(f'   错误: {e}')

# 测试再次列出工作空间
print('\n3. 再次列出工作空间...')
try:
    result = workspace_service.list_workspaces()
    workspaces = result.get('workspaces', [])
    print(f'   找到 {len(workspaces)} 个工作空间:')
    for workspace in workspaces:
        print(f'   - {workspace.get("name")} (ID: {workspace.get("workspace_id")})')
except Exception as e:
    print(f'   错误: {e}')

# 测试获取工作空间
print('\n4. 获取工作空间详情...')
try:
    if workspaces:
        workspace_id = workspaces[0].get('workspace_id')
        result = workspace_service.get_workspace(workspace_id)
        print(f'   工作空间详情:')
        print(f'   名称: {result.get("name")}')
        print(f'   描述: {result.get("description")}')
        print(f'   状态: {result.get("status")}')
        print(f'   所有者: {result.get("owner")}')
except Exception as e:
    print(f'   错误: {e}')

print('\n=== 测试完成 ===')