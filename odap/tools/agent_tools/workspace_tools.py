"""
工作空间操作工具集

为 Agent 提供工作空间的查询、分析、管理等功能。
"""

from typing import Dict, Any, List, Optional
from odap.biz.platform.workspace.services.workspace_service import WorkspaceService
from odap.tools import register_skill

# 初始化工作空间服务
workspace_service = WorkspaceService()


def list_workspaces(page: int = 1, page_size: int = 100) -> List[Dict]:
    """
    列出所有工作空间
    
    Args:
        page: 页码
        page_size: 每页数量
        
    Returns:
        工作空间列表
    """
    try:
        result = workspace_service.list_workspaces(
            filters={},
            page=page,
            page_size=page_size
        )
        return result.get("workspaces", [])
    except Exception as e:
        return [{"error": str(e)}]


def get_workspace_info(workspace_id: str) -> Dict[str, Any]:
    """
    获取工作空间详细信息
    
    Args:
        workspace_id: 工作空间ID
        
    Returns:
        工作空间详情
    """
    try:
        workspace = workspace_service.get_workspace(workspace_id)
        if not workspace:
            return {"error": f"工作空间不存在: {workspace_id}"}
        
        return {
            "workspace": workspace,
        }
    except Exception as e:
        return {"error": str(e)}


def create_workspace_summary(workspace_id: str = None) -> Dict[str, Any]:
    """
    创建工作空间摘要报告
    
    Args:
        workspace_id: 工作空间ID（可选，不提供则汇总所有）
        
    Returns:
        摘要报告
    """
    try:
        if workspace_id:
            # 单个工作空间摘要
            workspace = workspace_service.get_workspace(workspace_id)
            if not workspace:
                return {"error": f"工作空间不存在: {workspace_id}"}
            
            return {
                "type": "single",
                "workspace": {
                    "id": workspace.get("workspace_id"),
                    "name": workspace.get("name"),
                    "description": workspace.get("description"),
                    "status": workspace.get("status"),
                    "type": workspace.get("type"),
                    "owner": workspace.get("owner"),
                },
                "summary": f"工作空间 '{workspace.get('name')}' 状态为 {workspace.get('status')}，类型为 {workspace.get('type')}。",
            }
        else:
            # 所有工作空间汇总
            result = workspace_service.list_workspaces(filters={}, page=1, page_size=1000)
            workspaces = result.get("workspaces", [])
            
            return {
                "type": "overview",
                "total_workspaces": len(workspaces),
                "workspaces": [
                    {
                        "id": w.get("workspace_id"),
                        "name": w.get("name"),
                        "status": w.get("status"),
                        "type": w.get("type"),
                    }
                    for w in workspaces
                ],
                "summary": f"共有 {len(workspaces)} 个工作空间。",
            }
    except Exception as e:
        return {"error": str(e)}


# ============================================================
# 注册技能到 SKILL_CATALOG
# ============================================================

register_skill(
    name="list_workspaces",
    description="列出所有工作空间",
    handler=list_workspaces,
    category="workspace",
)

register_skill(
    name="get_workspace_info",
    description="获取工作空间详细信息",
    handler=get_workspace_info,
    category="workspace",
)

register_skill(
    name="create_workspace_summary",
    description="创建工作空间摘要报告",
    handler=create_workspace_summary,
    category="workspace",
)
